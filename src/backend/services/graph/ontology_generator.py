"""本体生成器 — 根据领域文本动态生成本体，失败时使用内置模板"""

import logging
from typing import Optional

from backend.services.graph.models import EntityDef, RelationDef, GraphOntology
from backend.services.graph.ontology_templates import get_default_ontology
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

ONTOLOGY_PROMPT = """你是一个知识图谱本体设计专家。请根据以下领域描述，设计一套适合中文社交媒体场景的知识图谱本体。

领域描述：
{domain_description}

请输出JSON格式，包含 entity_types 和 relation_types 两个字段：
- entity_types: 实体类型列表，每个包含 name, description, properties(属性名列表)
- relation_types: 关系类型列表，每个包含 name, source, target, description

要求：
1. 实体类型 8-15 个，覆盖人物、组织、事件、概念等核心类型
2. 关系类型 8-15 个，覆盖影响、参与、支持、反对等核心关系
3. 所有名称使用英文大驼峰，描述使用中文
4. properties 列出 3-5 个关键属性名
5. relation_types 的 source/target 必须是 entity_types 中已有的类型名

输出格式示例：
{{
  "entity_types": [
    {{"name": "Person", "description": "公众人物", "properties": ["name", "role"]}}
  ],
  "relation_types": [
    {{"name": "INFLUENCES", "source": "Event", "target": "Person", "description": "事件影响个人"}}
  ]
}}"""


async def generate_ontology(domain_description: str) -> GraphOntology:
    """根据领域描述动态生成本体

    Args:
        domain_description: 领域描述文本

    Returns:
        GraphOntology 实例
    """
    try:
        prompt = ONTOLOGY_PROMPT.format(domain_description=domain_description)
        resp = await call_llm(prompt)
        data = parse_llm_json(resp)

        if not data or "entity_types" not in data:
            logger.warning("LLM本体生成返回格式异常，使用内置模板")
            return get_default_ontology()

        entity_types = []
        for et in data.get("entity_types", []):
            entity_types.append(EntityDef(
                name=et.get("name", "Unknown"),
                description=et.get("description", ""),
                properties=et.get("properties", []),
            ))

        relation_types = []
        for rt in data.get("relation_types", []):
            relation_types.append(RelationDef(
                name=rt.get("name", "RELATED_TO"),
                source=rt.get("source", "Entity"),
                target=rt.get("target", "Entity"),
                description=rt.get("description", ""),
            ))

        if len(entity_types) < 3:
            logger.warning("LLM生成的实体类型不足3个，使用内置模板")
            return get_default_ontology()

        ontology = GraphOntology(
            entity_types=entity_types,
            relation_types=relation_types,
        )
        logger.info(f"LLM本体生成成功: {len(entity_types)}个实体类型, {len(relation_types)}个关系类型")
        return ontology

    except Exception as e:
        logger.error(f"LLM本体生成失败: {e}, 使用内置模板")
        return get_default_ontology()


def load_ontology(ontology_name: Optional[str] = None) -> GraphOntology:
    """加载本体模板

    Args:
        ontology_name: 本体名称，None则使用默认模板

    Returns:
        GraphOntology 实例
    """
    if ontology_name is None or ontology_name == "default":
        return get_default_ontology()

    logger.warning(f"未知的本体模板: {ontology_name}，使用默认模板")
    return get_default_ontology()
