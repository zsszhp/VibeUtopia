import json
import uuid
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction, SignalRecord, SeedEventRecord, AgentRecord, SocialRelation, AgentMemory, SimulationRecord, SimulationStatus, PropagationSnapshot, PropagationEdge, V2AnalysisResult
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

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=MAX_TEXT_LENGTH, description="待评估文案")


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str


class VideoExtractRequest(BaseModel):
    url: str = Field(..., description="视频链接(B站/抖音等)")


class VideoAnalyzeRequest(BaseModel):
    url: str = Field(..., description="视频链接(B站/抖音等)")


@router.post("/extract-video")
async def extract_video(req: VideoExtractRequest):
    """从视频链接提取文案文本"""
    result = await extract_video_text(req.url)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/analyze-video", response_model=AnalyzeResponse)
async def analyze_video(req: VideoAnalyzeRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """从视频链接提取文案并自动分析"""
    extract_result = await extract_video_text(req.url)
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

        result["summary"] = {
            "overall_score": summary.overall_score,
            "suggestion": summary.suggestion,
            "risk_dimensions": json.loads(summary.dimensions_json) if summary.dimensions_json else {},
            "transcript_quality": json.loads(summary.transcript_quality) if summary.transcript_quality else None,
            "dimension_weights": json.loads(summary.dimension_weights) if summary.dimension_weights else None,
            "cross_effects": json.loads(summary.cross_effects) if summary.cross_effects else [],
            "agents": json.loads(summary.agents_json) if summary.agents_json else [],
        }
        result["risk_items"] = [
            {
                "sentence": r.sentence,
                "dimension": r.dimension,
                "severity": r.severity,
                "evidence": r.evidence,
                "affected_groups": r.affected_groups.split(",") if r.affected_groups else [],
                "dimension_weight": r.dimension_weight,
            }
            for r in risk_items
        ]
        result["platform_reactions"] = {
            r.platform: {
                "positive": r.positive,
                "neutral": r.neutral,
                "negative": r.negative,
                "reason": r.reason,
            }
            for r in reactions
        }
        result["rewrites"] = json.loads(summary.rewrites_json) if summary.rewrites_json else []

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


@router.get("/history")
async def get_history(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload

    tasks = (
        db.query(Task)
        .options(joinedload(Task.summary))
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for t in tasks:
        item = {
            "task_id": t.id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "status": t.status,
            "text_preview": (t.text[:50] + "...") if t.text and len(t.text) > 50 else t.text,
        }
        if t.status == "completed" and t.summary:
            item["overall_score"] = t.summary.overall_score
            item["suggestion"] = t.summary.suggestion
        results.append(item)
    return results


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


@router.post("/simulation/create")
async def create_simulation(req: SimulationCreateRequest, background_tasks: BackgroundTasks):
    """创建仿真任务"""
    from backend.services.simulation.engine import SimulationEngine

    sim_id = str(uuid.uuid4())[:12]
    config = {
        "max_ticks": req.max_ticks,
        "start_hour": req.start_hour,
        "time_acceleration": req.time_acceleration,
        "tick_interval": req.tick_interval,
        "b_agent_per_tick": req.b_agent_per_tick,
    }

    engine = SimulationEngine(sim_id=sim_id, topic=req.topic, config=config)

    # 持久化仿真状态
    db_record = SimulationStatus(
        sim_id=sim_id,
        status="created",
        topic=req.topic,
        total_agents=0,
        config_json=json.dumps(config, ensure_ascii=False),
    )
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        db.add(db_record)
        db.commit()
    finally:
        db.close()

    # 初始化引擎
    await engine.initialize()

    # 更新Agent数
    db = SessionLocal()
    try:
        record = db.query(SimulationStatus).filter(SimulationStatus.sim_id == sim_id).first()
        if record:
            record.total_agents = len(engine.agents)
            db.commit()
    finally:
        db.close()

    _active_simulations[sim_id] = engine

    return {"sim_id": sim_id, "status": "created", "agent_count": len(engine.agents)}


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

    background_tasks.add_task(engine.run)

    return {"sim_id": sim_id, "status": "running"}


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

    return {"sim_id": sim_id, "status": "stopped"}


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

