"""仿真数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionType(str, Enum):
    POST = "post"
    COMMENT = "comment"
    LIKE = "like"
    SHARE = "share"
    VIEW = "view"
    FOLLOW = "follow"
    REPORT = "report"


class AgentTier(str, Enum):
    A = "A"  # 管理Agent
    B = "B"  # 市民Agent (LLM)
    C = "C"  # 功能Agent (规则)


class TimeSlot(str, Enum):
    LATE_NIGHT = "深夜(0-6)"
    MORNING = "早晨(6-8)"
    FORENOON = "上午(8-12)"
    NOON = "午间(12-14)"
    AFTERNOON = "下午(14-18)"
    EVENING = "傍晚(18-20)"
    NIGHT = "晚间(20-23)"
    MIDNIGHT = "深夜(23-24)"


@dataclass
class PlatformAction:
    """平台行为"""
    agent_id: str = ""
    platform: str = ""
    action_type: str = "view"
    content: str = ""
    target_id: str = ""
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "platform": self.platform,
            "action_type": self.action_type,
            "content": self.content,
            "target_id": self.target_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }


@dataclass
class PlatformPost:
    """平台帖子/内容"""
    post_id: str = ""
    author_id: str = ""
    platform: str = ""
    content: str = ""
    likes: int = 0
    comments: List[Dict] = field(default_factory=list)
    shares: int = 0
    views: int = 0
    created_at: Optional[datetime] = None
    is_hot: bool = False
    tags: List[str] = field(default_factory=list)


@dataclass
class SimulationTick:
    """仿真tick状态"""
    tick: int = 0
    sim_time: str = ""
    time_slot: str = ""
    actions: List[PlatformAction] = field(default_factory=list)
    platform_states: Dict[str, Dict] = field(default_factory=dict)
