"""信号采集层数据模型"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
import uuid


class SignalType(str, Enum):
    HOTLIST = "hotlist"
    RSS = "rss"
    API = "api"


class EventCategory(str, Enum):
    POLITICS = "politics"
    ECONOMY = "economy"
    SOCIETY = "society"
    CULTURE = "culture"
    TECH = "tech"


class EventStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class CrawlDepth(str, Enum):
    NONE = "none"
    SHALLOW = "shallow"
    DEEP = "deep"


@dataclass
class RankPoint:
    timestamp: datetime
    rank: int


@dataclass
class Signal:
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_platform: str = ""
    title: str = ""
    url: Optional[str] = None
    rank: Optional[int] = None
    rank_timeline: List[RankPoint] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    appearance_count: int = 1
    is_new: bool = False
    signal_type: SignalType = SignalType.HOTLIST
    category: Optional[EventCategory] = None
    raw_data: Optional[dict] = None


@dataclass
class AnnotatedComment:
    comment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform: str = ""
    content: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    confidence: float = 0.0
    like_count: Optional[int] = None
    reply_count: Optional[int] = None
    user_type: Optional[str] = None


@dataclass
class SearchKeyword:
    keyword: str = ""
    platforms: List[str] = field(default_factory=list)
    priority: int = 3


@dataclass
class SeedEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    category: EventCategory = EventCategory.SOCIETY
    signal_strength: float = 0.0
    sources: List[Signal] = field(default_factory=list)
    comments: List[AnnotatedComment] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
    causal_parents: List[str] = field(default_factory=list)
    causal_children: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = 72
    status: EventStatus = EventStatus.ACTIVE
    crawl_depth: CrawlDepth = CrawlDepth.NONE
