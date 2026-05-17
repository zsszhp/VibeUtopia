"""Director调度决策 — 评估仿真状态，控制仿真节奏

替换engine.py中的_director_tick stub，提供真实的仿真调度能力。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..propagation.spread_model import SpreadStage, STAGE_LABELS
from .watcher import MonitorReport

logger = logging.getLogger(__name__)


@dataclass
class DirectorDecision:
    """Director调度决策"""
    speed_adjustment: float = 1.0      # 速度调整系数 (>1 加速, <1 减速)
    should_inject: bool = False         # 是否需要注入新事件
    injection_content: str = ""         # 注入内容描述
    injection_platform: str = ""        # 注入平台
    injection_as_role: str = ""         # 以何种角色注入 (大V/媒体/官方)
    should_end: bool = False            # 是否应结束仿真
    end_reason: str = ""                # 结束原因
    advice: str = ""                    # 调度建议

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speed_adjustment": self.speed_adjustment,
            "should_inject": self.should_inject,
            "injection_content": self.injection_content,
            "injection_platform": self.injection_platform,
            "injection_as_role": self.injection_as_role,
            "should_end": self.should_end,
            "end_reason": self.end_reason,
            "advice": self.advice,
        }


class DirectorController:
    """Director调度决策"""

    def __init__(self, max_ticks: int = 144, target_duration_hours: int = 24):
        self.max_ticks = max_ticks
        self.target_duration_hours = target_duration_hours
        self._inject_count: int = 0
        self._max_injects: int = 3  # 每次仿真最多注入3次
        self._stagnant_ticks: int = 0  # 连续停滞tick数
        self._decision_history: List[DirectorDecision] = []

    async def evaluate(
        self, engine: Any, monitor_report: Optional[MonitorReport] = None
    ) -> DirectorDecision:
        """评估仿真状态，决定下一步调度

        Args:
            engine: SimulationEngine 实例
            monitor_report: Watcher最新监控报告（可选）

        Returns:
            DirectorDecision
        """
        tick = engine.current_tick
        spread_model = getattr(engine, "spread_model", None)

        # 默认决策
        decision = DirectorDecision()

        # 1. 速度调整
        decision.speed_adjustment = self._adjust_speed(monitor_report, spread_model)

        # 2. 事件注入判断
        if self._should_inject_event(monitor_report, spread_model, tick):
            injection = self._plan_injection(monitor_report, engine)
            if injection:
                decision.should_inject = True
                decision.injection_content = injection["content"]
                decision.injection_platform = injection["platform"]
                decision.injection_as_role = injection["role"]

        # 3. 结束判断
        should_end, end_reason = self._should_end(engine, monitor_report, spread_model)
        decision.should_end = should_end
        decision.end_reason = end_reason

        # 4. 生成建议
        decision.advice = self._generate_advice(monitor_report, spread_model)

        self._decision_history.append(decision)
        return decision

    def _adjust_speed(
        self, monitor_report: Optional[MonitorReport], spread_model: Any
    ) -> float:
        """根据传播阶段调整仿真速度

        - 种子注入阶段: 正常速度
        - 初级传播/社群扩散: 加速（等待传播发展）
        - 立场分化: 减速（观察极化过程）
        - 主流化/消退: 加速（等待结束）
        """
        if not spread_model:
            return 1.0

        stage = spread_model.current_stage
        speed_map = {
            SpreadStage.SEED: 1.0,
            SpreadStage.PRIMARY: 1.5,
            SpreadStage.COMMUNITY: 1.2,
            SpreadStage.POLARIZATION: 0.8,  # 减速，仔细观察极化
            SpreadStage.MAINSTREAM: 1.5,
            SpreadStage.FADING: 2.0,  # 快速推过消退期
        }
        return speed_map.get(stage, 1.0)

    def _should_inject_event(
        self,
        monitor_report: Optional[MonitorReport],
        spread_model: Any,
        tick: int,
    ) -> bool:
        """判断是否需要注入新事件保持动态性

        注入条件:
        - 舆论趋于稳定（动能连续低）
        - 尚未达到注入次数上限
        - 不是种子注入阶段
        """
        if self._inject_count >= self._max_injects:
            return False

        if not spread_model:
            return False

        # 种子注入阶段不额外注入
        if spread_model.current_stage == SpreadStage.SEED:
            return False

        # 传播动能持续低 → 需要注入新事件激活讨论
        if spread_model.kinetic_history:
            recent = spread_model.kinetic_history[-5:]
            avg_kinetic = sum(h["kinetic"] for h in recent) / len(recent)
            if avg_kinetic < 0.3:
                self._stagnant_ticks += 1
                if self._stagnant_ticks >= 3:
                    return True
            else:
                self._stagnant_ticks = 0

        return False

    def _plan_injection(
        self, monitor_report: Optional[MonitorReport], engine: Any
    ) -> Optional[Dict[str, str]]:
        """规划注入事件

        Returns:
            {"content": str, "platform": str, "role": str} 或 None
        """
        self._inject_count += 1
        self._stagnant_ticks = 0

        # 从引擎获取话题
        topic = getattr(engine, "topic", "未知事件")

        # 基于当前态势决定注入策略
        injection_strategies = [
            {
                "content": f"某知名大V就「{topic}」发表新观点，引发新一轮讨论",
                "platform": "weibo",
                "role": "大V",
            },
            {
                "content": f"主流媒体发布关于「{topic}」的深度报道",
                "platform": "zhihu",
                "role": "媒体",
            },
            {
                "content": f"官方就「{topic}」发布声明",
                "platform": "weibo",
                "role": "官方",
            },
        ]

        # 轮流选择注入策略
        idx = (self._inject_count - 1) % len(injection_strategies)
        return injection_strategies[idx]

    def _should_end(
        self,
        engine: Any,
        monitor_report: Optional[MonitorReport],
        spread_model: Any,
    ) -> tuple:
        """判断仿真是否应结束

        结束条件:
        - 达到最大tick数
        - 舆论已稳定消退（动能连续10tick < 0.1）
        - 极化指数归零且无传播
        """
        tick = engine.current_tick

        # 达到最大tick
        if tick >= self.max_ticks:
            return True, f"达到最大仿真时长{self.max_ticks}tick"

        # 传播动能持续极低
        if spread_model and spread_model.kinetic_history:
            recent = spread_model.kinetic_history[-10:]
            if len(recent) >= 10:
                avg_kinetic = sum(h["kinetic"] for h in recent) / len(recent)
                if avg_kinetic < 0.05:
                    return True, "舆论已完全消退，仿真结束"

        # 已进入消退阶段且持续较久
        if spread_model and spread_model.current_stage == SpreadStage.FADING:
            if len(spread_model.kinetic_history) > 20:
                fading_ticks = sum(
                    1 for h in spread_model.stage_history
                    if h.get("to_stage") == "fading"
                )
                if tick > 50:  # 至少运行50tick再考虑结束
                    recent_kinetic = [h["kinetic"] for h in spread_model.kinetic_history[-5:]]
                    if recent_kinetic and all(k < 0.2 for k in recent_kinetic):
                        return True, "舆论消退阶段，传播动能持续低迷"

        return False, ""

    def _generate_advice(
        self,
        monitor_report: Optional[MonitorReport],
        spread_model: Any,
    ) -> str:
        """生成调度建议"""
        if not spread_model:
            return "仿真正常运行中"

        stage = spread_model.current_stage
        stage_label = STAGE_LABELS.get(stage, "未知")

        advice_map = {
            SpreadStage.SEED: "种子事件已注入，等待传播启动",
            SpreadStage.PRIMARY: "初级传播进行中，关注大V反应",
            SpreadStage.COMMUNITY: "社群扩散中，观察跨圈层传播",
            SpreadStage.POLARIZATION: "立场分化中，密切关注极化趋势",
            SpreadStage.MAINSTREAM: "舆论已主流化，关注官方和媒体反应",
            SpreadStage.FADING: "舆论消退中，仿真即将结束",
        }

        return advice_map.get(stage, f"当前阶段: {stage_label}")

    def get_decision_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取决策历史"""
        return [d.to_dict() for d in self._decision_history[-limit:]]

    def clear_state(self):
        """清除状态"""
        self._inject_count = 0
        self._stagnant_ticks = 0
        self._decision_history.clear()
