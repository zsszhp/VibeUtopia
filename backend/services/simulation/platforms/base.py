"""平台仿真器基类"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.services.simulation.models import PlatformAction, PlatformPost

logger = logging.getLogger(__name__)


class BasePlatform(ABC):
    """平台仿真器基类"""

    platform_name: str = "base"
    display_name: str = "基础平台"

    def __init__(self):
        self.posts: Dict[str, PlatformPost] = {}
        self.hot_posts: List[str] = []
        self._action_history: List[Dict] = []

    def reset(self):
        """重置平台状态"""
        self.posts.clear()
        self.hot_posts.clear()
        self._action_history.clear()

    def process_action(self, action: PlatformAction, agent_persona: Dict = None) -> Dict:
        """处理一个Agent行为，返回更新结果"""
        result = {"action": action.to_dict(), "effects": []}

        if action.action_type == "post":
            post = self._create_post(action)
            self.posts[post.post_id] = post
            result["effects"].append({"type": "new_post", "post_id": post.post_id})

        elif action.action_type == "comment":
            target = self.posts.get(action.target_id)
            if target:
                comment = {
                    "comment_id": str(uuid.uuid4())[:8],
                    "author_id": action.agent_id,
                    "content": action.content[:500],
                }
                target.comments.append(comment)
                result["effects"].append({"type": "new_comment", "post_id": action.target_id})

        elif action.action_type == "like":
            target = self.posts.get(action.target_id)
            if target:
                target.likes += 1
                result["effects"].append({"type": "like", "post_id": action.target_id, "total": target.likes})

        elif action.action_type == "share":
            target = self.posts.get(action.target_id)
            if target:
                target.shares += 1
                result["effects"].append({"type": "share", "post_id": action.target_id, "total": target.shares})

        elif action.action_type == "view":
            target = self.posts.get(action.target_id)
            if target:
                target.views += 1

        self._action_history.append(result)
        self._update_hot_posts()
        return result

    def _create_post(self, action: PlatformAction) -> PlatformPost:
        """创建新帖子"""
        post_id = f"{self.platform_name}_{uuid.uuid4().hex[:8]}"
        return PlatformPost(
            post_id=post_id,
            author_id=action.agent_id,
            platform=self.platform_name,
            content=action.content[:1000],
            created_at=action.timestamp,
        )

    def _update_hot_posts(self):
        """更新热榜"""
        if not self.posts:
            return
        sorted_posts = sorted(
            self.posts.values(),
            key=lambda p: p.likes * 2 + p.comments.__len__() * 3 + p.shares * 5 + p.views,
            reverse=True,
        )
        self.hot_posts = [p.post_id for p in sorted_posts[:20]]

    def get_feed(self, limit: int = 10, agent_persona: Dict = None) -> List[Dict]:
        """获取平台feed内容"""
        feed = []
        # 优先热帖
        for pid in self.hot_posts[:limit]:
            post = self.posts.get(pid)
            if post:
                feed.append(self._post_to_feed_item(post))

        # 补充最新帖
        if len(feed) < limit:
            all_posts = sorted(
                self.posts.values(),
                key=lambda p: p.created_at or "",
                reverse=True,
            )
            seen = {f["post_id"] for f in feed}
            for p in all_posts:
                if p.post_id not in seen:
                    feed.append(self._post_to_feed_item(p))
                    if len(feed) >= limit:
                        break
        return feed

    def _post_to_feed_item(self, post: PlatformPost) -> Dict:
        """帖子转feed项"""
        return {
            "post_id": post.post_id,
            "author_id": post.author_id,
            "platform": post.platform,
            "content": post.content[:300],
            "likes": post.likes,
            "comment_count": len(post.comments),
            "shares": post.shares,
            "views": post.views,
            "is_hot": post.is_hot,
            "tags": post.tags,
        }

    def get_snapshot(self) -> Dict:
        """获取平台快照"""
        return {
            "platform": self.platform_name,
            "total_posts": len(self.posts),
            "hot_posts": len(self.hot_posts),
            "total_actions": len(self._action_history),
        }

    def seed_topic(self, topic: str, author_id: str = "system"):
        """注入种子话题"""
        action = PlatformAction(
            agent_id=author_id,
            platform=self.platform_name,
            action_type="post",
            content=topic,
        )
        return self.process_action(action)

    @abstractmethod
    def get_platform_features(self) -> Dict:
        """返回平台特有功能描述"""
        pass
