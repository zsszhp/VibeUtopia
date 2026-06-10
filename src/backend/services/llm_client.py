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
    text: bool = True  # 是否支持纯文本任务（Omni类模型设为False）
    image_gen: bool = False  # 是否支持图像生成
    image_mode: str = ""  # 图像生成模式: "t2i"(文生图) / "img2img"(图生图)
    key_index: int = 0  # 同一厂商多 Key 时的序号（从 0 开始）
    key_label: str = ""  # Key 显示标签，如 "Key2"


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
            raw_api_key = os.getenv(api_key_env, "")

            # 如果环境变量为空，直接跳过该 provider
            if not raw_api_key:
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

            # 支持多 Key：逗号分隔，如 "key1,key2,key3"
            api_keys = [k.strip() for k in raw_api_key.split(",") if k.strip()]
            if not api_keys:
                continue

            for mcfg in models_cfg:
                m_id = mcfg.get("id", "")
                for key_idx, ak in enumerate(api_keys):
                    key_label = f"Key{key_idx + 1}" if len(api_keys) > 1 else ""
                    ep = ModelEndpoint(
                        provider=provider_id,
                        model_id=m_id,
                        base_url=base_url,
                        api_key=ak,
                        tier=mcfg.get("tier", "standard"),
                        provider_name=provider_name,
                        vision=mcfg.get("vision", False),
                        text=mcfg.get("text", True),
                        image_gen=mcfg.get("image_gen", False),
                        image_mode=mcfg.get("image_mode", ""),
                        key_index=key_idx,
                        key_label=key_label,
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
        text_only: bool = False,
    ) -> list[ModelEndpoint]:
        """获取符合条件的端点列表

        Args:
            text_only: 如果为True，只返回支持纯文本任务的端点
        """
        result = []
        for ep in self.endpoints:
            if tier and ep.tier != tier:
                continue
            if provider and ep.provider != provider:
                continue
            if exclude and f"{ep.provider}:{ep.model_id}:{ep.key_index}" in exclude:
                continue
            if text_only and not ep.text:
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
                    "key_count": 0,
                }
            model_key = f"{ep.model_id}:{ep.tier}"
            if not any(m["id"] == ep.model_id for m in provider_map[ep.provider]["models"]):
                provider_map[ep.provider]["models"].append({
                    "id": ep.model_id,
                    "tier": ep.tier,
                })
            provider_map[ep.provider]["key_count"] = max(
                provider_map[ep.provider].get("key_count", 0),
                ep.key_index + 1,
            )
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
            if exclude and f"{ep.provider}:{ep.model_id}:{ep.key_index}" in exclude:
                continue
            result.append(ep)
        return result

    def get_image_gen_endpoints(
        self,
        image_mode: str | None = None,
        tier: str | None = None,
        exclude: set[str] | None = None,
    ) -> list[ModelEndpoint]:
        """获取支持图像生成的端点列表

        Args:
            image_mode: 图像生成模式过滤 ("t2i" 文生图 / "img2img" 图生图)
            tier: 模型级别过滤
            exclude: 排除的端点集合
        """
        result = []
        for ep in self.endpoints:
            if not ep.image_gen:
                continue
            if image_mode and ep.image_mode != image_mode:
                continue
            if tier and ep.tier != tier:
                continue
            if exclude and f"{ep.provider}:{ep.model_id}:{ep.key_index}" in exclude:
                continue
            result.append(ep)
        return result


# ---------------------------------------------------------------------------
# ModelRouter: 路由选择 + fallback + 冷却管理
# ---------------------------------------------------------------------------

