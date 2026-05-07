"""实体风险链模块 - 通过知识图谱追踪风险传导路径

从文案中提取命名实体，在知识图谱中查询关联实体和争议事件，
追踪风险传导路径，评估风险传导概率。
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class RiskChainNode:
    """风险链中的一个节点"""
    entity_name: str = ""
    entity_type: str = ""           # Person/Brand/Organization/Event/Topic
    risk_level: str = "low"         # low / medium / high
    controversy: str = ""           # 关联争议描述
   传导概率: float = 0.0            # 从上一个节点传导到此节点的概率


@dataclass
class RiskChain:
    """一条完整的风险传导链"""
    chain_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_entity: str = ""         # 文案中的原始实体
    path: List[RiskChainNode] = field(default_factory=list)
    total_risk_score: float = 0.0   # 链路总风险分 0-1
    risk_dimensions: List[str] = field(default_factory=list)  # 涉及的风险维度
    description: str = ""           # 风险链描述


@dataclass
class EntityRiskChainResult:
    """实体风险链总结果"""
    entities: List[str] = field(default_factory=list)       # 提取到的命名实体
    chains: List[RiskChain] = field(default_factory=list)   # 风险传导链
    max_risk_score: float = 0.0                             # 最高风险分
    risk_dimension_boosts: dict = field(default_factory=dict)  # {维度: 提升值}
    analysis_summary: str = ""


# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------

ENTITY_EXTRACT_PROMPT = """请从以下文案中提取所有命名实体。

文案内容：
{text}

输出JSON格式：
{{
    "entities": [
        {{"name": "实体名", "type": "Person/Brand/Organization/Event/Topic/Location", "importance": 1}}
    ]
}}

要求：
1. 提取人名、品牌名、机构名、事件名、地名等
2. importance: 1=核心实体, 2=重要实体, 3=提及实体
3. 不要遗漏任何可能引发争议的实体"""

RISK_CHAIN_PROMPT = """以下是文案中的命名实体和已知的相关信息，请分析风险传导链。

文案中的实体：{entities}

已知关联信息：
{context}

请分析每条风险传导链：
1. 从文案实体出发，追踪可能的风险传导路径
2. 每个路径节点的风险级别和争议描述
3. 风险传导概率（0-1）
4. 链路总风险分
5. 涉及的风险维度

输出JSON格式：
{{
    "chains": [
        {{
            "source_entity": "实体名",
            "path": [
                {{
                    "entity_name": "关联实体",
                    "entity_type": "Brand",
                    "risk_level": "high",
                    "controversy": "该品牌近期陷入XX争议",
                    "传导概率": 0.7
                }}
            ],
            "total_risk_score": 0.8,
            "risk_dimensions": ["道德伦理", "群体冒犯"],
            "description": "文案提及的XX品牌近期因XX事件引发舆论争议，相关讨论可能波及本内容"
        }}
    ],
    "risk_dimension_boosts": {{"道德伦理": 0.15, "群体冒犯": 0.1}},
    "analysis_summary": "文案涉及2个实体存在风险传导链"
}}

