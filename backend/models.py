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


class PropagationSnapshot(Base):
    """传播快照 - 每个关键tick记录一次"""
    __tablename__ = "propagation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, index=True)
    tick = Column(Integer)
    stage = Column(String)                     # seed/primary/community/polarization/mainstream/fading
    propagation_kinetic = Column(Float, default=0.0)
    polarization_index = Column(Float, default=0.0)
    reach_count = Column(Integer, default=0)
    depth = Column(Integer, default=0)
    sentiment_distribution = Column(Text, default="{}")  # JSON: {positive, negative, neutral}
    key_influencers = Column(Text, default="[]")         # JSON: [agent_id, ...]
    snapshot_data = Column(Text, default="{}")           # JSON: 完整快照数据
    created_at = Column(DateTime, default=utcnow)


class PropagationEdge(Base):
    """传播边 - 记录每条传播路径"""
    __tablename__ = "propagation_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, index=True)
    source_agent_id = Column(String, index=True)
    target_agent_id = Column(String, index=True)
    content_id = Column(String, index=True)
    action_type = Column(String)
    platform = Column(String)
    tick = Column(Integer)
    influence_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)


class V2AnalysisResult(Base):
    """V2增强分析结果（V2.R1新增）"""
    __tablename__ = "v2_analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), unique=True)
    mode = Column(String, default="quick")             # quick / deep
    mvp_score = Column(Integer, default=0)
    v2_score = Column(Integer, default=0)
    signal_matches = Column(Text, default="[]")         # JSON: 热点关联结果
    entity_risk_chains = Column(Text, default="[]")     # JSON: 实体风险链
    dynamic_weights = Column(Text, default="{}")        # JSON: 动态权重
    simulation_id = Column(String, default="")          # 关联仿真ID
    simulation_summary = Column(Text, default="{}")     # JSON: 仿真摘要
    confidence = Column(Float, default=0.0)             # 可信度
    confidence_sources = Column(Text, default="{}")     # JSON: 可信度来源
    analysis_time = Column(Float, default=0.0)          # 分析耗时(秒)
    created_at = Column(DateTime, default=utcnow)


class BacktestRecord(Base):
    """回测记录（V2.R2新增）"""
    __tablename__ = "backtest_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, index=True)
    title = Column(String)
    seed_content = Column(Text)
    actual_outcome = Column(Text, default="{}")         # JSON: 实际结果
    mvp_prediction = Column(Text, default="{}")         # JSON: MVP预测
    v2_prediction = Column(Text, default="{}")          # JSON: V2预测
    accuracy_scores = Column(Text, default="{}")        # JSON: 准确率评分
    created_at = Column(DateTime, default=utcnow)


class ConsistencyRecord(Base):
    """一致性检查记录（V2.R2新增）"""
    __tablename__ = "consistency_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_hash = Column(String, index=True)
    run_count = Column(Integer, default=3)
    direction_consistency = Column(Float, default=0.0)
    platform_consistency = Column(Float, default=0.0)
    dimension_consistency = Column(Float, default=0.0)
    overall_consistency = Column(Float, default=0.0)
    run_details = Column(Text, default="[]")            # JSON: 各次运行详情
    created_at = Column(DateTime, default=utcnow)


class TrendPredictionRecord(Base):
    """趋势预测记录（V2.R3新增）"""
    __tablename__ = "trend_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(String, index=True)
    task_id = Column(String, nullable=True)
    pattern_id = Column(String, default="")
    pattern_name = Column(String, default="")
    pattern_confidence = Column(Float, default=0.0)
    predictions_json = Column(Text, default="[]")       # JSON: 短/中/长预测
    risk_level = Column(String, default="green")
    decision_action = Column(String, default="")
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)


class ReportRecord(Base):
    """报告记录（V2.R3新增）"""
    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, index=True)
    report_type = Column(String)                        # risk/simulation/trend/decision
    title = Column(String)
    content = Column(Text)
    summary = Column(Text, default="")
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)
