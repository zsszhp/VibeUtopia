"""Guardian应急干预 — 检测异常行为并通过intervention通道干预

替换engine.py中的空实现，提供真实的异常检测和干预能力。
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..message_bus import CHANNEL_INTERVENTION

logger = logging.getLogger(__name__)


@dataclass
class InterventionAction:
    """干预行动"""
    type: str                     # silence/correct/force_stop/warn
    target_agent_id: str          # 目标Agent
    action: str                   # 具体行动描述
    reason: str                   # 干预原因
    severity: str                 # low/medium/high
    tick: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "target_agent_id": self.target_agent_id,
            "action": self.action,
            "reason": self.reason,
            "severity": self.severity,
            "tick": self.tick,
        }


class GuardianMonitor:
    """Guardian应急干预"""

    ANOMALY_RULES = [
        ("repeat_post", "Agent重复发布相同内容超过3次"),
        ("extreme_emotion", "Agent对无关话题表现出极端情绪"),
        ("contradictory_stance", "Agent产生自相矛盾的立场声明"),
        ("behavior_mismatch", "Agent行为与其人格Profile严重不符"),
        ("runaway_propagation", "传播动能超过安全阈值"),
    ]

    def __init__(self):
        self._agent_recent_posts: Dict[str, List[str]] = defaultdict(list)
        self._agent_stances: Dict[str, List[float]] = defaultdict(list)
        self._intervention_log: List[InterventionAction] = []
        self._kinetic_threshold: float = 8.0  # 传播动能安全阈值

    async def check_anomalies(self, engine: Any) -> List[InterventionAction]:
        """检测异常并决定干预

        Args:
            engine: SimulationEngine 实例

        Returns:
            需要执行的干预列表
        """
        interventions = []
        tick = engine.current_tick

        # 获取最近tick的行为数据
        if not hasattr(engine, "tick_results") or not engine.tick_results:
            return interventions

        latest_tick = engine.tick_results[-1]
        actions = []
        if hasattr(latest_tick, "actions"):
            actions = latest_tick.actions
        elif isinstance(latest_tick, dict):
            actions = latest_tick.get("actions", [])

        # 规则1: 重复发帖检测
        repeat_interventions = self._check_repeat_post(actions, tick, engine)
        interventions.extend(repeat_interventions)

        # 规则2: 矛盾立场检测
        stance_interventions = self._check_contradictory_stance(actions, tick, engine)
        interventions.extend(stance_interventions)

        # 规则3: 传播动能超限
        spread_model = getattr(engine, "spread_model", None)
        if spread_model and spread_model.kinetic_history:
            latest_kinetic = spread_model.kinetic_history[-1]["kinetic"]
            if latest_kinetic > self._kinetic_threshold:
                interventions.append(InterventionAction(
                    type="warn",
                    target_agent_id="system",
                    action="propagation_throttle",
                    reason=f"传播动能{latest_kinetic:.1f}超过安全阈值{self._kinetic_threshold}",
                    severity="high",
                    tick=tick,
                ))

        # 规则4: Agent异常活跃（已在Watcher中检测，Guardian负责干预）
        action_counter = Counter()
        for action in actions:
            if isinstance(action, dict):
                aid = action.get("agent_id", "")
            else:
                aid = getattr(action, "agent_id", "")
            if aid:
                action_counter[aid] += 1

        for aid, count in action_counter.items():
            if count > 15:
                interventions.append(InterventionAction(
                    type="correct",
                    target_agent_id=aid,
                    action="rate_limit",
                    reason=f"Agent单tick行为{count}次，执行限流",
                    severity="medium",
                    tick=tick,
                ))

        return interventions

    async def execute_intervention(
        self, engine: Any, intervention: InterventionAction
    ) -> bool:
        """通过intervention通道执行干预

        Args:
            engine: SimulationEngine 实例
            intervention: 干预行动

        Returns:
            是否成功执行
        """
        try:
            message_bus = getattr(engine, "message_bus", None)
            if message_bus:
                await message_bus.publish(
                    CHANNEL_INTERVENTION,
                    {
                        "type": intervention.type,
                        "target_agent_id": intervention.target_agent_id,
                        "action": intervention.action,
                        "reason": intervention.reason,
                        "severity": intervention.severity,
                        "tick": intervention.tick,
                    },
                )

            # 记录干预日志
            self._intervention_log.append(intervention)
            logger.info(
                "Guardian干预: %s -> Agent %s, 原因: %s",
                intervention.type,
                intervention.target_agent_id[:8] if intervention.target_agent_id else "system",
                intervention.reason,
            )
            return True

        except Exception as e:
            logger.error("Guardian干预执行失败: %s", e)
            return False

    def _check_repeat_post(
        self, actions: List[Any], tick: int, engine: Any
    ) -> List[InterventionAction]:
        """检查重复发帖"""
        interventions = []
        for action in actions:
            if isinstance(action, dict):
                aid = action.get("agent_id", "")
                content = action.get("content", "")
                action_type = action.get("action_type", "")
            else:
                aid = getattr(action, "agent_id", "")
                content = getattr(action, "content", "")
                action_type = getattr(action, "action_type", "")

            if action_type in ("post", "comment") and content:
                self._agent_recent_posts[aid].append(content)
                # 只保留最近5条
                if len(self._agent_recent_posts[aid]) > 5:
                    self._agent_recent_posts[aid] = self._agent_recent_posts[aid][-5:]

                # 检查重复
                recent = self._agent_recent_posts[aid]
                if len(recent) >= 3:
                    # 最近3条内容相同
                    if recent[-1] == recent[-2] == recent[-3]:
                        interventions.append(InterventionAction(
                            type="correct",
                            target_agent_id=aid,
                            action="force_diversify",
                            reason="Agent重复发布相同内容3次以上",
                            severity="medium",
                            tick=tick,
                        ))

        return interventions

    def _check_contradictory_stance(
        self, actions: List[Any], tick: int, engine: Any
    ) -> List[InterventionAction]:
        """检查矛盾立场"""
        interventions = []

        for action in actions:
            if isinstance(action, dict):
                aid = action.get("agent_id", "")
                content = action.get("content", "")
            else:
                aid = getattr(action, "agent_id", "")
                content = getattr(action, "content", "")

            if not content:
                continue

            # 简化立场推断
            stance = self._infer_simple_stance(content)
            self._agent_stances[aid].append(stance)
            if len(self._agent_stances[aid]) > 10:
                self._agent_stances[aid] = self._agent_stances[aid][-10:]

            # 检查矛盾：最近5条中立场的方差
            recent_stances = self._agent_stances[aid][-5:]
            if len(recent_stances) >= 3:
                mean = sum(recent_stances) / len(recent_stances)
                variance = sum((s - mean) ** 2 for s in recent_stances) / len(recent_stances)
                # 方差大 + 均值接近0 = 矛盾（在正负之间摇摆）
                if variance > 0.5 and abs(mean) < 0.2:
                    interventions.append(InterventionAction(
                        type="warn",
                        target_agent_id=aid,
                        action="stance_correction",
                        reason="Agent立场自相矛盾，注入纠偏信号",
                        severity="low",
                        tick=tick,
                    ))

        return interventions

    def _infer_simple_stance(self, text: str) -> float:
        """简单立场推断"""
        positive_keywords = ["支持", "赞同", "好", "棒", "对", "喜欢"]
        negative_keywords = ["反对", "差", "错", "离谱", "过分", "不满"]

        pos = sum(1 for kw in positive_keywords if kw in text)
        neg = sum(1 for kw in negative_keywords if kw in text)

        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    def get_intervention_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取干预日志"""
        return [i.to_dict() for i in self._intervention_log[-limit:]]

    def clear_state(self):
        """清除追踪状态（新仿真开始时调用）"""
        self._agent_recent_posts.clear()
        self._agent_stances.clear()
        self._intervention_log.clear()
