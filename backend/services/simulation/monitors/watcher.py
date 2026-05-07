"""Watcher实时监控 — 态势感知 + 异常检测

替换engine.py中的_watcher_tick stub，提供真实的舆论态势观察和异常检测能力。
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnomalyAlert:
    """异常告警"""
    type: str                     # anomaly type key
    severity: str                 # low / medium / high / critical
    description: str
    affected_agents: List[str] = field(default_factory=list)
    tick: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorReport:
    """监控报告"""
    # 情感分布
    sentiment_distribution: Dict[str, float] = field(default_factory=dict)
    # 热点话题
    trending_topics: List[str] = field(default_factory=list)
    # 关键影响者
    key_influencers: List[Dict[str, Any]] = field(default_factory=list)
    # 极化指数
    polarization_index: float = 0.0
    # 传播动能
    propagation_kinetic: float = 0.0
    # 传播阶段
    spread_stage: str = "seed"
    spread_stage_label: str = "种子注入"
    # 覆盖人数
    reach_count: int = 0
    # 传播深度
    depth: int = 0
    # 异常告警
    anomalies: List[AnomalyAlert] = field(default_factory=list)
    # tick
    tick: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentiment_distribution": self.sentiment_distribution,
            "trending_topics": self.trending_topics,
            "key_influencers": self.key_influencers,
            "polarization_index": self.polarization_index,
            "propagation_kinetic": self.propagation_kinetic,
            "spread_stage": self.spread_stage,
            "spread_stage_label": self.spread_stage_label,
            "reach_count": self.reach_count,
            "depth": self.depth,
            "anomalies": [
                {
                    "type": a.type,
                    "severity": a.severity,
                    "description": a.description,
                    "affected_agents": a.affected_agents,
                    "tick": a.tick,
                }
                for a in self.anomalies
            ],
            "tick": self.tick,
        }


class WatcherMonitor:
    """Watcher实时监控"""

    def __init__(self):
        self._prev_kinetic: float = 0.0
        self._prev_polarization: float = 0.0
        self._agent_action_counts: Dict[str, int] = defaultdict(int)
        self._prev_sentiment_negative: float = 0.0
        self._report_history: List[MonitorReport] = []

    async def observe(self, engine: Any) -> MonitorReport:
        """观察当前舆论态势

        Args:
            engine: SimulationEngine 实例

        Returns:
            MonitorReport
        """
        tick = engine.current_tick
        spread_model = getattr(engine, "spread_model", None)

        # 从传播模型获取核心指标
        if spread_model:
            summary = spread_model.get_summary()
            polarization_index = (
                spread_model.polarization_calc.get_history()[-1]["polarization_index"]
                if spread_model.polarization_calc.get_history()
                else 0.0
            )
            kinetic = (
                spread_model.kinetic_history[-1]["kinetic"]
                if spread_model.kinetic_history
                else 0.0
            )
            sentiment_dist = (
                spread_model.polarization_calc.get_history()[-1]
                if spread_model.polarization_calc.get_history()
                else {}
            )
            reach_count = spread_model.propagation_tree.get_reach_count()
            depth = spread_model.propagation_tree.get_depth()
            top_influencers = spread_model.propagation_tree.get_influencer_ranking(5)
        else:
            polarization_index = 0.0
            kinetic = 0.0
            sentiment_dist = {}
            reach_count = 0
            depth = 0
            top_influencers = []

        # 情感分布
        sentiment_distribution = self._calc_sentiment_distribution(engine)

        # 热点话题
        trending_topics = self._detect_trending(engine)

        # 关键影响者
        key_influencers = self._identify_influencers(engine, top_influencers)

        # 传播阶段
        current_stage = spread_model.current_stage if spread_model else None
        from ..propagation.spread_model import STAGE_LABELS
        stage_value = current_stage.value if current_stage else "seed"
        stage_label = STAGE_LABELS.get(current_stage, "种子注入") if current_stage else "种子注入"

        # 异常检测
        anomalies = self._detect_anomalies(
            engine, tick, kinetic, polarization_index, sentiment_distribution
        )

        report = MonitorReport(
            sentiment_distribution=sentiment_distribution,
            trending_topics=trending_topics,
            key_influencers=key_influencers,
            polarization_index=round(polarization_index, 4),
            propagation_kinetic=round(kinetic, 4),
            spread_stage=stage_value,
            spread_stage_label=stage_label,
            reach_count=reach_count,
            depth=depth,
            anomalies=anomalies,
            tick=tick,
        )

        # 更新状态追踪
        self._prev_kinetic = kinetic
        self._prev_polarization = polarization_index
        self._prev_sentiment_negative = sentiment_distribution.get("negative", 0.0)
        self._report_history.append(report)

        return report

    def _calc_sentiment_distribution(self, engine: Any) -> Dict[str, float]:
        """从仿真引擎计算情感分布"""
        if not hasattr(engine, "tick_results") or not engine.tick_results:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        # 统计最近一个tick的行为
        positive = 0
        negative = 0
        neutral = 0

        latest_tick = engine.tick_results[-1] if engine.tick_results else None
        if latest_tick and hasattr(latest_tick, "actions"):
            actions = latest_tick.actions
        elif latest_tick and isinstance(latest_tick, dict):
            actions = latest_tick.get("actions", [])
        else:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        positive_keywords = ["支持", "赞同", "好", "棒", "喜欢", "感动"]
        negative_keywords = ["反对", "差", "错", "离谱", "过分", "不满", "愤怒"]

        for action in actions:
            if isinstance(action, dict):
                action_type = action.get("action_type", "view")
                content = action.get("content", "")
            else:
                action_type = getattr(action, "action_type", "view")
                content = getattr(action, "content", "")

            if action_type in ("like", "share", "repost", "collect"):
                positive += 1
            elif action_type in ("dislike", "flag"):
                negative += 1
            elif action_type in ("comment", "post"):
                pos = sum(1 for kw in positive_keywords if kw in content)
                neg = sum(1 for kw in negative_keywords if kw in content)
                if pos > neg:
                    positive += 1
                elif neg > pos:
                    negative += 1
                else:
                    neutral += 1
            else:
                neutral += 1

        total = positive + negative + neutral
        if total == 0:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

        return {
            "positive": round(positive / total, 3),
            "negative": round(negative / total, 3),
            "neutral": round(neutral / total, 3),
        }

    def _detect_trending(self, engine: Any) -> List[str]:
        """热点话题检测"""
        # 从最近的行为中提取高频关键词
        if not hasattr(engine, "tick_results") or not engine.tick_results:
            return []

        topics = []
        latest_tick = engine.tick_results[-1] if engine.tick_results else None
        if not latest_tick:
            return []

        if hasattr(latest_tick, "actions"):
            actions = latest_tick.actions
        elif isinstance(latest_tick, dict):
            actions = latest_tick.get("actions", [])
        else:
            return []

        # 简化实现：收集高频分享/转发的内容摘要
        for action in actions:
            if isinstance(action, dict):
                if action.get("action_type") in ("share", "repost", "post") and action.get("content"):
                    content = action["content"][:50]
                    if content not in topics:
                        topics.append(content)
            elif hasattr(action, "action_type"):
                if action.action_type in ("share", "repost", "post") and getattr(action, "content", ""):
                    content = action.content[:50]
                    if content not in topics:
                        topics.append(content)

        return topics[:5]

    def _identify_influencers(
        self, engine: Any, top_influencers: List
    ) -> List[Dict[str, Any]]:
        """关键影响者识别"""
        result = []
        for item in top_influencers:
            if isinstance(item, tuple) and len(item) == 2:
                agent_id, count = item
                # 从引擎获取Agent信息
                agent = engine.agents.get(agent_id, {}) if hasattr(engine, "agents") else {}
                result.append({
                    "agent_id": agent_id,
                    "spread_count": count,
                    "platform": agent.get("platform", "unknown") if isinstance(agent, dict) else "unknown",
                    "influence_level": self._get_agent_influence(agent),
                })
        return result

    def _get_agent_influence(self, agent: Dict) -> str:
        """获取Agent影响力等级"""
        if not isinstance(agent, dict):
            return "普通用户"
        for key in ["influence_level", "L6_social"]:
            val = agent.get(key)
            if isinstance(val, dict):
                return val.get("influence_level", "普通用户")
            if isinstance(val, str):
                return val
        return "普通用户"

    def _detect_anomalies(
        self,
        engine: Any,
        tick: int,
        kinetic: float,
        polarization_index: float,
        sentiment_distribution: Dict[str, float],
    ) -> List[AnomalyAlert]:
        """异常检测"""
        anomalies = []

        # 1. 传播动能突变（1tick内增长>300%）
        if self._prev_kinetic > 0 and kinetic > self._prev_kinetic * 4:
            anomalies.append(AnomalyAlert(
                type="kinetic_surge",
                severity="high",
                description=f"传播动能突变: {self._prev_kinetic:.2f} → {kinetic:.2f} (增长{kinetic/max(self._prev_kinetic,0.01):.1f}倍)",
                tick=tick,
                details={"prev": self._prev_kinetic, "current": kinetic},
            ))

        # 2. 极化指数骤升（1tick内增长>0.3）
        if polarization_index - self._prev_polarization > 0.3:
            anomalies.append(AnomalyAlert(
                type="polarization_spike",
                severity="high",
                description=f"极化指数骤升: {self._prev_polarization:.3f} → {polarization_index:.3f}",
                tick=tick,
                details={"prev": self._prev_polarization, "current": polarization_index},
            ))

        # 3. 情感极端化（负面情感>80%）
        negative_ratio = sentiment_distribution.get("negative", 0.0)
        if negative_ratio > 0.8:
            anomalies.append(AnomalyAlert(
                type="extreme_sentiment",
                severity="medium",
                description=f"负面情感占比过高: {negative_ratio:.1%}",
                tick=tick,
                details={"negative_ratio": negative_ratio},
            ))

        # 4. 平台共振检测（3+平台同时有大量互动）
        if hasattr(engine, "platforms") and engine.platforms:
            active_platforms = []
            for platform_name, platform in engine.platforms.items():
                if hasattr(platform, "posts") and platform.posts:
                    if len(platform.posts) > 5:
                        active_platforms.append(platform_name)
            if len(active_platforms) >= 3:
                anomalies.append(AnomalyAlert(
                    type="platform_resonance",
                    severity="high",
                    description=f"多平台共振: {', '.join(active_platforms)}",
                    affected_agents=[],
                    tick=tick,
                    details={"platforms": active_platforms},
                ))

        # 5. 单Agent异常活跃检测
        if hasattr(engine, "tick_results") and engine.tick_results:
            latest = engine.tick_results[-1]
            actions = []
            if hasattr(latest, "actions"):
                actions = latest.actions
            elif isinstance(latest, dict):
                actions = latest.get("actions", [])

            action_counter = Counter()
            for action in actions:
                aid = action.get("agent_id", "") if isinstance(action, dict) else getattr(action, "agent_id", "")
                if aid:
                    action_counter[aid] += 1

            for aid, count in action_counter.items():
                if count > 20:
                    anomalies.append(AnomalyAlert(
                        type="agent_spam",
                        severity="medium",
                        description=f"Agent {aid[:8]}... 单tick行为{count}次，疑似异常",
                        affected_agents=[aid],
                        tick=tick,
                    ))

        return anomalies

    def get_report_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取监控报告历史"""
        return [r.to_dict() for r in self._report_history[-limit:]]
