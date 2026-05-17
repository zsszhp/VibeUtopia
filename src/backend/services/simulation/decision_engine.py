"""B级Agent行为决策引擎 — 感知-思考-行动循环 + LLM驱动"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.simulation.models import PlatformAction, ActionType

logger = logging.getLogger(__name__)

DECISION_PROMPT = """你是一个社交媒体用户仿真Agent。请根据你的人格特征和当前平台内容，决定你的行为。

## 你的人格
{persona_json}

## 当前平台环境
平台: {platform}
时段: {time_slot}
当前热榜话题数: {feed_count}

## 你看到的内容
{feed_text}

## 可选行为
- post: 发布新内容
- comment: 对某条内容发表评论
- like: 点赞
- share: 转发
- view: 仅浏览（不互动）

请输出JSON格式：
{{
  "actions": [
    {{
      "action_type": "comment/like/share/view/post",
      "target_id": "目标帖子ID（view/like/comment/share需要）",
      "content": "你的评论或发布内容（comment/post需要）",
      "reasoning": "简短的行为原因"
    }}
  ]
}}

要求：
1. 根据你的人格特征决定行为，保持角色一致
2. 行为数量1-3个，不要过度活跃
3. 评论内容要符合你的表达风格和认知水平
4. 如果内容与你的敏感触发点相关，可以选择不互动或发布反对意见
5. 所有文本使用中文"""


async def decide_actions(
    agent: Dict[str, Any],
    platform: str,
    time_slot: str,
    platform_feed: List[Dict],
) -> List[PlatformAction]:
    """B级Agent行为决策

    Args:
        agent: Agent 7层人格dict
        platform: 平台标识
        time_slot: 当前时段
        platform_feed: 平台可见内容列表

    Returns:
        行为列表
    """
    agent_id = agent.get("persona_id", "")
    persona_json = json.dumps(agent, ensure_ascii=False, indent=2)[:2000]

    # 格式化feed内容
    feed_text = ""
    for i, post in enumerate(platform_feed[:8]):
        feed_text += f"\n--- 帖子{i+1} (ID: {post.get('post_id', '')}) ---\n"
        feed_text += f"作者: {post.get('author_name', '匿名')}\n"
        feed_text += f"内容: {post.get('content', '')[:200]}\n"
        feed_text += f"点赞: {post.get('likes', 0)} 评论: {post.get('comment_count', 0)}\n"

    if not feed_text:
        feed_text = "（当前没有新内容）"

    prompt = DECISION_PROMPT.format(
        persona_json=persona_json,
        platform=platform,
        time_slot=time_slot,
        feed_count=len(platform_feed),
        feed_text=feed_text,
    )

    try:
        resp = await call_llm(prompt, task_type="simulation")
        data = parse_llm_json(resp)

        if not data or "actions" not in data:
            return _fallback_actions(agent_id, platform, platform_feed)

        actions = []
        for act in data.get("actions", []):
            action_type = act.get("action_type", "view")
            if action_type not in ("post", "comment", "like", "share", "view"):
                action_type = "view"

            actions.append(PlatformAction(
                agent_id=agent_id,
                platform=platform,
                action_type=action_type,
                content=act.get("content", ""),
                target_id=act.get("target_id", ""),
                timestamp=datetime.now(timezone.utc),
                metadata={"reasoning": act.get("reasoning", "")},
            ))

        return actions[:3]  # 最多3个行为

    except Exception as e:
        logger.error(f"Agent {agent_id} 行为决策失败: {e}")
        return _fallback_actions(agent_id, platform, platform_feed)


def _fallback_actions(agent_id: str, platform: str,
                       feed: List[Dict]) -> List[PlatformAction]:
    """规则兜底"""
    actions = []
    if feed:
        actions.append(PlatformAction(
            agent_id=agent_id,
            platform=platform,
            action_type="view",
            target_id=feed[0].get("post_id", ""),
            timestamp=datetime.now(timezone.utc),
        ))
    return actions
