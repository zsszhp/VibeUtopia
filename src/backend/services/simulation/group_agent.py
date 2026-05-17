"""GA-S3 Group Agent 机制 — 一个 GroupAgent 代表 10-100 个相似个体

通过统计特征（年龄分布、立场分布、活跃度分布）描述群体，
用蒙特卡洛采样生成群组反应，支持与 A/B/C-tier Agent 相同的感知-思考-行动接口。
"""

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.services.simulation.models import PlatformAction, ActionType, AgentTier

logger = logging.getLogger(__name__)


@dataclass
class DistributionSpec:
    """统计分布描述"""
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 1.0

    def sample(self) -> float:
        """从分布中采样一个值"""
        val = random.gauss(self.mean, self.std)
        return max(self.min_val, min(self.max_val, val))


@dataclass
class StanceDistribution:
    """立场分布：支持/反对/中立的比例"""
    support_ratio: float = 0.3
    oppose_ratio: float = 0.2
    neutral_ratio: float = 0.5

    def __post_init__(self):
        total = self.support_ratio + self.oppose_ratio + self.neutral_ratio
        if total > 0:
            self.support_ratio /= total
            self.oppose_ratio /= total
            self.neutral_ratio /= total

    def sample_stance(self) -> str:
        """采样一个立场"""
        r = random.random()
        if r < self.support_ratio:
            return "support"
        elif r < self.support_ratio + self.oppose_ratio:
            return "oppose"
        return "neutral"

    def sample_stance_value(self) -> float:
        """采样一个连续立场值 [-1, 1]"""
        stance = self.sample_stance()
        if stance == "support":
            return random.uniform(0.3, 1.0)
        elif stance == "oppose":
            return random.uniform(-1.0, -0.3)
        return random.uniform(-0.3, 0.3)


@dataclass
class GroupProfile:
    """群组统计特征"""
    age_distribution: DistributionSpec = field(default_factory=lambda: DistributionSpec(mean=28, std=8, min_val=15, max_val=65))
    stance_distribution: StanceDistribution = field(default_factory=StanceDistribution)
    activity_distribution: DistributionSpec = field(default_factory=lambda: DistributionSpec(mean=0.3, std=0.2, min_val=0.0, max_val=1.0))
    platform: str = "weibo"
    archetype: str = "普通用户"
    influence_level: str = "普通用户"


