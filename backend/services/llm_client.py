import asyncio
import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class ModelEndpoint:
    """一个可用的模型端点"""
    provider: str
    model_id: str
    base_url: str
    api_key: str
    tier: str
    provider_name: str = ""


# ---------------------------------------------------------------------------
# ModelRegistry: 加载配置，管理 provider/model
# ---------------------------------------------------------------------------

class ModelRegistry:
    """从 YAML 配置加载 provider/model 定义，合并 .env 中的 API key"""

    def __init__(self, config_path: str):
        self.providers: dict[str, dict] = {}       # provider_id -> provider_config
        self.endpoints: list[ModelEndpoint] = []    # 所有可用端点
        self.task_tier_map: dict[str, str] = {}
        self.fallback_strategy: dict = {}
        self._loaded = False

        try:
            self._load_config(config_path)
            self._loaded = True
        except FileNotFoundError:
            logger.warning("模型配置文件 %s 不存在，将使用单一 provider 降级模式", config_path)
        except Exception as e:
            logger.error("模型配置文件加载失败: %s，将使用单一 provider 降级模式", e)

    def _load_config(self, config_path: str):
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(config_path)

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.fallback_strategy = config.get("fallback_strategy", {})
        self.task_tier_map = config.get("task_tier_mapping", {})

        # 默认 tier 映射
        if "default" not in self.task_tier_map:
            self.task_tier_map["default"] = "standard"

        providers_config = config.get("providers", {})
        for provider_id, pcfg in providers_config.items():
            api_key_env = pcfg.get("api_key_env", "")
            api_key = os.getenv(api_key_env, "")

            # 如果环境变量为空，尝试用 DEFAULT_PROVIDER/DEFAULT_MODEL 的兼容逻辑
            if not api_key:
                continue  # 无 key 的 provider 直接跳过

            base_url = pcfg.get("base_url", "")
            provider_name = pcfg.get("name", provider_id)
            self.providers[provider_id] = pcfg

            for mcfg in pcfg.get("models", []):
                ep = ModelEndpoint(
                    provider=provider_id,
                    model_id=mcfg.get("id", ""),
                    base_url=base_url,
                    api_key=api_key,
                    tier=mcfg.get("tier", "standard"),
                    provider_name=provider_name,
                )
                self.endpoints.append(ep)

        logger.info(
            "模型配置加载完成: %d 个 provider, %d 个可用模型",
            len(self.providers),
            len(self.endpoints),
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded and len(self.endpoints) > 0

    def get_tier(self, task_type: str) -> str:
        """根据 task_type 获取目标 tier"""
        return self.task_tier_map.get(task_type, self.task_tier_map.get("default", "standard"))

    def get_endpoints(
        self,
        tier: str | None = None,
        provider: str | None = None,
        exclude: set[str] | None = None,
    ) -> list[ModelEndpoint]:
        """获取符合条件的端点列表"""
        result = []
        for ep in self.endpoints:
            if tier and ep.tier != tier:
                continue
            if provider and ep.provider != provider:
                continue
            if exclude and f"{ep.provider}:{ep.model_id}" in exclude:
                continue
            result.append(ep)
        return result


# ---------------------------------------------------------------------------
# ModelRouter: 路由选择 + fallback + 冷却管理
# ---------------------------------------------------------------------------

class ModelRouter:
    """根据 task_type 路由到最优模型，支持 fallback 和冷却"""

    # tier 降级顺序
    TIER_ORDER = ["advanced", "standard", "lite"]

    def __init__(self, registry: ModelRegistry, cooldown_seconds: int = 300):
        self.registry = registry
        self._cooldown_seconds = cooldown_seconds
        self._cooling: dict[str, float] = {}  # "provider:model_id" -> resume_timestamp

    def route(self, task_type: str = "default", exclude: set[str] | None = None) -> ModelEndpoint | None:
        """根据 task_type 路由到最优可用模型"""
        exclude = exclude or set()
        tier = self.registry.get_tier(task_type)

        # 1. 检查 DEFAULT_PROVIDER / DEFAULT_MODEL 覆盖
        if settings.DEFAULT_PROVIDER or settings.DEFAULT_MODEL:
            override = self._find_override(tier, exclude)
            if override:
                return override

        # 2. 四级 fallback 策略
        strategy = self.registry.fallback_strategy
        candidates = self._build_candidates(tier, strategy, exclude)
        return candidates[0] if candidates else None

    def _find_override(self, tier: str, exclude: set[str]) -> ModelEndpoint | None:
        """查找 DEFAULT_PROVIDER / DEFAULT_MODEL 指定的模型"""
        for ep in self.registry.get_endpoints():
            key = f"{ep.provider}:{ep.model_id}"
            if key in exclude:
                continue
            if not self.is_available(ep.provider, ep.model_id):
                continue
            if settings.DEFAULT_MODEL and ep.model_id == settings.DEFAULT_MODEL:
                return ep
            if settings.DEFAULT_PROVIDER and ep.provider == settings.DEFAULT_PROVIDER:
                if ep.tier == tier:
                    return ep
        return None

    def _build_candidates(self, tier: str, strategy: dict, exclude: set[str]) -> list[ModelEndpoint]:
        """按 fallback 策略构建候选模型列表"""
        candidates = []
        tier_idx = self.TIER_ORDER.index(tier) if tier in self.TIER_ORDER else 1

        # 同 provider 同 tier
        if strategy.get("same_provider_same_tier", True):
            for ep in self.registry.get_endpoints(tier=tier, exclude=exclude):
                if self.is_available(ep.provider, ep.model_id):
                    candidates.append(ep)

        # 同 provider 低 tier
        if strategy.get("same_provider_lower_tier", True):
            for lower_tier in self.TIER_ORDER[tier_idx + 1:]:
                for ep in self.registry.get_endpoints(tier=lower_tier, exclude=exclude):
                    if self.is_available(ep.provider, ep.model_id):
                        # 避免重复（前面的 tier 可能已包含）
                        if ep not in candidates:
                            candidates.append(ep)

        # 跨 provider 同 tier
        if strategy.get("cross_provider_same_tier", True):
            # 已在前面收集了同 tier 的所有 provider，无需重复
            pass

        # 跨 provider 低 tier（补充前面未覆盖的低 tier 跨 provider）
        if strategy.get("cross_provider_lower_tier", True):
            for lower_tier in self.TIER_ORDER[tier_idx + 1:]:
                for ep in self.registry.get_endpoints(tier=lower_tier, exclude=exclude):
                    if self.is_available(ep.provider, ep.model_id) and ep not in candidates:
                        candidates.append(ep)

        return candidates

    def mark_unavailable(self, provider: str, model_id: str):
        """标记模型临时不可用"""
        key = f"{provider}:{model_id}"
        self._cooling[key] = time.time() + self._cooldown_seconds
        logger.warning("模型 %s 标记为临时不可用，冷却 %d 秒", key, self._cooldown_seconds)

    def is_available(self, provider: str, model_id: str) -> bool:
        """检查模型是否可用（未冷却）"""
        key = f"{provider}:{model_id}"
        resume_at = self._cooling.get(key, 0)
        if time.time() < resume_at:
            return False
        # 已过冷却期，清除
        self._cooling.pop(key, None)
        return True


# ---------------------------------------------------------------------------
# 初始化全局实例
# ---------------------------------------------------------------------------

registry = ModelRegistry(settings.MODEL_CONFIG_PATH)
router = ModelRouter(registry, settings.MODEL_COOLDOWN_SECONDS)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def parse_llm_json(response: str, fallback: dict | None = None) -> dict:
    """从 LLM 响应中解析 JSON，支持多种格式降级提取"""
    if fallback is None:
        fallback = {}

    # 1. 直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 2. 从 markdown 代码块提取
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 提取最外层 JSON 对象
    brace_match = re.search(r'\{[\s\S]*\}', response)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("LLM JSON 解析失败，返回降级结果")
    return fallback


# ---------------------------------------------------------------------------
# 判断配额耗尽错误
# ---------------------------------------------------------------------------

def _is_quota_error(status_code: int) -> bool:
    """判断 HTTP 状态码是否表示配额耗尽"""
    return status_code in (429, 402, 403)


# ---------------------------------------------------------------------------
# 核心 LLM 调用
# ---------------------------------------------------------------------------

async def call_llm(prompt: str, system: str = "你是一个专业的AI助手。", task_type: str = "default") -> str:
    """调用 LLM API，自动路由模型，支持 fallback

    Args:
        prompt: 用户提示词
        system: 系统提示词
        task_type: 任务类型，用于智能路由 (risk_assessment / persona_simulation / rewrite / default)
    """
    if registry.is_loaded:
        return await _call_with_routing(prompt, system, task_type)
    else:
        # 降级模式：使用原有单一 provider
        return await _call_legacy(prompt, system)


async def _call_with_routing(prompt: str, system: str, task_type: str) -> str:
    """使用模型路由的调用方式"""
    tried: set[str] = set()
    last_error: Exception | None = None

    while True:
        endpoint = router.route(task_type, exclude=tried)
        if endpoint is None:
            break

        key = f"{endpoint.provider}:{endpoint.model_id}"
        tried.add(key)

        try:
            result = await _call_endpoint(endpoint, prompt, system)
            return result
        except QuotaExhaustedError as e:
            router.mark_unavailable(endpoint.provider, endpoint.model_id)
            logger.warning("模型 %s 配额耗尽 (%s)，触发 fallback", key, e)
            last_error = e
        except Exception as e:
            # 非配额错误：重试当前模型
            retried = False
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    result = await _call_endpoint(endpoint, prompt, system)
                    return result
                except QuotaExhausted as eq:
                    router.mark_unavailable(endpoint.provider, endpoint.model_id)
                    logger.warning("模型 %s 配额耗尽 (重试%d次): %s", key, attempt + 1, eq)
                    last_error = eq
                    retried = True
                    break
                except Exception as e2:
                    last_error = e2
                    logger.warning("LLM 调用失败 %s (重试%d次): %s", key, attempt + 1, e2)

            if not retried:
                # 非配额错误重试后仍失败，尝试下一个模型
                logger.warning("模型 %s 调用失败，尝试下一个模型", key)

    raise RuntimeError(f"所有模型不可用，已尝试: {tried}" + (f"，最后错误: {last_error}" if last_error else ""))


async def _call_endpoint(endpoint: ModelEndpoint, prompt: str, system: str) -> str:
    """调用指定端点"""
    url = f"{endpoint.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": endpoint.model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    if _HAS_HTTPX:
        return await _httpx_call(url, headers, payload, endpoint)
    else:
        return await _urllib_call(url, headers, payload, endpoint)


async def _httpx_call(url: str, headers: dict, payload: dict, endpoint: ModelEndpoint) -> str:
    """httpx 异步调用"""
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=payload)

        if _is_quota_error(resp.status_code):
            raise QuotaExhaustedError(
                f"{endpoint.provider_name} {endpoint.model_id} HTTP {resp.status_code}: {resp.text[:200]}"
            )

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _urllib_call(url: str, headers: dict, payload: dict, endpoint: ModelEndpoint) -> str:
    """urllib 同步调用 (httpx 不可用时的降级方案)"""
    payload_bytes = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
        loop = asyncio.get_event_loop()
        resp_data = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT),
        )
        data = json.loads(resp_data.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if _is_quota_error(e.code):
            raise QuotaExhaustedError(
                f"{endpoint.provider_name} {endpoint.model_id} HTTP {e.code}"
            )
        raise


# ---------------------------------------------------------------------------
# 降级模式：原有单一 provider
# ---------------------------------------------------------------------------

async def _call_legacy(prompt: str, system: str) -> str:
    """原有单一 provider 调用（配置文件缺失时降级）"""
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY 或配置 model_config.yaml")

    url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    if _HAS_HTTPX:
        return await _httpx_call(url, headers, payload, ModelEndpoint(
            provider="legacy", model_id=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL, api_key=settings.DEEPSEEK_API_KEY,
            tier="standard", provider_name="Legacy",
        ))
    else:
        return await _urllib_call(url, headers, payload, ModelEndpoint(
            provider="legacy", model_id=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL, api_key=settings.DEEPSEEK_API_KEY,
            tier="standard", provider_name="Legacy",
        ))


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class QuotaExhaustedError(Exception):
    """模型配额耗尽错误（429/402/403）"""
    pass


# 向后兼容别名
QuotaExhausted = QuotaExhaustedError