class ModelRouter:
    """根据 task_type 路由到最优模型，支持 fallback、冷却和 Key 智能轮换

    Key 轮换策略：
    1. 同一模型多 Key 时，优先使用 key_index 较小的（Key1 > Key2 > Key3）
    2. 当前 Key 限流（429）→ 标记冷却 → 自动切换下一个 Key
    3. 冷却期结束后，下次路由自动回切到优先级更高的 Key
    4. 冷却时间可通过 MODEL_COOLDOWN_SECONDS 环境变量配置（默认 300 秒）
    """

    TIER_ORDER = ["advanced", "standard", "lite"]

    def __init__(self, registry: ModelRegistry, cooldown_seconds: int = 300):
        self.registry = registry
        self._cooldown_seconds = cooldown_seconds
        self._cooling: dict[str, float] = {}  # "provider:model_id:key_index" -> resume_timestamp
        self._runtime_provider: str = ""
        self._runtime_model: str = ""
        self._key_usage_stats: dict[str, dict] = {}  # key -> {calls, errors, last_used}

    def set_override(self, provider: str = "", model: str = ""):
        """运行时设置覆盖，立即生效，无需重启"""
        self._runtime_provider = provider
        self._runtime_model = model
        logger.info("模型运行时覆盖已更新: provider=%s, model=%s", provider, model)

    def get_override(self) -> dict:
        """获取当前运行时覆盖设置"""
        return {"provider": self._runtime_provider, "model": self._runtime_model}

    def route(self, task_type: str = "default", exclude: set[str] | None = None) -> ModelEndpoint | None:
        """根据 task_type 路由到最优可用模型（自动回切已恢复的 Key）"""
        exclude = exclude or set()
        tier = self.registry.get_tier(task_type)

        # 1. 检查运行时覆盖 / DEFAULT_PROVIDER / DEFAULT_MODEL
        effective_provider = self._runtime_provider or settings.DEFAULT_PROVIDER
        effective_model = self._runtime_model or settings.DEFAULT_MODEL
        if effective_provider or effective_model:
            override = self._find_override(tier, exclude, effective_provider, effective_model)
            if override:
                return override

        # 2. 四级 fallback 策略（候选列表已按 key_index 排序，优先使用 Key1）
        strategy = self.registry.fallback_strategy
        candidates = self._build_candidates(tier, strategy, exclude)
        return candidates[0] if candidates else None

    def _find_override(self, tier: str, exclude: set[str], provider: str, model: str) -> ModelEndpoint | None:
        """查找指定的覆盖模型（同模型多 Key 时优先使用 Key1）"""
        candidates = []
        for ep in self.registry.get_endpoints(text_only=True):
            key = f"{ep.provider}:{ep.model_id}:{ep.key_index}"
            if key in exclude:
                continue
            if not self.is_available(ep.provider, ep.model_id, ep.key_index):
                continue
            if model and ep.model_id == model:
                candidates.append(ep)
            elif provider and ep.provider == provider and ep.tier == tier:
                candidates.append(ep)
        # 同模型多 Key 时优先使用 key_index 较小的
        candidates.sort(key=lambda e: e.key_index)
        return candidates[0] if candidates else None

    def _build_candidates(self, tier: str, strategy: dict, exclude: set[str]) -> list[ModelEndpoint]:
        """按 fallback 策略构建候选模型列表（同模型多 Key 按 key_index 排序，确保优先回切 Key1）"""
        candidates = []
        tier_idx = self.TIER_ORDER.index(tier) if tier in self.TIER_ORDER else 1

        if strategy.get("same_provider_same_tier", True):
            for ep in self.registry.get_endpoints(tier=tier, exclude=exclude, text_only=True):
                if self.is_available(ep.provider, ep.model_id, ep.key_index):
                    candidates.append(ep)

        if strategy.get("same_provider_lower_tier", True):
            for lower_tier in self.TIER_ORDER[tier_idx + 1:]:
                for ep in self.registry.get_endpoints(tier=lower_tier, exclude=exclude, text_only=True):
                    if self.is_available(ep.provider, ep.model_id, ep.key_index):
                        if ep not in candidates:
                            candidates.append(ep)

        if strategy.get("cross_provider_same_tier", True):
            pass

        if strategy.get("cross_provider_lower_tier", True):
            for lower_tier in self.TIER_ORDER[tier_idx + 1:]:
                for ep in self.registry.get_endpoints(tier=lower_tier, exclude=exclude, text_only=True):
                    if self.is_available(ep.provider, ep.model_id, ep.key_index) and ep not in candidates:
                        candidates.append(ep)

        # 关键排序：同 provider+model 的端点按 key_index 升序排列
        # 确保 Key1 冷却恢复后自动回切到 Key1（优先级高于 Key2）
        candidates.sort(key=lambda e: (self._endpoint_group_key(e), e.key_index))
        return candidates

    @staticmethod
    def _endpoint_group_key(ep: ModelEndpoint) -> tuple:
        """端点分组键：同 provider+model+tier 为一组"""
        return (ep.provider, ep.model_id, ep.tier)

    def mark_unavailable(self, provider: str, model_id: str, key_index: int = 0):
        """标记模型 Key 临时不可用（进入冷却期）"""
        key = f"{provider}:{model_id}:{key_index}"
        self._cooling[key] = time.time() + self._cooldown_seconds
        label = f"Key{key_index + 1}" if key_index else "Key1"

        # 更新使用统计
        if key not in self._key_usage_stats:
            self._key_usage_stats[key] = {"calls": 0, "errors": 0, "last_used": 0}
        self._key_usage_stats[key]["errors"] += 1

        logger.warning(
            "模型 %s %s 限流标记冷却 %d 秒（第%d次限流），自动切换到下一个可用 Key",
            provider, label, self._cooldown_seconds,
            self._key_usage_stats[key]["errors"],
        )

    def record_success(self, provider: str, model_id: str, key_index: int = 0):
        """记录 Key 调用成功（用于统计和回切判断）"""
        key = f"{provider}:{model_id}:{key_index}"
        if key not in self._key_usage_stats:
            self._key_usage_stats[key] = {"calls": 0, "errors": 0, "last_used": 0}
        self._key_usage_stats[key]["calls"] += 1
        self._key_usage_stats[key]["last_used"] = time.time()

    def is_available(self, provider: str, model_id: str, key_index: int = 0) -> bool:
        """检查模型 Key 是否可用（冷却期结束后自动恢复，实现回切）"""
        key = f"{provider}:{model_id}:{key_index}"
        resume_at = self._cooling.get(key, 0)
        if time.time() < resume_at:
            remaining = int(resume_at - time.time())
            return False
        # 冷却期已过 → 自动恢复，下次路由会优先选到此 Key（回切）
        if key in self._cooling:
            self._cooling.pop(key, None)
            label = f"Key{key_index + 1}"
            logger.info("模型 %s %s 冷却期已结束，自动恢复可用（回切生效）", provider, label)
        return True

    def get_key_pool_status(self) -> dict:
        """返回所有 Key 的实时状态，用于监控面板"""
        status: dict[str, dict] = {}
        for ep in self.registry.endpoints:
            pkey = ep.provider
            if pkey not in status:
                status[pkey] = {
                    "name": ep.provider_name,
                    "key_count": 0,
                    "models": {},
                }
            status[pkey]["key_count"] = max(
                status[pkey]["key_count"],
                ep.key_index + 1,
            )
            mk = ep.model_id
            if mk not in status[pkey]["models"]:
                status[pkey]["models"][mk] = {}
            avail = self.is_available(ep.provider, ep.model_id, ep.key_index)
            key_label = f"Key{ep.key_index + 1}"
            key_stats = self._key_usage_stats.get(f"{ep.provider}:{ep.model_id}:{ep.key_index}", {})
            cooling_key = f"{ep.provider}:{ep.model_id}:{ep.key_index}"
            remaining = max(0, int(self._cooling.get(cooling_key, 0) - time.time()))
            status[pkey]["models"][mk][key_label] = {
                "available": avail,
                "tier": ep.tier,
                "total_calls": key_stats.get("calls", 0),
                "total_errors": key_stats.get("errors", 0),
                "cooling_remaining_seconds": remaining if not avail else 0,
            }
        return status

    def get_active_endpoint(self, provider: str, model_id: str) -> ModelEndpoint | None:
        """返回指定模型当前可用的第一个 Key 端点（优先 key_index 较小者）"""
        candidates = []
        for ep in self.registry.endpoints:
            if ep.provider == provider and ep.model_id == model_id:
                if self.is_available(ep.provider, ep.model_id, ep.key_index):
                    candidates.append(ep)
        candidates.sort(key=lambda e: e.key_index)
        return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# 初始化全局实例
