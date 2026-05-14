"""Memory Stream 向量存储 — ChromaDB内嵌式部署 + 三因子检索

三因子检索: Recency(0.5) + Importance(0.3) + Relevance(0.2)
记忆类型: observation / reflection / plan
"""

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_HAS_CHROMADB = False
try:
    import chromadb
    _HAS_CHROMADB = True
except ImportError:
    pass


class MemoryStreamStore:
    """Memory Stream 向量存储

    ChromaDB优先，降级为MySQL/SQLite关键词检索
    """

    RECENCY_WEIGHT = 0.5
    IMPORTANCE_WEIGHT = 0.3
    RELEVANCE_WEIGHT = 0.2

    def __init__(self, persist_dir: str = "./data/chroma_memories"):
        self._persist_dir = persist_dir
        self._client = None
        self._collection = None

        if _HAS_CHROMADB:
            try:
                self._client = chromadb.PersistentClient(path=persist_dir)
                self._collection = self._client.get_or_create_collection(
                    name="memory_stream",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("ChromaDB Memory Stream 初始化成功")
            except Exception as e:
                logger.warning("ChromaDB初始化失败，降级为数据库检索: %s", e)
                self._client = None

    @property
    def is_chroma_available(self) -> bool:
        return self._client is not None

    def store(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "observation",
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> str:
        """存储一条记忆

        Args:
            agent_id: Agent ID
            content: 记忆内容
            memory_type: observation/reflection/plan
            importance: 重要性 0-1
            tags: 标签列表

        Returns:
            memory_id
        """
        memory_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        if self._collection is not None:
            try:
                self._collection.add(
                    ids=[memory_id],
                    documents=[content],
                    metadatas=[{
                        "agent_id": agent_id,
                        "memory_type": memory_type,
                        "importance": importance,
                        "created_at": now,
                        "tags": json.dumps(tags or [], ensure_ascii=False),
                        "access_count": 0,
                    }],
                )
                return memory_id
            except Exception as e:
                logger.warning("ChromaDB存储失败，降级: %s", e)

        self._store_db(memory_id, agent_id, content, memory_type, importance, tags)
        return memory_id

    def store_batch(
        self,
        agent_id: str,
        memories: List[Dict[str, Any]],
    ) -> List[str]:
        """批量存储记忆"""
        ids = []
        if self._collection is not None and memories:
            try:
                chroma_ids = []
                documents = []
                metadatas = []
                now = datetime.now(timezone.utc).isoformat()

                for mem in memories:
                    mid = str(uuid.uuid4())
                    ids.append(mid)
                    chroma_ids.append(mid)
                    documents.append(mem.get("content", ""))
                    metadatas.append({
                        "agent_id": agent_id,
                        "memory_type": mem.get("type", "observation"),
                        "importance": mem.get("importance", 0.5),
                        "created_at": now,
                        "tags": json.dumps(mem.get("tags", []), ensure_ascii=False),
                        "access_count": 0,
                    })

                if chroma_ids:
                    self._collection.add(
                        ids=chroma_ids,
                        documents=documents,
                        metadatas=metadatas,
                    )
                return ids
            except Exception as e:
                logger.warning("ChromaDB批量存储失败，降级: %s", e)

        for mem in memories:
            mid = str(uuid.uuid4())
            ids.append(mid)
            self._store_db(
                mid, agent_id,
                mem.get("content", ""),
                mem.get("type", "observation"),
                mem.get("importance", 0.5),
                mem.get("tags"),
            )
        return ids

    def retrieve(
        self,
        agent_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """三因子检索记忆

        Args:
            agent_id: Agent ID
            query: 查询文本
            top_k: 返回数量

        Returns:
            记忆列表，按综合得分降序
        """
        if self._collection is not None:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=min(top_k * 3, 50),
                    where={"agent_id": agent_id},
                )

                if not results or not results["ids"] or not results["ids"][0]:
                    return []

                now = datetime.now(timezone.utc)
                scored_memories = []

                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i]
                    relevance = 1.0 - (results["distances"][0][i] if results.get("distances") else 0.0)

                    recency = self._calc_recency(meta.get("created_at", ""), now)
                    importance = float(meta.get("importance", 0.5))

                    composite = (
                        self.RECENCY_WEIGHT * recency
                        + self.IMPORTANCE_WEIGHT * importance
                        + self.RELEVANCE_WEIGHT * relevance
                    )

                    scored_memories.append({
                        "memory_id": results["ids"][0][i],
                        "content": doc,
                        "memory_type": meta.get("memory_type", "observation"),
                        "importance": importance,
                        "recency_score": recency,
                        "relevance_score": relevance,
                        "composite_score": composite,
                        "created_at": meta.get("created_at", ""),
                        "tags": json.loads(meta.get("tags", "[]")),
                    })

                scored_memories.sort(key=lambda x: x["composite_score"], reverse=True)
                return scored_memories[:top_k]

            except Exception as e:
                logger.warning("ChromaDB检索失败，降级: %s", e)

        return self._retrieve_db(agent_id, query, top_k)

    def get_recent(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        if self._collection is not None:
            try:
                results = self._collection.get(
                    where={"agent_id": agent_id},
                    limit=limit,
                    order_by=["created_at"],
                )

                if not results or not results["ids"]:
                    return []

                return [
                    {
                        "memory_id": results["ids"][i],
                        "content": results["documents"][i],
                        "memory_type": results["metadatas"][i].get("memory_type", "observation"),
                        "importance": results["metadatas"][i].get("importance", 0.5),
                        "created_at": results["metadatas"][i].get("created_at", ""),
                    }
                    for i in range(len(results["ids"]))
                ]
            except Exception as e:
                logger.warning("ChromaDB获取最近记忆失败: %s", e)

        return self._get_recent_db(agent_id, limit)

    @staticmethod
    def _calc_recency(created_at_str: str, now: datetime) -> float:
        """计算Recency分数（指数衰减）"""
        if not created_at_str:
            return 0.5
        try:
            created = datetime.fromisoformat(created_at_str)
            hours_elapsed = max(0, (now - created).total_seconds() / 3600)
            return math.exp(-0.05 * hours_elapsed)
        except (ValueError, TypeError):
            return 0.5

    def _store_db(self, memory_id, agent_id, content, memory_type, importance, tags):
        """降级：存储到MySQL/SQLite"""
        try:
            from backend.database import SessionLocal
            from backend.models import AgentMemory
            db = SessionLocal()
            try:
                memory = AgentMemory(
                    memory_id=memory_id,
                    agent_id=agent_id,
                    memory_type=memory_type,
                    content=content,
                    weight=importance,
                )
                db.add(memory)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning("数据库存储记忆失败: %s", e)

    def _retrieve_db(self, agent_id, query, top_k):
        """降级：从数据库检索"""
        try:
            from backend.database import SessionLocal
            from backend.models import AgentMemory
            db = SessionLocal()
            try:
                records = (
                    db.query(AgentMemory)
                    .filter(AgentMemory.agent_id == agent_id)
                    .order_by(AgentMemory.weight.desc())
                    .limit(top_k)
                    .all()
                )
                return [
                    {
                        "memory_id": r.memory_id,
                        "content": r.content,
                        "memory_type": r.memory_type,
                        "importance": r.weight,
                        "composite_score": r.weight,
                    }
                    for r in records
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning("数据库检索记忆失败: %s", e)
            return []

    def _get_recent_db(self, agent_id, limit):
        """降级：从数据库获取最近记忆"""
        try:
            from backend.database import SessionLocal
            from backend.models import AgentMemory
            db = SessionLocal()
            try:
                records = (
                    db.query(AgentMemory)
                    .filter(AgentMemory.agent_id == agent_id)
                    .order_by(AgentMemory.created_at.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "memory_id": r.memory_id,
                        "content": r.content,
                        "memory_type": r.memory_type,
                        "importance": r.weight,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in records
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning("数据库获取最近记忆失败：%s", e)
            return []

    def check_and_trigger_reflection(self, agent_id: str) -> bool:
        """检查并触发 Reflection

        Args:
            agent_id: Agent ID

        Returns:
            True 如果触发了 Reflection
        """
        try:
            from backend.services.persona.reflection_engine import ReflectionEngine
            reflection_engine = ReflectionEngine(self)
            trigger = reflection_engine.trigger

            if trigger.should_reflect(agent_id):
                import asyncio
                # 在后台执行 Reflection（不阻塞主流程）
                asyncio.create_task(reflection_engine.execute_reflection(agent_id))
                logger.info("触发 Agent %s 的 Reflection 机制", agent_id)
                return True
        except Exception as e:
            logger.warning("Reflection 触发检查失败：%s", e)
        return False


def get_memory_stream_status() -> dict:
    """返回 Memory Stream 状态"""
    return {
        "chromadb_available": _HAS_CHROMADB,
        "fallback": "database" if not _HAS_CHROMADB else None,
        "reflection_enabled": True,
    }