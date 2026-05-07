"""记忆系统 — 工作记忆 + 情景记忆 + 语义记忆 + 遗忘机制"""

import json
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """Agent记忆管理器

    三层记忆架构：
    - 工作记忆：内存字典，当前分析上下文，任务结束后释放
    - 情景记忆：SQLite AgentMemory表，记录Agent经历的分析事件
    - 语义记忆：从情景记忆中LLM提炼的长期认知

    遗忘机制：按时间衰减权重，半衰期默认7天
    """

    def __init__(self, half_life_days: int = None, max_per_agent: int = None):
        self.half_life_days = half_life_days or settings.AGENT_MEMORY_HALF_LIFE_DAYS
        self.max_per_agent = max_per_agent or settings.AGENT_MEMORY_MAX_PER_AGENT
        # 工作记忆：内存字典 {agent_id: [context]}
        self._working_memory: Dict[str, List[Dict]] = {}

    # ── 工作记忆 ──────────────────────────────────────

    def set_working_memory(self, agent_id: str, context: Dict[str, Any]):
        """设置工作记忆（当前分析上下文）"""
        self._working_memory[agent_id] = [context]

    def get_working_memory(self, agent_id: str) -> List[Dict]:
        """获取工作记忆"""
        return self._working_memory.get(agent_id, [])

    def clear_working_memory(self, agent_id: str = None):
        """清除工作记忆"""
        if agent_id:
            self._working_memory.pop(agent_id, None)
        else:
            self._working_memory.clear()

    # ── 情景记忆 ──────────────────────────────────────

    def store_episodic(self, agent_id: str, event: str, source_task_id: str = "",
                       weight: float = 1.0):
        """存储情景记忆

        Args:
            agent_id: Agent ID
            event: 事件描述
            source_task_id: 来源分析任务ID
            weight: 初始权重
        """
        from backend.database import SessionLocal
        from backend.models import AgentMemory

        db = SessionLocal()
        try:
            memory = AgentMemory(
                memory_id=str(uuid.uuid4()),
                agent_id=agent_id,
                memory_type="episodic",
                content=event,
                weight=weight,
                source_task_id=source_task_id,
            )
            db.add(memory)
            db.commit()

            # 检查容量上限
            self._enforce_capacity(agent_id, db)
        except Exception as e:
            logger.error(f"存储情景记忆失败: {e}")
            db.rollback()
        finally:
            db.close()

    def store_episodic_batch(self, agent_id: str, events: List[str],
                             source_task_id: str = ""):
        """批量存储情景记忆"""
        from backend.database import SessionLocal
        from backend.models import AgentMemory

        db = SessionLocal()
        try:
            for event in events:
                memory = AgentMemory(
                    memory_id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    memory_type="episodic",
                    content=event,
                    weight=1.0,
                    source_task_id=source_task_id,
                )
                db.add(memory)
            db.commit()
            self._enforce_capacity(agent_id, db)
        except Exception as e:
            logger.error(f"批量存储情景记忆失败: {e}")
            db.rollback()
        finally:
            db.close()

    def get_episodic_memories(self, agent_id: str, limit: int = 20,
                              min_weight: float = 0.1) -> List[Dict]:
        """获取Agent的情景记忆（按权重降序）"""
        from backend.database import SessionLocal
        from backend.models import AgentMemory

        db = SessionLocal()
        try:
            # 先衰减权重
            self._decay_weights(agent_id, db)

            records = (
                db.query(AgentMemory)
                .filter(AgentMemory.agent_id == agent_id)
                .filter(AgentMemory.memory_type == "episodic")
                .filter(AgentMemory.weight >= min_weight)
                .order_by(AgentMemory.weight.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "memory_id": r.memory_id,
                    "content": r.content,
                    "weight": round(r.weight, 3),
                    "source_task_id": r.source_task_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"获取情景记忆失败: {e}")
            return []
        finally:
            db.close()

    # ── 语义记忆 ──────────────────────────────────────

    async def generate_semantic_memory(self, agent_id: str) -> Optional[str]:
        """从情景记忆中提炼语义记忆（LLM总结）

        Returns:
            语义记忆内容，或None
        """
        episodic = self.get_episodic_memories(agent_id, limit=20)
        if len(episodic) < 3:
            return None

        try:
            from backend.services.llm_client import call_llm, parse_llm_json

            events_text = "\n".join(
                f"- {e['content']} (权重: {e['weight']})"
                for e in episodic
            )
            prompt = f"""请从以下Agent的经历中提炼出核心认知和长期态度变化，输出1-2句话的语义记忆：

Agent经历：
{events_text}

输出格式：一段简洁的语义记忆文本，描述该Agent形成的长期认知。"""

            resp = await call_llm(prompt)
            semantic = resp.strip() if resp else None

            if semantic:
                self._store_semantic(agent_id, semantic)
            return semantic
        except Exception as e:
            logger.error(f"语义记忆生成失败: {e}")
            return None

    def get_semantic_memories(self, agent_id: str, limit: int = 5) -> List[Dict]:
        """获取语义记忆"""
        from backend.database import SessionLocal
        from backend.models import AgentMemory

        db = SessionLocal()
        try:
            records = (
                db.query(AgentMemory)
                .filter(AgentMemory.agent_id == agent_id)
                .filter(AgentMemory.memory_type == "semantic")
                .order_by(AgentMemory.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {"memory_id": r.memory_id, "content": r.content, "weight": r.weight,
                 "created_at": r.created_at.isoformat() if r.created_at else None}
                for r in records
            ]
        except Exception as e:
            logger.error(f"获取语义记忆失败: {e}")
            return []
        finally:
            db.close()

    # ── 遗忘机制 ──────────────────────────────────────

    def _decay_weights(self, agent_id: str, db):
        """按时间衰减记忆权重（指数衰减）"""
        from backend.models import AgentMemory

        now = datetime.now(timezone.utc)
        records = db.query(AgentMemory).filter(AgentMemory.agent_id == agent_id).all()

        for r in records:
            if r.created_at:
                age_days = (now - r.created_at).total_seconds() / 86400
                decay = math.exp(-0.693 * age_days / self.half_life_days)
                r.weight = min(r.weight, decay)

        db.commit()

    def _enforce_capacity(self, agent_id: str, db):
        """检查记忆容量，超限按权重淘汰"""
        from backend.models import AgentMemory

        count = db.query(AgentMemory).filter(AgentMemory.agent_id == agent_id).count()
        if count > self.max_per_agent:
            # 删除权重最低的记忆
            to_delete = (
                db.query(AgentMemory)
                .filter(AgentMemory.agent_id == agent_id)
                .order_by(AgentMemory.weight.asc())
                .limit(count - self.max_per_agent)
                .all()
            )
            for r in to_delete:
                db.delete(r)
            db.commit()
            logger.debug(f"Agent {agent_id} 记忆超限，淘汰 {len(to_delete)} 条")

    def _store_semantic(self, agent_id: str, content: str):
        """存储语义记忆"""
        from backend.database import SessionLocal
        from backend.models import AgentMemory

        db = SessionLocal()
        try:
            memory = AgentMemory(
                memory_id=str(uuid.uuid4()),
                agent_id=agent_id,
                memory_type="semantic",
                content=content,
                weight=0.8,
            )
            db.add(memory)
            db.commit()
        except Exception as e:
            logger.error(f"存储语义记忆失败: {e}")
            db.rollback()
        finally:
            db.close()