# ---------------------------------------------------------------------------

registry = ModelRegistry(settings.MODEL_CONFIG_PATH)
router = ModelRouter(registry, settings.MODEL_COOLDOWN_SECONDS)

_llm_semaphore = asyncio.Semaphore(10)
_vlm_semaphore = asyncio.Semaphore(5)
_image_gen_semaphore = asyncio.Semaphore(3)


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
    """调用 LLM API，自动路由模型，支持 fallback，带全局并发控制

    Args:
        prompt: 用户提示词
        system: 系统提示词
        task_type: 任务类型，用于智能路由 (risk_assessment / persona_simulation / rewrite / default)
    """
    async with _llm_semaphore:
        if registry.is_loaded:
            return await _call_with_routing(prompt, system, task_type)
        else:
            return await _call_legacy(prompt, system)


async def call_vlm(prompt: str, image_base64: str, system: str = "你是一个专业的AI助手。", task_type: str = "default") -> str:
    """调用视觉语言模型 (VLM) API，支持图片输入，带全局并发控制

    Args:
        prompt: 用户提示词
        image_base64: 图片的 base64 编码字符串
        system: 系统提示词
        task_type: 任务类型，用于智能路由

    Raises:
        RuntimeError: 无可用视觉模型时抛出
    """
    async with _vlm_semaphore:
        if not registry.is_loaded:
            raise RuntimeError("模型配置未加载，无法调用视觉模型")

        tried: set[str] = set()
        last_error: Exception | None = None

        while True:
            endpoint = _route_vlm(task_type, exclude=tried)
            if endpoint is None:
                break

            key = f"{endpoint.provider}:{endpoint.model_id}:{endpoint.key_index}"
            tried.add(key)

            try:
                result = await _call_endpoint_vlm(endpoint, prompt, image_base64, system)
                router.record_success(endpoint.provider, endpoint.model_id, endpoint.key_index)
                return result
            except QuotaExhaustedError as e:
                router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
                logger.warning("视觉模型 %s 配额耗尽 (%s)，触发 fallback", key, e)
                last_error = e
            except Exception as e:
                retried = False
                for attempt in range(settings.LLM_MAX_RETRIES):
                    try:
                        result = await _call_endpoint_vlm(endpoint, prompt, image_base64, system)
                        return result
                    except QuotaExhaustedError as eq:
                        router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
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
        if router.is_available(ep.provider, ep.model_id, ep.key_index):
            candidates.append(ep)

    # 低 tier 视觉模型
    for lower_tier in ModelRouter.TIER_ORDER[tier_idx + 1:]:
        for ep in registry.get_vision_endpoints(tier=lower_tier, exclude=exclude):
            if router.is_available(ep.provider, ep.model_id, ep.key_index) and ep not in candidates:
                candidates.append(ep)

    return candidates[0] if candidates else None


