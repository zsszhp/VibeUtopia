import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction, SignalRecord, SeedEventRecord
from backend.services.analyzer import run_analysis, MAX_TEXT_LENGTH
from backend.services.video_extractor import extract_video_text
from backend.services.signal.fetcher import HotlistFetcher
from backend.services.signal.rss_fetcher import RssFetcher
from backend.services.signal.event_detector import EventDetector
from backend.services.signal.keyword_extractor import KeywordExtractor
from backend.services.signal.deep_crawler import DeepCrawler
from backend.services.signal.models import SearchKeyword

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
