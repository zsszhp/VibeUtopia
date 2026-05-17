"""5阶段传播模型 — 种子注入→初级传播→社群扩散→立场分化→主流化/消退"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .propagation_tree import PropagationTree
from .polarization import PolarizationCalculator, calc_polarization_index, extract_stance_values
from .influence_quantifier import InfluenceQuantifier


class SpreadStage(str, Enum):
    """传播阶段枚举"""
    SEED = "seed"                    # 种子注入
    PRIMARY = "primary"              # 初级传播
    COMMUNITY = "community"          # 社群扩散
    POLARIZATION = "polarization"    # 立场分化
    MAINSTREAM = "mainstream"        # 主流化
    FADING = "fading"                # 消退


# 阶段中文标签
STAGE_LABELS = {
    SpreadStage.SEED: "种子注入",
    SpreadStage.PRIMARY: "初级传播",
    SpreadStage.COMMUNITY: "社群扩散",
    SpreadStage.POLARIZATION: "立场分化",
    SpreadStage.MAINSTREAM: "主流化",
    SpreadStage.FADING: "消退",
}

# 阶段描述
STAGE_DESCRIPTIONS = {
    SpreadStage.SEED: "种子事件刚注入，少数大V/活跃用户率先反应",
    SpreadStage.PRIMARY: "高影响力Agent率先反应，立场鲜明的内容更易传播",
    SpreadStage.COMMUNITY: "通过关注链/超话/兴趣圈传播，各圈层形成主流观点",
    SpreadStage.POLARIZATION: "评论区出现对立观点，中立方被迫选边，极化趋势加强",
    SpreadStage.MAINSTREAM: "上热搜→大众参与→主流媒体关注→官方回应",
    SpreadStage.FADING: "争议降温，新热点替代，舆论逐渐消退",
}


class SpreadModel:
    """5阶段传播模型

    整合传播树、极化指数、影响因素量化为统一接口，
    跟踪舆论从种子到消退的完整生命周期。
    """

    def __init__(self):
        self.propagation_tree = PropagationTree()
        self.polarization_calc = PolarizationCalculator()
        self.influence_quantifier = InfluenceQuantifier()

        # 当前状态
        self.current_stage: SpreadStage = SpreadStage.SEED
        self.prev_kinetic: float = 0.0
        self.kinetic_history: List[Dict[str, Any]] = []
        self.stage_history: List[Dict[str, Any]] = []

        # 连续低动能计数（用于判断消退）
        self._declining_count: int = 0

    def determine_stage(
        self,
        reach_count: int,
        polarization_index: float,
        propagation_kinetic: float,
        depth: int,
    ) -> SpreadStage:
        """根据当前态势判断传播阶段

        判断逻辑:
        - 种子注入: reach_count < 10
        - 初级传播: reach_count 10-100, 极化 < 0.3
        - 社群扩散: reach_count 100-500, 深度 >= 2
        - 立场分化: 极化 >= 0.4 或 出现2+对立阵营
        - 主流化: 传播动能 > 3.0 且 reach_count > 500
        - 消退: 传播动能连续3tick下降
        """
        # 消退优先判断（一旦消退不轻易恢复）
        if self._declining_count >= 3:
            return SpreadStage.FADING

        if reach_count < 10:
            return SpreadStage.SEED

        if reach_count < 100:
            if polarization_index >= 0.4:
                return SpreadStage.POLARIZATION
            return SpreadStage.PRIMARY

        # reach_count >= 100
        if polarization_index >= 0.4:
            return SpreadStage.POLARIZATION

        if reach_count >= 500 and propagation_kinetic > 3.0:
            return SpreadStage.MAINSTREAM

        if depth >= 2 or reach_count >= 100:
            return SpreadStage.COMMUNITY

        return SpreadStage.PRIMARY

    def calc_propagation_kinetic(
        self,
        current_interactions: int,
        previous_interactions: int,
        sentiment_intensity: float,
    ) -> float:
        """传播动能 = 互动增速 × 情感强度

        Args:
            current_interactions: 当前tick互动量
            previous_interactions: 上一tick互动量
            sentiment_intensity: 情感强度 (0-1)

        Returns:
            传播动能 (0-10)
        """
        # 互动增速
        if previous_interactions <= 0:
            growth_rate = 1.0 if current_interactions > 0 else 0.0
        else:
            growth_rate = (current_interactions - previous_interactions) / previous_interactions
        growth_rate = min(max(growth_rate, 0.0), 10.0)

        # 情感强度钳制
        sentiment_intensity = min(max(sentiment_intensity, 0.0), 1.0)

        kinetic = growth_rate * sentiment_intensity
        return round(min(kinetic, 10.0), 3)

    def calc_sentiment_distribution(self, actions: List[Dict[str, Any]]) -> Dict[str, float]:
        """统计情感分布 (正/负/中性比例)

        Args:
            actions: PlatformAction dict 列表

        Returns:
            {"positive": float, "negative": float, "neutral": float}
        """
        if not actions:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        positive_keywords = ["支持", "赞同", "好", "棒", "对", "喜欢", "感动", "赞"]
        negative_keywords = ["反对", "差", "错", "离谱", "过分", "不满", "愤怒", "恶心"]

        counts = {"positive": 0, "negative": 0, "neutral": 0}

        for action in actions:
            content = action.get("content", "")
            action_type = action.get("action_type", "view")

            # 基于行为类型的基础判断
            if action_type in ("like", "share", "repost", "collect"):
                counts["positive"] += 2
            elif action_type in ("dislike", "flag"):
                counts["negative"] += 2
            else:
                # 基于内容关键词
                pos = sum(1 for kw in positive_keywords if kw in content)
                neg = sum(1 for kw in negative_keywords if kw in content)
                if pos > neg:
                    counts["positive"] += 1
                elif neg > pos:
                    counts["negative"] += 1
                else:
                    counts["neutral"] += 1

        total = sum(counts.values())
        if total == 0:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        return {
            "positive": round(counts["positive"] / total, 3),
            "negative": round(counts["negative"] / total, 3),
            "neutral": round(counts["neutral"] / total, 3),
        }

    def update(
        self,
        tick: int,
        actions: List[Dict[str, Any]],
        prev_interactions: int = 0,
    ) -> Dict[str, Any]:
        """每tick更新传播模型

        处理所有行为，更新传播树，计算各项指标，判断传播阶段。

        Args:
            tick: 当前tick
            actions: 本tick产生的所有 PlatformAction dict
            prev_interactions: 上tick互动总量

        Returns:
            传播快照 dict
        """
        # 1. 更新传播树
        new_edges = []
        for action in actions:
            edge = self.propagation_tree.add_action(action, tick)
            if edge:
                new_edges.append(edge)

        # 2. 计算情感分布
        sentiment_dist = self.calc_sentiment_distribution(actions)

        # 3. 计算极化指数
        stance_values = extract_stance_values(actions)
        polarization_index = calc_polarization_index(stance_values)

        # 4. 计算传播动能
        current_interactions = len([a for a in actions if a.get("action_type") not in ("view", "do_nothing")])
        avg_sentiment_intensity = (
            sentiment_dist["negative"] * 0.7
            + sentiment_dist["positive"] * 0.3
        )
        kinetic = self.calc_propagation_kinetic(
            current_interactions, prev_interactions, avg_sentiment_intensity
        )

        # 跟踪动能变化
        if kinetic < self.prev_kinetic:
            self._declining_count += 1
        else:
            self._declining_count = 0
        self.prev_kinetic = kinetic

        # 5. 获取传播树指标
        reach_count = self.propagation_tree.get_reach_count()
        depth = self.propagation_tree.get_depth()

        # 6. 判断传播阶段
        new_stage = self.determine_stage(reach_count, polarization_index, kinetic, depth)
        stage_changed = new_stage != self.current_stage
        self.current_stage = new_stage

        # 7. 关键影响者
        top_influencers = self.propagation_tree.get_influencer_ranking(5)

        # 8. 记录历史
        snapshot = {
            "tick": tick,
            "stage": new_stage.value,
            "stage_label": STAGE_LABELS.get(new_stage, ""),
            "stage_changed": stage_changed,
            "propagation_kinetic": kinetic,
            "polarization_index": polarization_index,
            "reach_count": reach_count,
            "depth": depth,
            "sentiment_distribution": sentiment_dist,
            "current_interactions": current_interactions,
            "new_edges": len(new_edges),
            "top_influencers": top_influencers,
        }

        self.kinetic_history.append({
            "tick": tick,
            "kinetic": kinetic,
            "interactions": current_interactions,
        })

        if stage_changed:
            self.stage_history.append({
                "tick": tick,
                "from_stage": self.current_stage.value if not stage_changed else "",
                "to_stage": new_stage.value,
                "to_stage_label": STAGE_LABELS.get(new_stage, ""),
            })

        # 更新极化历史
        from .polarization import detect_camps
        stance_data = [
            {"agent_id": a.get("agent_id", ""), "stance": s, "content": a.get("content", "")}
            for a, s in zip(actions, stance_values)
        ]
        camps = detect_camps(stance_data)
        self.polarization_calc.record(tick, polarization_index, stance_values, camps)

        return snapshot

    def get_summary(self) -> Dict[str, Any]:
        """获取传播模型完整摘要"""
        return {
            "current_stage": self.current_stage.value,
            "current_stage_label": STAGE_LABELS.get(self.current_stage, ""),
            "propagation_tree": self.propagation_tree.get_stats(),
            "polarization_trend": self.polarization_calc.get_trend(),
            "kinetic_history": self.kinetic_history[-20:],  # 最近20tick
            "stage_history": self.stage_history,
            "polarization_history": self.polarization_calc.get_history()[-20:],
        }