async def _call_endpoint_vlm(endpoint: ModelEndpoint, prompt: str, image_base64: str, system: str) -> str:
    """调用指定端点的视觉模型，自动适配不同API格式"""
    url = f"{endpoint.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }

    is_omni = "omni" in endpoint.model_id.lower()

    if is_omni:
        payload = {
            "model": endpoint.model_id,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system}]},
                {"role": "user", "content": [
                    {"type": "input_image", "input_image": {"type": "base64", "data": [image_base64]}},
                    {"type": "text", "text": prompt},
                ]},
            ],
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.7,
            "output_modalities": ["text"],
        }
    else:
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

        key = f"{endpoint.provider}:{endpoint.model_id}:{endpoint.key_index}"
        tried.add(key)

        try:
            result = await _call_endpoint(endpoint, prompt, system)
            router.record_success(endpoint.provider, endpoint.model_id, endpoint.key_index)
            return result
        except QuotaExhaustedError as e:
            router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
            logger.warning("模型 %s 配额耗尽 (%s)，触发 fallback", key, e)
            last_error = e
        except Exception as e:
            # 非配额错误：重试当前模型
            retried = False
            for attempt in range(settings.LLM_MAX_RETRIES):
                try:
                    result = await _call_endpoint(endpoint, prompt, system)
                    return result
                except QuotaExhaustedError as eq:
                    router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
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
# 图像生成调用
# ---------------------------------------------------------------------------

