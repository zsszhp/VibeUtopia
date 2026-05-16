"""GraphUpdater — 增量更新与事件驱动的图谱维护 + 跨视频实体对齐"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.graph.models import Entity, Relation, ExtractionResult
from backend.services.graph.entity_extractor import extract_from_event
from backend.services.graph.graph_store import GraphStore
from backend.services.graph.ontology_generator import load_ontology
from backend.services.llm_client import call_llm

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

    async def align_and_merge_entities(
        self,
        new_entities: List[Entity],
        blogger_id: str,
        similarity_threshold: float = 0.7,
    ) -> List[Entity]:
        """跨视频实体对齐合并（VideoRAG核心思想）

        1. 对新实体与已有图谱进行语义匹配
        2. 等价实体合并（如"AI替代人工"和"人工智能取代人类"）
        3. 新实体添加到图谱
        4. 更新实体的多来源描述

        Args:
            new_entities: 新抽取的实体列表
            blogger_id: 博主ID
            similarity_threshold: 语义相似度阈值，高于此值视为等价

        Returns:
            合并后的实体列表（含已有实体ID的映射）
        """
        merged_entities = []
        merge_count = 0

        for entity in new_entities:
            existing = self.store.search_entities(
                entity.name, entity.entity_type, limit=5
            )

            best_match = None
            best_score = 0.0

            if existing:
                best_match, best_score = await self._find_best_match(
                    entity, existing
                )

            if best_match and best_score >= similarity_threshold:
                existing_id = best_match.get("entity_id", "")
                if existing_id:
                    self._merge_entity_properties(existing_id, entity)
                    entity.entity_id = existing_id
                    merge_count += 1
                    logger.debug(
                        "实体对齐合并: '%s' → 已有实体 '%s' (相似度=%.2f)",
                        entity.name,
                        best_match.get("name", ""),
                        best_score,
                    )
            else:
                saved = self.store.save_entity(entity)
                if saved:
                    merged_entities.append(entity)

        logger.info(
            "跨视频实体对齐完成: %d个新实体, %d个合并, %d个新增",
            len(new_entities), merge_count, len(merged_entities),
        )
        return merged_entities

    async def _find_best_match(
        self, entity: Entity, candidates: List[Dict]
    ) -> tuple:
        """用LLM判断新实体与候选实体的最佳匹配

        Returns:
            (best_match_dict, similarity_score)
        """
        if not candidates:
            return None, 0.0

        if len(candidates) == 1:
            name_sim = self._name_similarity(entity.name, candidates[0].get("name", ""))
            if name_sim > 0.8:
                return candidates[0], name_sim

        candidate_desc = "\n".join(
            f"{i+1}. 名称: {c.get('name', '')}, 类型: {c.get('entity_type', '')}"
            for i, c in enumerate(candidates[:5])
        )

        prompt = f"""判断以下新实体与哪个已有实体是同一个（语义等价）：

新实体: 名称="{entity.name}", 类型="{entity.entity_type}"

已有实体:
{candidate_desc}

请输出JSON: {{"match_index": 0或匹配序号(1-5), "similarity": 0.0-1.0}}
如果没有匹配的，match_index设为0，similarity设为0.0。"""

        try:
            from backend.services.llm_client import parse_llm_json
            response = await call_llm(
                prompt,
                system="你是一个实体对齐专家，判断两个实体是否指代同一事物。",
                task_type="default",
            )
            result = parse_llm_json(response, fallback={"match_index": 0, "similarity": 0.0})

            match_idx = int(result.get("match_index", 0))
            similarity = float(result.get("similarity", 0.0))

            if match_idx > 0 and match_idx <= len(candidates):
                return candidates[match_idx - 1], similarity

        except Exception as e:
            logger.warning("LLM实体匹配失败，降级为名称相似度: %s", e)

        best = None
        best_score = 0.0
        for c in candidates:
            score = self._name_similarity(entity.name, c.get("name", ""))
            if score > best_score:
                best_score = score
                best = c
        return best, best_score

    def _name_similarity(self, name1: str, name2: str) -> float:
        """简单的名称相似度计算（字符重叠率）"""
        if not name1 or not name2:
            return 0.0
        if name1 == name2:
            return 1.0
        if name1 in name2 or name2 in name1:
            return 0.85
        set1 = set(name1)
        set2 = set(name2)
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union) if union else 0.0

    def _merge_entity_properties(self, existing_id: str, new_entity: Entity):
        """将新实体的属性合并到已有实体"""
        existing = self.store.get_entity(existing_id)
        if not existing:
            return

        merged_props = existing.get("properties", {})
        if isinstance(merged_props, str):
            import json
            try:
                merged_props = json.loads(merged_props)
            except Exception:
                merged_props = {}

        for key, value in new_entity.properties.items():
            if key not in merged_props:
                merged_props[key] = value
            elif isinstance(merged_props[key], list):
                if value not in merged_props[key]:
                    merged_props[key].append(value)
            elif merged_props[key] != value:
                merged_props[f"{key}_alt"] = value

        merged_props["last_merged"] = datetime.now(timezone.utc).isoformat()

        update_entity = Entity(
            entity_id=existing_id,
            entity_type=new_entity.entity_type,
            name=existing.get("name", new_entity.name),
            properties=merged_props,
        )
        self.store.save_entity(update_entity)
