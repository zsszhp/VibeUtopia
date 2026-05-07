"""传播树构建与查询 — 追踪内容从源头到扩散的完整路径"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PropagationNode:
    """传播树节点 — 一条被传播的内容"""

    content_id: str = ""
    author_id: str = ""
    platform: str = ""
    tick: int = 0
    parent_content_id: Optional[str] = None  # 如果是转发/评论，指向源内容
    children: List[str] = field(default_factory=list)  # 子内容ID列表
    action_type: str = "post"  # post/comment/share/repost
    like_count: int = 0
    share_count: int = 0
    comment_count: int = 0
    view_count: int = 0


class PropagationTree:
    """传播树 — 记录内容的完整传播路径"""

    def __init__(self):
        self.nodes: Dict[str, PropagationNode] = {}  # content_id -> node
        self.edges: List[Dict[str, Any]] = []  # 传播边列表
        self._content_author: Dict[str, str] = {}  # content_id -> agent_id
        self._agent_content_count: Dict[str, int] = defaultdict(int)  # agent_id -> 被传播次数

    def add_action(self, action: Dict[str, Any], tick: int) -> Optional[Dict[str, Any]]:
        """处理Agent行为，更新传播树

        Args:
            action: PlatformAction 的 dict 形式，需包含 agent_id, platform, action_type,
                    content, target_id, metadata
            tick: 当前仿真tick

        Returns:
            新增的传播边 dict，若无传播行为则返回 None
        """
        agent_id = action.get("agent_id", "")
        platform = action.get("platform", "")
        action_type = action.get("action_type", "view")
        target_id = action.get("target_id", "")
        metadata = action.get("metadata", {})

        # POST: 新帖子 → 传播树新根节点
        if action_type in ("post",):
            content_id = metadata.get("post_id") or f"post_{agent_id}_{tick}_{uuid.uuid4().hex[:6]}"
            node = PropagationNode(
                content_id=content_id,
                author_id=agent_id,
                platform=platform,
                tick=tick,
                parent_content_id=None,
                action_type=action_type,
            )
            self.nodes[content_id] = node
            self._content_author[content_id] = agent_id
            return None

        # 传播行为: share/comment/repost → 建立传播边
        if action_type in ("share", "comment", "repost", "quote_post"):
            if not target_id:
                return None

            # 找到源内容的作者
            source_author = self._content_author.get(target_id)
            if not source_author:
                # 源内容不在传播树中（可能是种子内容），仍然记录
                source_author = f"unknown_{target_id}"

            # 避免自传播（自己传播自己的内容不算传播）
            if source_author == agent_id:
                return None

            # 建立传播边
            edge = {
                "source_agent_id": source_author,
                "target_agent_id": agent_id,
                "content_id": target_id,
                "action_type": action_type,
                "platform": platform,
                "tick": tick,
            }
            self.edges.append(edge)

            # 更新被传播计数
            self._agent_content_count[source_author] += 1

            # 如果传播者创建了新内容（如带评论的转发），添加新节点
            if action_type in ("repost", "quote_post", "comment") and action.get("content"):
                new_content_id = f"{action_type}_{agent_id}_{tick}_{uuid.uuid4().hex[:6]}"
                new_node = PropagationNode(
                    content_id=new_content_id,
                    author_id=agent_id,
                    platform=platform,
                    tick=tick,
                    parent_content_id=target_id,
                    action_type=action_type,
                )
                self.nodes[new_content_id] = new_node
                self._content_author[new_content_id] = agent_id

                # 更新父节点的 children 列表
                if target_id in self.nodes:
                    self.nodes[target_id].children.append(new_content_id)

                    # 更新父节点的互动计数
                    if action_type == "comment":
                        self.nodes[target_id].comment_count += 1
                    elif action_type in ("share", "repost", "quote_post"):
                        self.nodes[target_id].share_count += 1

            return edge

        # LIKE: 更新源内容的点赞计数
        if action_type == "like" and target_id in self.nodes:
            self.nodes[target_id].like_count += 1
            return None

        # VIEW: 更新源内容的浏览计数
        if action_type == "view" and target_id in self.nodes:
            self.nodes[target_id].view_count += 1
            return None

        return None

    def get_reach_count(self) -> int:
        """传播覆盖人数（去重）"""
        involved_agents = set()
        # 所有内容作者
        for node in self.nodes.values():
            involved_agents.add(node.author_id)
        # 所有传播边的两端
        for edge in self.edges:
            involved_agents.add(edge["source_agent_id"])
            involved_agents.add(edge["target_agent_id"])
        return len(involved_agents)

    def get_depth(self) -> int:
        """传播深度（最长传播链长度）"""
        if not self.nodes:
            return 0

        # 构建内容之间的父子关系图
        children_map: Dict[str, List[str]] = defaultdict(list)
        for content_id, node in self.nodes.items():
            if node.parent_content_id:
                children_map[node.parent_content_id].append(content_id)

        if not children_map:
            return 1

        # BFS 求最大深度
        # 找根节点（没有 parent_content_id 的）
        roots = [cid for cid, node in self.nodes.items() if node.parent_content_id is None]
        if not roots:
            return 1

        max_depth = 0
        queue = deque([(root, 1) for root in roots])
        while queue:
            content_id, depth = queue.popleft()
            max_depth = max(max_depth, depth)
            for child_id in children_map.get(content_id, []):
                queue.append((child_id, depth + 1))

        return max_depth

    def get_influencer_ranking(self, top_k: int = 10) -> List[Tuple[str, int]]:
        """关键传播节点排名（按被传播次数排序）

        Returns:
            [(agent_id, 被传播次数), ...] 降序排列
        """
        ranking = sorted(
            self._agent_content_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranking[:top_k]

    def get_propagation_paths(self, content_id: str) -> List[List[str]]:
        """获取指定内容的所有传播路径

        Returns:
            传播路径列表，每条路径为 [agent_id1, agent_id2, ...]
        """
        paths = []

        # 从该内容的所有传播边出发，DFS 追踪
        related_edges = [e for e in self.edges if e["content_id"] == content_id]
        if not related_edges:
            # 只有源作者
            node = self.nodes.get(content_id)
            if node:
                return [[node.author_id]]
            return []

        # 构建传播链：source -> target
        chain_map: Dict[str, List[str]] = defaultdict(list)
        for edge in related_edges:
            chain_map[edge["source_agent_id"]].append(edge["target_agent_id"])

        # DFS 从源作者开始
        source_author = self._content_author.get(content_id, "")
        if not source_author:
            return []

        def _dfs(agent_id: str, path: List[str], visited: set):
            path.append(agent_id)
            visited.add(agent_id)

            targets = chain_map.get(agent_id, [])
            if not targets:
                paths.append(path[:])
            else:
                for target in targets:
                    if target not in visited:
                        _dfs(target, path, visited)

            path.pop()
            visited.discard(agent_id)

        _dfs(source_author, [], set())
        return paths

    def get_stats(self) -> Dict[str, Any]:
        """获取传播树统计信息"""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "reach_count": self.get_reach_count(),
            "depth": self.get_depth(),
            "top_influencers": self.get_influencer_ranking(10),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict 供 API 返回"""
        return {
            "nodes": {
                cid: {
                    "content_id": n.content_id,
                    "author_id": n.author_id,
                    "platform": n.platform,
                    "tick": n.tick,
                    "parent_content_id": n.parent_content_id,
                    "children": n.children,
                    "action_type": n.action_type,
                    "like_count": n.like_count,
                    "share_count": n.share_count,
                    "comment_count": n.comment_count,
                    "view_count": n.view_count,
                }
                for cid, n in self.nodes.items()
            },
            "edges": self.edges,
            "stats": self.get_stats(),
        }
