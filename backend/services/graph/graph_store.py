"""GraphStore — Neo4j 图数据库 CRUD 与查询

支持 Neo4j 主存储 + MySQL/SQLite 降级模式：
- Neo4j 可用时：所有图操作走 Neo4j
- Neo4j 不可用时：自动降级到关系型数据库（通过 SQLAlchemy）
- 提供 is_neo4j_available 属性和 get_status() 方法查询当前状态
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.services.graph.models import Entity, Relation, GraphOntology

logger = logging.getLogger(__name__)


class GraphStore:
    """Neo4j 图存储，支持降级到关系型数据库"""

    def __init__(self, uri: str = "bolt://localhost:7687",
                 user: str = "neo4j", password: str = "vibeutopia"):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None
        self._neo4j_available = False
        self._fallback_mode = False
        self._fallback_entities: Dict[str, Dict] = {}
        self._fallback_relations: Dict[str, Dict] = {}

    # ── 连接管理 ──────────────────────────────────────

    def connect(self):
        """建立 Neo4j 连接，失败时降级到关系型数据库"""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self._driver.verify_connectivity()
            self._neo4j_available = True
            self._fallback_mode = False
            logger.info("Neo4j 连接成功: %s", self.uri)
        except ImportError:
            logger.warning("neo4j 驱动未安装，降级到关系型数据库模式")
            self._driver = None
            self._neo4j_available = False
            self._fallback_mode = True
            self._init_fallback()
        except Exception as e:
            logger.warning("Neo4j 连接失败: %s，降级到关系型数据库模式", e)
            self._driver = None
            self._neo4j_available = False
            self._fallback_mode = True
            self._init_fallback()

    def _init_fallback(self):
        """初始化降级模式：尝试从关系型数据库加载已有图数据"""
        try:
            from backend.database import get_db, SessionLocal
            from backend.models import AgentRecord, SocialRelation

            db = SessionLocal()
            try:
                relations = db.query(SocialRelation).limit(1000).all()
                for rel in relations:
                    self._fallback_relations[rel.relation_type + "_" + str(rel.id)] = {
                        "relation_id": str(rel.id),
                        "relation_type": rel.relation_type,
                        "source_id": rel.agent_id_a,
                        "target_id": rel.agent_id_b,
                        "weight": rel.weight,
                        "properties": {},
                    }

                agents = db.query(AgentRecord).limit(1000).all()
                for agent in agents:
                    self._fallback_entities[agent.agent_id] = {
                        "entity_id": agent.agent_id,
                        "name": agent.archetype_base or agent.agent_id,
                        "entity_type": "Agent",
                        "properties": {"platform": agent.platform or ""},
                    }

                logger.info("降级模式初始化完成: %d 实体, %d 关系",
                            len(self._fallback_entities), len(self._fallback_relations))
            finally:
                db.close()
        except Exception as e:
            logger.warning("降级模式初始化失败（将使用内存模式）: %s", e)

    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._neo4j_available = False

    @property
    def is_connected(self) -> bool:
        return self._driver is not None

    @property
    def is_neo4j_available(self) -> bool:
        """Neo4j 是否可用"""
        return self._neo4j_available and self._driver is not None

    def get_status(self) -> Dict[str, Any]:
        """返回当前数据库状态

        Returns:
            包含模式、连接状态、统计信息的字典
        """
        if self.is_neo4j_available:
            stats = self.get_stats()
            return {
                "mode": "neo4j",
                "neo4j_available": True,
                "fallback_mode": False,
                "connected": stats.get("connected", False),
                "node_count": stats.get("node_count", 0),
                "relation_count": stats.get("relation_count", 0),
                "uri": self.uri,
            }
        else:
            return {
                "mode": "fallback",
                "neo4j_available": False,
                "fallback_mode": True,
                "connected": True,
                "node_count": len(self._fallback_entities),
                "relation_count": len(self._fallback_relations),
                "uri": "sqlite/mysql",
                "message": "Neo4j 不可用，已降级到关系型数据库模式",
            }

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
                    logger.debug("约束 %s 已存在或创建失败: %s", label, e)

    # ── 实体 CRUD ─────────────────────────────────────

    def save_entity(self, entity: Entity) -> bool:
        """保存或更新实体（Neo4j 不可用时降级到关系型数据库）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 保存实体失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._save_entity_fallback(entity)
        else:
            return self._save_entity_fallback(entity)

    def _save_entity_fallback(self, entity: Entity) -> bool:
        """降级模式：将实体保存到关系型数据库"""
        try:
            self._fallback_entities[entity.entity_id] = {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "properties": entity.properties,
            }
            self._persist_entity_to_db(entity)
            return True
        except Exception as e:
            logger.error("降级模式保存实体失败: %s", e)
            return False

    def _persist_entity_to_db(self, entity: Entity):
        """将实体持久化到关系型数据库"""
        try:
            from backend.database import SessionLocal
            db = SessionLocal()
            try:
                from backend.models import AgentRecord
                existing = db.query(AgentRecord).filter(
                    AgentRecord.agent_id == entity.entity_id
                ).first()
                if existing:
                    existing.archetype_base = entity.name
                    existing.persona_json = json.dumps(entity.properties, ensure_ascii=False)
                else:
                    record = AgentRecord(
                        agent_id=entity.entity_id,
                        platform=entity.properties.get("platform", ""),
                        archetype_base=entity.name,
                        persona_json=json.dumps(entity.properties, ensure_ascii=False),
                    )
                    db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug("实体持久化到关系型数据库失败: %s", e)

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """按 ID 获取实体（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 获取实体失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._get_entity_fallback(entity_id)
        else:
            return self._get_entity_fallback(entity_id)

    def _get_entity_fallback(self, entity_id: str) -> Optional[Dict]:
        """降级模式：从内存缓存或关系型数据库获取实体"""
        if entity_id in self._fallback_entities:
            return self._fallback_entities[entity_id]
        try:
            from backend.database import SessionLocal
            from backend.models import AgentRecord
            db = SessionLocal()
            try:
                record = db.query(AgentRecord).filter(
                    AgentRecord.agent_id == entity_id
                ).first()
                if record:
                    entity_data = {
                        "entity_id": record.agent_id,
                        "name": record.archetype_base or record.agent_id,
                        "entity_type": "Agent",
                        "properties": json.loads(record.persona_json) if record.persona_json else {},
                    }
                    self._fallback_entities[entity_id] = entity_data
                    return entity_data
            finally:
                db.close()
        except Exception as e:
            logger.debug("降级模式获取实体失败: %s", e)
        return None

    def search_entities(self, name: str, entity_type: Optional[str] = None,
                        limit: int = 20) -> List[Dict]:
        """按名称模糊搜索实体（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 搜索实体失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._search_entities_fallback(name, entity_type, limit)
        else:
            return self._search_entities_fallback(name, entity_type, limit)

    def _search_entities_fallback(self, name: str, entity_type: Optional[str] = None,
                                  limit: int = 20) -> List[Dict]:
        """降级模式：从内存缓存中模糊搜索实体"""
        results = []
        for eid, entity in self._fallback_entities.items():
            if name.lower() in entity.get("name", "").lower():
                if entity_type is None or entity.get("entity_type") == entity_type:
                    results.append(entity)
                    if len(results) >= limit:
                        break
        return results

    def delete_entity(self, entity_id: str) -> bool:
        """删除实体及其所有关系（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
            try:
                with self._driver.session() as session:
                    session.run(
                        "MATCH (n {entity_id: $entity_id}) DETACH DELETE n",
                        entity_id=entity_id,
                    )
                return True
            except Exception as e:
                logger.error("Neo4j 删除实体失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._delete_entity_fallback(entity_id)
        else:
            return self._delete_entity_fallback(entity_id)

    def _delete_entity_fallback(self, entity_id: str) -> bool:
        """降级模式：从内存缓存和关系型数据库中删除实体"""
        self._fallback_entities.pop(entity_id, None)
        to_remove = [
            rid for rid, rel in self._fallback_relations.items()
            if rel.get("source_id") == entity_id or rel.get("target_id") == entity_id
        ]
        for rid in to_remove:
            del self._fallback_relations[rid]
        try:
            from backend.database import SessionLocal
            from backend.models import AgentRecord, SocialRelation
            db = SessionLocal()
            try:
                db.query(SocialRelation).filter(
                    (SocialRelation.agent_id_a == entity_id) |
                    (SocialRelation.agent_id_b == entity_id)
                ).delete()
                db.query(AgentRecord).filter(AgentRecord.agent_id == entity_id).delete()
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug("降级模式删除实体持久化失败: %s", e)
        return True

    # ── 关系 CRUD ─────────────────────────────────────

    def save_relation(self, relation: Relation) -> bool:
        """保存关系（Neo4j 不可用时降级到关系型数据库）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 保存关系失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._save_relation_fallback(relation)
        else:
            return self._save_relation_fallback(relation)

    def _save_relation_fallback(self, relation: Relation) -> bool:
        """降级模式：将关系保存到内存缓存和关系型数据库"""
        try:
            self._fallback_relations[relation.relation_id] = {
                "relation_id": relation.relation_id,
                "relation_type": relation.relation_type,
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "weight": relation.weight,
                "properties": relation.properties,
            }
            self._persist_relation_to_db(relation)
            return True
        except Exception as e:
            logger.error("降级模式保存关系失败: %s", e)
            return False

    def _persist_relation_to_db(self, relation: Relation):
        """将关系持久化到关系型数据库"""
        try:
            from backend.database import SessionLocal
            from backend.models import SocialRelation
            db = SessionLocal()
            try:
                record = SocialRelation(
                    agent_id_a=relation.source_id,
                    agent_id_b=relation.target_id,
                    relation_type=relation.relation_type,
                    weight=relation.weight,
                )
                db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug("关系持久化到关系型数据库失败: %s", e)

    def get_relations(self, entity_id: str, direction: str = "both",
                      relation_type: Optional[str] = None,
                      limit: int = 50) -> List[Dict]:
        """获取实体的关系（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 获取关系失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._get_relations_fallback(entity_id, direction, relation_type, limit)
        else:
            return self._get_relations_fallback(entity_id, direction, relation_type, limit)

    def _get_relations_fallback(self, entity_id: str, direction: str = "both",
                                relation_type: Optional[str] = None,
                                limit: int = 50) -> List[Dict]:
        """降级模式：从内存缓存获取关系"""
        results = []
        for rid, rel in self._fallback_relations.items():
            if relation_type and rel.get("relation_type") != relation_type:
                continue
            is_source = rel.get("source_id") == entity_id
            is_target = rel.get("target_id") == entity_id
            if direction == "out" and not is_source:
                continue
            if direction == "in" and not is_target:
                continue
            if not is_source and not is_target:
                continue
            source_entity = self._fallback_entities.get(rel.get("source_id", ""), {})
            target_entity = self._fallback_entities.get(rel.get("target_id", ""), {})
            results.append({
                "source": source_entity,
                "relation": rel,
                "target": target_entity,
            })
            if len(results) >= limit:
                break
        return results

    # ── 图查询 ────────────────────────────────────────

    def get_subgraph(self, entity_id: str, depth: int = 2,
                     limit: int = 100) -> Dict[str, List]:
        """获取以某实体为中心的子图（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 获取子图失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._get_subgraph_fallback(entity_id, depth, limit)
        else:
            return self._get_subgraph_fallback(entity_id, depth, limit)

    def _get_subgraph_fallback(self, entity_id: str, depth: int = 2,
                               limit: int = 100) -> Dict[str, List]:
        """降级模式：BFS 遍历获取子图"""
        visited_nodes = set()
        visited_edges = set()
        nodes = {}
        edges = []
        queue = [(entity_id, 0)]

        while queue and len(nodes) < limit:
            current_id, current_depth = queue.pop(0)
            if current_id in visited_nodes or current_depth > depth:
                continue
            visited_nodes.add(current_id)

            entity = self._fallback_entities.get(current_id)
            if entity:
                nodes[current_id] = entity

            for rid, rel in self._fallback_relations.items():
                if rid in visited_edges:
                    continue
                source_id = rel.get("source_id", "")
                target_id = rel.get("target_id", "")
                neighbor_id = None
                if source_id == current_id:
                    neighbor_id = target_id
                elif target_id == current_id:
                    neighbor_id = source_id

                if neighbor_id is not None:
                    visited_edges.add(rid)
                    edges.append({
                        "source": source_id,
                        "target": target_id,
                        "type": rel.get("relation_type", "RELATED_TO"),
                        "weight": rel.get("weight", 1.0),
                    })
                    if neighbor_id not in visited_nodes:
                        queue.append((neighbor_id, current_depth + 1))

        return {"nodes": list(nodes.values()), "edges": edges}

    def get_shortest_path(self, from_id: str, to_id: str,
                          max_depth: int = 5) -> List[Dict]:
        """两个实体间的最短路径（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 最短路径查询失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._get_shortest_path_fallback(from_id, to_id, max_depth)
        else:
            return self._get_shortest_path_fallback(from_id, to_id, max_depth)

    def _get_shortest_path_fallback(self, from_id: str, to_id: str,
                                    max_depth: int = 5) -> List[Dict]:
        """降级模式：BFS 求最短路径"""
        from collections import deque

        if from_id not in self._fallback_entities or to_id not in self._fallback_entities:
            return []

        adj = {}
        for rid, rel in self._fallback_relations.items():
            s = rel.get("source_id", "")
            t = rel.get("target_id", "")
            adj.setdefault(s, []).append(t)
            adj.setdefault(t, []).append(s)

        visited = {from_id}
        queue = deque([(from_id, [from_id])])

        while queue:
            current, path = queue.popleft()
            if len(path) - 1 > max_depth:
                continue
            if current == to_id:
                return [{"step": i, "node": self._fallback_entities.get(nid, {"entity_id": nid})}
                        for i, nid in enumerate(path)]
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息（Neo4j 不可用时降级）"""
        if self.is_neo4j_available:
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
                logger.error("Neo4j 获取统计信息失败: %s，尝试降级", e)
                self._handle_neo4j_failure()
                return self._get_stats_fallback()
        else:
            return self._get_stats_fallback()

    def _get_stats_fallback(self) -> Dict[str, Any]:
        """降级模式：返回内存缓存统计信息"""
        entity_types = set()
        relation_types = set()
        for entity in self._fallback_entities.values():
            entity_types.add(entity.get("entity_type", "Unknown"))
        for rel in self._fallback_relations.values():
            relation_types.add(rel.get("relation_type", "Unknown"))
        return {
            "connected": True,
            "node_count": len(self._fallback_entities),
            "relation_count": len(self._fallback_relations),
            "labels": list(entity_types),
            "relationship_types": list(relation_types),
            "mode": "fallback",
        }

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
        if self.is_neo4j_available:
            with self._driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Neo4j 图数据库已清空")
        else:
            self._fallback_entities.clear()
            self._fallback_relations.clear()
            logger.info("降级模式内存缓存已清空")

    # ── 降级处理 ──────────────────────────────────────

    def _handle_neo4j_failure(self):
        """处理 Neo4j 运行时故障：标记不可用并切换到降级模式"""
        if self._neo4j_available:
            logger.warning("Neo4j 运行时故障，切换到降级模式")
            self._neo4j_available = False
            self._fallback_mode = True
            try:
                if self._driver:
                    self._driver.close()
            except Exception:
                pass
            self._driver = None

    def try_reconnect(self) -> bool:
        """尝试重新连接 Neo4j

        Returns:
            是否重连成功
        """
        if self.is_neo4j_available:
            return True
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self._driver.verify_connectivity()
            self._neo4j_available = True
            self._fallback_mode = False
            logger.info("Neo4j 重连成功")
            return True
        except Exception as e:
            logger.debug("Neo4j 重连失败: %s", e)
            self._driver = None
            return False
