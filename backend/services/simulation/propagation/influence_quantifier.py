"""传播影响因素量化模型 — Agent因素 + 内容因素 + 平台因素"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# 各平台特有因素权重配置
PLATFORM_FACTORS = {
    "weibo": {
        "name": "微博",
        "algorithm_weight": 0.3,       # 热搜算法权重
        "hot_search_amplification": 10.0,  # 上热搜后曝光放大倍数
        "community_density": 0.4,      # 超话社群密度
        "emotion_multiplier": 1.5,     # 情绪放大系数（微博易极化）
        "cross_circle_difficulty": 0.6, # 跨圈层传播难度
    },
    "bilibili": {
        "name": "B站",
        "algorithm_weight": 0.4,       # 推荐算法权重
        "hot_search_amplification": 5.0,
        "community_density": 0.7,      # 分区文化社群密度高
        "emotion_multiplier": 1.2,     # 弹幕共鸣
        "cross_circle_difficulty": 0.7, # 跨分区传播
    },
    "xiaohongshu": {
        "name": "小红书",
        "algorithm_weight": 0.6,       # 推荐流主导
        "hot_search_amplification": 4.0,
        "community_density": 0.5,      # 种草圈层
        "emotion_multiplier": 1.0,
        "cross_circle_difficulty": 0.5, # 推荐算法帮助破圈
    },
    "zhihu": {
        "name": "知乎",
        "algorithm_weight": 0.3,       # 专业权重 > 算法权重
        "hot_search_amplification": 3.0,
        "community_density": 0.5,      # 话题/领域社群
        "emotion_multiplier": 0.8,     # 理性讨论为主
        "cross_circle_difficulty": 0.8, # 跨领域传播较难
    },
    "douyin": {
        "name": "抖音",
        "algorithm_weight": 0.7,       # 极强算法推荐
        "hot_search_amplification": 8.0,
        "community_density": 0.3,      # 算法推荐为主，社群弱
        "emotion_multiplier": 1.8,     # 情绪感染强
        "cross_circle_difficulty": 0.3, # 算法帮助快速破圈
    },
}

# 影响力等级到数值的映射
INFLUENCE_LEVEL_MAP = {
    "潜水者": 0.1,
    "普通用户": 0.3,
    "活跃分子": 0.6,
    "KOL": 0.9,
    "大V": 1.0,
}

# 社交活跃度到数值的映射
SOCIAL_ACTIVITY_MAP = {
    "低": 0.2,
    "中等": 0.5,
    "高": 0.8,
}


class InfluenceQuantifier:
    """传播影响因素量化模型"""

    def quantify_agent_factors(self, agent: Dict[str, Any]) -> Dict[str, float]:
        """量化Agent因素

        Args:
            agent: Agent 7层人格 dict

        Returns:
            {"influence": float, "activity": float,
             "stance_intensity": float, "emotion_arousal": float}
        """
        persona = agent if isinstance(agent, dict) else {}

        # 影响力: 从 L6_social.influence_level 提取
        influence_level = self._extract_field(persona, "influence_level", "普通用户")
        influence = INFLUENCE_LEVEL_MAP.get(influence_level, 0.3)

        # 活跃度: 从 L6_social.social_activity 提取
        social_activity = self._extract_field(persona, "social_activity", "中等")
        activity = SOCIAL_ACTIVITY_MAP.get(social_activity, 0.5)

        # 立场强度: 从 L2_values.social_stances 的强烈程度推断
        stance_intensity = self._calc_stance_intensity(persona)

        # 情绪唤醒: 从 agent 当前状态推断，默认 0.3
        emotion_arousal = self._extract_field(persona, "emotion_arousal", 0.3)
        if isinstance(emotion_arousal, str):
            emotion_arousal = 0.3

        return {
            "influence": round(influence, 3),
            "activity": round(activity, 3),
            "stance_intensity": round(stance_intensity, 3),
            "emotion_arousal": round(float(emotion_arousal), 3),
        }

    def quantify_content_factors(
        self, content: str, reactions: Optional[List[Dict]] = None
    ) -> Dict[str, float]:
        """量化内容因素

        Args:
            content: 文本内容
            reactions: 互动反应列表

        Returns:
            {"sentiment_intensity": float, "controversy_score": float,
             "resonance_score": float}
        """
        sentiment_intensity = self._calc_sentiment_intensity(content)
        controversy_score = self._calc_controversy(content, reactions or [])
        resonance_score = self._calc_resonance(content, reactions or [])

        return {
            "sentiment_intensity": round(sentiment_intensity, 3),
            "controversy_score": round(controversy_score, 3),
            "resonance_score": round(resonance_score, 3),
        }

    def quantify_platform_factors(
        self, platform: str, actions: Optional[List[Dict]] = None
    ) -> Dict[str, float]:
        """量化平台因素

        Args:
            platform: 平台名称
            actions: 该平台上的行为列表

        Returns:
            {"algorithm_weight": float, "hot_search_amplification": float,
             "community_density": float, "emotion_multiplier": float,
             "cross_circle_difficulty": float}
        """
        factors = PLATFORM_FACTORS.get(platform, PLATFORM_FACTORS["weibo"]).copy()
        # 移除 name 字段
        factors.pop("name", None)

        # 如果有行为数据，动态调整部分因素
        if actions:
            total_actions = len(actions)
            if total_actions > 0:
                # 高互动量 → 热搜概率上升
                share_count = sum(1 for a in actions if a.get("action_type") == "share")
                if share_count > 50:
                    factors["hot_search_amplification"] *= 1.5

        # round all values
        return {k: round(v, 3) for k, v in factors.items()}

    def calc_combined_score(
        self,
        agent_factors: Dict[str, float],
        content_factors: Dict[str, float],
        platform_factors: Dict[str, float],
    ) -> float:
        """综合传播影响力分数

        权重分配:
        - Agent因素: 40% (influence*0.4 + activity*0.2 + stance*0.2 + arousal*0.2)
        - 内容因素: 30% (sentiment*0.3 + controversy*0.3 + resonance*0.4)
        - 平台因素: 30% (algorithm*0.3 + hot_search*0.2 + community*0.2 + emotion*0.3)

        Returns:
            综合分数 0-1
        """
        # Agent因素子分数 (0-1)
        agent_score = (
            agent_factors.get("influence", 0.3) * 0.4
            + agent_factors.get("activity", 0.5) * 0.2
            + agent_factors.get("stance_intensity", 0.3) * 0.2
            + agent_factors.get("emotion_arousal", 0.3) * 0.2
        )

        # 内容因素子分数 (0-1)
        content_score = (
            content_factors.get("sentiment_intensity", 0.3) * 0.3
            + content_factors.get("controversy_score", 0.3) * 0.3
            + content_factors.get("resonance_score", 0.3) * 0.4
        )

        # 平台因素子分数 (0-1)
        platform_score = (
            platform_factors.get("algorithm_weight", 0.3) * 0.3
            + min(platform_factors.get("hot_search_amplification", 5.0) / 10.0, 1.0) * 0.2
            + platform_factors.get("community_density", 0.4) * 0.2
            + min(platform_factors.get("emotion_multiplier", 1.0) / 2.0, 1.0) * 0.3
        )

        # 加权平均
        combined = agent_score * 0.4 + content_score * 0.3 + platform_score * 0.3
        return round(min(max(combined, 0.0), 1.0), 4)

    def _extract_field(self, persona: Dict, field_name: str, default: Any) -> Any:
        """从7层人格结构中提取字段，支持嵌套查找"""
        # 直接查找
        if field_name in persona:
            return persona[field_name]

        # 在嵌套的各层中查找
        for layer_key in ["L1_demographics", "L2_values", "L3_knowledge",
                          "L4_behavior", "L5_emotion", "L6_social", "L7_self"]:
            layer = persona.get(layer_key, {})
            if isinstance(layer, dict) and field_name in layer:
                return layer[field_name]

        return default

    def _calc_stance_intensity(self, persona: Dict) -> float:
        """从人格中推断立场强度 (0-1)"""
        # 从 L2_values.social_stances 推断
        social_stances = self._extract_field(persona, "social_stances", "")
        if isinstance(social_stances, list) and social_stances:
            # 立场条目越多，立场越鲜明
            return min(len(social_stances) / 5.0, 1.0)
        if isinstance(social_stances, str) and social_stances:
            # 有明确文字描述的立场
            return min(len(social_stances) / 100.0, 0.8)

        # 从 L4_behavior.interaction_preference 推断
        interaction_pref = self._extract_field(persona, "interaction_preference", "")
        intensity_map = {
            "潜水": 0.1,
            "偶尔评论": 0.3,
            "活跃评论": 0.6,
            "创作者": 0.8,
        }
        return intensity_map.get(interaction_pref, 0.3)

    def _calc_sentiment_intensity(self, content: str) -> float:
        """计算内容情感强度 (0-1)"""
        if not content:
            return 0.0

        # 情感强烈的关键词
        strong_words = [
            "震惊", "愤怒", "不可思议", "离谱", "恶心", "太好了", "感动",
            "崩溃", "绝了", "可怕", "恐怖", "兴奋", "激动", "泪目",
            "！", "？", "…", "!!", "??",
        ]
        strong_count = sum(1 for w in strong_words if w in content)
        # 标点符号加倍计算
        exclamation = content.count("！") + content.count("!")
        question = content.count("？") + content.count("?")

        intensity = min((strong_count * 0.15 + exclamation * 0.05 + question * 0.03), 1.0)
        return round(intensity, 3)

    def _calc_controversy(self, content: str, reactions: List[Dict]) -> float:
        """计算内容争议性 (0-1)"""
        if not content:
            return 0.0

        # 争议性关键词
        controversy_words = [
            "但是", "然而", "争议", "分歧", "两面", "反转", "辩论",
            "不同意见", "质疑", "反对", "凭什么", "凭什么", "凭什么",
        ]
        controversy_count = sum(1 for w in controversy_words if w in content)
        content_controversy = min(controversy_count * 0.2, 0.6)

        # 如果有反应数据，看反应的分歧度
        reaction_controversy = 0.0
        if reactions:
            likes = sum(1 for r in reactions if r.get("action_type") == "like")
            dislikes = sum(1 for r in reactions if r.get("action_type") in ("dislike", "flag"))
            total = likes + dislikes
            if total > 0:
                # 均匀分布时最争议 (0.5 each)
                like_ratio = likes / total
                reaction_controversy = 1.0 - abs(like_ratio - 0.5) * 2  # 0~1

        return round(max(content_controversy, reaction_controversy), 3)

    def _calc_resonance(self, content: str, reactions: List[Dict]) -> float:
        """计算内容共鸣度 (0-1)"""
        if not content:
            return 0.0

        # 共鸣性关键词
        resonance_words = [
            "我也是", "感同身受", "太真实了", "说到心坎", "同感",
            "必须转", "顶", "收藏", "分享", "共勉",
        ]
        resonance_count = sum(1 for w in resonance_words if w in content)
        content_resonance = min(resonance_count * 0.2, 0.6)

        # 基于反应数据的共鸣度
        reaction_resonance = 0.0
        if reactions:
            share_count = sum(1 for r in reactions if r.get("action_type") in ("share", "repost"))
            total = len(reactions)
            if total > 0:
                reaction_resonance = min(share_count / total * 2, 0.6)

        return round(max(content_resonance, reaction_resonance), 3)
