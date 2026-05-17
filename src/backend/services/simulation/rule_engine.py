"""C级Agent规则引擎 — 基于人格属性的纯规则决策，无LLM调用"""

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.simulation.models import PlatformAction, ActionType

logger = logging.getLogger(__name__)


class RuleEngine:
    """C级Agent规则引擎

    基于Agent的L2价值观、L4行为模式、L6社交关系做规则决策
    """

    def decide(self, agent: Dict, platform_feed: List[Dict],
               platform: str) -> List[PlatformAction]:
        """为C级Agent生成行为列表

        Args:
            agent: Agent 7层人格dict
            platform_feed: 当前平台可见内容
            platform: 平台标识

        Returns:
            行为列表
        """
        actions = []
        l2 = agent.get("L2_values", {})
        l4 = agent.get("L4_behavior", {})
        l6 = agent.get("L6_social", {})
        agent_id = agent.get("persona_id", "")

        if isinstance(l2, str):
            try:
                l2 = json.loads(l2)
            except Exception:
                l2 = {}
        if isinstance(l4, str):
            try:
                l4 = json.loads(l4)
            except Exception:
                l4 = {}
        if isinstance(l6, str):
            try:
                l6 = json.loads(l6)
            except Exception:
                l6 = {}

        # 行为基础概率（基于L4行为模式）
        interaction = l4.get("interaction_preference", "偶尔评论")
        base_prob = {"潜水": 0.05, "偶尔评论": 0.15, "活跃评论": 0.35, "创作者": 0.5}
        action_prob = base_prob.get(interaction, 0.15)

        # 社交活跃度调节
        social_act = l6.get("social_activity", "中等")
        social_mod = {"低": 0.7, "中等": 1.0, "高": 1.3}
        action_prob *= social_mod.get(social_act, 1.0)

        # 对每条feed内容决定行为
        for post in platform_feed[:5]:  # 最多看5条
            if random.random() > action_prob:
                continue

            post_id = post.get("post_id", "")
            content_sentiment = post.get("sentiment", "neutral")

            # 浏览行为（最常见）
            actions.append(PlatformAction(
                agent_id=agent_id,
                platform=platform,
                action_type=ActionType.VIEW,
                content="",
                target_id=post_id,
                timestamp=datetime.now(timezone.utc),
            ))

            # 点赞概率
            like_prob = self._calc_like_prob(l2, content_sentiment)
            if random.random() < like_prob:
                actions.append(PlatformAction(
                    agent_id=agent_id,
                    platform=platform,
                    action_type=ActionType.LIKE,
                    content="",
                    target_id=post_id,
                    timestamp=datetime.now(timezone.utc),
                ))

            # 评论概率（较低）
            comment_prob = action_prob * 0.3
            if random.random() < comment_prob:
                comment = self._generate_rule_comment(agent, post)
                actions.append(PlatformAction(
                    agent_id=agent_id,
                    platform=platform,
                    action_type=ActionType.COMMENT,
                    content=comment,
                    target_id=post_id,
                    timestamp=datetime.now(timezone.utc),
                ))

            # 转发概率（基于L6社交影响力）
            share_prob = self._calc_share_prob(l2, l6, content_sentiment)
            if random.random() < share_prob:
                actions.append(PlatformAction(
                    agent_id=agent_id,
                    platform=platform,
                    action_type=ActionType.SHARE,
                    content="",
                    target_id=post_id,
                    timestamp=datetime.now(timezone.utc),
                ))

        return actions

    def _calc_like_prob(self, l2: Dict, content_sentiment: str) -> float:
        """计算点赞概率"""
        social_justice = float(l2.get("social_justice", 5.0))
        base = 0.2
        if content_sentiment == "positive":
            base += 0.1
        elif content_sentiment == "negative":
            base -= 0.05
        # 社会正义感高的人更容易对正义内容点赞
        if social_justice > 7 and content_sentiment == "positive":
            base += 0.15
        return min(0.6, max(0.05, base))

    def _calc_share_prob(self, l2: Dict, l6: Dict, content_sentiment: str) -> float:
        """计算转发概率"""
        influence = l6.get("influence_level", "普通用户")
        base = {"潜水者": 0.02, "普通用户": 0.05, "活跃分子": 0.15, "KOL": 0.3}
        return base.get(influence, 0.05)

    def _generate_rule_comment(self, agent: Dict, post: Dict) -> str:
        """规则生成简短评论（无需LLM）"""
        l4 = agent.get("L4_behavior", {})
        expression = l4.get("expression_style", "中立") if isinstance(l4, dict) else "中立"

        templates = {
            "激进": ["完全不同意！", "太离谱了！", "必须曝光！", "这就是问题所在！"],
            "直率": ["说得对", "不太认同", "我也有同感", "有道理但偏激了"],
            "中立": ["了解一下", "关注了", "有点意思", "看看再说"],
            "温和": ["希望能和平解决", "大家冷静一下", "各有各的道理", "理性讨论"],
            "谨慎": ["需要更多信息", "等等看吧", "不好评价", "让子弹飞一会"],
        }

        options = templates.get(expression, templates["中立"])
        return random.choice(options)
