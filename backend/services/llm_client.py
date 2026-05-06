import json
import logging
import urllib.request
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# 尝试导入 httpx，不可用时使用 urllib
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


def load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


async def call_llm(prompt: str, system: str = "你是一个专业的AI助手。") -> str:
    """调用 LLM API，返回模型响应文本"""
    if not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("API Key 未配置，请设置环境变量 DEEPSEEK_API_KEY")

    if _HAS_HTTPX:
        return await _call_with_httpx(prompt, system)
    else:
        return await _call_with_urllib(prompt, system)


async def _call_with_httpx(prompt: str, system: str) -> str:
    """使用 httpx 异步调用"""
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

    last_error = None
    for attempt in range(1 + settings.LLM_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
                resp = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            logger.warning(f"LLM 调用失败 (第{attempt + 1}次): {e}")

    raise RuntimeError(f"LLM 调用失败，已重试{settings.LLM_MAX_RETRIES}次: {last_error}")


async def _call_with_urllib(prompt: str, system: str) -> str:
    """使用 urllib 同步调用 (httpx 不可用时的降级方案)"""
    import asyncio

    url = f"{settings.DEEPSEEK_BASE_URL}/chat/completions"
    payload = json.dumps({
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(1 + settings.LLM_MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            # 在事件循环中运行同步的 urllib 调用
            loop = asyncio.get_event_loop()
            resp_data = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT),
            )
            data = json.loads(resp_data.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            logger.warning(f"LLM 调用失败 (第{attempt + 1}次): {e}")

    raise RuntimeError(f"LLM 调用失败，已重试{settings.LLM_MAX_RETRIES}次: {last_error}")
