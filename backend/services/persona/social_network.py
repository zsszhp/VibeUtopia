"""社会关系网络生成器 — 小世界网络 + 跨平台桥接 + 对立关系 + 权力节点"""

import logging
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 5种关系类型
RELATION_FOLLOW = "follow"        # 关注
RELATION_FRIEND = "friend"        # 好友
RELATION_OPPOSE = "oppose"        # 对立
RELATION_MENTOR = "mentor"        # 师徒
RELATION_ORG = "same_org"         # 同组织


class SocialNetworkGenerator:
    """社会关系网络生成器

    算法4步：
    1. 平台内小世界网络（Watts-Strogatz）
    2. 跨平台桥接（相似兴趣Agent连接）
    3. 对立关系注入（价值观差异大）
    4. 权力节点生成（少数高影响力Agent）
    """

    def __init__(self, k: int = 4, beta: float = 0.3, oppose_ratio: float = 0.1,
                 power_ratio: float = 0.05):
        """
        Args:
            k: 小世界网络每个节点的初始邻居数（偶数）
            beta: 重连概率（0=规则网络，1=随机网络，0.3=小世界）
            oppose_ratio: 对立关系占比
            power_ratio: 权力节点占比
        """
        self.k = k
        self.beta = beta
        self.oppose_ratio = oppose_ratio
        self.power_ratio = power_ratio

    def generate(self, agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """为社会Agent列表生成关系网络

        Args:
            agents: Agent列表，每个包含 persona_id, platform, L2_values 等

        Returns:
            关系列表 [{"agent_a": ..., "agent_b": ..., "type": ..., "weight": ...}]
        """
        if len(agents) < 3:
            logger.warning("Agent数量不足3个，无法生成关系网络")
            return []

        relations = []

        # 按平台分组
        platform_groups = {}
        for agent in agents:
            p = agent.get("platform", "unknown")
            if p not in platform_groups:
                platform_groups[p] = []
            platform_groups[p].append(agent)

        # Step 1: 平台内小世界网络
        for platform, group in platform_groups.items():
            if len(group) >= 3:
                ws_edges = self._watts_strogatz(group)
                relations.extend(ws_edges)

        # Step 2: 跨平台桥接
        cross_edges = self._cross_platform_bridge(agents, platform_groups)
        relations.extend(cross_edges)

        # Step 3: 对立关系注入
        oppose_edges = self._inject_opposition(agents)
        relations.extend(oppose_edges)

        # Step 4: 权力节点
        power_edges = self._generate_power_nodes(agents)
        relations.extend(power_edges)

        logger.info(f"关系网络生成完成: {len(relations)}条关系")
        return relations

    def _watts_strogatz(self, agents: List[Dict]) -> List[Dict]:
        """Watts-Strogatz小世界模型

        每个节点连接k/2个左邻居和k/2个右邻居，然后以概率beta重连
        """
        n = len(agents)
        if n <= self.k:
            # 节点太少，全连接
            return self._full_connect(agents, RELATION_FOLLOW)

        edges = []
        half_k = self.k // 2

        # 创建环状规则网络
        for i in range(n):
            for j in range(1, half_k + 1):
                target = (i + j) % n
                edges.append(self._make_edge(agents[i], agents[target], RELATION_FOLLOW, 0.5))

        # 以概率beta重连
        rewired = []
        for edge in edges:
            if random.random() < self.beta:
                # 重连：选择一个随机新目标
                new_target_idx = random.randint(0, n - 1)
                source_id = edge["agent_a"]
                new_target = agents[new_target_idx]
                if new_target.get("persona_id") != source_id:
                    edge["agent_b"] = new_target.get("persona_id", "")
                    edge["platform"] = new_target.get("platform", "")
            rewired.append(edge)

        # 补充好友关系（随机10%升级为好友）
        for edge in rewired:
            if random.random() < 0.1:
                edge["type"] = RELATION_FRIEND
                edge["weight"] = 0.8

        return rewired

    def _cross_platform_bridge(self, agents: List[Dict],
                                platform_groups: Dict[str, List]) -> List[Dict]:
        """跨平台桥接：相似兴趣的Agent连接"""
        edges = []

        platforms = list(platform_groups.keys())
        if len(platforms) < 2:
            return edges

        # 为每个Agent计算兴趣向量（基于L2 values）
        for i in range(len(platforms)):
            for j in range(i + 1, len(platforms)):
                group_a = platform_groups[platforms[i]]
                group_b = platform_groups[platforms[j]]

                # 随机选择一些对进行跨平台连接
                bridge_count = max(1, min(len(group_a), len(group_b)) // 3)
                for _ in range(bridge_count):
                    a = random.choice(group_a)
                    b = random.choice(group_b)

                    # 计算价值观相似度
                    similarity = self._value_similarity(a, b)
                    if similarity > 0.5:
                        edges.append(self._make_edge(a, b, RELATION_FOLLOW, similarity * 0.7))

        return edges

    def _inject_opposition(self, agents: List[Dict]) -> List[Dict]:
        """对立关系注入：价值观差异大的Agent"""
        edges = []
        oppose_count = max(1, int(len(agents) * self.oppose_ratio))

        for _ in range(oppose_count):
            a = random.choice(agents)
            b = random.choice(agents)

            if a.get("persona_id") == b.get("persona_id"):
                continue

            # 计算价值观差异
            diff = self._value_distance(a, b)
            if diff > 0.5:  # 差异大才建立对立关系
                edges.append(self._make_edge(a, b, RELATION_OPPOSE, diff * 0.8))

        return edges

    def _generate_power_nodes(self, agents: List[Dict]) -> List[Dict]:
        """权力节点：少数高影响力Agent获得大量关注"""
        edges = []
        power_count = max(1, int(len(agents) * self.power_ratio))

        # 选择权力节点
        power_agents = random.sample(agents, min(power_count, len(agents)))

        for power_agent in power_agents:
            # 每个权力节点获得额外的关注者
            follower_count = max(3, len(agents) // 5)
            followers = random.sample(agents, min(follower_count, len(agents)))

            for follower in followers:
                if follower.get("persona_id") != power_agent.get("persona_id"):
                    edges.append(self._make_edge(
                        follower, power_agent, RELATION_FOLLOW, 0.9
                    ))

            # 师徒关系
            if len(followers) >= 2:
                mentee = followers[0]
                edges.append(self._make_edge(mentee, power_agent, RELATION_MENTOR, 0.7))

        return edges

    def _value_similarity(self, a: Dict, b: Dict) -> float:
        """计算两个Agent的价值观相似度（余弦相似度）"""
        va = self._value_vector(a)
        vb = self._value_vector(b)
        dot = sum(x * y for x, y in zip(va, vb))
        norm_a = sum(x * x for x in va) ** 0.5
        norm_b = sum(x * x for x in vb) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.5
        return dot / (norm_a * norm_b)

    def _value_distance(self, a: Dict, b: Dict) -> float:
        """计算价值观距离（1 - 相似度）"""
        return 1.0 - self._value_similarity(a, b)

    def _value_vector(self, agent: Dict) -> List[float]:
        """提取L2价值观向量"""
        l2 = agent.get("L2_values", {})
        if isinstance(l2, str):
            try:
                import json
                l2 = json.loads(l2)
            except Exception:
                l2 = {}
        return [
            float(l2.get("political_tendency", 5.0)),
            float(l2.get("consumerism", 5.0)),
            float(l2.get("family_tradition", 5.0)),
            float(l2.get("social_justice", 5.0)),
            float(l2.get("tech_optimism", 5.0)),
        ]

    def _make_edge(self, a: Dict, b: Dict, rel_type: str, weight: float) -> Dict:
        """创建一条关系边"""
        return {
            "agent_a": a.get("persona_id", ""),
            "agent_b": b.get("persona_id", ""),
            "type": rel_type,
            "weight": round(min(1.0, max(0.1, weight)), 2),
            "platform": a.get("platform", ""),
        }

    def _full_connect(self, agents: List[Dict], rel_type: str) -> List[Dict]:
        """全连接（节点少时使用）"""
        edges = []
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                edges.append(self._make_edge(agents[i], agents[j], rel_type, 0.5))
        return edges

    def persist_relations(self, relations: List[Dict]):
        """将关系持久化到数据库"""
        from datetime import datetime, timezone
        from backend.database import SessionLocal
        from backend.models import SocialRelation

        db = SessionLocal()
        try:
            for rel in relations:
                record = SocialRelation(
                    agent_id_a=rel.get("agent_a", ""),
                    agent_id_b=rel.get("agent_b", ""),
                    relation_type=rel.get("type", "follow"),
                    weight=rel.get("weight", 0.5),
                    platform=rel.get("platform", ""),
                )
                db.add(record)
            db.commit()
            logger.info(f"持久化 {len(relations)} 条社会关系到数据库")
        except Exception as e:
            logger.error(f"持久化社会关系失败: {e}")
            db.rollback()
        finally:
            db.close()
