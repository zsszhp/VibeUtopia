import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
from backend.services.analyzer import run_analysis

router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    if len(req.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文案内容至少需要10个字符")

    task_id = str(uuid.uuid4())
    task = Task(id=task_id, text=req.text, status="processing", model=settings.DEEPSEEK_MODEL)
    db.add(task)
    db.commit()

    import asyncio
    asyncio.create_task(run_analysis(task_id, req.text))

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

        result["summary"] = {
            "overall_score": summary.overall_score,
            "suggestion": summary.suggestion,
            "risk_dimensions": json.loads(summary.dimensions_json) if summary.dimensions_json else {},
        }
        result["risk_items"] = [
            {
                "sentence": r.sentence,
                "dimension": r.dimension,
                "severity": r.severity,
                "evidence": r.evidence,
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
    tasks = (
        db.query(Task)
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
            # 返回原始文案预览（前50字），方便历史列表识别
            "text_preview": (t.text[:50] + "...") if t.text and len(t.text) > 50 else t.text,
        }
        if t.status == "completed":
            summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == t.id).first()
            if summary:
                item["overall_score"] = summary.overall_score
                item["suggestion"] = summary.suggestion
        results.append(item)
    return results
