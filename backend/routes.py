from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction, SignalRecord, SeedEventRecord, AgentRecord, SocialRelation, AgentMemory, SimulationRecord, SimulationStatus, PropagationSnapshot, PropagationEdge, V2AnalysisResult, BacktestRecord, ConsistencyRecord, TrendPredictionRecord, ReportRecord, VideoAnalysisRecord, FrameRecord, BloggerProfileRecord, CompetitorCompareRecord
from backend.services.analyzer import run_analysis, MAX_TEXT_LENGTH
from backend.services.video_extractor import extract_video_text
from backend.services.signal.fetcher import HotlistFetcher
from backend.services.signal.rss_fetcher import RssFetcher
from backend.services.signal.event_detector import EventDetector
from backend.services.signal.keyword_extractor import KeywordExtractor
from backend.services.signal.deep_crawler import DeepCrawler
from backend.services.signal.models import SearchKeyword
from backend.services.graph.models import EntityType, RelationType
from backend.services.graph.graph_store import GraphStore
from backend.services.graph.graph_updater import GraphUpdater
from backend.services.graph.ontology_generator import generate_ontology, load_ontology
from backend.services.graph.ontology_templates import get_default_ontology

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=MAX_TEXT_LENGTH, description="待评估文案")


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str


class VideoExtractRequest(BaseModel):
    video_path: str = Field(..., description="本地视频文件路径")


class VideoAnalyzeRequest(BaseModel):
    video_path: str = Field(..., description="本地视频文件路径")


@router.post("/extract-video")
async def extract_video(req: VideoExtractRequest):
    """从本地视频文件提取文案文本"""
    result = await extract_video_text(req.video_path)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.post("/analyze-video", response_model=AnalyzeResponse)
async def analyze_video(req: VideoAnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """从本地视频文件提取文案并自动分析"""
    extract_result = await extract_video_text(req.video_path)
    if extract_result.get("error"):
        raise HTTPException(status_code=400, detail=extract_result["error"])

    text = extract_result.get("text", "")
    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="视频提取的文案太短，无法进行分析")

    task_id = str(uuid.uuid4())
    task = Task(id=task_id, text=text, status="processing", model=settings.DEEPSEEK_MODEL)
    db.add(task)
    db.commit()

    background_tasks.add_task(run_analysis, task_id, text)

    return AnalyzeResponse(task_id=task_id, status="processing")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    stripped = req.text.strip()
    if len(stripped) < 10:
        raise HTTPException(status_code=400, detail="文案内容至少需要10个字符")

    task_id = str(uuid.uuid4())
    task = Task(id=task_id, text=req.text, status="processing", model=settings.DEEPSEEK_MODEL)
    db.add(task)
    db.commit()

    background_tasks.add_task(run_analysis, task_id, req.text)

    return AnalyzeResponse(task_id=task_id, status="processing")


@router.get("/analyze/{task_id}")
async def get_result(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = {"task_id": task.id, "status": task.status}

    if task.status == "completed":
        summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).first()
        risk_items = db.query(RiskItem).filter(RiskItem.task_id == task_id).all()
        reactions = db.query(PlatformReaction).filter(PlatformReaction.task_id == task_id).all()

        if not summary:
            result["status"] = "failed"
            result["error"] = "分析结果数据缺失"
            return result

        result["overall_score"] = summary.overall_score
        result["suggestion"] = summary.suggestion
        result["dimensions"] = json.loads(summary.dimensions_json) if summary.dimensions_json else {}
        result["risk_items"] = [
            {"sentence": ri.sentence, "dimension": ri.dimension, "severity": ri.severity}
            for ri in risk_items
        ]
        result["platform_reactions"] = {
            r.platform: {"positive": r.positive, "neutral": r.neutral, "negative": r.negative}
            for r in reactions
        }
        result["rewrites"] = json.loads(summary.rewrites_json) if summary.rewrites_json else []

    elif task.status == "failed":
        result["error"] = task.error if hasattr(task, 'error') else "分析失败"

    return result
# ── V2.R1 增强风控 API ──────────────────────────────────────


class AnalyzeV2Request(BaseModel):
    text: str = Field(..., min_length=10, max_length=MAX_TEXT_LENGTH, description="待评估文案")
    mode: str = Field("quick", description="评估模式: quick(快速)/deep(深度仿真)")
    enable_signal: bool = Field(True, description="启用热点信号关联")
    enable_entity_chain: bool = Field(True, description="启用实体风险链")
    enable_simulation: bool = Field(False, description="启用仿真增强(仅deep模式)")