class GroupAgent:
    """群组Agent — 代表 10-100 个相似个体

    与 A/B/C-tier Agent 相同的感知-思考-行动接口，
    通过蒙特卡洛采样生成群组反应。
    """

    def __init__(
        self,
        group_id: str = "",
        group_size: int = 50,
        profile: Optional[GroupProfile] = None,
    ):
        self.group_id = group_id or f"group_{uuid.uuid4().hex[:8]}"
        self.group_size = max(10, min(100, group_size))
        self.profile = profile or GroupProfile()
        self.tier = AgentTier.C  # GroupAgent 默认为 C-tier 行为

        # 群组内个体缓存（惰性生成）
        self._individuals: Optional[List[Dict[str, Any]]] = None

        # 历史反应记录
        self._reaction_history: List[Dict[str, Any]] = []

    @classmethod
    def from_persona_list(cls, personas: List[Dict[str, Any]], group_id: str = "") -> "GroupAgent":
        """从一组人格数据创建 GroupAgent

        统计提取群组特征，自动计算分布参数。
        """
        if not personas:
            return cls(group_id=group_id)

        # 提取年龄分布
        ages = []
        stances = []
        activities = []
        platform = personas[0].get("platform", "weibo")
        archetype = personas[0].get("archetype", "普通用户")
        influence = personas[0].get("L6_social", {})
        if isinstance(influence, str):
            influence = {}
        influence_level = influence.get("influence_level", "普通用户") if isinstance(influence, dict) else "普通用户"

        for p in personas:
            l1 = p.get("L1_demographics", {})
            if isinstance(l1, dict):
                age = l1.get("age", 28)
                if isinstance(age, (int, float)):
                    ages.append(age)

            l3 = p.get("L3_values", {})
            if isinstance(l3, dict):
                lean = l3.get("political_lean", "中")
                stance_map = {"左": -0.5, "中": 0.0, "右": 0.5}
                stances.append(stance_map.get(lean, 0.0))

            l4 = p.get("L4_behavior", {})
            if isinstance(l4, dict):
                act = l4.get("interaction_preference", "偶尔评论")
                act_map = {"潜水": 0.05, "偶尔评论": 0.15, "活跃评论": 0.35, "创作者": 0.5}
                activities.append(act_map.get(act, 0.15))

        # 计算统计分布
        age_dist = DistributionSpec(mean=28, std=8, min_val=15, max_val=65)
        if ages:
            age_dist = DistributionSpec(
                mean=sum(ages) / len(ages),
                std=(sum((a - sum(ages) / len(ages)) ** 2 for a in ages) / len(ages)) ** 0.5 if len(ages) > 1 else 5,
                min_val=min(ages),
                max_val=max(ages),
            )

        # 计算立场分布
        stance_dist = StanceDistribution()
        if stances:
            support_count = sum(1 for s in stances if s > 0.3)
            oppose_count = sum(1 for s in stances if s < -0.3)
            neutral_count = len(stances) - support_count - oppose_count
            total = len(stances)
            stance_dist = StanceDistribution(
                support_ratio=support_count / total,
                oppose_ratio=oppose_count / total,
                neutral_ratio=neutral_count / total,
            )

        # 活跃度分布
        act_dist = DistributionSpec(mean=0.3, std=0.2, min_val=0.0, max_val=1.0)
        if activities:
            act_mean = sum(activities) / len(activities)
            act_std = (sum((a - act_mean) ** 2 for a in activities) / len(activities)) ** 0.5 if len(activities) > 1 else 0.1
            act_dist = DistributionSpec(mean=act_mean, std=act_std, min_val=0.0, max_val=1.0)

        profile = GroupProfile(
            age_distribution=age_dist,
            stance_distribution=stance_dist,
            activity_distribution=act_dist,
            platform=platform,
            archetype=archetype,
            influence_level=influence_level,
        )

        return cls(
            group_id=group_id or f"group_{uuid.uuid4().hex[:8]}",
            group_size=len(personas),
            profile=profile,
        )

    def generate_individuals(self) -> List[Dict[str, Any]]:
        """蒙特卡洛采样生成群组内个体"""
        if self._individuals is not None:
            return self._individuals

        individuals = []
        for i in range(self.group_size):
            age = int(self.profile.age_distribution.sample())
            stance_value = self.profile.stance_distribution.sample_stance_value()
            activity = self.profile.activity_distribution.sample()

            # 立场值转政治倾向
            if stance_value > 0.3:
                political_lean = "右"
            elif stance_value < -0.3:
                political_lean = "左"
            else:
                political_lean = "中"

            # 活跃度转交互偏好
            if activity < 0.1:
                interaction = "潜水"
            elif activity < 0.25:
                interaction = "偶尔评论"
            elif activity < 0.4:
                interaction = "活跃评论"
            else:
                interaction = "创作者"

            individual = {
                "persona_id": f"{self.group_id}_ind_{i}",
                "group_id": self.group_id,
                "platform": self.profile.platform,
                "archetype": self.profile.archetype,
                "L1_demographics": {"age": age, "gender": random.choice(["男", "女"])},
                "L2_personality": {"openness": random.random(), "conscientiousness": random.random()},
                "L3_values": {"political_lean": political_lean},
                "L4_behavior": {"active_hours": random.choice(["早晨", "午间", "晚间", "深夜"]), "interaction_preference": interaction},
                "L5_knowledge": {},
                "L6_social": {"influence_level": self.profile.influence_level},
                "L7_narrative": {"style": random.choice(["理性分析", "情绪表达", "幽默调侃"])},
                "_stance_value": stance_value,
                "_activity": activity,
            }
            individuals.append(individual)

        self._individuals = individuals
        return individuals

    async def perceive(self, platform_feed: List[Dict[str, Any]], time_slot: str = "晚间") -> Dict[str, Any]:
        """感知阶段 — 分析平台内容，提取群组关注点"""
        if not platform_feed:
            return {"attention_level": 0.0, "hot_topics": [], "group_sentiment": "neutral"}

        # 计算群组对内容的关注程度
        attention_scores = []
        for post in platform_feed:
            content = post.get("content", "")
            post_sentiment = post.get("sentiment", "neutral")

            # 基于群组立场计算关注度
            stance_alignment = 0.0
            if post_sentiment == "positive":
                stance_alignment = self.profile.stance_distribution.support_ratio
            elif post_sentiment == "negative":
                stance_alignment = self.profile.stance_distribution.oppose_ratio
            else:
                stance_alignment = self.profile.stance_distribution.neutral_ratio

            # 活跃度加权
            attention = stance_alignment * self.profile.activity_distribution.mean
            attention_scores.append(attention)

        avg_attention = sum(attention_scores) / len(attention_scores) if attention_scores else 0.0

        # 群组整体情感
        if self.profile.stance_distribution.support_ratio > 0.5:
            group_sentiment = "positive"
        elif self.profile.stance_distribution.oppose_ratio > 0.5:
            group_sentiment = "negative"
        else:
            group_sentiment = "neutral"

        return {
            "attention_level": round(avg_attention, 3),
            "hot_topics": platform_feed[:3],
            "group_sentiment": group_sentiment,
            "feed_count": len(platform_feed),
        }

    async def think(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """思考阶段 — 基于群组统计特征，用概率模型生成群体反应决策"""
        attention = perception.get("attention_level", 0.0)
        group_sentiment = perception.get("group_sentiment", "neutral")

        # 采样每个个体的反应
        reaction_counts = {"post": 0, "comment": 0, "like": 0, "share": 0, "view": 0, "ignore": 0}
        stance_counts = {"support": 0, "oppose": 0, "neutral": 0}

        individuals = self.generate_individuals()
        for ind in individuals:
            activity = ind.get("_activity", 0.15)
            stance = ind.get("_stance_value", 0.0)

            # 是否关注（基于注意力和活跃度）
            engage_prob = attention * activity * 2
            if random.random() > engage_prob:
                reaction_counts["ignore"] += 1
                continue

            # 浏览是最基础的行为
            reaction_counts["view"] += 1

            # 进一步互动概率
            if random.random() < activity * 0.6:
                # 决定行为类型
                r = random.random()
                if r < 0.3:
                    reaction_counts["like"] += 1
                elif r < 0.5:
                    reaction_counts["comment"] += 1
                elif r < 0.6:
                    reaction_counts["share"] += 1
                elif r < 0.65:
                    reaction_counts["post"] += 1

            # 立场统计
            if stance > 0.3:
                stance_counts["support"] += 1
            elif stance < -0.3:
                stance_counts["oppose"] += 1
            else:
                stance_counts["neutral"] += 1

        return {
            "reaction_counts": reaction_counts,
            "stance_counts": stance_counts,
            "group_sentiment": group_sentiment,
            "engagement_rate": round(
                (self.group_size - reaction_counts["ignore"]) / self.group_size, 3
            ),
        }

    async def act(self, thought: Dict[str, Any], platform_feed: List[Dict[str, Any]]) -> List[PlatformAction]:
        """行动阶段 — 将群组反应转化为平台行为"""
        actions = []
        reaction_counts = thought.get("reaction_counts", {})
        stance_counts = thought.get("stance_counts", {})
        group_sentiment = thought.get("group_sentiment", "neutral")

        # 生成行为（每个类型生成代表性数量，而非逐个体）
        # 浏览行为
        view_count = reaction_counts.get("view", 0)
        for _ in range(min(view_count, 5)):  # 采样代表
            if platform_feed:
                target = random.choice(platform_feed)
                actions.append(PlatformAction(
                    agent_id=self.group_id,
                    platform=self.profile.platform,
                    action_type=ActionType.VIEW,
                    content="",
                    target_id=target.get("post_id", ""),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"group_size": self.group_size, "representative_count": view_count},
                ))

        # 点赞行为
        like_count = reaction_counts.get("like", 0)
        for _ in range(min(like_count, 3)):
            if platform_feed:
                target = random.choice(platform_feed)
                actions.append(PlatformAction(
                    agent_id=self.group_id,
                    platform=self.profile.platform,
                    action_type=ActionType.LIKE,
                    content="",
                    target_id=target.get("post_id", ""),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"group_size": self.group_size, "representative_count": like_count},
                ))

        # 评论行为
        comment_count = reaction_counts.get("comment", 0)
        for _ in range(min(comment_count, 3)):
            if platform_feed:
                target = random.choice(platform_feed)
                comment = self._generate_group_comment(group_sentiment, stance_counts)
                actions.append(PlatformAction(
                    agent_id=self.group_id,
                    platform=self.profile.platform,
                    action_type=ActionType.COMMENT,
                    content=comment,
                    target_id=target.get("post_id", ""),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"group_size": self.group_size, "representative_count": comment_count},
                ))

        # 转发行为
        share_count = reaction_counts.get("share", 0)
        for _ in range(min(share_count, 2)):
            if platform_feed:
                target = random.choice(platform_feed)
                actions.append(PlatformAction(
                    agent_id=self.group_id,
                    platform=self.profile.platform,
                    action_type=ActionType.SHARE,
                    content="",
                    target_id=target.get("post_id", ""),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"group_size": self.group_size, "representative_count": share_count},
                ))

        # 发帖行为
        post_count = reaction_counts.get("post", 0)
        for _ in range(min(post_count, 2)):
            post_content = self._generate_group_post(group_sentiment)
            actions.append(PlatformAction(
                agent_id=self.group_id,
                platform=self.profile.platform,
                action_type=ActionType.POST,
                content=post_content,
                target_id="",
                timestamp=datetime.now(timezone.utc),
                metadata={"group_size": self.group_size, "representative_count": post_count},
            ))

        # 记录反应历史
        self._reaction_history.append({
            "tick": len(self._reaction_history),
            "reaction_counts": reaction_counts,
            "stance_counts": stance_counts,
            "action_count": len(actions),
        })

        return actions

    async def perceive_think_act(self, platform_feed: List[Dict[str, Any]], time_slot: str = "晚间") -> List[PlatformAction]:
        """完整的感知-思考-行动循环"""
        perception = await self.perceive(platform_feed, time_slot)
        thought = await self.think(perception)
        actions = await self.act(thought, platform_feed)
        return actions

    def _generate_group_comment(self, group_sentiment: str, stance_counts: Dict[str, int]) -> str:
        """基于群组立场生成代表性评论"""
        templates = {
            "positive": [
                "支持这个观点，说得太对了",
                "终于有人把这事说清楚了",
                "完全同意，这才是正道",
                "大家都是这么想的",
                "理性看待，这个立场站得住",
            ],
            "negative": [
                "完全不同意这种说法",
                "这观点太偏激了",
                "别被带节奏了，大家冷静想想",
                "这种言论才是问题所在",
                "强烈反对，毫无道理",
            ],
            "neutral": [
                "了解一下情况再说",
                "各有各的道理",
                "让子弹飞一会吧",
                "理性讨论，别急着站队",
                "关注后续发展",
            ],
        }

        options = templates.get(group_sentiment, templates["neutral"])
        return random.choice(options)

    def _generate_group_post(self, group_sentiment: str) -> str:
        """基于群组立场生成代表性发帖"""
        templates = {
            "positive": [
                "关于这个话题，我们群体有话要说：整体上我们是支持的",
                "从我们这个群体的角度看，这件事的方向是对的",
            ],
            "negative": [
                "作为利益相关方，我们群体对此表示强烈反对",
                "这件事从我们群体的角度看，存在很大问题",
            ],
            "neutral": [
                "关于这个话题，我们群体还在观望中",
                "这件事比较复杂，我们群体内部也有不同看法",
            ],
        }

        options = templates.get(group_sentiment, templates["neutral"])
        return random.choice(options)

    def get_stats(self) -> Dict[str, Any]:
        """获取群组统计信息"""
        return {
            "group_id": self.group_id,
            "group_size": self.group_size,
            "platform": self.profile.platform,
            "archetype": self.profile.archetype,
            "age_mean": round(self.profile.age_distribution.mean, 1),
            "age_std": round(self.profile.age_distribution.std, 1),
            "stance_support": round(self.profile.stance_distribution.support_ratio, 3),
            "stance_oppose": round(self.profile.stance_distribution.oppose_ratio, 3),
            "stance_neutral": round(self.profile.stance_distribution.neutral_ratio, 3),
            "activity_mean": round(self.profile.activity_distribution.mean, 3),
            "reaction_history_count": len(self._reaction_history),
        }

    def reset_individuals(self):
        """重置个体缓存（下次访问时重新采样）"""
        self._individuals = None
