"""平台权重体系管理器 — T2.1

P0核心平台(微博/B站/小红书/抖音/知乎)权重1.0，P1/P2平台权重递减。
不同平台的结果按权重影响总风险分，确保P0平台评估结果在总分中占比≥70%。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PlatformTier(str, Enum):
    P0 = "P0"  # 核心平台，权重1.0
    P1 = "P1"  # 次要平台，权重0.7
    P2 = "P2"  # 边缘平台，权重0.4


@dataclass
class PlatformWeight:
    """平台权重配置"""
    platform: str            # 平台标识
    platform_name: str       # 平台中文名
    tier: PlatformTier       # 平台层级
    weight: float            # 权重值 (0-1)
    description: str         # 权重说明


# P0核心平台 (5个) - 权重2.0
P0_PLATFORMS = {
    "weibo": PlatformWeight(
        platform="weibo", platform_name="微博",
        tier=PlatformTier.P0, weight=2.0,
        description="舆论风向标，热点发酵第一阵地"
    ),
    "bilibili": PlatformWeight(
        platform="bilibili", platform_name="B站",
        tier=PlatformTier.P0, weight=2.0,
        description="Z世代聚集地，弹幕文化深度互动"
    ),
    "xiaohongshu": PlatformWeight(
        platform="xiaohongshu", platform_name="小红书",
        tier=PlatformTier.P0, weight=2.0,
        description="消费决策+生活方式，女性用户主导"
    ),
    "douyin": PlatformWeight(
        platform="douyin", platform_name="抖音",
        tier=PlatformTier.P0, weight=2.0,
        description="最大短视频平台，下沉市场覆盖广"
    ),
    "zhihu": PlatformWeight(
        platform="zhihu", platform_name="知乎",
        tier=PlatformTier.P0, weight=2.0,
        description="高知社区，理性讨论与深度分析"
    ),
}

# P1次要平台 (6个) - 权重0.5
P1_PLATFORMS = {
    "kuaishou": PlatformWeight(
        platform="kuaishou", platform_name="快手",
        tier=PlatformTier.P1, weight=0.5,
        description="下沉市场短视频，老铁文化"
    ),
    "wechat_channels": PlatformWeight(
        platform="wechat_channels", platform_name="微信视频号",
        tier=PlatformTier.P1, weight=0.5,
        description="微信生态内短视频，熟人社交传播"
    ),
    "wechat_official": PlatformWeight(
        platform="wechat_official", platform_name="公众号",
        tier=PlatformTier.P1, weight=0.5,
        description="深度长文内容，专业领域影响力"
    ),
    "douban": PlatformWeight(
        platform="douban", platform_name="豆瓣",
        tier=PlatformTier.P1, weight=0.5,
        description="文艺青年社区，影视/书评分发酵地"
    ),
    "hupu": PlatformWeight(
        platform="hupu", platform_name="虎扑",
        tier=PlatformTier.P1, weight=0.5,
        description="男性用户为主，体育/直男话题"
    ),
    "toutiao": PlatformWeight(
        platform="toutiao", platform_name="今日头条",
        tier=PlatformTier.P1, weight=0.5,
        description="资讯聚合平台，算法推荐驱动"
    ),
}

# P2边缘平台 (4个) - 权重0.2
P2_PLATFORMS = {
    "tieba": PlatformWeight(
        platform="tieba", platform_name="贴吧",
        tier=PlatformTier.P2, weight=0.2,
        description="兴趣社区，垂直话题讨论"
    ),
    "taptap": PlatformWeight(
        platform="taptap", platform_name="TapTap",
        tier=PlatformTier.P2, weight=0.2,
        description="游戏玩家社区，游戏相关话题"
    ),
    "weibo_super_topic": PlatformWeight(
        platform="weibo_super_topic", platform_name="微博超话",
        tier=PlatformTier.P2, weight=0.2,
        description="饭圈文化重镇，粉丝聚集地"
    ),
    "bilibili_dynamic": PlatformWeight(
        platform="bilibili_dynamic", platform_name="B站动态",
        tier=PlatformTier.P2, weight=0.2,
        description="UP主粉丝互动区"
    ),
}

# 全部平台权重映射
ALL_PLATFORM_WEIGHTS: Dict[str, PlatformWeight] = {
    **P0_PLATFORMS,
    **P1_PLATFORMS,
    **P2_PLATFORMS,
}


class PlatformWeightManager:
    """平台权重管理器

    职责:
    1. 管理各平台权重配置
    2. 计算加权总分
    3. 验证P0平台占比≥70%
    4. 支持动态调整权重
    """

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """初始化权重管理器

        Args:
            custom_weights: 自定义权重覆盖 {platform: weight}
        """
        self.weights: Dict[str, PlatformWeight] = {
            k: v for k, v in ALL_PLATFORM_WEIGHTS.items()
        }
        if custom_weights:
            for platform, weight in custom_weights.items():
                if platform in self.weights:
                    pw = self.weights[platform]
                    self.weights[platform] = PlatformWeight(
                        platform=pw.platform,
                        platform_name=pw.platform_name,
                        tier=pw.tier,
                        weight=weight,
                        description=pw.description,
                    )

    def get_weight(self, platform: str) -> float:
        """获取平台权重"""
        if platform in self.weights:
            return self.weights[platform].weight
        return 0.5  # 未知平台默认权重

    def get_tier(self, platform: str) -> PlatformTier:
        """获取平台层级"""
        if platform in self.weights:
            return self.weights[platform].tier
        return PlatformTier.P2

    def calculate_weighted_score(
        self,
        platform_scores: Dict[str, float],
    ) -> float:
        """计算加权总分

        Args:
            platform_scores: {platform: score} 各平台原始评分

        Returns:
            加权后的总分 (0-100)
        """
        if not platform_scores:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for platform, score in platform_scores.items():
            weight = self.get_weight(platform)
            weighted_sum += score * weight
            weight_total += weight

        if weight_total == 0:
            return 0.0

        return round(weighted_sum / weight_total, 2)

    def calculate_p0_impact_ratio(
        self,
        platform_scores: Dict[str, float],
    ) -> float:
        """计算P0平台在总分中的影响占比

        Returns:
            P0平台加权分占总加权分的比例 (0-1)
        """
        if not platform_scores:
            return 0.0

        p0_weighted = 0.0
        total_weighted = 0.0

        for platform, score in platform_scores.items():
            weight = self.get_weight(platform)
            weighted = score * weight
            total_weighted += weighted
            if self.get_tier(platform) == PlatformTier.P0:
                p0_weighted += weighted

        if total_weighted == 0:
            return 0.0

        return round(p0_weighted / total_weighted, 4)

    def verify_p0_threshold(
        self,
        platform_scores: Dict[str, float],
        threshold: float = 0.7,
    ) -> Dict[str, object]:
        """验证P0平台影响占比是否达到阈值

        Args:
            platform_scores: 各平台评分
            threshold: P0占比阈值，默认0.7 (70%)

        Returns:
            验证结果dict
        """
        p0_ratio = self.calculate_p0_impact_ratio(platform_scores)
        passed = p0_ratio >= threshold

        p0_platforms = [
            p for p in platform_scores
            if self.get_tier(p) == PlatformTier.P0
        ]
        non_p0_platforms = [
            p for p in platform_scores
            if self.get_tier(p) != PlatformTier.P0
        ]

        return {
            "passed": passed,
            "p0_ratio": p0_ratio,
            "threshold": threshold,
            "p0_platforms": p0_platforms,
            "non_p0_platforms": non_p0_platforms,
            "p0_weighted_scores": {
                p: platform_scores[p] * self.get_weight(p)
                for p in p0_platforms
            },
        }

    def get_platform_summary(self) -> List[Dict[str, object]]:
        """获取全部平台权重摘要"""
        return [
            {
                "platform": pw.platform,
                "platform_name": pw.platform_name,
                "tier": pw.tier.value,
                "weight": pw.weight,
                "description": pw.description,
            }
            for pw in self.weights.values()
        ]

    def adjust_weight(self, platform: str, new_weight: float) -> bool:
        """动态调整单个平台权重

        Args:
            platform: 平台标识
            new_weight: 新权重值 (0-1)

        Returns:
            是否调整成功
        """
        if platform not in self.weights:
            return False
        if not (0.0 <= new_weight <= 1.0):
            return False

        pw = self.weights[platform]
        self.weights[platform] = PlatformWeight(
            platform=pw.platform,
            platform_name=pw.platform_name,
            tier=pw.tier,
            weight=new_weight,
            description=pw.description,
        )
        return True

    def get_weights_by_tier(self) -> Dict[str, List[Dict]]:
        """按层级分组返回平台权重"""
        result = {"P0": [], "P1": [], "P2": []}
        for pw in self.weights.values():
            result[pw.tier.value].append({
                "platform": pw.platform,
                "platform_name": pw.platform_name,
                "weight": pw.weight,
            })
        return result
