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
