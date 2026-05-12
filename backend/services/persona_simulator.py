import asyncio
import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)

PLATFORMS = ["bilibili", "xiaohongshu", "zhihu", "douyin", "weibo", "kuaishou", "wechat_channels"]
PLATFORM_NAMES = {
    "bilibili": "B站",
    "xiaohongshu": "小红书",
    "zhihu": "知乎",
    "douyin": "抖音",
    "weibo": "微博",
    "kuaishou": "快手",
    "wechat_channels": "微信视频号",
}


async def simulate_platform(text: str, platform: str) -> dict:
    """模拟单个平台的用户反应"""
    prompt_template = load_prompt(f"persona_{platform}.txt")
    prompt = prompt_template + text

    try:
        response = await call_llm(prompt, task_type="persona_simulation")
        result = parse_llm_json(response, fallback={
            "focus": "", "comment": "", "sentiment": "neutral", "reason": "",
            "sub_reactions": [],
        })
        result["platform"] = platform
        result["platform_name"] = PLATFORM_NAMES[platform]
        # 确保 sub_reactions 存在
        if "sub_reactions" not in result or not result["sub_reactions"]:
            result["sub_reactions"] = []
        return result
    except Exception as e:
        logger.error("平台 %s 模拟失败: %s", platform, e)
        return {
            "platform": platform,
            "platform_name": PLATFORM_NAMES[platform],
            "focus": "模拟失败",
            "comment": "",
            "sentiment": "neutral",
            "reason": f"模拟失败: {e}",
            "sub_reactions": [],
        }


async def simulate_platforms(text: str) -> list[dict]:
    """并行模拟所有平台的用户反应"""
    tasks = [simulate_platform(text, p) for p in PLATFORMS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("平台模拟异常: %s", r)
            continue
        processed.append(r)

    return processed
