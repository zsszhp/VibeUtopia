from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction, HotspotCorrelationRecord
from backend.services.analyzer import run_analysis, MAX_TEXT_LENGTH
from backend.services.video_extractor import extract_video_text
from backend.services.hardware_detector import get_hardware_summary

logger = logging.getLogger(__name__)

router = APIRouter()


class ReviewRequest(BaseModel):
    """内容预审请求"""
    mode: str = Field("text", description="输入模式：text/video/mixed")
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

        # 置信度计算 - 使用新的置信度模块结果(如存在)
        confidence = 0.8
        uncertainty_sources = []
        
        # 优先使用新的置信度计算结果
        if summary.confidence_json:
            try:
                confidence_data = json.loads(summary.confidence_json)
                confidence = confidence_data.get("overall_confidence", 0.8)
                # 从不确定性说明中提取来源
                if summary.uncertainty_notes_json:
                    uncertainty_sources = json.loads(summary.uncertainty_notes_json)
            except json.JSONDecodeError:
                pass
        else:
            # 降级到旧逻辑
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

        # 阶段1.2新增: 证据链数据
        if summary.evidence_chains_json:
            try:
                result["evidence_chains"] = json.loads(summary.evidence_chains_json)
            except json.JSONDecodeError:
                result["evidence_chains"] = []
        
        # 阶段1.2新增: 置信度详细分解
        if summary.confidence_json:
            try:
                result["confidence_breakdown"] = json.loads(summary.confidence_json)
            except json.JSONDecodeError:
                pass

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
    """获取当前可用模型和硬件等级
    
    阶段1.3增强: 使用硬件自适应检测模块返回详细配置
    """
    # 使用新的硬件检测模块
    try:
        from backend.services.hardware_detector import get_hardware_summary
        hardware_info = get_hardware_summary()
        hardware_tier = hardware_info["hardware"]["tier"]
        
        models = {
            "text_analysis": {
                "primary": hardware_info["recommendation"]["risk_assessment_model"],
                "fallback": "deepseek-chat"
            },
            "vision": {
                "primary": hardware_info["recommendation"]["vision_model"],
                "fallback": "glm-4v"
            },
            "audio": {
                "primary": hardware_info["recommendation"]["audio_model"],
                "fallback": "faster-whisper-local"
            },
            "ocr": {
                "primary": hardware_info["recommendation"]["ocr_model"],
                "fallback": "glm-ocr-api"
            },
            "agent_simulation": {
                "primary": hardware_info["recommendation"]["agent_simulation_model"],
                "fallback": "qwen3-8b"
            }
        }
        
        # 附加硬件详情
        models["_hardware_details"] = hardware_info
        
    except Exception as e:
        logger.warning("硬件检测失败,使用默认配置: %s", e)
        # 降级到旧逻辑
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

