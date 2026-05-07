"""图谱注入器 — 将知识图谱实体注入Agent的L3/L6层"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphInjector:
    """从知识图谱中提取实体，注入Agent人格模板"""

    def __init__(self, graph_store=None):
        """
        Args:
            graph_store: GraphStore 实例，None时跳过图谱注入
        """
        self.store = graph_store

    def inject(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        """将图谱相关实体注入人格模板

        注入策略：
        - L3知识背景：根据Agent的职业领域和关注点，从图谱搜索相关实体
        - L6社会关系：根据Agent的关注领域，从图谱搜索相关KOL/组织

        Args:
            persona: 7层人格字典

        Returns:
            注入后的人格字典（深拷贝）
        """
        import copy
        persona = copy.deepcopy(persona)

        if not self.store or not self.store.is_connected:
            logger.debug("图谱未连接，跳过注入")
            return persona

        try:
            self._inject_knowledge(persona)
            self._inject_social(persona)
        except Exception as e:
            logger.warning(f"图谱注入失败（不影响人格生成）: {e}")

        return persona

    def _inject_knowledge(self, persona: Dict[str, Any]):
        """注入L3知识背景层"""
        l1 = persona.get("L1_basic", {})
        l3 = persona.setdefault("L3_knowledge", {})

        # 根据职业和关注点搜索图谱实体
        search_terms = []
        occupation = l1.get("occupation", "")
        if occupation:
            search_terms.append(occupation)

        domains = l3.get("professional_domains", [])
        search_terms.extend(domains[:3])

        related_entities = []
        for term in search_terms:
            if not term:
                continue
            try:
                results = self.store.search_entities(term, limit=3)
                for r in results:
                    name = r.get("name", "")
                    etype = r.get("entity_id", "")
                    if name and name not in related_entities:
                        related_entities.append(name)
            except Exception:
                continue

        if related_entities:
            # 注入到信息源
            existing_sources = l3.get("information_sources", [])
            for entity_name in related_entities[:5]:
                if entity_name not in existing_sources:
                    existing_sources.append(entity_name)
            l3["information_sources"] = existing_sources

            # 注入到知识领域
            existing_domains = l3.get("professional_domains", [])
            for entity_name in related_entities[:3]:
                if entity_name not in existing_domains:
                    existing_domains.append(entity_name)
            l3["professional_domains"] = existing_domains

            # 标记图谱注入来源
            l3["graph_enhanced"] = True

    def _inject_social(self, persona: Dict[str, Any]):
        """注入L6社会关系层"""
        l6 = persona.setdefault("L6_social", {})
        l3 = persona.get("L3_knowledge", {})

        # 根据关注领域搜索相关人物/组织
        domains = l3.get("professional_domains", [])
        search_terms = domains[:2]

        related_persons = []
        related_orgs = []
        for term in search_terms:
            if not term:
                continue
            try:
                # 搜索人物
                persons = self.store.search_entities(term, entity_type="Person", limit=3)
                for p in persons:
                    name = p.get("name", "")
                    if name and name not in related_persons:
                        related_persons.append(name)

                # 搜索组织
                orgs = self.store.search_entities(term, entity_type="Organization", limit=2)
                for o in orgs:
                    name = o.get("name", "")
                    if name and name not in related_orgs:
                        related_orgs.append(name)
            except Exception:
                continue

        if related_persons:
            existing_kol = l6.get("followed_kol_domains", [])
            for person in related_persons[:3]:
                if person not in existing_kol:
                    existing_kol.append(person)
            l6["followed_kol_domains"] = existing_kol

        if related_orgs:
            existing_circles = l6.get("social_circles", [])
            for org in related_orgs[:2]:
                if org not in existing_circles:
                    existing_circles.append(org)
            l6["social_circles"] = existing_circles

        if related_persons or related_orgs:
            l6["graph_enhanced"] = True
