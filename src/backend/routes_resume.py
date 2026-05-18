"""
断点续传 API 路由

提供以下端点：
  POST /api/v1/resume/submit          — 提交可恢复分析任务
  GET  /api/v1/resume/{task_id}/status — 获取任务状态和进度
  POST /api/v1/resume/{task_id}/resume — 手动恢复中断的任务
  DELETE /api/v1/resume/{task_id}      — 删除任务和检查点
  GET  /api/v1/resume/list             — 列出所有可恢复任务
  GET  /api/v1/resume/{task_id}/checkpoint — 获取检查点详情
"""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Task
from backend.services.resumable_analyzer import ResumableAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter()


class ResumeSubmitRequest(BaseModel):
    """可恢复分析提交请求"""
    text: str = Field(..., description="要分析的文本内容")
    video_path: str = Field("", description="视频文件路径（可选）")
    mode: str = Field("standard", description="分析模式: quick/standard/deep")
    auto_resume: bool = Field(True, description="是否自动从检查点恢复")
    quota_retry_wait: int = Field(60, description="限流后等待秒数")
    max_quota_retries: int = Field(5, description="最大限流重试次数")


class ResumeSubmitResponse(BaseModel):
    """可恢复分析提交响应"""
    task_id: str
    status: str
    was_resumed: bool = False
    message: str = ""


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    progress: float = 0.0
    current_stage: str = ""
    last_completed_stage: str = ""
    total_llm_calls: int = 0
    quota_exhausted_count: int = 0
    stages: dict = Field(default_factory=dict)
    checkpoint_path: str = ""


@router.post("/resume/submit", response_model=ResumeSubmitResponse)
async def submit_resumable_analysis(
    req: ResumeSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """提交可恢复分析任务

    与普通分析不同，此端点支持：
    - 自动检查点保存
    - API 限流后自动重试
    - 中断后手动恢复
    """
    task_id = f"resume_{uuid.uuid4().hex[:12]}"

    # 创建数据库任务记录
    task = Task(
        id=task_id,
        text=req.text[:500],
        status="processing",
        model="resumable",
        mode="video" if req.video_path else "text",
        depth=req.mode,
    )
    db.add(task)
    db.commit()

    # 启动后台分析
    background_tasks.add_task(
        _run_resumable_analysis,
        task_id=task_id,
        text=req.text,
        video_path=req.video_path,
        mode=req.mode,
        auto_resume=req.auto_resume,
        quota_retry_wait=req.quota_retry_wait,
        max_quota_retries=req.max_quota_retries,
    )

    # 检查是否是恢复的任务
    from backend.services.checkpoint_manager import CheckpointManager
    mgr = CheckpointManager(task_id)
    existing = mgr.load()
    was_resumed = existing is not None and existing.is_resumable

    return ResumeSubmitResponse(
        task_id=task_id,
        status="processing",
        was_resumed=was_resumed,
        message="任务已提交" + ("（从检查点恢复）" if was_resumed else ""),
    )


async def _run_resumable_analysis(
    task_id: str,
    text: str,
    video_path: str,
    mode: str,
    auto_resume: bool,
    quota_retry_wait: int,
    max_quota_retries: int,
):
    """后台运行可恢复分析"""
    analyzer = ResumableAnalyzer(
        task_id=task_id,
        video_path=video_path,
        mode=mode,
        auto_resume=auto_resume,
        quota_retry_wait=quota_retry_wait,
        max_quota_retries=max_quota_retries,
    )
    result = await analyzer.run(text)

    # 更新数据库任务状态
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            if result.get("status") == "completed":
                task.status = "completed"
            else:
                task.status = "interrupted"
                task.error = result.get("error", "未知错误")
            from datetime import datetime, timezone
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.error("更新任务状态失败: %s", e)
    finally:
        db.close()


@router.get("/resume/{task_id}/status", response_model=TaskStatusResponse)
async def get_resume_status(task_id: str):
    """获取可恢复任务状态"""
    from backend.services.resumable_analyzer import ResumableAnalyzer
    analyzer = ResumableAnalyzer(task_id=task_id)
    status = analyzer.get_status()

    if status.get("status") == "not_started":
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return TaskStatusResponse(**status)


@router.post("/resume/{task_id}/resume", response_model=ResumeSubmitResponse)
async def resume_interrupted_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    quota_retry_wait: int = 60,
    max_quota_retries: int = 5,
):
    """手动恢复中断的分析任务"""
    from backend.services.checkpoint_manager import CheckpointManager
    from backend.database import SessionLocal

    mgr = CheckpointManager(task_id)
    checkpoint = mgr.load()

    if not checkpoint:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 的检查点不存在")

    if checkpoint.overall_status == "completed":
        return ResumeSubmitResponse(
            task_id=task_id,
            status="completed",
            message="任务已完成，无需恢复",
        )

    # 恢复任务
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "processing"
            task.error = ""
            db.commit()
    finally:
        db.close()

    # 重新启动后台分析
    text = checkpoint.intermediate_results.get("text", "")
    background_tasks.add_task(
        _run_resumable_analysis,
        task_id=task_id,
        text=text,
        video_path=checkpoint.video_path,
        mode=checkpoint.mode,
        auto_resume=True,
        quota_retry_wait=quota_retry_wait,
        max_quota_retries=max_quota_retries,
    )

    return ResumeSubmitResponse(
        task_id=task_id,
        status="resuming",
        was_resumed=True,
        message=f"任务已恢复，从阶段 '{checkpoint.next_pending_stage}' 继续",
    )


@router.delete("/resume/{task_id}")
async def delete_resumable_task(task_id: str, db: Session = Depends(get_db)):
    """删除可恢复任务及其检查点"""
    from backend.services.checkpoint_manager import CheckpointManager

    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()

    mgr = CheckpointManager(task_id)
    mgr.delete()

    return {"status": "deleted", "task_id": task_id}


@router.get("/resume/list")
async def list_resumable_tasks():
    """列出所有可恢复任务"""
    from backend.services.checkpoint_manager import CheckpointManager
    checkpoints = CheckpointManager.list_checkpoints()
    return {"tasks": checkpoints, "total": len(checkpoints)}


@router.get("/resume/{task_id}/checkpoint")
async def get_checkpoint_detail(task_id: str):
    """获取检查点详细信息"""
    from backend.services.checkpoint_manager import CheckpointManager

    mgr = CheckpointManager(task_id)
    checkpoint = mgr.load()

    if not checkpoint:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 的检查点不存在")

    return checkpoint.to_dict()
