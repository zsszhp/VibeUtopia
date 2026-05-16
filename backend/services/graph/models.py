"""知识图谱数据模型"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    EVENT = "Event"
    CONCEPT = "Concept"
    LOCATION = "Location"
    POLICY = "Policy"
    INDUSTRY = "Industry"
    PLATFORM = "Platform"
    PRODUCT = "Product"
    SOCIAL_GROUP = "SocialGroup"
    VIDEO_SEGMENT = "VideoSegment"
    TOPIC = "Topic"
    VIEWPOINT = "Viewpoint"
    EVIDENCE = "Evidence"


class RelationType(str, Enum):
    INFLUENCES = "INFLUENCES"
    BELONGS_TO = "BELONGS_TO"
    TRIGGERS = "TRIGGERS"
    OPPOSES = "OPPOSES"
    SUPPORTS = "SUPPORTS"
    PARTICIPATES = "PARTICIPATES"
    LOCATED_IN = "LOCATED_IN"
    RELATED_TO = "RELATED_TO"
    EMPLOYS = "EMPLOYS"
    MENTIONS = "MENTIONS"
    HOLDS_VIEW = "HOLDS_VIEW"
    CONTRADICTS = "CONTRADICTS"
    EVOLVED_FROM = "EVOLVED_FROM"
    APPEARS_IN = "APPEARS_IN"


@dataclass
class EntityDef:
    """实体类型定义"""
    name: str
    description: str
    properties: List[str] = field(default_factory=list)


@dataclass
class RelationDef:
    """关系类型定义"""
    name: str
    source: str
    target: str
    description: str = ""
    weight_type: str = "float"


@dataclass
class GraphOntology:
    """图谱本体"""
    entity_types: List[EntityDef] = field(default_factory=list)
    relation_types: List[RelationDef] = field(default_factory=list)


@dataclass
class Entity:
    """实体实例"""
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: str = "Event"
    name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    source_event_id: Optional[str] = None


@dataclass
class Relation:
    """关系实例"""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    relation_type: str = "RELATED_TO"
    source_id: str = ""
    target_id: str = ""
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """抽取结果"""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    source_event_id: Optional[str] = None


@dataclass
class VideoSegment:
    """视频片段"""
    segment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    video_path: str = ""
    blogger_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    frame_paths: List[str] = field(default_factory=list)
    visual_description: str = ""
    asr_text: str = ""
    ocr_text: str = ""
    combined_text: str = ""
    embedding: Optional[List[float]] = None


@dataclass
class IndexResult:
    """博主视频索引结果"""
    blogger_id: str = ""
    videos_indexed: int = 0
    segments_created: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    entities_merged: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class IndexStatus:
    """博主索引状态"""
    blogger_id: str = ""
    total_videos: int = 0
    total_segments: int = 0
    total_entities: int = 0
    total_relations: int = 0
    total_duration_hours: float = 0.0
    indexed_video_paths: List[str] = field(default_factory=list)
    last_updated: str = ""


@dataclass
class AnswerResult:
    """博主知识问答结果"""
    question: str = ""
    answer: str = ""
    references: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    retrieval_mode: str = "text"


@dataclass
class BloggerKnowledgeProfile:
    """博主全知识画像"""
    blogger_id: str = ""
    platform: str = ""
    narrative_style: str = ""
    expression_style: str = ""
    vocabulary_profile: Dict[str, Any] = field(default_factory=dict)
    core_viewpoints: List[Dict[str, Any]] = field(default_factory=list)
    topic_stances: Dict[str, str] = field(default_factory=dict)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    primary_topics: List[str] = field(default_factory=list)
    topic_distribution: Dict[str, float] = field(default_factory=dict)
    estimated_audience: Dict[str, Any] = field(default_factory=dict)
    risk_profile: Dict[str, Any] = field(default_factory=dict)
    total_videos: int = 0
    total_duration_hours: float = 0.0
    knowledge_graph_stats: Dict[str, Any] = field(default_factory=dict)
    last_updated: str = ""
