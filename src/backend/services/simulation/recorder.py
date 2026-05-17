"""仿真记录与回放"""

import json
import logging
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal
from backend.models import SimulationRecord, SimulationStatus

logger = logging.getLogger(__name__)


class SimulationRecorder:
    """仿真记录查询与回放"""

    def get_timeline(self, sim_id: str, start_tick: int = 0,
                     end_tick: int = None, limit: int = 200) -> List[Dict]:
        """获取仿真时间线"""
        db = SessionLocal()
        try:
            query = db.query(SimulationRecord).filter(
                SimulationRecord.sim_id == sim_id
            )
            if start_tick > 0:
                query = query.filter(SimulationRecord.tick >= start_tick)
            if end_tick is not None:
                query = query.filter(SimulationRecord.tick <= end_tick)

            records = query.order_by(SimulationRecord.tick.asc()).limit(limit).all()

            return [
                {
                    "id": r.id,
                    "tick": r.tick,
                    "sim_time": r.sim_time,
                    "agent_id": r.agent_id,
                    "agent_tier": r.agent_tier,
                    "platform": r.platform,
                    "action_type": r.action_type,
                    "content": r.content,
                    "target_id": r.target_id,
                }
                for r in records
            ]
        finally:
            db.close()

    def get_platform_snapshot(self, sim_id: str, platform: str = None) -> Dict:
        """获取平台快照"""
        db = SessionLocal()
        try:
            status = db.query(SimulationStatus).filter(
                SimulationStatus.sim_id == sim_id
            ).first()
            if not status or not status.platform_snapshot_json:
                return {}

            snapshots = json.loads(status.platform_snapshot_json)
            if platform:
                return snapshots.get(platform, {})
            return snapshots
        finally:
            db.close()

    def get_simulation_info(self, sim_id: str) -> Optional[Dict]:
        """获取仿真基本信息"""
        db = SessionLocal()
        try:
            status = db.query(SimulationStatus).filter(
                SimulationStatus.sim_id == sim_id
            ).first()
            if not status:
                return None
            return {
                "sim_id": status.sim_id,
                "status": status.status,
                "topic": status.topic,
                "total_ticks": status.total_ticks,
                "total_agents": status.total_agents,
                "config": json.loads(status.config_json) if status.config_json else {},
                "created_at": status.created_at.isoformat() if status.created_at else None,
                "updated_at": status.updated_at.isoformat() if status.updated_at else None,
            }
        finally:
            db.close()

    def get_action_stats(self, sim_id: str) -> Dict:
        """获取行为统计"""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            records = db.query(SimulationRecord).filter(
                SimulationRecord.sim_id == sim_id
            ).all()

            by_type = {}
            by_platform = {}
            by_tier = {}
            for r in records:
                by_type[r.action_type] = by_type.get(r.action_type, 0) + 1
                by_platform[r.platform] = by_platform.get(r.platform, 0) + 1
                by_tier[r.agent_tier] = by_tier.get(r.agent_tier, 0) + 1

            return {
                "total_actions": len(records),
                "by_type": by_type,
                "by_platform": by_platform,
                "by_tier": by_tier,
            }
        finally:
            db.close()
