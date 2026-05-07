"""微博仿真 — 热搜机制 + 转发链 + 话题标签"""

from backend.services.simulation.platforms.base import BasePlatform


class WeiboSimulator(BasePlatform):
    platform_name = "weibo"
    display_name = "微博"

    def __init__(self):
        super().__init__()
        self.trending_topics: list = []
        self.hashtags: dict = {}

    def get_platform_features(self) -> dict:
        return {
            "trending": True,
            "repost_chain": True,
            "hashtag": True,
            "character_limit": 2000,
        }

    def process_action(self, action, agent_persona=None):
        result = super().process_action(action, agent_persona)
        # 微博热搜：点赞+转发过阈值自动上热搜
        if action.action_type == "share" and action.target_id:
            post = self.posts.get(action.target_id)
            if post and post.shares >= 5:
                if action.target_id not in self.trending_topics:
                    self.trending_topics.append(action.target_id)
        return result

    def get_feed(self, limit=10, agent_persona=None):
        feed = super().get_feed(limit, agent_persona)
        # 微博：热搜帖子置顶
        for pid in self.trending_topics[:3]:
            post = self.posts.get(pid)
            if post and post.post_id not in {f["post_id"] for f in feed}:
                item = self._post_to_feed_item(post)
                item["is_trending"] = True
                feed.insert(0, item)
        return feed

    def get_snapshot(self):
        snap = super().get_snapshot()
        snap["trending_count"] = len(self.trending_topics)
        snap["hashtag_count"] = len(self.hashtags)
        return snap
