import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
from backend.services.analyzer import run_analysis, MAX_TEXT_LENGTH
from backend.services.video_extractor import extract_video_text

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