@router.post("/analyze/v2", response_model=AnalyzeResponse)
async def analyze_v2(req: AnalyzeV2Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """V2仿真增强风控分析"""
    stripped = req.text.strip()
    if len(stripped) < 10:
        raise HTTPException(status_code=400, detail="文案内容至少需要10个字符")

    if req.mode not in ("quick", "deep"):
        raise HTTPException(status_code=400, detail="mode必须为quick或deep")

    task_id = str(uuid.uuid4())
    task = Task(id=task_id, text=req.text, status="processing", model="v2-" + req.mode)
    db.add(task)
    db.commit()

    from backend.services.enhanced_analyzer import run_enhanced_analysis
    background_tasks.add_task(
        run_enhanced_analysis,
        task_id, req.text, req.mode,
        req.enable_signal, req.enable_entity_chain, req.enable_simulation,
    )

    return AnalyzeResponse(task_id=task_id, status="processing")


@router.get("/analyze/v2/{task_id}")
async def get_v2_result(task_id: str, db: Session = Depends(get_db)):
    """获取V2增强分析结果"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = {"task_id": task.id, "status": task.status}

    # MVP基础结果
    if task.status == "completed":
        summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).first()
        risk_items = db.query(RiskItem).filter(RiskItem.task_id == task_id).all()
        reactions = db.query(PlatformReaction).filter(PlatformReaction.task_id == task_id).all()

        if summary:
            result["mvp_result"] = {
                "overall_score": summary.overall_score,
                "suggestion": summary.suggestion,
                "dimensions": json.loads(summary.dimensions_json) if summary.dimensions_json else {},
                "risk_items": [
                    {"sentence": ri.sentence, "dimension": ri.dimension, "severity": ri.severity}
                    for ri in risk_items
                ],
                "platform_reactions": {
                    r.platform: {"positive": r.positive, "neutral": r.neutral, "negative": r.negative}
                    for r in reactions
                },
                "rewrites": json.loads(summary.rewrites_json) if summary.rewrites_json else [],
            }

    # V2增强结果
    v2_record = db.query(V2AnalysisResult).filter(V2AnalysisResult.task_id == task_id).first()
    if v2_record:
        result["v2_enhanced"] = {
            "mode": v2_record.mode,
            "mvp_score": v2_record.mvp_score,
            "v2_score": v2_record.v2_score,
            "signal_matches": json.loads(v2_record.signal_matches) if v2_record.signal_matches else [],
            "entity_risk_chains": json.loads(v2_record.entity_risk_chains) if v2_record.entity_risk_chains else [],
            "dynamic_weights": json.loads(v2_record.dynamic_weights) if v2_record.dynamic_weights else {},
            "simulation_id": v2_record.simulation_id,
            "simulation_summary": json.loads(v2_record.simulation_summary) if v2_record.simulation_summary else {},
            "confidence": v2_record.confidence,
            "confidence_sources": json.loads(v2_record.confidence_sources) if v2_record.confidence_sources else {},
            "analysis_time": v2_record.analysis_time,
        }

    return result

@router.get("/risk/context")
async def get_risk_context(db: Session = Depends(get_db)):
    """获取当前热点风险上下文"""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)

    recent_signals = (
        db.query(SignalRecord)
        .filter(SignalRecord.last_seen >= cutoff)
        .order_by(SignalRecord.appearance_count.desc())
        .limit(20)
        .all()
    )

    active_events = (
        db.query(SeedEventRecord)
        .filter(SeedEventRecord.status == "active")
        .order_by(SeedEventRecord.signal_strength.desc())
        .limit(10)
        .all()
    )

    return {
        "recent_signals": [
            {"title": s.title, "platform": s.source_platform, "count": s.appearance_count, "rank": s.rank}
            for s in recent_signals
        ],
        "active_events": [
            {"title": e.title, "category": e.category, "strength": e.signal_strength}
            for e in active_events
        ],
        "total_signals": len(recent_signals),
        "total_events": len(active_events),
    }


@router.get("/entities/{name}/risk-chain")
async def get_entity_risk_chain(name: str):
    """查询指定实体的风险链"""
    from backend.services.entity_risk_chain import EntityRiskChain
    chain_analyzer = EntityRiskChain()
    result = await chain_analyzer.trace(name)
    return {
        "entity": name,
        "entities": result.entities,
        "chains": [
            {
                "source": c.source_entity,
                "path": [{"name": p.entity_name, "type": p.entity_type, "risk": p.risk_level} for p in c.path],
                "total_risk": c.total_risk_score,
                "dimensions": c.risk_dimensions,
                "description": c.description,
            }
            for c in result.chains
        ],
        "max_risk_score": result.max_risk_score,
        "dimension_boosts": result.risk_dimension_boosts,
        "summary": result.analysis_summary,
    }
# ── V2.R2 回测与一致性 API ──────────────────────────────────


class BacktestRunRequest(BaseModel):
    case_ids: list[str] = Field(default_factory=list, description="指定案例ID列表，空则运行全部")


@router.post("/backtest/run")
async def run_backtest(req: BacktestRunRequest, background_tasks: BackgroundTasks):
    """运行回测"""
    from backend.services.backtest import BacktestRunner, PREDEFINED_CASES

    async def _run():
        runner = BacktestRunner()
        cases = PREDEFINED_CASES
        if req.case_ids:
            cases = [c for c in cases if c.case_id in req.case_ids]
        report = await runner.run_backtest(cases)
        runner.persist_report(report)

    background_tasks.add_task(_run)
    return {"status": "started", "message": f"回测已启动，{len(req.case_ids) or '全部'}案例"}


@router.get("/backtest/results")
async def get_backtest_results(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """获取回测结果"""
    records = (
        db.query(BacktestRecord)
        .order_by(BacktestRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "case_id": r.case_id,
            "title": r.title,
            "accuracy_scores": json.loads(r.accuracy_scores) if r.accuracy_scores else {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


class ConsistencyCheckRequest(BaseModel):
    text: str = Field(..., min_length=10, description="待检查文案")
    run_count: int = Field(3, ge=2, le=5, description="运行次数(2-5)")


@router.post("/consistency/check")
async def run_consistency_check(req: ConsistencyCheckRequest):
    """运行一致性检查"""
    from backend.services.consistency_checker import ConsistencyChecker

    checker = ConsistencyChecker(run_count=req.run_count)
    result = await checker.check(req.text)

    # 持久化
    db = SessionLocal()
    try:
        record = ConsistencyRecord(
            content_hash=result.content_hash,
            run_count=result.run_count,
            direction_consistency=result.direction_consistency,
            platform_consistency=result.platform_consistency,
            dimension_consistency=result.dimension_consistency,
            overall_consistency=result.overall_consistency,
            run_details=json.dumps(
                [{"index": r.run_index, "score": r.overall_score, "error": r.error} for r in result.runs],
                ensure_ascii=False,
            ),
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.get("/consistency/results")
async def get_consistency_results(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """获取一致性检查结果"""
    records = (
        db.query(ConsistencyRecord)
        .order_by(ConsistencyRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "content_hash": r.content_hash,
            "run_count": r.run_count,
            "direction_consistency": r.direction_consistency,
            "platform_consistency": r.platform_consistency,
            "dimension_consistency": r.dimension_consistency,
            "overall_consistency": r.overall_consistency,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/system/db-status")
async def get_db_status():
    """获取数据库状态"""
    from backend.database import get_db_type, engine
    from sqlalchemy import inspect

    db_type = get_db_type()
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return {
            "db_type": db_type,
            "tables": tables,
            "table_count": len(tables),
            "status": "connected",
        }
    except Exception as e:
        return {
            "db_type": db_type,
            "status": "error",
            "error": str(e),
        }


# ── 模型管理 API ────────────────────────────────────────────────


class ModelSettingRequest(BaseModel):
    provider: str = Field("", description="厂商ID，留空表示不覆盖")
    model: str = Field("", description="模型ID，留空表示不覆盖")

@router.get("/settings/model")
async def get_model_setting():
    """获取当前模型设置（运行时覆盖 + 环境变量默认值）"""
    from backend.services.llm_client import router as llm_router
    override = llm_router.get_override()
    return {
        "runtime": override,
        "env": {
            "provider": settings.DEFAULT_PROVIDER,
            "model": settings.DEFAULT_MODEL,
        },
    }


@router.post("/settings/model")
async def set_model_setting(req: ModelSettingRequest):
    """运行时切换模型，立即生效无需重启"""
    from backend.services.llm_client import router as llm_router
    llm_router.set_override(provider=req.provider, model=req.model)
    return {
        "success": True,
        "runtime": {"provider": req.provider, "model": req.model},
    }


# ── V2.R3 趋势预测与决策 API ────────────────────────────────


class TrendPredictRequest(BaseModel):
    simulation_data: dict = Field(default_factory=dict, description="仿真数据")
    risk_dimensions: dict = Field(default_factory=dict, description="风险维度分值")
    overall_score: int = Field(0, description="总风险分")


@router.post("/prediction/trend")
async def predict_trend(req: TrendPredictRequest):
    """趋势预测"""
    from backend.services.trend_predictor import TrendPredictor
    predictor = TrendPredictor()
    result = await predictor.predict(req.simulation_data, req.risk_dimensions, req.overall_score)

    # 持久化
    db = SessionLocal()
    try:
        record = TrendPredictionRecord(
            prediction_id=result.prediction_id,
            pattern_id=result.pattern.pattern_id if result.pattern else "",
            pattern_name=result.pattern.pattern_name if result.pattern else "",
            pattern_confidence=result.pattern.confidence if result.pattern else 0,
            predictions_json=json.dumps(
                [{"timeframe": p.timeframe, "direction": p.direction, "confidence": p.confidence} for p in result.predictions],
                ensure_ascii=False,
            ),
            risk_level=result.decision.risk_level if result.decision else "green",
            decision_action=result.decision.action if result.decision else "",
            summary=result.summary,
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.post("/prediction/pattern")
async def classify_pattern(req: TrendPredictRequest):
    """舆论模式分类"""
    from backend.services.trend_predictor import TrendPredictor
    predictor = TrendPredictor()
    situation = predictor._extract_situation(req.simulation_data, req.risk_dimensions)
    pattern = await predictor._classify_pattern(situation)
    return {
        "pattern_id": pattern.pattern_id,
        "pattern_name": pattern.pattern_name,
        "confidence": pattern.confidence,
        "similar_cases": pattern.similar_cases,
    }


class SimulationBranchRequest(BaseModel):
    sim_id: str = Field(..., description="原始仿真ID")
    intervention_type: str = Field("modify_text", description="干预类型")
    content: str = Field("", description="干预内容")
    platform: str = Field("weibo", description="干预平台")
    tick: int = Field(0, description="注入tick")


@router.post("/simulation/{sim_id}/branch")
async def create_simulation_branch(sim_id: str, req: SimulationBranchRequest):
    """创建反事实仿真分支"""
    from backend.services.counterfactual import CounterfactualEngine, Intervention
    engine = CounterfactualEngine()
    intervention = Intervention(
        intervention_type=req.intervention_type,
        content=req.content,
        platform=req.platform,
        tick=req.tick,
    )
    branch_id = await engine.create_branch(sim_id, intervention)
    return {"branch_id": branch_id, "original_sim_id": sim_id}


class SimulationCompareRequest(BaseModel):
    original_id: str
    branch_ids: list[str]


@router.post("/simulation/compare")
async def compare_simulations(req: SimulationCompareRequest):
    """对比仿真分支"""
    from backend.services.counterfactual import CounterfactualEngine
    engine = CounterfactualEngine()
    result = await engine.compare_branches(req.original_id, req.branch_ids)
    return {
        "original_id": result.original_id,
        "best_branch": result.best_branch,
        "score_improvement": result.score_improvement,
        "summary": result.summary,
    }


class ReportRequest(BaseModel):
    report_type: str = Field(..., description="报告类型: risk/simulation/trend/decision")
    data: dict = Field(default_factory=dict, description="报告数据")
    task_id: str = Field("", description="关联任务ID")


@router.post("/report/risk")
async def generate_risk_report(req: ReportRequest, background_tasks: BackgroundTasks):
    """生成风控报告"""
    from backend.services.report_generator import ReportGenerator
    gen = ReportGenerator()
    report = await gen.generate_risk_report(req.task_id, req.data)

    db = SessionLocal()
    try:
        record = ReportRecord(report_id=report.report_id, report_type="risk", title=report.title, content=report.content, summary=report.summary)
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
@router.post("/report/simulation")
async def generate_simulation_report(req: ReportRequest):
    """生成仿真报告"""
    from backend.services.report_generator import ReportGenerator
    gen = ReportGenerator()
    report = await gen.generate_simulation_report(req.data)
    return {"report_id": report.report_id, "title": report.title, "summary": report.summary, "content": report.content}


@router.post("/report/trend")
async def generate_trend_report(req: ReportRequest):
    """生成趋势报告"""
    from backend.services.report_generator import ReportGenerator
    gen = ReportGenerator()
    report = await gen.generate_trend_report(req.data)
    return {"report_id": report.report_id, "title": report.title, "summary": report.summary, "content": report.content}


@router.post("/report/decision")
async def generate_decision_report(req: ReportRequest):
    """生成决策报告"""
    from backend.services.report_generator import ReportGenerator
    gen = ReportGenerator()
    report = await gen.generate_decision_report(req.data)
    return {"report_id": report.report_id, "title": report.title, "summary": report.summary, "content": report.content}


class ConsensusRunRequest(BaseModel):
    text: str = Field(..., min_length=10, description="待评估文案")
    run_count: int = Field(3, ge=2, le=5, description="仿真次数")


@router.post("/consensus/run")
async def run_consensus(req: ConsensusRunRequest):
    """运行多轮仿真共识"""
    from backend.services.consensus_engine import ConsensusEngine
    engine = ConsensusEngine(run_count=req.run_count)
    result = await engine.run_consensus(req.text)
    return {
        "consensus_id": result.consensus_id,
        "direction_consensus": result.direction_consensus,
        "direction_confidence": result.direction_confidence,
        "consensus_score": result.consensus_score,
        "consensus_suggestion": result.consensus_suggestion,
        "overall_confidence": result.overall_confidence,
        "uncertainty_sources": result.uncertainty_sources,
        "divergent_dimensions": result.divergent_dimensions,
        "summary": result.summary,
    }

# ============ 信号采集 API ============

class CrawlRequest(BaseModel):
    keyword: str = Field("", description="手动搜索关键词")
    platforms: list[str] = Field(default_factory=lambda: ["微博", "知乎", "B站"], description="搜索平台")
    event_id: str = Field("", description="指定种子事件ID进行深度爬取")


class SchedulerRequest(BaseModel):
    action: str = Field(..., description="操作: start/stop")
    mode: str = Field("standard", description="调度模式: realtime/standard/economy/manual")


@router.get("/signals/hot")
async def get_hot_signals(platform: str = None, limit: int = 20, db: Session = Depends(get_db)):
    """获取当前各平台热榜数据"""
    from backend.main import signal_scheduler
    fetcher = HotlistFetcher()

    # 优先从数据库读取
    query = db.query(SignalRecord).filter(SignalRecord.signal_type == "hotlist")
    if platform:
        query = query.filter(SignalRecord.source_platform == platform)
    query = query.order_by(SignalRecord.last_seen.desc())

    records = query.limit(limit * 11).all()  # 每平台最多limit条

    # 按平台分组
    result: dict = {}
    for r in records:
        pid = r.source_platform
        platform_name = signal_scheduler._platform_map.get(pid, pid)
        if platform_name not in result:
            result[platform_name] = []
        if len(result[platform_name]) < limit:
            result[platform_name].append({
                "title": r.title,
                "url": r.url,
                "rank": r.rank,
                "is_new": r.is_new,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            })

    return {"platforms": result}


@router.get("/signals/events")
async def get_seed_events(
    category: str = None,
    status: str = "active",
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """获取种子事件列表"""
    query = db.query(SeedEventRecord)
    if status:
        query = query.filter(SeedEventRecord.status == status)
    if category:
        query = query.filter(SeedEventRecord.category == category)

    total = query.count()
    records = query.order_by(SeedEventRecord.created_at.desc()).offset(offset).limit(limit).all()

    events = []
    for r in records:
        events.append({
            "event_id": r.event_id,
            "title": r.title,
            "category": r.category,
            "signal_strength": r.signal_strength,
            "source_platforms": json.loads(r.source_platforms) if r.source_platforms else [],
            "crawl_depth": r.crawl_depth,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })

    return {"total": total, "events": events}


@router.get("/signals/events/{event_id}")
async def get_seed_event_detail(event_id: str, db: Session = Depends(get_db)):
    """获取种子事件详情"""
    record = db.query(SeedEventRecord).filter(SeedEventRecord.event_id == event_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="种子事件不存在")

    return {
        "event_id": record.event_id,
        "title": record.title,
        "description": record.description,
        "category": record.category,
        "signal_strength": record.signal_strength,
        "source_platforms": json.loads(record.source_platforms) if record.source_platforms else [],
        "source_urls": json.loads(record.source_urls) if record.source_urls else [],
        "comments": json.loads(record.comments_json) if record.comments_json else [],
        "related_events": json.loads(record.related_events) if record.related_events else [],
        "causal_parents": json.loads(record.causal_parents) if record.causal_parents else [],
        "causal_children": json.loads(record.causal_children) if record.causal_children else [],
        "crawl_depth": record.crawl_depth,
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.post("/signals/crawl")
async def trigger_crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    """手动触发深度爬取"""
    crawler = DeepCrawler()

    if req.event_id:
        # 基于种子事件爬取
        from backend.database import SessionLocal
        from backend.models import SeedEventRecord
        db = SessionLocal()
        try:
            event = db.query(SeedEventRecord).filter(SeedEventRecord.event_id == req.event_id).first()
            if not event:
                raise HTTPException(status_code=404, detail="种子事件不存在")

            keyword = SearchKeyword(
                keyword=event.title[:30],
                platforms=["微博", "知乎", "B站"],
                priority=1,
            )
            comments = await crawler.crawl_comments(keyword, max_comments=30)

            # 更新事件评论
            event.comments_json = json.dumps([
                {
                    "comment_id": c.comment_id,
                    "platform": c.platform,
                    "content": c.content[:200],
                    "sentiment": c.sentiment,
                    "sentiment_score": c.sentiment_score,
                    "confidence": c.confidence,
                }
                for c in comments
            ], ensure_ascii=False)
            event.crawl_depth = "deep"
            db.commit()
        finally:
            db.close()

        return {"status": "completed", "comments_count": len(comments)}

    elif req.keyword:
        keyword = SearchKeyword(
            keyword=req.keyword,
            platforms=req.platforms,
            priority=1,
        )
        comments = await crawler.crawl_comments(keyword, max_comments=30)
        return {
            "status": "completed",
            "comments_count": len(comments),
            "comments": [
                {
                    "platform": c.platform,
                    "content": c.content[:200],
                    "sentiment": c.sentiment,
                    "sentiment_score": c.sentiment_score,
                }
                for c in comments[:10]
            ],
        }
    else:
        raise HTTPException(status_code=400, detail="请提供 keyword 或 event_id")


@router.post("/signals/scheduler")
async def control_scheduler(req: SchedulerRequest):
    """调度器控制（启动/停止/切换模式）"""
    from backend.main import signal_scheduler

    if req.action == "start":
        success = signal_scheduler.start(req.mode)
        return {"status": "running" if success else "failed", "mode": signal_scheduler.current_mode}
    elif req.action == "stop":
        signal_scheduler.stop()
        return {"status": "stopped", "mode": "manual"}
    else:
        raise HTTPException(status_code=400, detail="action 必须是 start 或 stop")


# ============ 知识图谱 API ============

class OntologyGenerateRequest(BaseModel):
    domain_description: str = Field(..., description="领域描述文本")


class GraphExtractRequest(BaseModel):
    event_id: str = Field("", description="种子事件ID（从DB获取事件详情后抽取）")
    title: str = Field("", description="事件标题（手动提供时使用）")
    description: str = Field("", description="事件描述")


class GraphQueryRequest(BaseModel):
    entity_id: str = Field("", description="中心实体ID")
    depth: int = Field(2, ge=1, le=4, description="子图展开深度")
    limit: int = Field(100, ge=1, le=500, description="返回节点上限")


class GraphPathRequest(BaseModel):
    from_id: str = Field(..., description="起始实体ID")
    to_id: str = Field(..., description="目标实体ID")
    max_depth: int = Field(5, ge=1, le=10, description="最大搜索深度")


def _get_graph_store() -> GraphStore:
    """获取 GraphStore 单例"""
    from backend.main import graph_store
    return graph_store


@router.get("/graph/ontology")
async def get_ontology():
    """获取当前图谱本体定义"""
    ontology = load_ontology()
    return {
        "entity_types": [
            {"name": et.name, "description": et.description, "properties": et.properties}
            for et in ontology.entity_types
        ],
        "relation_types": [
            {"name": rt.name, "source": rt.source, "target": rt.target, "description": rt.description}
            for rt in ontology.relation_types
        ],
    }


@router.post("/graph/ontology/generate")
async def generate_ontology_endpoint(req: OntologyGenerateRequest):
    """根据领域描述动态生成本体"""
    ontology = await generate_ontology(req.domain_description)
    return {
        "entity_types": [
            {"name": et.name, "description": et.description, "properties": et.properties}
            for et in ontology.entity_types
        ],
        "relation_types": [
            {"name": rt.name, "source": rt.source, "target": rt.target, "description": rt.description}
            for rt in ontology.relation_types
        ],
    }


@router.post("/graph/extract")
async def extract_entities(req: GraphExtractRequest, db: Session = Depends(get_db)):
    """从事件中抽取实体和关系，存入图谱"""
    store = _get_graph_store()
    updater = GraphUpdater(store)

    if req.event_id:
        # 从数据库获取事件详情
        record = db.query(SeedEventRecord).filter(SeedEventRecord.event_id == req.event_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="种子事件不存在")
        event_data = {
            "event_id": record.event_id,
            "title": record.title,
            "description": record.description or "",
            "comments": json.loads(record.comments_json) if record.comments_json else [],
        }
    elif req.title:
        event_data = {
            "event_id": str(uuid.uuid4()),
            "title": req.title,
            "description": req.description,
            "comments": [],
        }
    else:
        raise HTTPException(status_code=400, detail="请提供 event_id 或 title")

    result = await updater.process_seed_event(event_data)
    if not result:
        return {"status": "no_extraction", "entities": 0, "relations": 0}

    return {
        "status": "completed",
        "entities": [
            {"entity_id": e.entity_id, "entity_type": e.entity_type, "name": e.name, "properties": e.properties}
            for e in result.entities
        ],
        "relations": [
            {"relation_type": r.relation_type, "source_id": r.source_id, "target_id": r.target_id, "weight": r.weight}
            for r in result.relations
        ],
    }


@router.get("/graph/entity/{entity_id}")
async def get_graph_entity(entity_id: str):
    """获取图谱实体详情"""
    store = _get_graph_store()
    entity = store.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    relations = store.get_relations(entity_id)
    return {"entity": entity, "relations": relations}


@router.post("/graph/query")
async def query_subgraph(req: GraphQueryRequest):
    """查询以某实体为中心的子图"""
    store = _get_graph_store()
    subgraph = store.get_subgraph(req.entity_id, depth=req.depth, limit=req.limit)
    return subgraph


@router.get("/graph/stats")
async def get_graph_stats():
    """获取图谱统计信息"""
    store = _get_graph_store()
    return store.get_stats()


# ============ 人格工厂 API ============

class AgentGenerateRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["bilibili", "xiaohongshu", "zhihu", "douyin"], description="目标平台列表")
    count_per_platform: int = Field(5, ge=1, le=50, description="每平台生成数量")
    inject_graph: bool = Field(False, description="是否注入知识图谱实体")
    persist: bool = Field(True, description="是否持久化到数据库")


class AgentUpdateRequest(BaseModel):
    persona_json: str = Field("", description="更新的人格JSON")
    status: str = Field("", description="更新状态: active/archived/evolved")


class NetworkGenerateRequest(BaseModel):
    k: int = Field(4, ge=2, le=10, description="小世界网络邻居数")
    beta: float = Field(0.3, ge=0.0, le=1.0, description="重连概率")
    oppose_ratio: float = Field(0.1, ge=0.0, le=0.5, description="对立关系占比")
    persist: bool = Field(True, description="是否持久化到数据库")


@router.post("/agents/generate")
async def generate_agents(req: AgentGenerateRequest):
    """批量生成Agent"""
    from backend.services.persona_generator import generate_agents_cross_platform
    from backend.services.persona.graph_injector import GraphInjector

    graph_injector = None
    if req.inject_graph:
        store = _get_graph_store()
        graph_injector = GraphInjector(store)

    result = await generate_agents_cross_platform(
        platforms=req.platforms,
        count_per_platform=req.count_per_platform,
        graph_injector=graph_injector,
        persist=req.persist,
    )

    total = sum(len(v) for v in result.values())
    return {
        "status": "completed",
        "total_agents": total,
        "by_platform": {k: len(v) for k, v in result.items()},
    }


@router.get("/agents")
async def list_agents(
    platform: str = None,
    archetype: str = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """列出Agent"""
    query = db.query(AgentRecord)
    if platform:
        query = query.filter(AgentRecord.platform == platform)
    if archetype:
        query = query.filter(AgentRecord.archetype_base.contains(archetype))
    if status:
        query = query.filter(AgentRecord.status == status)

    total = query.count()
    records = query.order_by(AgentRecord.created_at.desc()).offset(offset).limit(limit).all()

    agents = []
    for r in records:
        persona = json.loads(r.persona_json) if r.persona_json else {}
        agents.append({
            "agent_id": r.agent_id,
            "platform": r.platform,
            "archetype_base": r.archetype_base,
            "quality_score": r.quality_score,
            "status": r.status,
            "version": r.version,
            "name": persona.get("L1_basic", {}).get("occupation", "未知"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {"total": total, "agents": agents}


@router.get("/agents/stats")
async def get_agent_stats(db: Session = Depends(get_db)):
    """获取Agent统计信息"""
    from sqlalchemy import func
    total = db.query(AgentRecord).filter(AgentRecord.status == "active").count()

    platform_stats = db.query(
        AgentRecord.platform, func.count(AgentRecord.agent_id)
    ).filter(AgentRecord.status == "active").group_by(AgentRecord.platform).all()

    archetype_stats = db.query(
        AgentRecord.archetype_base, func.count(AgentRecord.agent_id)
    ).filter(AgentRecord.status == "active").group_by(AgentRecord.archetype_base).all()

    relation_count = db.query(SocialRelation).count()
    memory_count = db.query(AgentMemory).count()
    avg_quality = db.query(func.avg(AgentRecord.quality_score)).filter(
        AgentRecord.status == "active"
    ).scalar() or 0.0

    return {
        "total_agents": total,
        "by_platform": dict(platform_stats),
        "by_archetype": dict(archetype_stats),
        "total_relations": relation_count,
        "total_memories": memory_count,
        "avg_quality_score": round(float(avg_quality), 3),
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """获取Agent详情"""
    record = db.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Agent不存在")

    persona = json.loads(record.persona_json) if record.persona_json else {}
    return {
        "agent_id": record.agent_id,
        "platform": record.platform,
        "archetype_base": record.archetype_base,
        "persona": persona,
        "quality_score": record.quality_score,
        "status": record.status,
        "version": record.version,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest, db: Session = Depends(get_db)):
    """更新Agent"""
    record = db.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Agent不存在")

    if req.persona_json:
        record.persona_json = req.persona_json
        record.version += 1
    if req.status:
        record.status = req.status

    from datetime import datetime, timezone
    record.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "updated", "agent_id": agent_id, "version": record.version}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """删除Agent"""
    record = db.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Agent不存在")

    db.delete(record)
    # 同时删除关联记忆和社会关系
    db.query(AgentMemory).filter(AgentMemory.agent_id == agent_id).delete()
    db.query(SocialRelation).filter(
        (SocialRelation.agent_id_a == agent_id) | (SocialRelation.agent_id_b == agent_id)
    ).delete()
    db.commit()

    return {"status": "deleted", "agent_id": agent_id}


@router.get("/agents/{agent_id}/relations")
async def get_agent_relations(agent_id: str, db: Session = Depends(get_db)):
    """获取Agent的社会关系"""
    record = db.query(AgentRecord).filter(AgentRecord.agent_id == agent_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Agent不存在")

    relations = db.query(SocialRelation).filter(
        (SocialRelation.agent_id_a == agent_id) | (SocialRelation.agent_id_b == agent_id)
    ).all()

    result = []
    for r in relations:
        other_id = r.agent_id_b if r.agent_id_a == agent_id else r.agent_id_a
        direction = "outgoing" if r.agent_id_a == agent_id else "incoming"
        result.append({
            "relation_id": r.id,
            "other_agent_id": other_id,
            "type": r.relation_type,
            "weight": r.weight,
            "direction": direction,
            "platform": r.platform,
        })

    return {"agent_id": agent_id, "relations": result, "total": len(result)}


@router.get("/agents/{agent_id}/memories")
async def get_agent_memories(agent_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """获取Agent的记忆"""
    from backend.services.persona.memory import MemoryManager
    mm = MemoryManager()

    episodic = mm.get_episodic_memories(agent_id, limit=limit)
    semantic = mm.get_semantic_memories(agent_id, limit=5)
    working = mm.get_working_memory(agent_id)

    return {
        "agent_id": agent_id,
        "episodic": episodic,
        "semantic": semantic,
        "working_memory_count": len(working),
    }


@router.post("/agents/network/generate")
async def generate_social_network(req: NetworkGenerateRequest, db: Session = Depends(get_db)):
    """生成社会关系网络"""
    from backend.services.persona.social_network import SocialNetworkGenerator

    # 获取所有活跃Agent
    records = db.query(AgentRecord).filter(AgentRecord.status == "active").all()

    if len(records) < 3:
        raise HTTPException(status_code=400, detail="活跃Agent数量不足3个，无法生成关系网络")

    agents = []
    for r in records:
        persona = json.loads(r.persona_json) if r.persona_json else {}
        persona["persona_id"] = r.agent_id
        persona["platform"] = r.platform
        agents.append(persona)

    generator = SocialNetworkGenerator(
        k=req.k, beta=req.beta, oppose_ratio=req.oppose_ratio
    )
    relations = generator.generate(agents)

    if req.persist:
        generator.persist_relations(relations)

    # 统计
    type_counts = {}
    for r in relations:
        t = r.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "status": "completed",
        "total_relations": len(relations),
        "agent_count": len(agents),
        "type_distribution": type_counts,
    }


# ============ 社交仿真 API ============

class SimulationCreateRequest(BaseModel):
    topic: str = Field(..., description="仿真话题/种子内容")
    max_ticks: int = Field(144, ge=10, le=1000, description="最大tick数")
    start_hour: int = Field(8, ge=0, le=23, description="仿真起始小时")
    time_acceleration: int = Field(60, ge=10, le=360, description="每tick推进的仿真分钟数")
    tick_interval: float = Field(0.5, ge=0.1, le=5.0, description="tick间隔（秒）")
    b_agent_per_tick: int = Field(5, ge=1, le=20, description="每tick参与LLM决策的B级Agent数")


class SimulationControlRequest(BaseModel):
    action: str = Field(..., description="操作: start/pause/resume/stop")


# 全局仿真引擎实例
_active_simulations: Dict[str, Any] = {}
@router.post("/simulation/{sim_id}/start")
async def start_simulation(sim_id: str, background_tasks: BackgroundTasks):
    """启动仿真"""
    engine = _active_simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail="仿真任务不存在")

    if engine.status == "running":
        raise HTTPException(status_code=400, detail="仿真已在运行中")

    # 更新状态
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        record = db.query(SimulationStatus).filter(SimulationStatus.sim_id == sim_id).first()
        if record:
            record.status = "running"
            db.commit()
    finally:
        db.close()
@router.post("/simulation/{sim_id}/pause")
async def pause_simulation(sim_id: str):
    """暂停仿真"""
    engine = _active_simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail="仿真任务不存在")

    engine.pause()
    return {"sim_id": sim_id, "status": "paused"}


@router.post("/simulation/{sim_id}/resume")
async def resume_simulation(sim_id: str):
    """恢复仿真"""
    engine = _active_simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail="仿真任务不存在")

    engine.resume()
    return {"sim_id": sim_id, "status": "running"}


@router.post("/simulation/{sim_id}/stop")
async def stop_simulation(sim_id: str):
    """停止仿真"""
    engine = _active_simulations.get(sim_id)
    if not engine:
        raise HTTPException(status_code=404, detail="仿真任务不存在")

    engine.stop()

    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        record = db.query(SimulationStatus).filter(SimulationStatus.sim_id == sim_id).first()
        if record:
            record.status = "stopped"
            db.commit()
    finally:
        db.close()
@router.get("/simulation/{sim_id}/status")
async def get_simulation_status(sim_id: str):
    """获取仿真状态"""
    engine = _active_simulations.get(sim_id)
    if engine:
        return engine.get_status()

    # 从数据库查询已完成的仿真
    from backend.services.simulation.recorder import SimulationRecorder
    recorder = SimulationRecorder()
    info = recorder.get_simulation_info(sim_id)
    if not info:
        raise HTTPException(status_code=404, detail="仿真任务不存在")
    return info


@router.get("/simulation/{sim_id}/timeline")
async def get_simulation_timeline(
    sim_id: str,
    start_tick: int = 0,
    end_tick: int = None,
    limit: int = 100,
):
    """获取仿真时间线"""
    from backend.services.simulation.recorder import SimulationRecorder
    recorder = SimulationRecorder()
    timeline = recorder.get_timeline(sim_id, start_tick, end_tick, limit)
    return {"sim_id": sim_id, "events": timeline, "count": len(timeline)}


@router.get("/simulation/{sim_id}/platform/{platform}")
async def get_platform_snapshot(sim_id: str, platform: str):
    """获取平台快照"""
    from backend.services.simulation.recorder import SimulationRecorder
    recorder = SimulationRecorder()
    snapshot = recorder.get_platform_snapshot(sim_id, platform)
    if not snapshot:
        engine = _active_simulations.get(sim_id)
        if engine:
            plat = engine.platforms.get(platform)
            if plat:
                return plat.get_snapshot()
        raise HTTPException(status_code=404, detail="平台快照不存在")
    return snapshot
# ── V2.5 传播动力学 API ──────────────────────────────────

@router.get("/simulation/{sim_id}/propagation")
async def get_propagation(sim_id: str, db: Session = Depends(get_db)):
    """获取传播树与传播统计数据"""
    engine = _active_simulations.get(sim_id)

    if engine:
        # 从活跃引擎获取实时数据
        spread_model = engine.spread_model
        return {
            "sim_id": sim_id,
            "propagation_tree": spread_model.propagation_tree.to_dict(),
            "current_stage": spread_model.current_stage.value,
            "stage_label": __import__(
                "backend.services.simulation.propagation.spread_model",
                fromlist=["STAGE_LABELS"]
            ).STAGE_LABELS.get(spread_model.current_stage, ""),
            "kinetic_history": spread_model.kinetic_history[-30:],
            "stage_history": spread_model.stage_history,
            "summary": spread_model.get_summary(),
        }

    # 从DB查询历史数据
    snapshots = db.query(PropagationSnapshot).filter(
        PropagationSnapshot.simulation_id == sim_id
    ).order_by(PropagationSnapshot.tick).all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="传播数据不存在")

    return {
        "sim_id": sim_id,
        "snapshots": [
            {
                "tick": s.tick,
                "stage": s.stage,
                "kinetic": s.propagation_kinetic,
                "polarization": s.polarization_index,
                "reach": s.reach_count,
                "depth": s.depth,
            }
            for s in snapshots
        ],
        "edges_count": db.query(PropagationEdge).filter(
            PropagationEdge.simulation_id == sim_id
        ).count(),
    }


@router.get("/simulation/{sim_id}/polarization")
async def get_polarization(sim_id: str, db: Session = Depends(get_db)):
    """获取极化指数时间序列"""
    engine = _active_simulations.get(sim_id)

    if engine:
        history = engine.spread_model.polarization_calc.get_history()
        return {
            "sim_id": sim_id,
            "current_polarization": history[-1]["polarization_index"] if history else 0.0,
            "trend": engine.spread_model.polarization_calc.get_trend(),
            "history": history[-50:],
        }

    # 从DB查询
    snapshots = db.query(PropagationSnapshot).filter(
        PropagationSnapshot.simulation_id == sim_id
    ).order_by(PropagationSnapshot.tick).all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="极化数据不存在")

    return {
        "sim_id": sim_id,
        "history": [
            {"tick": s.tick, "polarization_index": s.polarization_index}
            for s in snapshots
        ],
    }


@router.get("/simulation/{sim_id}/kinetic")
async def get_kinetic(sim_id: str, db: Session = Depends(get_db)):
    """获取传播动能时间序列"""
    engine = _active_simulations.get(sim_id)

    if engine:
        return {
            "sim_id": sim_id,
            "current_kinetic": engine.spread_model.prev_kinetic,
            "history": engine.spread_model.kinetic_history[-50:],
        }

    # 从DB查询
    snapshots = db.query(PropagationSnapshot).filter(
        PropagationSnapshot.simulation_id == sim_id
    ).order_by(PropagationSnapshot.tick).all()

    if not snapshots:
        raise HTTPException(status_code=404, detail="动能数据不存在")

    return {
        "sim_id": sim_id,
        "history": [
            {"tick": s.tick, "kinetic": s.propagation_kinetic}
            for s in snapshots
        ],
    }


@router.get("/simulation/{sim_id}/replay")
async def get_replay_timeline(sim_id: str):
    """获取回放时间轴"""
    from backend.services.simulation.replay.timeline import ReplayTimeline
    timeline = ReplayTimeline(sim_id)
    data = await timeline.get_timeline()
    return {"sim_id": sim_id, "timeline": data, "count": len(data)}


@router.get("/simulation/{sim_id}/snapshot/{tick}")
async def get_snapshot(sim_id: str, tick: int):
    """获取指定tick的快照"""
    from backend.services.simulation.replay.timeline import ReplayTimeline
    timeline = ReplayTimeline(sim_id)
    frame = await timeline.get_frame(tick)
    if not frame:
        raise HTTPException(status_code=404, detail=f"tick {tick} 的快照不存在")
    return frame


@router.get("/simulation/{sim_id}/diff")
async def get_snapshot_diff(sim_id: str, tick1: int, tick2: int):
    """对比两个时刻的快照差异"""
    from backend.services.simulation.replay.timeline import ReplayTimeline
    timeline = ReplayTimeline(sim_id)
    diff = await timeline.get_diff(tick1, tick2)
    return diff


@router.get("/simulation/{sim_id}/monitor")
async def get_monitor_report(sim_id: str):
    """获取Watcher监控报告"""
    engine = _active_simulations.get(sim_id)

    if engine and engine._latest_monitor_report:
        return {
            "sim_id": sim_id,
            "current_report": engine._latest_monitor_report.to_dict(),
            "history": engine.watcher.get_report_history(10),
        }

    raise HTTPException(status_code=404, detail="监控报告不存在（仿真可能未运行或未到观察周期）")


@router.get("/simulation/{sim_id}/interventions")
async def get_interventions(sim_id: str):
    """获取Guardian干预日志"""
    engine = _active_simulations.get(sim_id)

    if engine:
        return {
            "sim_id": sim_id,
            "interventions": engine.guardian.get_intervention_log(50),
        }

    raise HTTPException(status_code=404, detail="仿真任务不存在")


@router.get("/simulation/{sim_id}/influence-factors")
async def get_influence_factors(sim_id: str, agent_id: str = None, platform: str = None):
    """获取影响因素量化结果"""
    engine = _active_simulations.get(sim_id)

    if not engine:
        raise HTTPException(status_code=404, detail="仿真任务不存在")

    from backend.services.simulation.propagation.influence_quantifier import InfluenceQuantifier
    quantifier = InfluenceQuantifier()

    result = {"sim_id": sim_id}

    # Agent因素
    if agent_id:
        agent = engine.agents.get(agent_id, {})
        result["agent_factors"] = quantifier.quantify_agent_factors(agent)
    else:
        # 返回所有Agent的平均因素
        if engine.agents:
            sample_ids = list(engine.agents.keys())[:5]
            agent_results = {}
            for aid in sample_ids:
                agent_results[aid] = quantifier.quantify_agent_factors(engine.agents[aid])
            result["agent_factors_sample"] = agent_results

    # 平台因素
    if platform and platform in engine.platforms:
        result["platform_factors"] = quantifier.quantify_platform_factors(platform)
    else:
        # 返回所有平台因素
        result["platform_factors"] = {
            pname: quantifier.quantify_platform_factors(pname)
            for pname in engine.platforms.keys()
        }

    return result


# ═══════════════════════════════════════════════════════════════
# V2.R4 多模态风控 API
# ═══════════════════════════════════════════════════════════════

class VideoAnalyzeV2Request(BaseModel):
    url: str = Field("", description="视频链接(B站/抖音等)")
    video_path: str = Field("", description="本地视频文件路径(优先于url)")
    mode: str = Field("quick", description="分析模式: quick(关键帧+OCR)/deep(全部模态)")
    max_frames: int = Field(50, description="最大关键帧数")


class FrameAnalyzeRequest(BaseModel):
    video_path: str = Field(..., description="视频文件路径")
    max_frames: int = Field(50, description="最大关键帧数")
    enable_ocr: bool = Field(True, description="是否启用OCR")
    enable_risk: bool = Field(True, description="是否启用画面风险评估")


class AudioTranscribeRequest(BaseModel):
    video_path: str = Field(..., description="视频文件路径")
    enable_sentiment: bool = Field(True, description="是否启用情感分析")


@router.post("/analyze-video/v2")
async def analyze_video_v2(req: VideoAnalyzeV2Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """多模态视频风控分析（V2.R4）- 关键帧提取+OCR+画面风险+音频+交叉检测"""
    task_id = str(uuid.uuid4())

    record = VideoAnalysisRecord(
        task_id=task_id,
        video_url=req.url,
        video_path=req.video_path,
        status="processing",
    )
    db.add(record)
    db.commit()

    background_tasks.add_task(_run_video_analysis_v2, task_id, req.url, req.video_path, req.mode, req.max_frames)

    return {"task_id": task_id, "status": "processing", "mode": req.mode}


@router.post("/analyze-frames")
async def analyze_frames(req: FrameAnalyzeRequest, db: Session = Depends(get_db)):
    """关键帧提取+OCR+画面风险分析"""
    import time
    start_time = time.time()

    # 1. 提取关键帧
    from backend.services.keyframe_extractor import KeyframeExtractor
    extractor = KeyframeExtractor({"max_frames": req.max_frames})
    frame_result = await extractor.extract(req.video_path)

    if frame_result.error:
        raise HTTPException(status_code=400, detail=frame_result.error)

    result = {
        "total_frames": frame_result.total_frames,
        "duration": frame_result.duration,
        "method_used": frame_result.method_used,
        "scene_count": frame_result.scene_count,
        "frames": [
            {
                "index": f.index,
                "timestamp": f.timestamp,
                "file_path": f.file_path,
                "method": f.method,
                "scene_index": f.scene_index,
            }
            for f in frame_result.frames
        ],
    }

    # 2. OCR识别
    if req.enable_ocr:
        from backend.services.frame_ocr import FrameOCR
        ocr = FrameOCR()
        ocr_result = await ocr.extract_video_text(frame_result.frames)
        result["ocr"] = {
            "engine_used": ocr_result.engine_used,
            "all_text": ocr_result.all_text,
            "frame_count": len(ocr_result.frame_results),
            "frame_results": [
                {
                    "frame_index": fr.frame_index,
                    "timestamp": fr.timestamp,
                    "full_text": fr.full_text,
                    "items": [
                        {"text": item.text, "confidence": item.confidence, "position": item.position}
                        for item in fr.items
                    ],
                }
                for fr in ocr_result.frame_results
            ],
        }

    # 3. 画面风险评估
    if req.enable_risk:
        from backend.services.frame_risk import FrameRiskAssessor
        assessor = FrameRiskAssessor()
        risk_result = await assessor.assess_video_frames(frame_result.frames)
        result["frame_risks"] = {
            "overall_risk_level": risk_result.overall_risk_level,
            "high_risk_frames": risk_result.high_risk_frames,
            "risk_summary": risk_result.risk_summary,
            "frame_results": [
                {
                    "frame_index": fr.frame_index,
                    "timestamp": fr.timestamp,
                    "risk_level": fr.risk_level,
                    "summary": fr.summary,
                    "risks": [
                        {
                            "risk_type": r.risk_type,
                            "description": r.description,
                            "severity": r.severity,
                            "confidence": r.confidence,
                            "suggestion": r.suggestion,
                        }
                        for r in fr.risks
                    ],
                }
                for fr in risk_result.frame_results
            ],
        }

    result["analysis_time"] = round(time.time() - start_time, 2)
    return result


@router.get("/frames/{task_id}")
async def get_frame_results(task_id: str, db: Session = Depends(get_db)):
    """获取视频帧分析结果"""
    record = db.query(VideoAnalysisRecord).filter(VideoAnalysisRecord.task_id == task_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="视频分析任务不存在")

    result = {
        "task_id": task_id,
        "status": record.status,
        "keyframe_method": record.keyframe_method,
        "keyframe_count": record.keyframe_count,
        "ocr_engine": record.ocr_engine,
        "ocr_text": record.ocr_text,
        "frame_risk_level": record.frame_risk_level,
        "audio_engine": record.audio_engine,
        "audio_text": record.audio_text,
        "overall_risk_level": record.overall_risk_level,
        "overall_risk_score": record.overall_risk_score,
        "analysis_time": record.analysis_time,
    }

    if record.error:
        result["error"] = record.error

    # 获取帧记录
    frames = db.query(FrameRecord).filter(FrameRecord.task_id == task_id).order_by(FrameRecord.frame_index).all()
    result["frames"] = [
        {
            "frame_index": f.frame_index,
            "timestamp": f.timestamp,
            "file_path": f.file_path,
            "ocr_text": f.ocr_text,
            "risk_level": f.risk_level,
        }
        for f in frames
    ]

    return result


@router.post("/audio/transcribe")
async def transcribe_audio(req: AudioTranscribeRequest):
    """音频转写+情感分析"""
    from backend.services.audio_analyzer import AudioAnalyzer
    analyzer = AudioAnalyzer({"enable_sentiment": req.enable_sentiment})
    result = await analyzer.analyze(req.video_path)

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    response = {
        "engine_used": result.engine_used,
        "duration": result.duration,
        "language": result.language,
        "full_text": result.full_text,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in result.segments
        ],
        "risk_text": result.risk_text,
    }

    if result.sentiment:
        response["sentiment"] = {
            "sentiment": result.sentiment.sentiment,
            "emotion": result.sentiment.emotion,
            "intensity": result.sentiment.intensity,
            "confidence": result.sentiment.confidence,
            "description": result.sentiment.description,
        }

    return response


@router.get("/cross-modal/{task_id}")
async def get_cross_modal_risk(task_id: str, db: Session = Depends(get_db)):
    """获取交叉模态风险检测结果"""
    record = db.query(VideoAnalysisRecord).filter(VideoAnalysisRecord.task_id == task_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="视频分析任务不存在")

    if record.status != "completed":
        return {"task_id": task_id, "status": record.status}

    return {
        "task_id": task_id,
        "status": "completed",
        "text_risks": {},  # 文字风控需要单独查
        "ocr_text": record.ocr_text,
        "audio_text": record.audio_text,
        "audio_sentiment": json.loads(record.audio_sentiment) if record.audio_sentiment else {},
        "frame_risk_level": record.frame_risk_level,
        "cross_modal_risks": json.loads(record.cross_modal_risks) if record.cross_modal_risks else [],
        "overall_risk_level": record.overall_risk_level,
        "overall_risk_score": record.overall_risk_score,
        "risk_breakdown": json.loads(record.risk_breakdown) if record.risk_breakdown else {},
    }


async def _run_video_analysis_v2(task_id: str, video_url: str, video_path: str, mode: str, max_frames: int):
    """后台运行多模态视频分析"""
    import time
    start_time = time.time()

    from backend.database import SessionLocal
    db = SessionLocal()

    try:
        record = db.query(VideoAnalysisRecord).filter(VideoAnalysisRecord.task_id == task_id).first()
        if not record:
            return

        # 解析视频路径
        actual_path = video_path
        if not actual_path and video_url:
            # 下载视频
            from backend.services.keyframe_extractor import KeyframeExtractor
            extractor = KeyframeExtractor({"max_frames": max_frames})
            downloaded = await extractor._download_video(video_url)
            if downloaded:
                actual_path = downloaded
                record.video_path = downloaded
                db.commit()
            else:
                record.status = "failed"
                record.error = "无法下载视频"
                db.commit()
                return

        if not actual_path or not os.path.exists(actual_path):
            record.status = "failed"
            record.error = "视频文件不存在"
            db.commit()
            return

        # 1. 关键帧提取
        from backend.services.keyframe_extractor import KeyframeExtractor
        extractor = KeyframeExtractor({"max_frames": max_frames})
        frame_result = await extractor.extract(actual_path)

        if frame_result.error:
            record.status = "failed"
            record.error = frame_result.error
            db.commit()
            return

        record.keyframe_method = frame_result.method_used
        record.keyframe_count = len(frame_result.frames)
        record.keyframe_dir = os.path.dirname(frame_result.frames[0].file_path) if frame_result.frames else ""

        # 保存帧记录
        for f in frame_result.frames:
            frame_record = FrameRecord(
                task_id=task_id,
                frame_index=f.index,
                timestamp=f.timestamp,
                file_path=f.file_path,
                method=f.method,
                scene_index=f.scene_index,
            )
            db.add(frame_record)

        db.commit()

        # 2. OCR识别
        ocr_text = ""
        if mode in ("quick", "deep"):
            from backend.services.frame_ocr import FrameOCR
            ocr = FrameOCR()
            ocr_result = await ocr.extract_video_text(frame_result.frames)
            record.ocr_engine = ocr_result.engine_used
            record.ocr_text = ocr_result.all_text
            ocr_text = ocr_result.all_text

            # 更新帧OCR结果
            for fr in ocr_result.frame_results:
                frame_rec = db.query(FrameRecord).filter(
                    FrameRecord.task_id == task_id,
                    FrameRecord.timestamp == fr.timestamp,
                ).first()
                if frame_rec:
                    frame_rec.ocr_text = fr.full_text
                    frame_rec.ocr_items = json.dumps(
                        [{"text": item.text, "confidence": item.confidence, "position": item.position}
                         for item in fr.items]
                    )
            db.commit()

        # 3. 画面风险评估
        frame_risk_level = "safe"
        frame_risk_details = []
        if mode in ("quick", "deep"):
            from backend.services.frame_risk import FrameRiskAssessor
            assessor = FrameRiskAssessor()
            risk_result = await assessor.assess_video_frames(frame_result.frames)
            record.frame_risk_level = risk_result.overall_risk_level
            frame_risk_level = risk_result.overall_risk_level
            frame_risk_details = [
                {
                    "frame_index": fr.frame_index,
                    "risk_level": fr.risk_level,
                    "risks": [{"risk_type": r.risk_type, "severity": r.severity, "description": r.description}
                              for r in fr.risks],
                }
                for fr in risk_result.frame_results
            ]
            record.frame_risk_details = json.dumps(frame_risk_details)

            # 更新帧风险结果
            for fr in risk_result.frame_results:
                frame_rec = db.query(FrameRecord).filter(
                    FrameRecord.task_id == task_id,
                    FrameRecord.timestamp == fr.timestamp,
                ).first()
                if frame_rec:
                    frame_rec.risk_level = fr.risk_level
                    frame_rec.risk_details = json.dumps(
                        [{"risk_type": r.risk_type, "severity": r.severity, "description": r.description}
                         for r in fr.risks]
                    )
            db.commit()

        # 4. 音频分析（deep模式）
        audio_text = ""
        audio_sentiment = {}
        if mode == "deep":
            from backend.services.audio_analyzer import AudioAnalyzer
            analyzer = AudioAnalyzer({"enable_sentiment": True})
            audio_result = await analyzer.analyze(actual_path)

            if not audio_result.error:
                record.audio_engine = audio_result.engine_used
                record.audio_text = audio_result.full_text
                record.audio_language = audio_result.language
                audio_text = audio_result.full_text

                if audio_result.sentiment:
                    audio_sentiment = {
                        "sentiment": audio_result.sentiment.sentiment,
                        "emotion": audio_result.sentiment.emotion,
                        "intensity": audio_result.sentiment.intensity,
                        "confidence": audio_result.sentiment.confidence,
                    }
                    record.audio_sentiment = json.dumps(audio_sentiment)
            db.commit()

        # 5. 交叉风险检测（deep模式）
        cross_risks = []
        if mode == "deep":
            from backend.services.cross_modal_risk import CrossModalRiskDetector
            detector = CrossModalRiskDetector()
            cross_result = await detector.detect(
                text_analysis={"text": "", "risk_level": "safe"},  # 文字风控结果需要从Task获取
                image_risks=frame_risk_details,
                audio_analysis=audio_sentiment if audio_sentiment else None,
                ocr_text=ocr_text,
                audio_text=audio_text,
                task_id=task_id,
            )

            cross_risks = [
                {
                    "risk_type": r.risk_type,
                    "modalities": r.modalities,
                    "description": r.description,
                    "severity": r.severity,
                    "confidence": r.confidence,
                }
                for r in cross_result.cross_risks
            ]
            record.cross_modal_risks = json.dumps(cross_risks)
            record.overall_risk_level = cross_result.overall_risk_level
            record.overall_risk_score = cross_result.overall_risk_score
            record.risk_breakdown = json.dumps(cross_result.risk_breakdown)
            db.commit()

        # 完成
        record.analysis_time = round(time.time() - start_time, 2)
        record.status = "completed"
        db.commit()

    except Exception as e:
        record = db.query(VideoAnalysisRecord).filter(VideoAnalysisRecord.task_id == task_id).first()
        if record:
            record.status = "failed"
            record.error = str(e)
            db.commit()
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# V2.R6 博主附加服务 API
# ═══════════════════════════════════════════════════════════════

class BloggerAnalyzeRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    name: str = Field("", description="博主名称")
    platform: str = Field("", description="平台")
    contents: list = Field(default_factory=list, description="历史内容列表")


class BloggerRecommendRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    hot_topics: list = Field(default_factory=list, description="可选热点列表")


class CompetitorCompareRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    competitor_id: str = Field(..., description="竞品博主ID")
    competitor_contents: list = Field(default_factory=list, description="竞品历史内容")


@router.post("/blogger/analyze")
async def analyze_blogger(req: BloggerAnalyzeRequest, db: Session = Depends(get_db)):
    """生成博主风格画像"""
    from backend.services.blogger_profiler import BloggerProfiler

    profiler = BloggerProfiler()
    profile = await profiler.generate_profile(
        blogger_id=req.blogger_id,
        name=req.name,
        platform=req.platform,
        contents=req.contents,
    )

    # 保存到数据库
    import dataclasses
    existing = db.query(BloggerProfileRecord).filter(
        BloggerProfileRecord.blogger_id == req.blogger_id
    ).first()

    profile_data = {
        "vocabulary_json": json.dumps(dataclasses.asdict(profile.vocabulary), ensure_ascii=False),
        "expression_json": json.dumps(dataclasses.asdict(profile.expression), ensure_ascii=False),
        "topics_json": json.dumps(dataclasses.asdict(profile.topics), ensure_ascii=False),
        "audience_json": json.dumps(dataclasses.asdict(profile.audience), ensure_ascii=False),
        "risk_json": json.dumps(dataclasses.asdict(profile.risk), ensure_ascii=False),
        "overall_style": profile.overall_style,
        "style_tags": json.dumps(profile.style_tags, ensure_ascii=False),
        "confidence": profile.confidence,
        "content_count": profile.content_count,
        "name": req.name,
        "platform": req.platform,
    }

    if existing:
        for k, v in profile_data.items():
            setattr(existing, k, v)
        existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    else:
        record = BloggerProfileRecord(blogger_id=req.blogger_id, **profile_data)
        db.add(record)

    db.commit()

    return {
        "blogger_id": profile.blogger_id,
        "name": profile.name,
        "overall_style": profile.overall_style,
        "style_tags": profile.style_tags,
        "confidence": profile.confidence,
        "vocabulary": dataclasses.asdict(profile.vocabulary),
        "expression": dataclasses.asdict(profile.expression),
        "topics": dataclasses.asdict(profile.topics),
        "audience": dataclasses.asdict(profile.audience),
        "risk": dataclasses.asdict(profile.risk),
    }


@router.get("/blogger/{blogger_id}/profile")
async def get_blogger_profile(blogger_id: str, db: Session = Depends(get_db)):
    """获取博主画像"""
    record = db.query(BloggerProfileRecord).filter(
        BloggerProfileRecord.blogger_id == blogger_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="博主画像不存在")

    return {
        "blogger_id": record.blogger_id,
        "name": record.name,
        "platform": record.platform,
        "content_count": record.content_count,
        "vocabulary": json.loads(record.vocabulary_json) if record.vocabulary_json else {},
        "expression": json.loads(record.expression_json) if record.expression_json else {},
        "topics": json.loads(record.topics_json) if record.topics_json else {},
        "audience": json.loads(record.audience_json) if record.audience_json else {},
        "risk": json.loads(record.risk_json) if record.risk_json else {},
        "overall_style": record.overall_style,
        "style_tags": json.loads(record.style_tags) if record.style_tags else [],
        "confidence": record.confidence,
        "updated_at": str(record.updated_at) if record.updated_at else "",
    }


@router.post("/blogger/recommend")
async def recommend_topics(req: BloggerRecommendRequest, db: Session = Depends(get_db)):
    """选题推荐"""
    from backend.services.topic_recommender import TopicRecommender

    # 获取博主画像
    record = db.query(BloggerProfileRecord).filter(
        BloggerProfileRecord.blogger_id == req.blogger_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="请先生成博主画像")

    profile_data = {
        "vocabulary": json.loads(record.vocabulary_json) if record.vocabulary_json else {},
        "expression": json.loads(record.expression_json) if record.expression_json else {},
        "topics": json.loads(record.topics_json) if record.topics_json else {},
        "audience": json.loads(record.audience_json) if record.audience_json else {},
        "risk": json.loads(record.risk_json) if record.risk_json else {},
        "overall_style": record.overall_style,
        "style_tags": json.loads(record.style_tags) if record.style_tags else [],
    }

    recommender = TopicRecommender()
    result = await recommender.recommend(
        blogger_profile=profile_data,
        hot_topics=req.hot_topics if req.hot_topics else None,
        blogger_id=req.blogger_id,
        blogger_name=record.name,
    )

    return {
        "blogger_id": result.blogger_id,
        "blogger_name": result.blogger_name,
        "hot_topics_used": result.hot_topics_used,
        "recommendations": [
            {
                "topic": r.topic,
                "angle": r.angle,
                "reason": r.reason,
                "trend_score": r.trend_score,
                "style_match": r.style_match,
                "risk_level": r.risk_level,
                "risk_note": r.risk_note,
                "estimated_reach": r.estimated_reach,
                "priority": r.priority,
            }
            for r in result.recommendations
        ],
        "summary": result.summary,
    }


@router.post("/competitor/compare")
async def compare_competitors(req: CompetitorCompareRequest, db: Session = Depends(get_db)):
    """竞品对标分析"""
    from backend.services.competitor_analyzer import CompetitorAnalyzer
    from backend.services.blogger_profiler import BloggerProfiler

    # 获取博主画像
    blogger_record = db.query(BloggerProfileRecord).filter(
        BloggerProfileRecord.blogger_id == req.blogger_id
    ).first()

    if not blogger_record:
        raise HTTPException(status_code=404, detail="请先生成博主画像")

    blogger_data = {
        "vocabulary": json.loads(blogger_record.vocabulary_json) if blogger_record.vocabulary_json else {},
        "expression": json.loads(blogger_record.expression_json) if blogger_record.expression_json else {},
        "topics": json.loads(blogger_record.topics_json) if blogger_record.topics_json else {},
        "audience": json.loads(blogger_record.audience_json) if blogger_record.audience_json else {},
        "risk": json.loads(blogger_record.risk_json) if blogger_record.risk_json else {},
        "overall_style": blogger_record.overall_style,
        "style_tags": json.loads(blogger_record.style_tags) if blogger_record.style_tags else [],
    }

    # 获取或生成竞品画像
    competitor_record = db.query(BloggerProfileRecord).filter(
        BloggerProfileRecord.blogger_id == req.competitor_id
    ).first()

    if competitor_record:
        competitor_data = {
            "vocabulary": json.loads(competitor_record.vocabulary_json) if competitor_record.vocabulary_json else {},
            "expression": json.loads(competitor_record.expression_json) if competitor_record.expression_json else {},
            "topics": json.loads(competitor_record.topics_json) if competitor_record.topics_json else {},
            "audience": json.loads(competitor_record.audience_json) if competitor_record.audience_json else {},
            "risk": json.loads(competitor_record.risk_json) if competitor_record.risk_json else {},
            "overall_style": competitor_record.overall_style,
            "style_tags": json.loads(competitor_record.style_tags) if competitor_record.style_tags else [],
        }
    elif req.competitor_contents:
        # 实时生成竞品画像
        profiler = BloggerProfiler()
        comp_profile = await profiler.generate_profile(
            blogger_id=req.competitor_id,
            contents=req.competitor_contents,
        )
        import dataclasses
        competitor_data = dataclasses.asdict(comp_profile)
    else:
        raise HTTPException(status_code=400, detail="竞品画像不存在且未提供内容，无法生成画像")

    # 对比分析
    analyzer = CompetitorAnalyzer()
    result = await analyzer.compare(
        blogger_profile=blogger_data,
        competitor_profile=competitor_data,
        blogger_id=req.blogger_id,
        blogger_name=blogger_record.name,
        competitor_id=req.competitor_id,
    )

    # 保存记录
    import dataclasses
    compare_record = CompetitorCompareRecord(
        blogger_id=req.blogger_id,
        competitor_id=req.competitor_id,
        style_comparisons=json.dumps([dataclasses.asdict(c) for c in result.style_comparisons], ensure_ascii=False),
        content_gaps=json.dumps([dataclasses.asdict(g) for g in result.content_gaps], ensure_ascii=False),
        suggestions=json.dumps([dataclasses.asdict(s) for s in result.suggestions], ensure_ascii=False),
        overall_assessment=result.overall_assessment,
    )
    db.add(compare_record)
    db.commit()

    return {
        "blogger_id": result.blogger_id,
        "competitor_id": result.competitor_id,
        "style_comparisons": [dataclasses.asdict(c) for c in result.style_comparisons],
        "content_gaps": [dataclasses.asdict(g) for g in result.content_gaps],
        "suggestions": [dataclasses.asdict(s) for s in result.suggestions],
        "overall_assessment": result.overall_assessment,
    }



# ═══════════════════════════════════════════════════════════════════════════════
# 阶段1核心流程 - 5个核心API端点
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import UploadFile, File


class ReviewRequest(BaseModel):
    """内容预审请求"""
    mode: str = Field("text", description="输入模式: text/video/mixed")
    video_files: list[str] | None = Field(None, description="上传后的视频文件路径列表")
    texts: list[dict] | None = Field(None, description="文本内容列表 [{type, content}]")
    options: dict | None = Field(None, description="分析选项 {depth, platforms, enable_simulation}")


class ReviewResponse(BaseModel):
    """内容预审响应"""
    task_id: str
    status: str
    estimated_depth: str = ""
    estimated_duration_seconds: int = 0


class ProgressResponse(BaseModel):
    """分析进度响应"""
    task_id: str
    current_step: str = ""
    progress: float = 0.0
    detail: str = ""
    completed_dimensions: list[str] = Field(default_factory=list)
    remaining_dimensions: list[str] = Field(default_factory=list)


class HistoryItemResponse(BaseModel):
    """历史记录项"""
    task_id: str
    status: str
    created_at: str | None = None
    overall_risk: int | None = None
    risk_level: str | None = None


class HistoryResponse(BaseModel):
    """历史记录响应"""
    total: int
    items: list[HistoryItemResponse]


class ModelsResponse(BaseModel):
    """可用模型响应"""
    hardware_tier: str
    models: dict[str, dict[str, str]]


class UploadResponse(BaseModel):
    """文件上传响应"""
    file_path: str
    file_name: str
    file_size: int


def _get_estimated_duration(depth: str | None) -> tuple[str, int]:
    """根据分析深度返回预估深度和时长"""
    depth_map = {
        "quick": ("快速分析", 60),
        "standard": ("标准分析", 180),
        "deep": ("深度分析", 600),
        "large_scale": ("大规模仿真", 1800),
    }
    return depth_map.get(depth or "standard", ("标准分析", 180))


def _score_to_risk_level(score: int | None) -> str:
    """将分数转换为风险等级"""
    if score is None:
        return "green"
    if score <= 25:
        return "green"
    elif score <= 55:
        return "yellow"
    elif score <= 75:
        return "orange"
    return "red"


@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    req: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """提交内容预审（统一入口）

    支持三种输入模式:
    - text: 纯文本分析
    - video: 视频文件分析（提取文案后分析）
    - mixed: 文本+视频混合分析
    """
    # 收集所有文本内容
    texts_to_analyze: list[str] = []

    # 处理文本输入
    if req.texts:
        for item in req.texts:
            if item.get("type") == "text" and item.get("content"):
                texts_to_analyze.append(item["content"])

    # 处理视频文件（提取文案）
    if req.video_files:
        for video_path in req.video_files:
            if os.path.exists(video_path):
                extract_result = await extract_video_text(video_path)
                if not extract_result.get("error"):
                    text = extract_result.get("text", "").strip()
                    if len(text) >= 10:
                        texts_to_analyze.append(text)

    # 合并所有文本
    combined_text = "\n\n".join(texts_to_analyze)

    if len(combined_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="内容太短，无法进行分析（至少需要10个字符）")

    # 创建任务
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        text=combined_text,
        status="processing",
        model=settings.DEEPSEEK_MODEL,
        mode=req.mode,
        depth=req.options.get("depth", "standard") if req.options else "standard",
    )
    db.add(task)
    db.commit()

    # 启动后台分析
    background_tasks.add_task(run_analysis, task_id, combined_text)

    # 计算预估时间
    depth = req.options.get("depth", "standard") if req.options else "standard"
    estimated_depth, estimated_seconds = _get_estimated_duration(depth)

    return ReviewResponse(
        task_id=task_id,
        status="processing",
        estimated_depth=estimated_depth,
        estimated_duration_seconds=estimated_seconds
    )


@router.get("/review/{task_id}")
async def get_review_result(task_id: str, db: Session = Depends(get_db)):
    """获取预审结果

    返回完整分析结果，字段对齐前端ReviewResult接口
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result: dict[str, Any] = {
        "task_id": task.id,
        "status": task.status,
    }

    if task.status == "completed":
        summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).first()
        risk_items = db.query(RiskItem).filter(RiskItem.task_id == task_id).all()
        reactions = db.query(PlatformReaction).filter(PlatformReaction.task_id == task_id).all()

        if not summary:
            result["status"] = "failed"
            result["error"] = "分析结果数据缺失"
            return result

        # 解析维度数据 - 支持新格式(完整对象)和旧格式(仅分数)
        dimensions = []
        if summary.dimensions_json:
            try:
                dims_data = json.loads(summary.dimensions_json)
                if isinstance(dims_data, dict):
                    for name, data in dims_data.items():
                        if isinstance(data, dict):
                            dimensions.append({
                                "name": name,
                                "score": data.get("score", 0),
                                "severity": data.get("severity", "low"),
                                "evidence": data.get("evidence", ""),
                                "evidence_source": data.get("evidence_source", {}),
                                "confidence": data.get("confidence", 0.8),
                                "suggestion": data.get("suggestion", ""),
                                "affected_groups": data.get("affected_groups", []),
                            })
                        elif isinstance(data, (int, float)):
                            score = int(data)
                            severity = "high" if score >= 60 else ("medium" if score >= 30 else "low")
                            dimensions.append({
                                "name": name,
                                "score": score,
                                "severity": severity,
                                "evidence": "",
                                "confidence": 0.5,
                                "suggestion": "",
                            })
            except json.JSONDecodeError:
                pass

        # 信号关联数据
        signal_correlations = []
        try:
            from backend.models import HotspotCorrelationRecord
            correlations = db.query(HotspotCorrelationRecord).filter(
                HotspotCorrelationRecord.task_id == task_id
            ).all()
            for c in correlations:
                signal_correlations.append({
                    "signal_id": c.signal_id,
                    "title": c.signal_title,
                    "platform": c.signal_platform,
                    "correlation_score": c.correlation_score,
                    "risk_boost": c.risk_boost,
                })
        except Exception:
            pass

        # 置信度计算
        confidence = 0.8
        uncertainty_sources = []
        if summary.transcript_quality:
            try:
                tq = json.loads(summary.transcript_quality)
                if tq.get("quality_level") not in ("clean", None):
                    confidence -= 0.15
                    uncertainty_sources.append("转写质量不佳")
            except json.JSONDecodeError:
                pass
        if len(dimensions) < 3:
            confidence -= 0.1
            uncertainty_sources.append("评估维度不完整")

        # 构建响应
        result["overall_risk"] = summary.overall_score
        result["risk_level"] = _score_to_risk_level(summary.overall_score)
        result["method"] = "standard"
        result["dimensions"] = dimensions
        result["platform_reactions"] = {
            r.platform: {"positive": r.positive, "neutral": r.neutral, "negative": r.negative}
            for r in reactions
        }
        result["signal_correlations"] = signal_correlations
        result["confidence"] = round(confidence, 2)
        result["uncertainty_sources"] = uncertainty_sources

        # 交叉效应
        cross_effects = []
        if summary.cross_effects:
            try:
                cross_effects = json.loads(summary.cross_effects)
            except json.JSONDecodeError:
                pass
        result["cross_effects"] = cross_effects

        # 改写建议
        suggestions = []
        if summary.rewrites_json:
            try:
                rewrites = json.loads(summary.rewrites_json)
                for rw in rewrites:
                    if isinstance(rw, dict):
                        suggestions.append({
                            "original": rw.get("original", ""),
                            "suggestion": rw.get("suggestion", ""),
                            "dimension": rw.get("dimension", ""),
                        })
            except json.JSONDecodeError:
                pass
        result["suggestions"] = suggestions

    elif task.status == "failed":
        result["error"] = task.error if hasattr(task, 'error') and task.error else "分析失败"

    return result


