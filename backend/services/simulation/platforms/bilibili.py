"""B站仿真 — 弹幕 + 投币 + 收藏 + 追番"""

from backend.services.simulation.platforms.base import BasePlatform


class BilibiliSimulator(BasePlatform):
    platform_name = "bilibili"
    display_name = "B站"

    def __init__(self):
        super().__init__()
        self.danmaku: dict = {}  # post_id -> [弹幕列表]
        self.coins: dict = {}    # post_id -> 投币数
        self.favorites: dict = {}  # post_id -> 收藏数

    def get_platform_features(self) -> dict:
        return {
            "danmaku": True,
            "coin": True,
            "favorite": True,
            "character_limit": 5000,
        }

    def process_action(self, action, agent_persona=None):
        # B站特有：评论可作为弹幕
        if action.action_type == "comment":
            pid = action.target_id
            if pid not in self.danmaku:
                self.danmaku[pid] = []
            self.danmaku[pid].append(action.content[:50])

        result = super().process_action(action, agent_persona)

        # B站特有：投币（share变体）
        if action.action_type == "share":
            pid = action.target_id
            self.coins[pid] = self.coins.get(pid, 0) + 1

        return result

    def get_snapshot(self):
        snap = super().get_snapshot()
        snap["total_danmaku"] = sum(len(v) for v in self.danmaku.values())
        snap["total_coins"] = sum(self.coins.values())
        snap["total_favorites"] = sum(self.favorites.values())
        return snap
