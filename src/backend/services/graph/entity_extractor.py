"""实体抽取器 — 从种子事件文本中抽取实体和关系"""

import json
import logging
from typing import List, Optional

from backend.services.graph.models import Entity, Relation, ExtractionResult, EntityType
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一个知识图谱实体关系抽取专家。请从以下事件文本中抽取实体和关系。

事件标题: {title}
事件描述: {description}
事件评论摘要: {comments_summary}

可用的实体类型: {entity_types}
可用的关系类型: {relation_types}

请输出JSON格式：
{{
  "entities": [
    {{
      "entity_type": "实体类型（必须是上面列出的之一）",
      "name": "实体名称",
      "properties": {{"属性名": "属性值"}}
    }}
  ],
  "relations": [
    {{
      "relation_type": "关系类型（必须是上面列出的之一）",
      "source_name": "源实体名称（必须在entities中出现）",
      "target_name": "目标实体名称（必须在entities中出现）",
      "weight": 0.8,
      "properties": {{"属性名": "属性值"}}
    }}
  ]
}}

要求：
1. 尽可能多抽取有意义的实体，至少5个
2. 关系必须有明确的源和目标，且都在entities中
3. weight 范围 0.0-1.0，表示关系强度
4. properties 中的值要具体、有信息量
5. 所有文本内容使用中文"""


async def extract_from_event(
    title: str,
    description: str = "",
    comments_summary: str = "",
    entity_types: Optional[List[str]] = None,
    relation_types: Optional[List[str]] = None,
    source_event_id: Optional[str] = None,
) -> ExtractionResult:
    """从单个事件中抽取实体和关系

    Args:
        title: 事件标题
        description: 事件描述
        comments_summary: 评论摘要
        entity_types: 可用实体类型列表
        relation_types: 可用关系类型列表
        source_event_id: 源事件ID

    Returns:
        ExtractionResult
    """
    if entity_types is None:
        entity_types = [e.value for e in EntityType]
    if relation_types is None:
        from backend.services.graph.models import RelationType
        relation_types = [r.value for r in RelationType]

    try:
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            description=description or "无",
            comments_summary=comments_summary or "无",
            entity_types=", ".join(entity_types),
            relation_types=", ".join(relation_types),
        )

        resp = await call_llm(prompt)
        data = parse_llm_json(resp)

        if not data:
            return _fallback_extraction(title, description, source_event_id)

        # 构建实体名称到实体的映射
        entity_name_map = {}
        entities = []
        for ent_data in data.get("entities", []):
            entity = Entity(
                entity_type=ent_data.get("entity_type", "Event"),
                name=ent_data.get("name", "未知"),
                properties=ent_data.get("properties", {}),
                source_event_id=source_event_id,
            )
            entities.append(entity)
            entity_name_map[entity.name] = entity

        # 构建关系（通过名称匹配源和目标）
        relations = []
        for rel_data in data.get("relations", []):
            source_name = rel_data.get("source_name", "")
            target_name = rel_data.get("target_name", "")

            # 尝试模糊匹配
            source_entity = _find_entity(source_name, entity_name_map)
            target_entity = _find_entity(target_name, entity_name_map)

            if source_entity and target_entity:
                relation = Relation(
                    relation_type=rel_data.get("relation_type", "RELATED_TO"),
                    source_id=source_entity.entity_id,
                    target_id=target_entity.entity_id,
                    weight=min(1.0, max(0.0, float(rel_data.get("weight", 0.5)))),
                    properties=rel_data.get("properties", {}),
                )
                relations.append(relation)

        logger.info(f"抽取完成: {len(entities)}个实体, {len(relations)}个关系")
        return ExtractionResult(
            entities=entities,
            relations=relations,
            source_event_id=source_event_id,
        )

    except Exception as e:
        logger.error(f"实体抽取失败: {e}")
        return _fallback_extraction(title, description, source_event_id)


def _find_entity(name: str, entity_map: dict) -> Optional[Entity]:
    """精确匹配 + 前缀/包含模糊匹配"""
    if name in entity_map:
        return entity_map[name]
    for key, entity in entity_map.items():
        if name in key or key in name:
            return entity
    return None


def _fallback_extraction(
    title: str, description: str, source_event_id: Optional[str]
) -> ExtractionResult:
    """规则兜底：从标题中提取事件实体"""
    event_entity = Entity(
        entity_type="Event",
        name=title[:50],
        properties={"raw_title": title, "raw_description": (description or "")[:200]},
        source_event_id=source_event_id,
    )
    return ExtractionResult(
        entities=[event_entity],
        relations=[],
        source_event_id=source_event_id,
    )
