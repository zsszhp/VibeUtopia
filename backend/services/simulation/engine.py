"""仿真主循环引擎 — Tick驱动的多Agent社交仿真（V2.5 集成传播动力学）"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from backend.services.simulation.models import PlatformAction, ActionType, AgentTier, SimulationTick
from backend.services.simulation.message_bus import MessageBus
from backend.services.simulation.time_model import TimeModel
from backend.services.simulation.rule_engine import RuleEngine
from backend.services.simulation.decision_engine import decide_actions
from backend.services.simulation.platforms.weibo import WeiboSimulator
from backend.services.simulation.platforms.bilibili import BilibiliSimulator
from backend.services.simulation.platforms.xiaohongshu import XiaohongshuSimulator
from backend.services.simulation.platforms.zhihu import ZhihuSimulator
from backend.services.simulation.platforms.douyin import DouyinSimulator

# V2.5 传播动力学模块
from backend.services.simulation.propagation.spread_model import SpreadModel, SpreadStage, STAGE_LABELS
from backend.services.simulation.monitors.watcher import WatcherMonitor, MonitorReport
from backend.services.simulation.monitors.guardian import GuardianMonitor, InterventionAction
from backend.services.simulation.monitors.director import DirectorController, DirectorDecision
from backend.services.simulation.replay.timeline import ReplayTimeline

logger = logging.getLogger(__name__)

PLATFORM_MAP = {
    "weibo": WeiboSimulator,
    "bilibili": BilibiliSimulator,
    "xiaohongshu": XiaohongshuSimulator,
    "zhihu": ZhihuSimulator,
    "douyin": DouyinSimulator,
}


class SimulationEngine:
    """仿真引擎（V2.5 集成传播动力学）"""

    def __init__(self, sim_id: str, topic: str, config: Dict = None):
        self.sim_id = sim_id
        self.topic = topic
        self.config = config or {}

        # 核心组件
        self.message_bus = MessageBus()
        self.time_model = TimeModel(
            start_hour=self.config.get("start_hour", 8),
            time_acceleration=self.config.get("time_acceleration", 60),
        )
        self.rule_engine = RuleEngine()

        # 平台实例
        self.platforms: Dict[str, Any] = {}
        for pname, cls in PLATFORM_MAP.items():
            self.platforms[pname] = cls()

        # Agent数据
        self.agents: Dict[str, Dict] = {}  # agent_id -> persona dict
        self.agent_tiers: Dict[str, str] = {}  # agent_id -> A/B/C
        self.agent_platform_map: Dict[str, str] = {}  # agent_id -> primary platform

        # 仿真状态
        self.status = "created"
        self.current_tick = 0
        self.max_ticks = self.config.get("max_ticks", 144)  # 默认仿真24小时(144 ticks × 10min)
        self.tick_results: List[SimulationTick] = []

        # 控制标志
        self._running = False
        self._paused = False

        # V2.5 传播动力学模块
        self.spread_model = SpreadModel()
        self.watcher = WatcherMonitor()
        self.guardian = GuardianMonitor()
        self.director = DirectorController(max_ticks=self.max_ticks)
        self.replay = ReplayTimeline(sim_id)

        # 传播模型状态
        self._prev_interactions: int = 0
        self._latest_monitor_report: Optional[MonitorReport] = None
        self._propagation_edges_buffer: List[Dict] = []  # 传播边缓冲区

    async def initialize(self):
        """初始化：加载Agent、注入种子话题"""
        self.message_bus.initialize()

        # 从数据库加载Agent
        await self._load_agents()

        # 向每个平台注入种子话题
        for pname, platform in self.platforms.items():
            platform.seed_topic(self.topic, author_id="system_director")

        # 消息总线通知
        await self.message_bus.publish(CHANNEL_SYSTEM_EVENTS, {
            "type": "simulation_initialized",
            "sim_id": self.sim_id,
            "agent_count": len(self.agents),
            "platforms": list(self.platforms.keys()),
        })

        logger.info(f"仿真 {self.sim_id} 初始化完成: {len(self.agents)} 个Agent, {len(self.platforms)} 个平台")

    async def _load_agents(self):
        """从数据库加载Agent并分配层级"""
        from backend.database import SessionLocal
        from backend.models import AgentRecord

        db = SessionLocal()
        try:
            records = db.query(AgentRecord).filter(AgentRecord.status == "active").all()
            for r in records:
                persona = json.loads(r.persona_json) if r.persona_json else {}
                persona["persona_id"] = r.agent_id
                persona["platform"] = r.platform
                self.agents[r.agent_id] = persona

                # 分配层级
                l6 = persona.get("L6_social", {})
                influence = l6.get("influence_level", "普通用户") if isinstance(l6, dict) else "普通用户"
                if influence == "KOL":
                    self.agent_tiers[r.agent_id] = AgentTier.B
                elif influence == "活跃分子":
                    self.agent_tiers[r.agent_id] = AgentTier.B
                else:
                    self.agent_tiers[r.agent_id] = AgentTier.C

                self.agent_platform_map[r.agent_id] = r.platform

                # 设置Agent时间表
                l4 = persona.get("L4_behavior", {})
                active_hours = l4.get("active_hours", "晚间") if isinstance(l4, dict) else "晚间"
                self.time_model.set_agent_schedule(r.agent_id, active_hours)

        finally:
            db.close()

    async def run(self):
        """运行仿真主循环"""
        self._running = True
        self.status = "running"

        while self._running and self.current_tick < self.max_ticks:
            if self._paused:
                await asyncio.sleep(0.5)
                continue

            await self._execute_tick()
            self.current_tick += 1

            # 通知监控
            await self.message_bus.publish(CHANNEL_MONITORING, {
                "tick": self.current_tick,
                "sim_time": self.time_model.time_str,
                "status": self.status,
                "spread_stage": self.spread_model.current_stage.value,
                "propagation_kinetic": self.spread_model.prev_kinetic,
            })

            # tick间隔（控制仿真速度）
            interval = self.config.get("tick_interval", 0.5)
            await asyncio.sleep(interval)

        self.status = "completed"
        self._running = False

        await self.message_bus.publish(CHANNEL_SYSTEM_EVENTS, {
            "type": "simulation_completed",
            "sim_id": self.sim_id,
            "total_ticks": self.current_tick,
        })

        logger.info(f"仿真 {self.sim_id} 完成: {self.current_tick} ticks")

    async def _execute_tick(self):
        """执行一个tick（V2.5 集成传播动力学）"""
        # 1. 推进时间
        sim_time = self.time_model.advance()

        # 2. Director调度决策（每12个tick）
        if self.current_tick % 12 == 0:
            await self._director_tick()

        # 3. B层Agent行为（LLM驱动，并发控制）
        b_actions = await self._b_agent_tick()

        # 4. C层Agent行为（规则引擎批量）
        c_actions = self._c_agent_tick()

        # 5. 平台处理action
        all_actions = b_actions + c_actions
        for action in all_actions:
            platform = self.platforms.get(action.platform)
            if platform:
                agent = self.agents.get(action.agent_id, {})
                platform.process_action(action, agent)

        # 6. V2.5 传播模型更新
        action_dicts = [self._action_to_dict(a) for a in all_actions]
        propagation_snapshot = self.spread_model.update(
            tick=self.current_tick,
            actions=action_dicts,
            prev_interactions=self._prev_interactions,
        )
        self._prev_interactions = propagation_snapshot.get("current_interactions", 0)

        # 收集传播边
        new_edges = propagation_snapshot.get("new_edges", 0)
        if new_edges > 0 and self.spread_model.propagation_tree.edges:
            # 只收集本tick新增的边
            recent_edges = self.spread_model.propagation_tree.edges[-new_edges:]
            self._propagation_edges_buffer.extend(recent_edges)

        # 7. Watcher监控（每6个tick）
        if self.current_tick % 6 == 0:
            await self._watcher_tick()

            # Guardian干预
            interventions = await self.guardian.check_anomalies(self)
            for intervention in interventions:
                await self.guardian.execute_intervention(self, intervention)

            # 保存回放快照
            await self.replay.save_snapshot(self.current_tick, self)

            # 批量持久化传播边
            if self._propagation_edges_buffer:
                await self.replay.save_edges(self._propagation_edges_buffer)
                self._propagation_edges_buffer.clear()

        # 8. 记录
        tick_data = SimulationTick(
            tick=self.current_tick,
            sim_time=sim_time.time_str,
            time_slot=sim_time.current_slot,
            actions=all_actions,
            platform_states={p: plat.get_snapshot() for p, plat in self.platforms.items()},
        )
        self.tick_results.append(tick_data)

        # 9. 持久化
        await self._persist_tick(tick_data)

        # 10. 传播阶段变更通知
        if propagation_snapshot.get("stage_changed"):
            await self.message_bus.publish(CHANNEL_SYSTEM_EVENTS, {
                "type": "stage_changed",
                "tick": self.current_tick,
                "new_stage": propagation_snapshot["stage"],
                "stage_label": propagation_snapshot["stage_label"],
            })
            logger.info(
                f"仿真 {self.sim_id} 传播阶段变更: {propagation_snapshot['stage_label']} (tick {self.current_tick})"
            )

    async def _director_tick(self):
        """A层Director：调度决策（V2.5 真实实现）"""
        decision = await self.director.evaluate(self, self._latest_monitor_report)

        # 发布Director决策
        await self.message_bus.publish(CHANNEL_SYSTEM_EVENTS, {
            "type": "director_decision",
            "tick": self.current_tick,
            "speed_adjustment": decision.speed_adjustment,
            "should_inject": decision.should_inject,
            "should_end": decision.should_end,
            "advice": decision.advice,
        })

        # 执行事件注入
        if decision.should_inject and decision.injection_content:
            platform_name = decision.injection_platform or "weibo"
            platform = self.platforms.get(platform_name)
            if platform:
                # 模拟大V/媒体/官方发帖
                inject_agent_id = f"system_injector_{decision.injection_as_role}"
                platform.seed_topic(decision.injection_content, author_id=inject_agent_id)
                logger.info(
                    f"Director注入事件: {decision.injection_content[:50]}... "
                    f"(角色: {decision.injection_as_role}, 平台: {platform_name})"
                )

        # 执行结束决策
        if decision.should_end:
            self._running = False
            logger.info(f"Director决定结束仿真: {decision.end_reason}")

    async def _watcher_tick(self):
        """A层Watcher：监控舆论态势（V2.5 真实实现）"""
        report = await self.watcher.observe(self)
        self._latest_monitor_report = report

        # 发布监控报告
        await self.message_bus.publish(CHANNEL_MONITORING, {
            "type": "watcher_report",
            "tick": self.current_tick,
            "report": report.to_dict(),
        })

    async def _b_agent_tick(self) -> List[PlatformAction]:
        """B层Agent行为（LLM驱动）"""
        actions = []
        b_agents = [aid for aid, tier in self.agent_tiers.items() if tier == AgentTier.B]

        # 限制并发
        semaphore = asyncio.Semaphore(3)

        async def _process_b_agent(agent_id):
            async with semaphore:
                agent = self.agents.get(agent_id, {})
                platform_name = self.agent_platform_map.get(agent_id, "weibo")
                platform = self.platforms.get(platform_name)
                if not platform:
                    return []

                # 检查是否活跃
                l4 = agent.get("L4_behavior", {})
                active_hours = l4.get("active_hours", "晚间") if isinstance(l4, dict) else "晚间"
                if not self.time_model.is_agent_active(agent_id, active_hours):
                    return []

                feed = platform.get_feed(limit=5, agent_persona=agent)
                return await decide_actions(
                    agent=agent,
                    platform=platform_name,
                    time_slot=self.time_model.current_slot,
                    platform_feed=feed,
                )

        if b_agents:
            # 随机采样部分B级Agent（控制LLM成本）
            import random
            sample_size = min(len(b_agents), self.config.get("b_agent_per_tick", 5))
            sampled = random.sample(b_agents, sample_size)

            results = await asyncio.gather(
                *[_process_b_agent(aid) for aid in sampled],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, list):
                    actions.extend(r)

        return actions

    def _c_agent_tick(self) -> List[PlatformAction]:
        """C层Agent行为（规则引擎批量）"""
        actions = []
        c_agents = [aid for aid, tier in self.agent_tiers.items() if tier == AgentTier.C]

        # 按活跃度筛选
        active_agents = []
        for aid in c_agents:
            agent = self.agents.get(aid, {})
            l4 = agent.get("L4_behavior", {})
            active_hours = l4.get("active_hours", "晚间") if isinstance(l4, dict) else "晚间"
            if self.time_model.is_agent_active(aid, active_hours):
                # 全局活跃度概率过滤
                import random
                if random.random() < self.time_model.current_activity:
                    active_agents.append(aid)

        for aid in active_agents:
            agent = self.agents.get(aid, {})
            platform_name = self.agent_platform_map.get(aid, "weibo")
            platform = self.platforms.get(platform_name)
            if not platform:
                continue

            feed = platform.get_feed(limit=3)
            agent_actions = self.rule_engine.decide(agent, feed, platform_name)
            actions.extend(agent_actions)

        return actions

    async def _persist_tick(self, tick: SimulationTick):
        """持久化tick记录"""
        from backend.database import SessionLocal
        from backend.models import SimulationRecord, SimulationStatus

        db = SessionLocal()
        try:
            for action in tick.actions:
                record = SimulationRecord(
                    sim_id=self.sim_id,
                    tick=tick.tick,
                    sim_time=tick.sim_time,
                    agent_id=action.agent_id,
                    agent_tier=self.agent_tiers.get(action.agent_id, "C"),
                    platform=action.platform,
                    action_type=action.action_type,
                    content=action.content[:500] if action.content else None,
                    target_id=action.target_id,
                    metadata_json=json.dumps(action.metadata, ensure_ascii=False) if action.metadata else None,
                )
                db.add(record)

            # 更新仿真状态
            status_record = db.query(SimulationStatus).filter(
                SimulationStatus.sim_id == self.sim_id
            ).first()
            if status_record:
                status_record.total_ticks = tick.tick + 1
                status_record.platform_snapshot_json = json.dumps(
                    tick.platform_states, ensure_ascii=False
                )
                status_record.updated_at = datetime.now(timezone.utc)

            db.commit()
        except Exception as e:
            logger.error(f"持久化tick失败: {e}")
            db.rollback()
        finally:
            db.close()

    # ── 控制接口 ──────────────────────────────────────

    def pause(self):
        self._paused = True
        self.status = "paused"

    def resume(self):
        self._paused = False
        self.status = "running"

    def stop(self):
        self._running = False
        self.status = "stopped"

    def get_status(self) -> Dict:
        """获取仿真状态（V2.5 含传播动力学数据）"""
        base_status = {
            "sim_id": self.sim_id,
            "status": self.status,
            "current_tick": self.current_tick,
            "max_ticks": self.max_ticks,
            "sim_time": self.time_model.time_str,
            "time_slot": self.time_model.current_slot,
            "total_agents": len(self.agents),
            "b_agents": sum(1 for t in self.agent_tiers.values() if t == AgentTier.B),
            "c_agents": sum(1 for t in self.agent_tiers.values() if t == AgentTier.C),
            "platforms": {p: plat.get_snapshot() for p, plat in self.platforms.items()},
        }

        # V2.5 传播动力学数据
        base_status["propagation"] = {
            "stage": self.spread_model.current_stage.value,
            "stage_label": STAGE_LABELS.get(self.spread_model.current_stage, ""),
            "kinetic": self.spread_model.prev_kinetic,
            "reach_count": self.spread_model.propagation_tree.get_reach_count(),
            "depth": self.spread_model.propagation_tree.get_depth(),
            "total_nodes": len(self.spread_model.propagation_tree.nodes),
            "total_edges": len(self.spread_model.propagation_tree.edges),
        }

        # V2.5 监控报告摘要
        if self._latest_monitor_report:
            base_status["monitor"] = {
                "polarization_index": self._latest_monitor_report.polarization_index,
                "propagation_kinetic": self._latest_monitor_report.propagation_kinetic,
                "spread_stage": self._latest_monitor_report.spread_stage,
                "anomaly_count": len(self._latest_monitor_report.anomalies),
                "sentiment_distribution": self._latest_monitor_report.sentiment_distribution,
            }

        return base_status

    # ── V2.5 辅助方法 ──────────────────────────────────────

    def _action_to_dict(self, action: PlatformAction) -> Dict[str, Any]:
        """将 PlatformAction 转为 dict 供传播模型使用"""
        if isinstance(action, dict):
            return action
        return {
            "agent_id": getattr(action, "agent_id", ""),
            "platform": getattr(action, "platform", ""),
            "action_type": getattr(action, "action_type", ""),
            "content": getattr(action, "content", ""),
            "target_id": getattr(action, "target_id", ""),
            "metadata": getattr(action, "metadata", {}) or {},
        }


# 引用常量
CHANNEL_SYSTEM_EVENTS = "system_events"
CHANNEL_MONITORING = "monitoring"
