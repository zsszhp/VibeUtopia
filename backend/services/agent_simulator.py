"""Agent模拟器 — 基于独立7层人格的多Agent反应模拟

替代旧的persona_simulator.py中的"群体模拟"方式。
每个Agent拥有独立7层人格，基于人格做出差异化反应。
每个平台生成3个不同人格的Agent，聚合为平台整体反应。
"""
import asyncio
import json
import logging
from typing import Optional

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json
from backend.services.persona_generator import generate_personas_batch

PLATFORM_NAMES = {
    # P0
    "bilibili": "B站",
    "xiaohongshu": "小红书",
    "zhihu": "知乎",
    "douyin": "抖音",
    "weibo": "微博",
    # P1
    "kuaishou": "快手",
    "wechat_channels": "微信视频号",
    "douban": "豆瓣",
    "hupu": "虎扑",
    "toutiao": "今日头条",
    "tieba": "贴吧",
    "taptap": "TapTap",
    "wechat_official": "公众号",
    "shipinhao": "微信视频号",
    "twitter": "Twitter/X",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "youtube": "YouTube",
    "telegram": "Telegram",
    "reddit": "Reddit",
    # P2
    "tiktok_global": "TikTok(国际)",
    "linkedin": "LinkedIn",
    "nga": "NGA",
    "v2ex": "V2EX",
    "maimai": "脉脉",
    "boss_zhilian": "Boss直聘",
    "smzdm": "什么值得买",
    "zhihu_zhuanlan": "知乎专栏",
    "jike": "即刻",
}

logger = logging.getLogger(__name__)

AGENTS_PER_PLATFORM = 5  # 每个平台生成的Agent数量


async def _agent_react(persona: dict, text: str, platform_name: str) -> Optional[dict]:
    """单个Agent基于其人格对文案做出反应

    Args:
        persona: 7层人格dict
        text: 待分析文案
        platform_name: 平台中文名

    Returns:
        Agent反应dict
    """
    prompt_template = load_prompt("agent_reaction.txt")
    persona_json = json.dumps(persona, ensure_ascii=False, indent=2)
    prompt = (
        prompt_template
        .replace("{platform_name}", platform_name)
        .replace("{persona_json}", persona_json)
    )
    prompt += text

    try:
        response = await call_llm(prompt, task_type="agent_simulation")
        result = parse_llm_json(response, fallback=None)

        if not result or "reaction_type" not in result:
            logger.warning("Agent %s 反应解析失败", persona.get("persona_id", "unknown"))
            return None

        # 补充人格元信息
        result["persona_id"] = persona.get("persona_id", "unknown")
        result["persona_name"] = persona.get("L1_basic", {}).get("occupation", "匿名用户")
        result["persona_archetype"] = persona.get("archetype_base", "")
        result["platform"] = persona.get("platform", "")

        return result

    except Exception as e:
        logger.error("Agent %s 反应生成失败: %s", persona.get("persona_id", "unknown"), e)
        return None


