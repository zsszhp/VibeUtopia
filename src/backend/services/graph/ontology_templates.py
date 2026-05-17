"""内置中文社交领域本体模板 — LLM生成失败时的兜底"""

from backend.services.graph.models import EntityDef, RelationDef, GraphOntology


def get_default_ontology() -> GraphOntology:
    """返回内置中文社交领域本体模板"""
    return GraphOntology(
        entity_types=[
            EntityDef(
                name="Person",
                description="公众人物、明星、政治人物、意见领袖等",
                properties=["name", "role", "influence_area", "platform", "gender"],
            ),
            EntityDef(
                name="Organization",
                description="企业、机构、政府部门、NGO等",
                properties=["name", "type", "industry", "scale"],
            ),
            EntityDef(
                name="Event",
                description="社会事件、新闻事件、争议事件等",
                properties=["name", "category", "time", "impact_level"],
            ),
            EntityDef(
                name="Concept",
                description="抽象概念、议题、价值观等",
                properties=["name", "domain", "controversy_level"],
            ),
            EntityDef(
                name="Location",
                description="地理位置、区域、城市等",
                properties=["name", "level", "region"],
            ),
            EntityDef(
                name="Policy",
                description="政策、法规、规定等",
                properties=["name", "issuer", "effective_date", "scope"],
            ),
            EntityDef(
                name="Industry",
                description="行业、产业领域等",
                properties=["name", "size", "growth_rate"],
            ),
            EntityDef(
                name="Platform",
                description="社交媒体平台、内容平台等",
                properties=["name", "type", "user_scale"],
            ),
            EntityDef(
                name="Product",
                description="产品、品牌、服务项目等",
                properties=["name", "brand", "category", "price_range"],
            ),
            EntityDef(
                name="SocialGroup",
                description="社会群体、阶层、圈层等",
                properties=["name", "size", "demographic", "core_values"],
            ),
        ],
        relation_types=[
            RelationDef(
                name="INFLUENCES",
                source="Event", target="Person",
                description="事件影响了个人的立场或行为",
            ),
            RelationDef(
                name="BELONGS_TO",
                source="Person", target="Organization",
                description="个人从属于某个组织",
            ),
            RelationDef(
                name="TRIGGERS",
                source="Event", target="Event",
                description="一个事件触发了另一个事件",
            ),
            RelationDef(
                name="OPPOSES",
                source="Person", target="Concept",
                description="个人反对某个概念或立场",
            ),
            RelationDef(
                name="SUPPORTS",
                source="Person", target="Concept",
                description="个人支持某个概念或立场",
            ),
            RelationDef(
                name="PARTICIPATES",
                source="Person", target="Event",
                description="个人参与了某个事件",
            ),
            RelationDef(
                name="LOCATED_IN",
                source="Event", target="Location",
                description="事件发生在某地",
            ),
            RelationDef(
                name="RELATED_TO",
                source="Entity", target="Entity",
                description="两个实体有关联（通用）",
            ),
            RelationDef(
                name="EMPLOYS",
                source="Organization", target="Person",
                description="组织雇佣了个人",
            ),
            RelationDef(
                name="MENTIONS",
                source="Event", target="Product",
                description="事件中提及了某产品或品牌",
            ),
        ],
    )