@router.get("/review/{task_id}/progress", response_model=ProgressResponse)
async def get_review_progress(task_id: str, db: Session = Depends(get_db)):
    """获取分析进度

    返回当前分析步骤和进度百分比
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 从任务状态推断进度
    step_progress_map = {
        "pending": ("understanding", 0.0),
        "processing": ("assessment", 0.3),
        "signal": ("signal", 0.5),
        "simulation": ("simulation", 0.7),
        "reporting": ("report", 0.9),
        "completed": ("report", 1.0),
        "failed": ("report", 0.0),
    }

    current_step, progress = step_progress_map.get(task.status, ("understanding", 0.0))

    detail_map = {
        "understanding": "正在理解内容...",
        "assessment": "正在进行风险评估...",
        "signal": "正在采集平台信号...",
        "simulation": "正在推演平台反应...",
        "report": "正在生成报告...",
    }

    return ProgressResponse(
        task_id=task_id,
        current_step=current_step,
        progress=progress,
        detail=detail_map.get(current_step, "处理中..."),
        completed_dimensions=[],
        remaining_dimensions=[]
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    page: int = 1,
    per_page: int = 20,
    risk_level: str | None = None,
    db: Session = Depends(get_db)
):
    """获取历史记录

    支持分页和风险等级筛选
    """
    query = db.query(Task).order_by(Task.created_at.desc())

    # 风险等级筛选
    if risk_level:
        score_ranges = {
            "green": (0, 25),
            "yellow": (26, 55),
            "orange": (56, 75),
            "red": (76, 100),
        }
        if risk_level in score_ranges:
            min_score, max_score = score_ranges[risk_level]
            query = query.join(AnalysisSummary).filter(
                AnalysisSummary.overall_score >= min_score,
                AnalysisSummary.overall_score <= max_score
            )

    # 分页
    total = query.count()
    tasks = query.offset((page - 1) * per_page).limit(per_page).all()

    items: list[HistoryItemResponse] = []
    for task in tasks:
        risk_level_val = None
        overall_risk = None
        if task.status == "completed":
            summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task.id).first()
            if summary:
                overall_risk = summary.overall_score
                risk_level_val = _score_to_risk_level(summary.overall_score)

        items.append(HistoryItemResponse(
            task_id=task.id,
            status=task.status,
            created_at=task.created_at.isoformat() if task.created_at else None,
            overall_risk=overall_risk,
            risk_level=risk_level_val
        ))

    return HistoryResponse(total=total, items=items)


@router.get("/models", response_model=ModelsResponse)
async def get_models():
    """获取当前可用模型和硬件等级"""
    hardware_tier = "lite"
    try:
        import torch
        if torch.cuda.is_available():
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            if gpu_mem >= 24:
                hardware_tier = "ultra"
            elif gpu_mem >= 12:
                hardware_tier = "pro"
            elif gpu_mem >= 6:
                hardware_tier = "standard"
    except ImportError:
        pass

    models = {
        "text_analysis": {
            "primary": settings.DEEPSEEK_MODEL,
            "fallback": "deepseek-chat"
        },
        "vision": {
            "primary": "qwen3-vl-plus",
            "fallback": "glm-4v"
        },
        "audio": {
            "primary": "paraformer",
            "fallback": "faster-whisper-local"
        }
    }

    return ModelsResponse(
        hardware_tier=hardware_tier,
        models=models
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 文件上传端点
# ═══════════════════════════════════════════════════════════════════════════════

# 允许的视频文件类型
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传视频文件

    支持格式: mp4, mov, avi, webm
    最大大小: 100MB
    """
    # 验证文件类型
    content_type = file.content_type or ""
    file_ext = os.path.splitext(file.filename or "")[1].lower()

    if content_type not in ALLOWED_VIDEO_TYPES and file_ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {content_type or file_ext}。仅支持: mp4, mov, avi, webm"
        )

    # 创建上传目录
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # 生成唯一文件名
    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{file.filename or 'video.mp4'}"
    file_path = os.path.join(upload_dir, safe_filename)

    # 保存文件
    try:
        contents = await file.read()

        # 验证文件大小
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制: {len(contents) / (1024*1024):.1f}MB > 100MB"
            )

        with open(file_path, "wb") as f:
            f.write(contents)

        return UploadResponse(
            file_path=file_path,
            file_name=file.filename or "video.mp4",
            file_size=len(contents)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("文件上传失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

