"""GraphStore — Neo4j 图数据库 CRUD 与查询"""

import logging
from typing import Any, Dict, List, Optional

from backend.services.graph.models import Entity, Relation, GraphOntology

logger = logging.getLogger(__name__)


class GraphStore:
    """Neo4j 图存储"""

    def __init__(self, uri: str = "bolt://localhost:7687",
                 user: str = "neo4j", password: str = "vibeutopia"):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    # ── 连接管理 ──────────────────────────────────────

    def connect(self):
        """建立 Neo4j 连接"""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            # 验证连接
            self._driver.verify_connectivity()
            logger.info(f"Neo4j 连接成功: {self.uri}")
        except ImportError:
            logger.warning("neo4j 驱动未安装，使用内存模式")
            self._driver = None
        except Exception as e:
            logger.warning(f"Neo4j 连接失败: {e}，使用内存模式")
            self._driver = None

    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None

    @property
    def is_connected(self) -> bool:
        return self._driver is not None

    # ── Schema 管理 ───────────────────────────────────

    def create_constraints(self, ontology: GraphOntology):
        """为本体中的实体类型创建唯一性约束"""
        if not self.is_connected:
            return
        with self._driver.session() as session:
            for et in ontology.entity_types:
                label = et.name
                try:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                        f"REQUIRE n.entity_id IS UNIQUE"
                    )
                except Exception as e:
                    logger.debug(f"约束 {label} 已存在或创建失败: {e}")

    # ── 实体 CRUD ─────────────────────────────────────

    def save_entity(self, entity: Entity) -> bool:
        """保存或更新实体"""
        if not self.is_connected:
            return False
        try:
            with self._driver.session() as session:
                props = {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    **{f"prop_{k}": str(v) for k, v in entity.properties.items()},
                }
                session.run(
                    f"MERGE (n:{entity.entity_type} {{entity_id: $entity_id}}) "
                    f"SET n += $props",
                    entity_id=entity.entity_id,
                    props=props,
                )
            return True
        except Exception as e:
            logger.error(f"保存实体失败: {e}")
            return False

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """按 ID 获取实体"""
        if not self.is_connected:
            return None
        try:
            with self._driver.session() as session:
                result = session.run(
                    "MATCH (n {entity_id: $entity_id}) RETURN n",
                    entity_id=entity_id,
                )
                record = result.single()
                if record:
                    return dict(record["n"])
            return None
        except Exception as e:
            logger.error(f"获取实体失败: {e}")
            return None

    def search_entities(self, name: str, entity_type: Optional[str] = None,
                        limit: int = 20) -> List[Dict]:
        """按名称模糊搜索实体"""
        if not self.is_connected:
            return []
        try:
            label_clause = f":{entity_type}" if entity_type else ""
            with self._driver.session() as session:
                result = session.run(
                    f"MATCH (n{label_clause}) "
                    f"WHERE n.name CONTAINS $name "
                    f"RETURN n LIMIT $limit",
                    name=name, limit=limit,
                )
                return [dict(r["n"]) for r in result]
        except Exception as e:
            logger.error(f"搜索实体失败: {e}")
            return []

    def delete_entity(self, entity_id: str) -> bool:
        """删除实体及其所有关系"""
        if not self.is_connected:
            return False
        try:
            with self._driver.session() as session:
                session.run(
                    "MATCH (n {entity_id: $entity_id}) DETACH DELETE n",
                    entity_id=entity_id,
                )
            return True
        except Exception as e:
            logger.error(f"删除实体失败: {e}")
            return False

    # ── 关系 CRUD ─────────────────────────────────────

    def save_relation(self, relation: Relation) -> bool:
        """保存关系"""
        if not self.is_connected:
            return False
        try:
            with self._driver.session() as session:
                props = {
                    "relation_id": relation.relation_id,
                    "weight": relation.weight,
                    **{f"prop_{k}": str(v) for k, v in relation.properties.items()},
                }
                session.run(
                    f"MATCH (a {{entity_id: $source_id}}) "
                    f"MATCH (b {{entity_id: $target_id}}) "
                    f"MERGE (a)-[r:{relation.relation_type}]->(b) "
                    f"SET r += $props",
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    props=props,
                )
            return True
        except Exception as e:
            logger.error(f"保存关系失败: {e}")
            return False

    def get_relations(self, entity_id: str, direction: str = "both",
                      relation_type: Optional[str] = None,
                      limit: int = 50) -> List[Dict]:
        """获取实体的关系"""
        if not self.is_connected:
            return []
        try:
            rel_type = f":{relation_type}" if relation_type else ""
            if direction == "out":
                pattern = f"(a {{entity_id: $entity_id}})-[r{rel_type}]->(b)"
            elif direction == "in":
                pattern = f"(a {{entity_id: $entity_id}})<-[r{rel_type}]-(b)"
            else:
                pattern = f"(a {{entity_id: $entity_id}})-[r{rel_type}]-(b)"

            with self._driver.session() as session:
                result = session.run(
                    f"MATCH {pattern} RETURN a, r, b LIMIT $limit",
                    entity_id=entity_id, limit=limit,
                )
                records = []
                for r in result:
                    records.append({
                        "source": dict(r["a"]),
                        "relation": dict(r["r"]),
                        "target": dict(r["b"]),
                    })
                return records
        except Exception as e:
            logger.error(f"获取关系失败: {e}")
            return []

    # ── 图查询 ────────────────────────────────────────

    def get_subgraph(self, entity_id: str, depth: int = 2,
                     limit: int = 100) -> Dict[str, List]:
        """获取以某实体为中心的子图"""
        if not self.is_connected:
            return {"nodes": [], "edges": []}
        try:
            with self._driver.session() as session:
                result = session.run(
                    f"MATCH path = (center {{entity_id: $entity_id}})-[*1..{depth}]-(other) "
                    f"RETURN path LIMIT $limit",
                    entity_id=entity_id, limit=limit,
                )
                nodes = {}
                edges = []
                for record in result:
                    path = record["path"]
                    for node in path.nodes:
                        nid = dict(node).get("entity_id", str(node.id))
                        if nid not in nodes:
                            nodes[nid] = dict(node)
                    for rel in path.relationships:
                        edges.append({
                            "source": dict(rel.start_node).get("entity_id", "") if rel.start_node else "",
                            "target": dict(rel.end_node).get("entity_id", "") if rel.end_node else "",
                            "type": rel.type,
                            "weight": dict(rel).get("weight", 1.0),
                        })
                return {"nodes": list(nodes.values()), "edges": edges}
        except Exception as e:
            logger.error(f"获取子图失败: {e}")
            return {"nodes": [], "edges": []}

    def get_shortest_path(self, from_id: str, to_id: str,
                          max_depth: int = 5) -> List[Dict]:
        """两个实体间的最短路径"""
        if not self.is_connected:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(
                    f"MATCH path = shortestPath("
                    f"(a {{entity_id: $from_id}})-[*..{max_depth}]-(b {{entity_id: $to_id}})"
                    f") RETURN path",
                    from_id=from_id, to_id=to_id,
                )
                record = result.single()
                if not record:
                    return []
                path = record["path"]
                steps = []
                for i, node in enumerate(path.nodes):
                    steps.append({"step": i, "node": dict(node)})
                return steps
        except Exception as e:
            logger.error(f"最短路径查询失败: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        if not self.is_connected:
            return {"connected": False, "node_count": 0, "relation_count": 0}
        try:
            with self._driver.session() as session:
                nc = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rc = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                labels = session.run("CALL db.labels()").value()
                rel_types = session.run("CALL db.relationshipTypes()").value()
                return {
                    "connected": True,
                    "node_count": nc,
                    "relation_count": rc,
                    "labels": labels,
                    "relationship_types": rel_types,
                }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"connected": False, "node_count": 0, "relation_count": 0, "error": str(e)}

    # ── 批量操作 ──────────────────────────────────────

    def save_extraction_result(self, result) -> int:
        """批量保存抽取结果，返回保存的关系数"""
        saved = 0
        entity_id_map = {}
        for entity in result.entities:
            ok = self.save_entity(entity)
            if ok:
                entity_id_map[entity.name] = entity.entity_id
        for relation in result.relations:
            ok = self.save_relation(relation)
            if ok:
                saved += 1
        return saved

    def clear_all(self):
        """清空图数据库"""
        if not self.is_connected:
            return
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("图数据库已清空")