async def call_image_gen(
    prompt: str,
    size: str = "1024x1024",
    image_mode: str = "t2i",
    image_urls: list[str] | None = None,
    model: str | None = None,
) -> dict:
    """调用图像生成 API，支持文生图和图生图

    Args:
        prompt: 图像描述提示词
        size: 图像尺寸，如 "1024x1024", "1024x768"
        image_mode: 生成模式 "t2i"(文生图) 或 "img2img"(图生图)
        image_urls: 图生图模式下的参考图片 URL 列表
        model: 指定模型名称（可选，不指定则自动路由）

    Returns:
        包含 image_url 或 image_base64 的字典

    Raises:
        RuntimeError: 无可用图像生成模型时抛出
    """
    async with _image_gen_semaphore:
        if not registry.is_loaded:
            raise RuntimeError("模型配置未加载，无法调用图像生成模型")

        tried: set[str] = set()
        last_error: Exception | None = None

        while True:
            endpoint = _route_image_gen(image_mode=image_mode, model=model, exclude=tried)
            if endpoint is None:
                break

            key = f"{endpoint.provider}:{endpoint.model_id}:{endpoint.key_index}"
            tried.add(key)

            try:
                result = await _call_endpoint_image_gen(endpoint, prompt, size, image_urls)
                router.record_success(endpoint.provider, endpoint.model_id, endpoint.key_index)
                return result
            except QuotaExhaustedError as e:
                router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
                logger.warning("图像生成模型 %s 配额耗尽 (%s)，触发 fallback", key, e)
                last_error = e
            except Exception as e:
                for attempt in range(settings.LLM_MAX_RETRIES):
                    try:
                        result = await _call_endpoint_image_gen(endpoint, prompt, size, image_urls)
                        return result
                    except QuotaExhaustedError as eq:
                        router.mark_unavailable(endpoint.provider, endpoint.model_id, endpoint.key_index)
                        logger.warning("图像生成模型 %s 配额耗尽 (重试%d次): %s", key, attempt + 1, eq)
                        last_error = eq
                        break
                    except Exception as e2:
                        last_error = e2
                        logger.warning("图像生成调用失败 %s (重试%d次): %s", key, attempt + 1, e2)
                else:
                    logger.warning("图像生成模型 %s 调用失败，尝试下一个模型", key)

        if last_error:
            raise RuntimeError(f"所有图像生成模型不可用，已尝试: {tried}，最后错误: {last_error}")
        raise RuntimeError("无可用图像生成模型（需要配置支持 image_gen 的模型端点）")


def _route_image_gen(
    image_mode: str = "t2i",
    model: str | None = None,
    exclude: set[str] | None = None,
) -> ModelEndpoint | None:
    """路由到可用的图像生成模型端点"""
    exclude = exclude or set()

    # 如果指定了模型名，优先匹配
    if model:
        for ep in registry.get_image_gen_endpoints(exclude=exclude):
            if ep.model_id == model and router.is_available(ep.provider, ep.model_id, ep.key_index):
                return ep

    # 按 image_mode 过滤，再按 tier 排序
    candidates = []
    for ep in registry.get_image_gen_endpoints(image_mode=image_mode, exclude=exclude):
        if router.is_available(ep.provider, ep.model_id, ep.key_index):
            candidates.append(ep)

    # 如果指定模式无可用模型，尝试所有图像生成模型
    if not candidates:
        for ep in registry.get_image_gen_endpoints(exclude=exclude):
            if router.is_available(ep.provider, ep.model_id, ep.key_index):
                candidates.append(ep)

    # 按 tier 优先级排序
    tier_order = {"advanced": 0, "standard": 1, "lite": 2}
    candidates.sort(key=lambda e: (tier_order.get(e.tier, 1), e.key_index))
    return candidates[0] if candidates else None


