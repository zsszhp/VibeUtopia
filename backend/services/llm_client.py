from __future__ import annotations

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
    vision: bool = False  # 是否支持视觉/多模态


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
            prefix = provider_id.upper()
            api_key_env = pcfg.get("api_key_env", f"{prefix}_API_KEY")
            api_key = os.getenv(api_key_env, "")

            # 如果环境变量为空，直接跳过该 provider
            if not api_key:
                continue

            # --- 动态覆盖逻辑 ---
            # 1. 允许从 .env 覆盖 base_url
            base_url = os.getenv(f"{prefix}_BASE_URL", pcfg.get("base_url", ""))
            
            # 2. 允许从 .env 指定该厂商的主力模型
            env_model_id = os.getenv(f"{prefix}_MODEL", "")
            
            provider_name = pcfg.get("name", provider_id)
            self.providers[provider_id] = pcfg

            # 获取 YAML 中的模型定义
            models_cfg = pcfg.get("models", [])
            
            # 如果 .env 指定了模型名，且该模型不在 YAML 列表中，将其作为 standard 级别加入
            if env_model_id:
                existing_model_ids = [m.get("id") for m in models_cfg]
                if env_model_id not in existing_model_ids:
                    # 插入到首位作为优先候选项
                    models_cfg.insert(0, {"id": env_model_id, "tier": "standard"})

            for mcfg in models_cfg:
                m_id = mcfg.get("id", "")
                ep = ModelEndpoint(
                    provider=provider_id,
                    model_id=m_id,
                    base_url=base_url,
                    api_key=api_key,
                    tier=mcfg.get("tier", "standard"),
                    provider_name=provider_name,
                    vision=mcfg.get("vision", False),
                )
                self.endpoints.append(ep)

        logger.info(
            "模型配置加载完成: %d 个 provider, %d 个可用模型 (支持 .env 动态覆盖)",
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

    def get_available_providers(self) -> list[dict]:
        """返回所有有 API key 的厂商及其模型，供前端选择器使用"""
        provider_map: dict[str, dict] = {}
        for ep in self.endpoints:
            if ep.provider not in provider_map:
                provider_map[ep.provider] = {
                    "id": ep.provider,
                    "name": ep.provider_name,
                    "models": [],
                }
            provider_map[ep.provider]["models"].append({
                "id": ep.model_id,
                "tier": ep.tier,
            })
        return list(provider_map.values())

    def get_vision_endpoints(
        self,
        tier: str | None = None,
        exclude: set[str] | None = None,
    ) -> list[ModelEndpoint]:
        """获取支持视觉/多模态的端点列表"""
        result = []
        for ep in self.endpoints:
            if not ep.vision:
                continue
            if tier and ep.tier != tier:
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
        self._runtime_provider: str = ""  # 运行时覆盖：厂商
        self._runtime_model: str = ""     # 运行时覆盖：模型

    def set_override(self, provider: str = "", model: str = ""):
        """运行时设置覆盖，立即生效，无需重启"""
        self._runtime_provider = provider
        self._runtime_model = model
        logger.info("模型运行时覆盖已更新: provider=%s, model=%s", provider, model)

    def get_override(self) -> dict:
        """获取当前运行时覆盖设置"""
        return {"provider": self._runtime_provider, "model": self._runtime_model}

    def route(self, task_type: str = "default", exclude: set[str] | None = None) -> ModelEndpoint | None:
        """根据 task_type 路由到最优可用模型"""
        exclude = exclude or set()
        tier = self.registry.get_tier(task_type)

        # 1. 检查运行时覆盖 / DEFAULT_PROVIDER / DEFAULT_MODEL
        effective_provider = self._runtime_provider or settings.DEFAULT_PROVIDER
        effective_model = self._runtime_model or settings.DEFAULT_MODEL
        if effective_provider or effective_model:
            override = self._find_override(tier, exclude, effective_provider, effective_model)
            if override:
                return override

        # 2. 四级 fallback 策略
        strategy = self.registry.fallback_strategy
        candidates = self._build_candidates(tier, strategy, exclude)
        return candidates[0] if candidates else None

    def _find_override(self, tier: str, exclude: set[str], provider: str, model: str) -> ModelEndpoint | None:
        """查找指定的覆盖模型"""
        for ep in self.registry.get_endpoints():
            key = f"{ep.provider}:{ep.model_id}"
            if key in exclude:
                continue
            if not self.is_available(ep.provider, ep.model_id):
                continue
            if model and ep.model_id == model:
                return ep
            if provider and ep.provider == provider:
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


async def call_vlm(prompt: str, image_base64: str, system: str = "你是一个专业的AI助手。", task_type: str = "default") -> str:
    """调用视觉语言模型 (VLM) API，支持图片输入

    Args:
        prompt: 用户提示词
        image_base64: 图片的 base64 编码字符串
        system: 系统提示词
        task_type: 任务类型，用于智能路由

    Raises:
        RuntimeError: 无可用视觉模型时抛出
    """
    if not registry.is_loaded:
        raise RuntimeError("模型配置未加载，无法调用视觉模型")

    tried: set[str] = set()
    last_error: Exception | None = None

    while True:
        endpoint = _route_vlm(task_type, exclude=tried)
        if endpoint is None:
            break

        key = f"{endpoint.provider}:{endpoint.model_id}"
        tried.add(key)

        try:
            result = await _call_endpoint_vlm(endpoint, prompt, image_base64, system)
            return result
        except QuotaExhaustedError as e:
            router.mark_unavailable(endpoint.provider, endpoint.model_id)
            logger.warning("视觉模型 %s 配额耗尽 (%s)，触发 fallback", key, e)
            last_error = e
        except Exception as e:
            retried = False
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    result = await _call_endpoint_vlm(endpoint, prompt, image_base64, system)
                    return result
                except QuotaExhaustedError as eq:
                    router.mark_unavailable(endpoint.provider, endpoint.model_id)
                    logger.warning("视觉模型 %s 配额耗尽 (重试%d次): %s", key, attempt + 1, eq)
                    last_error = eq
                    retried = True
                    break
                except Exception as e2:
                    last_error = e2
                    logger.warning("VLM 调用失败 %s (重试%d次): %s", key, attempt + 1, e2)

            if not retried:
                logger.warning("视觉模型 %s 调用失败，尝试下一个模型", key)

    if last_error:
        raise RuntimeError(f"所有视觉模型不可用，已尝试: {tried}，最后错误: {last_error}")
    raise RuntimeError(f"无可用视觉模型（需要配置支持 vision 的模型端点）")


def _route_vlm(task_type: str = "default", exclude: set[str] | None = None) -> ModelEndpoint | None:
    """路由到可用的视觉模型端点"""
    exclude = exclude or set()
    tier = registry.get_tier(task_type)

    # 按优先级收集视觉端点
    candidates = []
    tier_idx = ModelRouter.TIER_ORDER.index(tier) if tier in ModelRouter.TIER_ORDER else 1

    # 同 tier 视觉模型
    for ep in registry.get_vision_endpoints(tier=tier, exclude=exclude):
        if router.is_available(ep.provider, ep.model_id):
            candidates.append(ep)

    # 低 tier 视觉模型
    for lower_tier in ModelRouter.TIER_ORDER[tier_idx + 1:]:
        for ep in registry.get_vision_endpoints(tier=lower_tier, exclude=exclude):
            if router.is_available(ep.provider, ep.model_id) and ep not in candidates:
                candidates.append(ep)

    return candidates[0] if candidates else None


async def _call_endpoint_vlm(endpoint: ModelEndpoint, prompt: str, image_base64: str, system: str) -> str:
    """调用指定端点的视觉模型，构造 OpenAI Vision 多模态消息格式"""
    url = f"{endpoint.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": endpoint.model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            ]},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    if _HAS_HTTPX:
        return await _httpx_call(url, headers, payload, endpoint)
    else:
        return await _urllib_call(url, headers, payload, endpoint)


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

        if resp.status_code == 400:
            logger.error("LLM 400 错误详情: url=%s, model=%s, response=%s", url, endpoint.model_id, resp.text[:500])
            raise RuntimeError(f"请求格式错误 (HTTP 400): {resp.text[:300]}")

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
