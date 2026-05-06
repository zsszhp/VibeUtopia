import asyncio
import json
import logging
import re
import urllib.request
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


def load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def parse_llm_json(response: str, fallback: dict | None = None) -> dict:
    """从 LLM 响应中解析 JSON，支持多种格式降级提取

    Args:
        response: LLM 原始响应文本
        fallback: 解析失败时返回的默认值
    """
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


async def call_llm(prompt: str, system: str = "你是一个专业的AI助手。") -> str:
    """调用 LLM API，返回模型响应文本"""
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY")

    if _HAS_HTTPX:
        return await _call_with_httpx(prompt, system)
    else:
        return await _call_with_urllib(prompt, system)


def _build_payload(prompt: str, system: str) -> dict:
    """构建统一的请求体"""
    return {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }


def _build_headers() -> dict:
    """构建统一的请求头"""
    return {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }


async def _call_with_httpx(prompt: str, system: str) -> str:
    """使用 httpx 异步调用"""
    headers = _build_headers()
    payload = _build_payload(prompt, system)
    url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"

    last_error = None
    for attempt in range(1 + settings.LLM_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            logger.warning("LLM 调用失败 (第%d次): %s", attempt + 1, e)

    raise RuntimeError(f"LLM 调用失败，已重试{settings.LLM_MAX_RETRIES}次: {last_error}")


async def _call_with_urllib(prompt: str, system: str) -> str:
    """使用 urllib 同步调用 (httpx 不可用时的降级方案)"""
    url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"
    payload = json.dumps(_build_payload(prompt, system)).encode("utf-8")
    headers = _build_headers()

    last_error = None
    for attempt in range(1 + settings.LLM_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            resp_data = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT),
            )
            data = json.loads(resp_data.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            logger.warning("LLM 调用失败 (第%d次): %s", attempt + 1, e)

    raise RuntimeError(f"LLM 调用失败，已重试{settings.LLM_MAX_RETRIES}次: {last_error}")
