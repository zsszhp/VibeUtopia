"""仿真回放时间轴 — 快照管理、回放、对比"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayFrame:
    """回放帧 — 某个tick的仿真快照摘要"""
    tick: int = 0
    sim_time: str = ""               # 如 "Day1 14:00"
    stage: str = "seed"              # 传播阶段
    stage_label: str = "种子注入"
    kinetic: float = 0.0            # 传播动能
    polarization: float = 0.0       # 极化指数
    reach: int = 0                  # 覆盖人数
    depth: int = 0                  # 传播深度
    total_actions: int = 0          # 本tick行为总数
    sentiment_dist: Dict[str, float] = field(default_factory=dict)
    key_content: List[str] = field(default_factory=list)  # 本tick热点内容
    key_influencers: List[Dict] = field(default_factory=list)
    interventions: List[Dict] = field(default_factory=list)  # Guardian干预记录
    snapshot_id: Optional[int] = None  # DB中PropagationSnapshot的ID


class ReplayTimeline:
    """仿真回放时间轴"""

    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self._frames: Dict[int, ReplayFrame] = {}  # tick -> frame
        self._pending_edges: List[Dict] = []  # 待持久化的传播边

    async def save_snapshot(self, tick: int, engine: Any) -> Optional[int]:
        """每个关键tick保存快照到数据库

        Args:
            tick: 当前tick
            engine: SimulationEngine 实例

        Returns:
            保存的snapshot ID，失败返回None
        """
        try:
            from backend.database import SessionLocal
            from backend.models import PropagationSnapshot

            spread_model = getattr(engine, "spread_model", None)
            watcher = getattr(engine, "watcher", None)

            # 收集快照数据
            if spread_model:
                stage = spread_model.current_stage.value
                from ..propagation.spread_model import STAGE_LABELS
                stage_label = STAGE_LABELS.get(spread_model.current_stage, "")
                kinetic = (
                    spread_model.kinetic_history[-1]["kinetic"]
                    if spread_model.kinetic_history else 0.0
                )
                polarization = (
                    spread_model.polarization_calc.get_history()[-1]["polarization_index"]
                    if spread_model.polarization_calc.get_history() else 0.0
                )
                reach = spread_model.propagation_tree.get_reach_count()
                depth = spread_model.propagation_tree.get_depth()
                top_influencers = spread_model.propagation_tree.get_influencer_ranking(5)
                sentiment_dist = (
                    spread_model.calc_sentiment_distribution(
                        self._get_recent_actions(engine)
                    )
                )
            else:
                stage = "seed"
                stage_label = "种子注入"
                kinetic = 0.0
                polarization = 0.0
                reach = 0
                depth = 0
                top_influencers = []
                sentiment_dist = {}

            # 获取仿真时间
            sim_time = ""
            if hasattr(engine, "time_model") and engine.time_model:
                sim_time = engine.time_model.sim_time.time_str

            # 构建完整快照数据
            snapshot_data = {
                "tick": tick,
                "sim_time": sim_time,
                "platform_snapshot": self._get_platform_snapshot(engine),
                "propagation_tree_stats": (
                    spread_model.propagation_tree.get_stats()
                    if spread_model else {}
                ),
            }

            # 本tick热点内容
            key_content = self._get_key_content(engine)

            # Guardian干预记录
            guardian = getattr(engine, "guardian", None)
            interventions = guardian.get_intervention_log(5) if guardian else []

            # 写入DB
            db = SessionLocal()
            try:
                snapshot = PropagationSnapshot(
                    simulation_id=self.simulation_id,
                    tick=tick,
                    stage=stage,
                    propagation_kinetic=kinetic,
                    polarization_index=polarization,
                    reach_count=reach,
                    depth=depth,
                    sentiment_distribution=json.dumps(sentiment_dist, ensure_ascii=False),
                    key_influencers=json.dumps(
                        [{"agent_id": aid, "count": c} for aid, c in top_influencers],
                        ensure_ascii=False,
                    ),
                    snapshot_data=json.dumps(snapshot_data, ensure_ascii=False),
                )
                db.add(snapshot)
                db.commit()
                db.refresh(snapshot)

                # 同时缓存到内存
                frame = ReplayFrame(
                    tick=tick,
                    sim_time=sim_time,
                    stage=stage,
                    stage_label=stage_label,
                    kinetic=kinetic,
                    polarization=polarization,
                    reach=reach,
                    depth=depth,
                    total_actions=len(self._get_recent_actions(engine)),
                    sentiment_dist=sentiment_dist,
                    key_content=key_content,
                    key_influencers=[{"agent_id": aid, "count": c} for aid, c in top_influencers],
                    interventions=interventions,
                    snapshot_id=snapshot.id,
                )
                self._frames[tick] = frame

                return snapshot.id

            except Exception as e:
                db.rollback()
                logger.error("保存传播快照失败: %s", e)
                return None
            finally:
                db.close()

        except ImportError:
            logger.warning("数据库模块不可用，快照仅保存在内存中")

            # 内存保存
            frame = ReplayFrame(tick=tick)
            if spread_model:
                frame.stage = spread_model.current_stage.value
                frame.kinetic = spread_model.kinetic_history[-1]["kinetic"] if spread_model.kinetic_history else 0.0
                frame.reach = spread_model.propagation_tree.get_reach_count()
                frame.depth = spread_model.propagation_tree.get_depth()
            self._frames[tick] = frame
            return None

    async def save_edges(self, edges: List[Dict[str, Any]]):
        """批量保存传播边到数据库

        Args:
            edges: 传播边列表，每个边包含 source_agent_id, target_agent_id, content_id, action_type, platform, tick
        """
        if not edges:
            return

        try:
            from backend.database import SessionLocal
            from backend.models import PropagationEdge

            db = SessionLocal()
            try:
                for edge in edges:
                    db_edge = PropagationEdge(
                        simulation_id=self.simulation_id,
                        source_agent_id=edge.get("source_agent_id", ""),
                        target_agent_id=edge.get("target_agent_id", ""),
                        content_id=edge.get("content_id", ""),
                        action_type=edge.get("action_type", ""),
                        platform=edge.get("platform", ""),
                        tick=edge.get("tick", 0),
                    )
                    db.add(db_edge)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("保存传播边失败: %s", e)
            finally:
                db.close()

        except ImportError:
            logger.warning("数据库模块不可用，传播边仅保存在内存中")

    async def get_timeline(self) -> List[Dict[str, Any]]:
        """获取完整回放时间轴

        先尝试从DB加载，如果失败则从内存缓存返回
        """
        # 尝试从DB加载
        try:
            from backend.database import SessionLocal
            from backend.models import PropagationSnapshot

            db = SessionLocal()
            try:
                snapshots = (
                    db.query(PropagationSnapshot)
                    .filter(PropagationSnapshot.simulation_id == self.simulation_id)
                    .order_by(PropagationSnapshot.tick)
                    .all()
                )
                if snapshots:
                    return [
                        {
                            "tick": s.tick,
                            "stage": s.stage,
                            "kinetic": s.propagation_kinetic,
                            "polarization": s.polarization_index,
                            "reach": s.reach_count,
                            "depth": s.depth,
                            "sentiment_distribution": json.loads(s.sentiment_distribution) if s.sentiment_distribution else {},
                            "key_influencers": json.loads(s.key_influencers) if s.key_influencers else [],
                        }
                        for s in snapshots
                    ]
            finally:
                db.close()
        except (ImportError, Exception):
            pass

        # 从内存返回
        return [
            {
                "tick": f.tick,
                "sim_time": f.sim_time,
                "stage": f.stage,
                "stage_label": f.stage_label,
                "kinetic": f.kinetic,
                "polarization": f.polarization,
                "reach": f.reach,
                "depth": f.depth,
                "total_actions": f.total_actions,
                "sentiment_distribution": f.sentiment_dist,
                "key_content": f.key_content,
                "key_influencers": f.key_influencers,
                "interventions": f.interventions,
            }
            for f in sorted(self._frames.values(), key=lambda x: x.tick)
        ]

    async def get_frame(self, tick: int) -> Optional[Dict[str, Any]]:
        """获取特定时刻的快照"""
        # 先查内存
        if tick in self._frames:
            f = self._frames[tick]
            return {
                "tick": f.tick,
                "sim_time": f.sim_time,
                "stage": f.stage,
                "stage_label": f.stage_label,
                "kinetic": f.kinetic,
                "polarization": f.polarization,
                "reach": f.reach,
                "depth": f.depth,
                "total_actions": f.total_actions,
                "sentiment_distribution": f.sentiment_dist,
                "key_content": f.key_content,
                "key_influencers": f.key_influencers,
                "interventions": f.interventions,
            }

        # 从DB查询
        try:
            from backend.database import SessionLocal
            from backend.models import PropagationSnapshot

            db = SessionLocal()
            try:
                snapshot = (
                    db.query(PropagationSnapshot)
                    .filter(
                        PropagationSnapshot.simulation_id == self.simulation_id,
                        PropagationSnapshot.tick == tick,
                    )
                    .first()
                )
                if snapshot:
                    return {
                        "tick": snapshot.tick,
                        "stage": snapshot.stage,
                        "kinetic": snapshot.propagation_kinetic,
                        "polarization": snapshot.polarization_index,
                        "reach": snapshot.reach_count,
                        "depth": snapshot.depth,
                        "sentiment_distribution": json.loads(snapshot.sentiment_distribution) if snapshot.sentiment_distribution else {},
                        "key_influencers": json.loads(snapshot.key_influencers) if snapshot.key_influencers else [],
                        "snapshot_data": json.loads(snapshot.snapshot_data) if snapshot.snapshot_data else {},
                    }
            finally:
                db.close()
        except (ImportError, Exception):
            pass

        return None

    async def get_diff(self, tick1: int, tick2: int) -> Dict[str, Any]:
        """对比两个时刻的差异"""
        frame1 = await self.get_frame(tick1)
        frame2 = await self.get_frame(tick2)

        if not frame1 or not frame2:
            return {"error": "指定的tick快照不存在"}

        def _safe_diff(v1, v2):
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                return round(v2 - v1, 4)
            return None

        return {
            "tick_range": [tick1, tick2],
            "kinetic_diff": _safe_diff(frame1.get("kinetic", 0), frame2.get("kinetic", 0)),
            "polarization_diff": _safe_diff(frame1.get("polarization", 0), frame2.get("polarization", 0)),
            "reach_diff": _safe_diff(frame1.get("reach", 0), frame2.get("reach", 0)),
            "depth_diff": _safe_diff(frame1.get("depth", 0), frame2.get("depth", 0)),
            "stage_change": {
                "from": frame1.get("stage", ""),
                "to": frame2.get("stage", ""),
                "changed": frame1.get("stage") != frame2.get("stage"),
            },
            "sentiment_shift": {
                "positive_diff": _safe_diff(
                    frame1.get("sentiment_distribution", {}).get("positive", 0),
                    frame2.get("sentiment_distribution", {}).get("positive", 0),
                ),
                "negative_diff": _safe_diff(
                    frame1.get("sentiment_distribution", {}).get("negative", 0),
                    frame2.get("sentiment_distribution", {}).get("negative", 0),
                ),
            },
        }

    def _get_recent_actions(self, engine: Any) -> List[Dict]:
        """获取最近的Agent行为列表"""
        if not hasattr(engine, "tick_results") or not engine.tick_results:
            return []

        latest = engine.tick_results[-1]
        if hasattr(latest, "actions"):
            actions = latest.actions
        elif isinstance(latest, dict):
            actions = latest.get("actions", [])
        else:
            return []

        # 统一转为dict
        result = []
        for a in actions:
            if isinstance(a, dict):
                result.append(a)
            else:
                result.append({
                    "agent_id": getattr(a, "agent_id", ""),
                    "action_type": getattr(a, "action_type", ""),
                    "content": getattr(a, "content", ""),
                    "platform": getattr(a, "platform", ""),
                })
        return result

    def _get_key_content(self, engine: Any) -> List[str]:
        """获取本tick热点内容"""
        actions = self._get_recent_actions(engine)
        key = []
        for a in actions:
            if a.get("action_type") in ("post", "comment", "repost") and a.get("content"):
                content = a["content"][:80]
                if content not in key:
                    key.append(content)
        return key[:5]

    def _get_platform_snapshot(self, engine: Any) -> Dict:
        """获取各平台快照"""
        result = {}
        if hasattr(engine, "platforms") and engine.platforms:
            for name, platform in engine.platforms.items():
                if hasattr(platform, "posts"):
                    result[name] = {"post_count": len(platform.posts)}
                else:
                    result[name] = {}
        return result
