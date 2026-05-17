"""知乎仿真 — 问答 + 赞同 + 专栏 + 圆桌"""

from backend.services.simulation.platforms.base import BasePlatform


class ZhihuSimulator(BasePlatform):
    platform_name = "zhihu"
    display_name = "知乎"

    def __init__(self):
        super().__init__()
        self.upvotes: dict = {}    # post_id -> 赞同数
        self.questions: dict = {}  # question_id -> [answer_ids]

    def get_platform_features(self) -> dict:
        return {
            "qa": True,
            "upvote": True,
            "column": True,
            "character_limit": 50000,
        }

    def process_action(self, action, agent_persona=None):
        result = super().process_action(action, agent_persona)
        # 知乎特有：赞同（like变体）
        if action.action_type == "like":
            pid = action.target_id
            self.upvotes[pid] = self.upvotes.get(pid, 0) + 1
        return result

    def get_snapshot(self):
        snap = super().get_snapshot()
        snap["total_upvotes"] = sum(self.upvotes.values())
        snap["total_questions"] = len(self.questions)
        return snap