async def _call_endpoint_image_gen(
    endpoint: ModelEndpoint,
    prompt: str,
    size: str = "1024x1024",
    image_urls: list[str] | None = None,
) -> dict:
    """调用指定端点的图像生成模型（OpenAI Images API 兼容格式）"""
    url = f"{endpoint.base_url}/images/generations"
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": endpoint.model_id,
        "prompt": prompt,
        "size": size,
    }

    # 图生图模式：添加 extra_body
    if endpoint.image_mode == "img2img" and image_urls:
        payload["extra_body"] = {
            "tags": ["img2img"],
            "image": image_urls,
            "response_format": "url",
        }

    if _HAS_HTTPX:
        return await _httpx_call_image_gen(url, headers, payload, endpoint)
    else:
        return await _urllib_call_image_gen(url, headers, payload, endpoint)


async def _httpx_call_image_gen(
    url: str, headers: dict, payload: dict, endpoint: ModelEndpoint,
) -> dict:
    """httpx 异步调用图像生成"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)

        if _is_quota_error(resp.status_code):
            raise QuotaExhaustedError(
                f"{endpoint.provider_name} {endpoint.model_id} HTTP {resp.status_code}: {resp.text[:200]}"
            )

        if resp.status_code == 400:
            logger.error("图像生成 400 错误: url=%s, model=%s, response=%s", url, endpoint.model_id, resp.text[:500])
            raise RuntimeError(f"请求格式错误 (HTTP 400): {resp.text[:300]}")

        resp.raise_for_status()
        data = resp.json()

        # 解析 OpenAI Images API 响应格式
        images = data.get("data", [])
        if not images:
            raise RuntimeError(f"图像生成返回空结果: {data}")

        result = {
            "model": endpoint.model_id,
            "provider": endpoint.provider,
            "images": [],
        }
        for img in images:
            img_info = {}
            if "url" in img:
                img_info["url"] = img["url"]
            if "b64_json" in img:
                img_info["b64_json"] = img["b64_json"]
            if "revised_prompt" in img:
                img_info["revised_prompt"] = img["revised_prompt"]
            result["images"].append(img_info)

        return result


async def _urllib_call_image_gen(
    url: str, headers: dict, payload: dict, endpoint: ModelEndpoint,
) -> dict:
    """urllib 同步调用图像生成（httpx 不可用时的降级方案）"""
    payload_bytes = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
        loop = asyncio.get_event_loop()
        resp_data = await loop.run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, timeout=60),
        )
        data = json.loads(resp_data.read().decode("utf-8"))

        images = data.get("data", [])
        if not images:
            raise RuntimeError(f"图像生成返回空结果: {data}")

        result = {
            "model": endpoint.model_id,
            "provider": endpoint.provider,
            "images": [],
        }
        for img in images:
            img_info = {}
            if "url" in img:
                img_info["url"] = img["url"]
            if "b64_json" in img:
                img_info["b64_json"] = img["b64_json"]
            if "revised_prompt" in img:
                img_info["revised_prompt"] = img["revised_prompt"]
            result["images"].append(img_info)

        return result
    except urllib.error.HTTPError as e:
        if _is_quota_error(e.code):
            raise QuotaExhaustedError(
                f"{endpoint.provider_name} {endpoint.model_id} HTTP {e.code}"
            )
        raise


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------

class QuotaExhaustedError(Exception):
    """模型配额耗尽错误（429/402/403）"""
    pass


# 向后兼容别名
QuotaExhausted = QuotaExhaustedError
