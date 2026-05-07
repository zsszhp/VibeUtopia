"""小红书仿真 — 种草 + 笔记 + 评论 + 收藏"""

from backend.services.simulation.platforms.base import BasePlatform


class XiaohongshuSimulator(BasePlatform):
    platform_name = "xiaohongshu"
    display_name = "小红书"

    def __init__(self):
        super().__init__()
        self.collections: dict = {}  # post_id -> 收藏数
        self.notes_tags: dict = {}   # post_id -> [标签]

    def get_platform_features(self) -> dict:
        return {
            "note": True,
            "collection": True,
            "seeding": True,
            "character_limit": 1000,
        }

    def process_action(self, action, agent_persona=None):
        result = super().process_action(action, agent_persona)
        # 小红书特有：收藏（like变体）
        if action.action_type == "like":
            pid = action.target_id
            self.collections[pid] = self.collections.get(pid, 0) + 1
        return result

    def get_snapshot(self):
        snap = super().get_snapshot()
        snap["total_collections"] = sum(self.collections.values())
        return snap
