"""GraphUpdater — 增量更新与事件驱动的图谱维护"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.graph.models import Entity, Relation, ExtractionResult
from backend.services.graph.entity_extractor import extract_from_event
from backend.services.graph.graph_store import GraphStore
from backend.services.graph.ontology_generator import load_ontology

logger = logging.getLogger(__name__)


class GraphUpdater:
    """图谱增量更新器"""

    def __init__(self, store: GraphStore):
        self.store = store
        self._processed_events: set = set()

    async def process_seed_event(self, event_data: Dict[str, Any]) -> Optional[ExtractionResult]:
        """处理单个种子事件：抽取 → 去重 → 存储

        Args:
            event_data: 种子事件数据，包含 event_id, title, description, comments 等

        Returns:
            ExtractionResult 或 None
        """
        event_id = event_data.get("event_id", "")
        if event_id in self._processed_events:
            logger.debug(f"事件 {event_id} 已处理，跳过")
            return None

        title = event_data.get("title", "")
        description = event_data.get("description", "")
        comments = event_data.get("comments", [])
        comments_summary = ""
        if comments:
            if isinstance(comments, list):
                comments_summary = "\n".join(
                    c.get("text", str(c))[:100] for c in comments[:10]
                )
            else:
                comments_summary = str(comments)[:500]

        # 抽取
        result = await extract_from_event(
            title=title,
            description=description,
            comments_summary=comments_summary,
            source_event_id=event_id,
        )

        if not result.entities:
            logger.warning(f"事件 {event_id} 未抽取出任何实体")
            return None

        # 去重：检查同名实体是否已存在
        deduped_entities = []
        for entity in result.entities:
            existing = self.store.search_entities(entity.name, entity.entity_type, limit=1)
            if existing:
                # 合并属性
                logger.debug(f"实体 {entity.name} 已存在，合并属性")
                for key, value in entity.properties.items():
                    existing[0].set(f"prop_{key}", str(value))
            else:
                deduped_entities.append(entity)

        result.entities = deduped_entities

        # 存储
        saved = self.store.save_extraction_result(result)
        self._processed_events.add(event_id)

        logger.info(f"事件 {event_id} 处理完成: {len(result.entities)}个实体, {saved}个关系")
        return result

    async def batch_update(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量处理种子事件列表

        Returns:
            统计信息 {total, processed, entities, relations, errors}
        """
        stats = {"total": len(events), "processed": 0, "entities": 0, "relations": 0, "errors": 0}

        for event in events:
            try:
                result = await self.process_seed_event(event)
                if result:
                    stats["processed"] += 1
                    stats["entities"] += len(result.entities)
                    stats["relations"] += len(result.relations)
                else:
                    stats["errors"] += 1
            except Exception as e:
                logger.error(f"批量更新中事件处理失败: {e}")
                stats["errors"] += 1

        return stats

    def get_processed_count(self) -> int:
        """已处理事件数"""
        return len(self._processed_events)

    def reset_processed(self):
        """重置已处理记录"""
        self._processed_events.clear()
