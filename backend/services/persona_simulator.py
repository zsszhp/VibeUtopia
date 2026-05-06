import asyncio
import json
import logging

from backend.services.llm_client import call_llm, load_prompt

logger = logging.getLogger(__name__)

PLATFORMS = ["bilibili", "xiaohongshu", "zhihu", "douyin"]
PLATFORM_NAMES = {
    "bilibili": "B站",
    "xiaohongshu": "小红书",
    "zhihu": "知乎",
    "douyin": "抖音",
}


async def simulate_platform(text: str, platform: str) -> dict:
    """模拟单个平台的用户反应"""
    prompt_template = load_prompt(f"persona_{platform}.txt")
    prompt = prompt_template + text

    try:
        response = await call_llm(prompt)
        result = _parse_response(response)
        result["platform"] = platform
        result["platform_name"] = PLATFORM_NAMES[platform]
        return result
    except Exception as e:
        logger.error(f"平台 {platform} 模拟失败: {e}")
        return {
            "platform": platform,
            "platform_name": PLATFORM_NAMES[platform],
            "focus": "模拟失败",
            "comment": "",
            "sentiment": "neutral",
            "reason": f"模拟失败: {str(e)}",
        }


async def simulate_platforms(text: str) -> list[dict]:
    """并行模拟所有平台的用户反应"""
    tasks = [simulate_platform(text, p) for p in PLATFORMS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"平台模拟异常: {r}")
            continue
        processed.append(r)

    return processed


def _parse_response(response: str) -> dict:
    """解析 LLM 返回的 JSON，降级用正则提取"""
    # 尝试直接解析 JSON
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 降级：正则提取关键字段
    result = {"focus": "", "comment": "", "sentiment": "neutral", "reason": ""}

    for field in ["focus", "comment", "sentiment", "reason"]:
        match = re.search(rf'"{field}"\s*:\s*"([^"]*)"', response)
        if match:
            result[field] = match.group(1)

    return result