注意：只输出确实存在风险传导的链路，无风险的不要输出。"""


class EntityRiskChain:
    """实体风险链 - 通过知识图谱追踪风险传导"""

    def __init__(self, graph_store=None):
        self._graph_store = graph_store  # 可选的GraphStore实例

    async def trace(self, text: str, max_depth: int = 3) -> EntityRiskChainResult:
        """主入口：从文案追踪实体风险链

        Args:
            text: 用户输入的文案
            max_depth: 风险链最大深度

        Returns:
            EntityRiskChainResult: 实体风险链结果
        """
        # 1. LLM提取文案命名实体
        entities = await self._extract_entities(text)
        logger.info("EntityRiskChain: 提取到 %d 个实体: %s", len(entities), entities)

        if not entities:
            return EntityRiskChainResult(entities=[], analysis_summary="未提取到命名实体")

        # 2. 从知识图谱查询关联信息
        context = self._query_graph_context(entities, max_depth)
        logger.info("EntityRiskChain: 图谱上下文长度 %d", len(context))

        # 3. LLM分析风险传导链
        result = await self._analyze_risk_chains(entities, context)
        return result

    async def _extract_entities(self, text: str) -> List[str]:
        """LLM提取文案中的命名实体"""
        prompt = ENTITY_EXTRACT_PROMPT.format(text=text[:2000])

        try:
            response = await call_llm(
                prompt,
                system="你是一个命名实体识别专家，擅长从中文文本中提取人名、品牌、机构等实体。",
                task_type="persona_simulation",
            )
            data = parse_llm_json(response, fallback={"entities": []})
            entities_data = data.get("entities", [])

            entities = []
            for e in entities_data:
                name = e.get("name", "").strip()
                if name:
                    entities.append(name)

            # 降级：如果LLM未返回实体，用简单规则
            if not entities:
                entities = self._fallback_entities(text)

            return entities

        except Exception as e:
            logger.error("EntityRiskChain: 实体提取失败 %s", e)
            return self._fallback_entities(text)

    def _fallback_entities(self, text: str) -> List[str]:
        """降级：简单规则提取实体"""
        import re
        # 匹配2-4个中文字符的专有名词（简单启发式）
        entities = []
        # 匹配引号内的内容
        quoted = re.findall(r'[""「」『』](.+?)[""「」『』]', text)
        entities.extend(quoted[:5])
        # 匹配含"品牌/公司/集团"等后缀的
        orgs = re.findall(r'[\u4e00-\u9fff]{2,6}(?:品牌|公司|集团|机构|大学)', text)
        entities.extend(orgs[:3])
        return entities[:8]

    def _query_graph_context(self, entities: List[str], max_depth: int) -> str:
        """从知识图谱查询实体关联信息"""
        if not self._graph_store or not self._graph_store.is_connected:
            logger.info("EntityRiskChain: Neo4j不可用，跳过图谱查询")
            return "知识图谱不可用，仅基于常识分析"

        context_parts = []
        try:
            for entity_name in entities[:10]:
                # 搜索实体
                found = self._graph_store.search_entities(entity_name, limit=5)
                if found:
                    for e in found:
                        eid = e.get("entity_id", "")
                        name = e.get("name", "")
                        context_parts.append(f"实体: {name} (ID: {eid})")

                        # 获取关联关系
                        relations = self._graph_store.get_relations(eid, limit=10)
                        for r in relations:
                            target = r.get("target", {})
                            rel = r.get("relation", {})
                            target_name = target.get("name", "")
                            rel_type = r.get("type", "RELATED")
                            context_parts.append(
                                f"  - {name} --[{rel_type}]--> {target_name}"
                            )

                        # 获取子图（限制深度）
                        if max_depth >= 2:
                            subgraph = self._graph_store.get_subgraph(eid, depth=min(max_depth, 2), limit=30)
                            for edge in subgraph.get("edges", []):
                                context_parts.append(
                                    f"  图谱边: {edge.get('source', '')} --[{edge.get('type', '')}]--> {edge.get('target', '')}"
                                )

        except Exception as e:
            logger.error("EntityRiskChain: 图谱查询失败 %s", e)
            return "图谱查询异常，仅基于常识分析"

        return "\n".join(context_parts) if context_parts else "图谱中无相关实体信息"

    async def _analyze_risk_chains(
        self, entities: List[str], context: str
    ) -> EntityRiskChainResult:
        """LLM分析风险传导链"""
        prompt = RISK_CHAIN_PROMPT.format(
            entities=", ".join(entities),
            context=context[:3000],  # 限制上下文长度
        )

        try:
            response = await call_llm(
                prompt,
                system="你是一个舆情风险分析专家，擅长追踪实体间的风险传导路径和争议关联。",
                task_type="risk_assessment",
            )
            data = parse_llm_json(response, fallback={
                "chains": [],
                "risk_dimension_boosts": {},
                "analysis_summary": "分析失败",
            })

            chains: List[RiskChain] = []
            for c in data.get("chains", []):
                path: List[RiskChainNode] = []
                for p in c.get("path", []):
                    path.append(RiskChainNode(
                        entity_name=p.get("entity_name", ""),
                        entity_type=p.get("entity_type", ""),
                        risk_level=p.get("risk_level", "low"),
                        controversy=p.get("controversy", ""),
                        传导概率=min(1.0, max(0.0, p.get("传导概率", 0.0))),
                    ))

                chains.append(RiskChain(
                    source_entity=c.get("source_entity", ""),
                    path=path,
                    total_risk_score=min(1.0, max(0.0, c.get("total_risk_score", 0.0))),
                    risk_dimensions=c.get("risk_dimensions", []),
                    description=c.get("description", ""),
                ))

            # 按风险分排序
            chains.sort(key=lambda c: c.total_risk_score, reverse=True)
            max_risk = max((c.total_risk_score for c in chains), default=0.0)

            return EntityRiskChainResult(
                entities=entities,
                chains=chains,
                max_risk_score=max_risk,
                risk_dimension_boosts=data.get("risk_dimension_boosts", {}),
                analysis_summary=data.get("analysis_summary", ""),
            )

        except Exception as e:
            logger.error("EntityRiskChain: 风险链分析失败 %s", e)
            return self._fallback_risk_chain(entities)

    def _fallback_risk_chain(self, entities: List[str]) -> EntityRiskChainResult:
        """降级：基于关键词的简单风险推断"""
        # 高风险关键词映射
        risk_keywords = {
            "政治敏感": ["政府", "领导", "政策", "体制", "敏感"],
            "法律合规": ["违法", "犯罪", "官司", "侵权", "造假"],
            "道德伦理": ["出轨", "代孕", "塌房", "翻车", "卖惨"],
            "群体冒犯": ["歧视", "侮辱", "贬低", "刻板印象"],
            "性别议题": ["性别", "女权", "男权", "歧视"],
            "民族宗教": ["民族", "宗教", "信仰"],
            "时事踩雷": ["热搜", "争议", "风波", "丑闻"],
        }

        chains: List[RiskChain] = []
        dimension_boosts: dict = {}

        for entity in entities:
            for dim, keywords in risk_keywords.items():
                if any(kw in entity for kw in keywords):
                    chains.append(RiskChain(
                        source_entity=entity,
                        path=[RiskChainNode(
                            entity_name=entity,
                            entity_type="Unknown",
                            risk_level="medium",
                            controversy=f"实体包含{dim}相关关键词",
                            传导概率=0.5,
                        )],
                        total_risk_score=0.4,
                        risk_dimensions=[dim],
                        description=f"实体'{entity}'可能涉及{dim}风险",
                    ))
                    dimension_boosts[dim] = dimension_boosts.get(dim, 0.0) + 0.1

        return EntityRiskChainResult(
            entities=entities,
            chains=chains,
            max_risk_score=max((c.total_risk_score for c in chains), default=0.0),
            risk_dimension_boosts=dimension_boosts,
            analysis_summary=f"识别到 {len(chains)} 条潜在风险链（降级模式）" if chains else "未发现明显风险链",
        )