def _aggregate_agent_reactions(
    agent_reactions: list[dict],
    platform: str,
    platform_name: str,
) -> dict:
    """聚合多个Agent的反应为平台整体反应

    Returns:
        聚合后的平台反应dict（兼容旧格式 + 新增agents详情）
    """
    if not agent_reactions:
        return {
            "platform": platform,
            "platform_name": platform_name,
            "focus": "无Agent反应",
            "comment": "",
            "positive": 0.33,
            "neutral": 0.34,
            "negative": 0.33,
            "sentiment": "neutral",
            "reason": "Agent模拟未产出有效反应",
            "sub_reactions": [],
            "agent_details": [],
        }

    # 计算情绪比例
    positive_count = sum(1 for r in agent_reactions if r.get("reaction_type") in ("positive", "mixed") and r.get("emotional_intensity", 0) > 0.3)
    negative_count = sum(1 for r in agent_reactions if r.get("reaction_type") == "negative")
    neutral_count = len(agent_reactions) - positive_count - negative_count

    total = len(agent_reactions)
    positive = round(positive_count / total, 2)
    negative = round(negative_count / total, 2)
    neutral = round(1.0 - positive - negative, 2)

    # 确定整体sentiment
    if positive > negative and positive > neutral:
        sentiment = "positive"
    elif negative > positive and negative > neutral:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # 选择最具代表性的评论（情感最强烈的）
    representative = max(agent_reactions, key=lambda r: r.get("emotional_intensity", 0))

    # 聚合关注点
    all_focuses = [r.get("focus", "") for r in agent_reactions if r.get("focus")]
    main_focus = all_focuses[0] if all_focuses else ""

    # 构建聚合原因
    reasons = []
    for r in agent_reactions:
        name = r.get("persona_name", "用户")
        reaction = r.get("reaction_type", "neutral")
        focus = r.get("focus", "")
        reasons.append(f"{name}({reaction}): {focus[:50]}")
    reason = f"基于{total}个Agent反应聚合: " + "; ".join(reasons)

    # 构建sub_reactions（按人格原型分组）
    sub_reactions = []
    archetype_groups = {}
    for r in agent_reactions:
        arch = r.get("persona_archetype", "unknown")
        if arch not in archetype_groups:
            archetype_groups[arch] = []
        archetype_groups[arch].append(r)

    for arch, reactions in archetype_groups.items():
        sub_reactions.append({
            "group": arch,
            "reaction": reactions[0].get("comment", "")[:100] if reactions else "",
            "ratio": round(len(reactions) / total, 2),
        })

    # 构建agent_details
    agent_details = []
    for r in agent_reactions:
        agent_details.append({
            "persona_id": r.get("persona_id", ""),
            "persona_name": r.get("persona_name", ""),
            "archetype": r.get("persona_archetype", ""),
            "reaction_type": r.get("reaction_type", "neutral"),
            "comment": r.get("comment", ""),
            "focus": r.get("focus", ""),
            "emotional_intensity": r.get("emotional_intensity", 0),
            "reasoning": r.get("reasoning", ""),
        })

    return {
        "platform": platform,
        "platform_name": platform_name,
        "focus": main_focus,
        "comment": representative.get("comment", ""),
        "positive": positive,
        "neutral": neutral,
        "negative": negative,
        "sentiment": sentiment,
        "reason": reason,
        "sub_reactions": sub_reactions,
        "agent_details": agent_details,
    }


async def simulate_platform_with_agents(text: str, platform: str) -> dict:
    """使用多Agent模拟单个平台的用户反应

    Args:
        text: 待分析文案
        platform: 平台标识

    Returns:
        聚合后的平台反应dict
    """
    platform_name = PLATFORM_NAMES.get(platform, platform)

    # 1. 生成Agent人格
    personas = await generate_personas_batch(platform, AGENTS_PER_PLATFORM)

    if not personas:
        # 降级：如果人格生成全部失败，返回基础反应
        logger.warning("平台 %s Agent人格生成失败，使用降级反应", platform)
        return {
            "platform": platform,
            "platform_name": platform_name,
            "focus": "模拟降级",
            "comment": "",
            "positive": 0.33,
            "neutral": 0.34,
            "negative": 0.33,
            "sentiment": "neutral",
            "reason": "Agent人格生成失败，使用默认反应",
            "sub_reactions": [],
            "agent_details": [],
        }

    # 2. 并行获取各Agent反应
    react_tasks = [_agent_react(p, text, platform_name) for p in personas]
    reactions = await asyncio.gather(*react_tasks, return_exceptions=True)

    valid_reactions = []
    for r in reactions:
        if isinstance(r, Exception):
            logger.error("Agent反应异常: %s", r)
            continue
        if r is not None:
            valid_reactions.append(r)

    # 3. 聚合反应
    result = _aggregate_agent_reactions(valid_reactions, platform, platform_name)
    return result


async def simulate_all_platforms_with_agents(text: str) -> list[dict]:
    """并行模拟所有平台的Agent反应

    Args:
        text: 待分析文案

    Returns:
        各平台聚合反应列表
    """
    from backend.services.persona_simulator import PLATFORMS

    tasks = [simulate_platform_with_agents(text, p) for p in PLATFORMS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("平台模拟异常: %s", r)
            continue
        processed.append(r)

    return processed
