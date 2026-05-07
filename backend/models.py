from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    status = Column(String, default="processing")
    model = Column(String)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)

    risk_items = relationship("RiskItem", backref="task", cascade="all, delete-orphan")
    platform_reactions = relationship("PlatformReaction", backref="task", cascade="all, delete-orphan")
    summary = relationship("AnalysisSummary", backref="task", uselist=False, cascade="all, delete-orphan")


class RiskItem(Base):
    __tablename__ = "risk_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    sentence = Column(Text)
    dimension = Column(String)
    severity = Column(String)
    evidence = Column(Text)
    affected_groups = Column(Text, nullable=True)
    dimension_weight = Column(Float, nullable=True)


class PlatformReaction(Base):
    __tablename__ = "platform_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    platform = Column(String)
    positive = Column(Float)
    neutral = Column(Float)
    negative = Column(Float)
    reason = Column(Text)


class AnalysisSummary(Base):
    __tablename__ = "analysis_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), unique=True)
    overall_score = Column(Integer)
    suggestion = Column(String)
    dimensions_json = Column(Text)
    rewrites_json = Column(Text)
    transcript_quality = Column(Text, nullable=True)
    dimension_weights = Column(Text, nullable=True)
    cross_effects = Column(Text, nullable=True)
    agents_json = Column(Text, nullable=True)


class SignalRecord(Base):
    __tablename__ = "signal_records"

    signal_id = Column(String, primary_key=True)
    source_platform = Column(String, index=True)
    title = Column(String, index=True)
    url = Column(String, nullable=True)
    rank = Column(Integer, nullable=True)
    rank_timeline = Column(Text, default="[]")
    first_seen = Column(DateTime, default=utcnow)
    last_seen = Column(DateTime, default=utcnow)
    appearance_count = Column(Integer, default=1)
    is_new = Column(Boolean, default=False)
    signal_type = Column(String, default="hotlist")
    category = Column(String, nullable=True)
    raw_data = Column(Text, nullable=True)


class SeedEventRecord(Base):
    __tablename__ = "seed_events"

    event_id = Column(String, primary_key=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String)
    signal_strength = Column(Float, default=0.0)
    source_platforms = Column(Text, default="[]")
    source_urls = Column(Text, default="[]")
    comments_json = Column(Text, default="[]")
    related_events = Column(Text, default="[]")
    causal_parents = Column(Text, default="[]")
    causal_children = Column(Text, default="[]")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)
    ttl = Column(Integer, default=72)
    status = Column(String, default="active")
    crawl_depth = Column(String, default="none")


class AgentRecord(Base):
    __tablename__ = "agent_records"

    agent_id = Column(String, primary_key=True)
    platform = Column(String, index=True)
    archetype_base = Column(String)
    persona_json = Column(Text)
    quality_score = Column(Float, default=0.0)
    status = Column(String, default="active")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)


class SocialRelation(Base):
    __tablename__ = "social_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id_a = Column(String, index=True)
    agent_id_b = Column(String, index=True)
    relation_type = Column(String)
    weight = Column(Float, default=1.0)
    platform = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    memory_id = Column(String, primary_key=True)
    agent_id = Column(String, index=True)
    memory_type = Column(String)
    content = Column(Text)
    weight = Column(Float, default=1.0)
    source_task_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class SimulationRecord(Base):
    __tablename__ = "simulation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_id = Column(String, index=True)
    tick = Column(Integer, default=0)
    sim_time = Column(String)
    agent_id = Column(String, index=True)
    agent_tier = Column(String)
    platform = Column(String)
    action_type = Column(String)
    content = Column(Text, nullable=True)
    target_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class SimulationStatus(Base):
    __tablename__ = "simulation_statuses"

    sim_id = Column(String, primary_key=True)
    status = Column(String, default="created")
    topic = Column(Text)
    total_ticks = Column(Integer, default=0)
    total_agents = Column(Integer, default=0)
    config_json = Column(Text, default="{}")
    platform_snapshot_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)
