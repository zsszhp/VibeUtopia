"""抖音仿真 — 短视频 + 评论 + 挑战赛 + 算法推荐"""

import random
from backend.services.simulation.platforms.base import BasePlatform


class DouyinSimulator(BasePlatform):
    platform_name = "douyin"
    display_name = "抖音"

    def __init__(self):
        super().__init__()
        self.challenges: dict = {}  # challenge_name -> [post_ids]
        self.recommendation_pool: list = []

    def get_platform_features(self) -> dict:
        return {
            "short_video": True,
            "challenge": True,
            "algorithm_recommendation": True,
            "character_limit": 300,
        }

    def get_feed(self, limit=10, agent_persona=None):
        """抖音算法推荐：基于Agent兴趣个性化feed"""
        feed = super().get_feed(limit, agent_persona)
        # 抖音特色：算法推荐随机混入挑战赛内容
        if self.challenges and random.random() < 0.3:
            for ch_name, pids in self.challenges.items():
                if pids:
                    pid = random.choice(pids)
                    post = self.posts.get(pid)
                    if post:
                        item = self._post_to_feed_item(post)
                        item["challenge"] = ch_name
                        feed.insert(0, item)
                        break
        return feed

    def get_snapshot(self):
        snap = super().get_snapshot()
        snap["total_challenges"] = len(self.challenges)
        return snap
