from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import AuthIdentity, get_identity
from backend.config import settings
from backend.database import get_db
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction, HotspotCorrelationRecord
from backend.services.analyzer import run_analysis, MAX_TEXT_LENGTH
from backend.services.video_extractor import extract_video_text
from backend.services.hardware_detector import get_hardware_summary
from backend.services.persona.life_story_generator import PersonaFactory

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
    hardware_details: dict | None = None


class UploadResponse(BaseModel):
    """文件上传响应"""
    file_path: str
    file_name: str
    file_size: int


class WorkflowUpdateRequest(BaseModel):
    """审核工作流状态更新请求"""
    status: str = Field(..., description="目标状态：draft/pending_review/approved/rejected")
    note: str = Field("", description="审批备注（写入状态历史留痕）")


# R5 审核工作流：状态与合法流转（同状态重复提交仅追加备注留痕）
WORKFLOW_STATUSES = ("draft", "pending_review", "approved", "rejected")
WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_review"},
    "pending_review": {"approved", "rejected", "draft"},
    "approved": {"pending_review"},
    "rejected": {"pending_review", "draft"},
}

EXPORT_DISCLAIMER = (
    "本报告由 VibeUtopia 自动分析生成，仅供内容合规参考，不构成法律意见。"
    "模型判断存在误差与不确定性，请结合人工复核后决策；"
    "触及红线维度的内容不提供改写方案，建议不予发布。"
)


class PersonaGenerateRequest(BaseModel):
    """人格生成请求"""
    platform: str = Field("bilibili", description="平台名")
    archetype: str = Field("主流用户", description="原型类型")
    tier: str = Field("C", description="生成层级 A/B/C")
    base_profile: dict | None = Field(None, description="可选的基础人口统计信息")


class PersonaGenerateBatchRequest(BaseModel):
    """批量人格生成请求"""
    platform: str = Field("bilibili", description="平台名")
    count: int = Field(10, description="生成数量")
    tier_distribution: dict | None = Field(None, description="各层级数量 {A:1, B:3, C:6}")


class MemoryStoreRequest(BaseModel):
    """记忆存储请求"""
    agent_id: str = Field(..., description="Agent ID")
    content: str = Field(..., description="记忆内容")
    memory_type: str = Field("observation", description="记忆类型 observation/reflection/plan")
    importance: float = Field(0.5, description="重要性 0-1")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class MemoryRetrieveRequest(BaseModel):
    """记忆检索请求"""
    agent_id: str = Field(..., description="Agent ID")
    query: str = Field(..., description="查询文本")
    top_k: int = Field(5, description="返回数量")


class MemoryStatusResponse(BaseModel):
    """Memory Stream 状态响应"""
    chromadb_available: bool
    total_memories: int
    agent_memories: dict


class PersonaResponse(BaseModel):
    """人格响应"""
    tier: str
    life_story: str
    persona_7layers: dict
    big_five: dict
    quality_score: float
    platform: str
    archetype: str


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

class BatchReviewItem(BaseModel):
    """批量预审单项（MCN 场景）"""
    client_id: str = ""
    text: str = Field(..., min_length=10)


class BatchReviewRequest(BaseModel):
    items: list[BatchReviewItem] = Field(..., min_length=1, max_length=20)
    depth: str = "quick"


class BatchReviewResult(BaseModel):
    client_id: str
    status: str
    overall_score: int | None = None
    risk_level: str | None = None
    suggestion: str | None = None
    top_dimensions: list[dict] = []
    error: str | None = None


class BatchReviewResponse(BaseModel):
    total: int
    ok: int
    failed: int
    results: list[BatchReviewResult]
    disclaimer: str = EXPORT_DISCLAIMER


@router.post("/review/batch", response_model=BatchReviewResponse)
async def submit_review_batch(
    req: BatchReviewRequest,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(get_identity),
):
    """批量快速预审（MCN/机构）：对多条文案做 11 维快筛

    - 单条失败不阻断整批
    - 返回 overall/level/top 维度，便于人工复核队列排序
    """
    from backend.services.risk_assessor import assess_risks
    from backend.services.analyzer import calculate_overall_score, get_suggestion

    results: list[BatchReviewResult] = []
    ok = 0
    for item in req.items:
        try:
            assessment = await assess_risks(item.text)
            dimensions = assessment.get("dimensions") or []
            if not dimensions:
                raise RuntimeError("空维度")
            overall, _w, _c = calculate_overall_score(dimensions, context_text=item.text)
            score = int(overall)
            if score >= 76:
                level = "red"
            elif score >= 61:
                level = "orange"
            elif score >= 31:
                level = "yellow"
            else:
                level = "green"
            top = sorted(dimensions, key=lambda d: int(d.get("score") or 0), reverse=True)[:3]
            results.append(BatchReviewResult(
                client_id=item.client_id,
                status="ok",
                overall_score=score,
                risk_level=level,
                suggestion=get_suggestion(score),
                top_dimensions=[
                    {"name": d.get("name"), "score": d.get("score"), "severity": d.get("severity")}
                    for d in top
                ],
            ))
            ok += 1
        except Exception as e:
            results.append(BatchReviewResult(
                client_id=item.client_id,
                status="error",
                error=str(e)[:200],
            ))

    return BatchReviewResponse(
        total=len(req.items),
        ok=ok,
        failed=len(req.items) - ok,
        results=results,
    )


@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    req: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(get_identity),
):
    """提交内容预审（统一入口）

    支持三种输入模式:
    - text: 纯文本分析
    - video: 视频文件分析（提取文案后分析）
    - mixed: 文本+视频混合分析

    携带 JWT 时任务写入 owner_id 归属；无 token 行为与旧版兼容（owner_id 为空）。
    """
    # 收集所有文本内容
    texts_to_analyze: list[str] = []
    # 分模态文本：画面OCR 与 音频转写（供跨模态冲突检测）
    visual_parts: list[str] = []
    audio_parts: list[str] = []

    # 处理文本输入
    if req.texts:
        for item in req.texts:
            if item.get("type") == "text" and item.get("content"):
                texts_to_analyze.append(item["content"])
            elif item.get("type") == "visual" and item.get("content"):
                visual_parts.append(item["content"])
            elif item.get("type") == "audio" and item.get("content"):
                audio_parts.append(item["content"])

    # 处理视频文件（提取文案 + Paraformer音频转写）
    audio_transcriptions: list[str] = []
    if req.video_files:
        for video_path in req.video_files:
            # 路径校验：限制在上传目录内，拒绝路径穿越/绝对路径越权
            safe_path = _validate_video_path(video_path)
            if not safe_path:
                logger.warning("拒绝非法视频路径: %s", video_path)
                raise HTTPException(status_code=400, detail="视频文件路径非法或不在上传目录内")
            if os.path.exists(safe_path):
                # 提取视频文案（OCR + 本地音频转写）
                extract_result = await extract_video_text(safe_path)
                if not extract_result.get("error"):
                    text = extract_result.get("text", "").strip()
                    if len(text) >= 10:
                        texts_to_analyze.append(text)
                    if extract_result.get("ocr_text"):
                        visual_parts.append(extract_result["ocr_text"])
                    if extract_result.get("audio_text"):
                        audio_parts.append(extract_result["audio_text"])

                # Paraformer 云端音频转写（降级：API Key未配置时跳过）
                try:
                    from backend.services.audio_transcriber import ParaformerTranscriber
                    transcriber = ParaformerTranscriber()
                    if transcriber.api_key:
                        paraformer_result = await transcriber.transcribe(
                            audio_file_path=safe_path,
                            speaker_separation=True,
                        )
                        para_text = paraformer_result.get("text", "").strip()
                        if para_text:
                            audio_transcriptions.append(para_text)
                            audio_parts.append(para_text)
                            logger.info("Paraformer音频转写成功: %d字", len(para_text))
                    else:
                        logger.info("Paraformer API Key未配置，跳过云端音频转写")
                except RuntimeError as e:
                    logger.warning("Paraformer不可用，跳过音频转写: %s", e)
                except Exception as e:
                    logger.warning("Paraformer音频转写失败，降级跳过: %s", e)

    # 合并所有文本
    combined_text = "\n\n".join(texts_to_analyze)

    # 将Paraformer音频转写结果追加到分析文本
    if audio_transcriptions:
        audio_section = "\n\n【音频转写内容】\n" + "\n".join(audio_transcriptions)
        combined_text += audio_section

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
        owner_id=identity.owner_id,
        workflow_status="draft",
    )
    db.add(task)
    db.commit()

    # 启动后台分析（传入 depth 档位 + 分模态文本）
    depth = req.options.get("depth", "standard") if req.options else "standard"
    visual_description = "\n".join(visual_parts).strip() or None
    audio_transcript = "\n".join(audio_parts).strip() or None
    background_tasks.add_task(
        run_analysis, task_id, combined_text, depth,
        visual_description=visual_description,
        audio_transcript=audio_transcript,
    )

    # 计算预估时间
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
        "owner_id": task.owner_id,
        "workflow_status": task.workflow_status or "draft",
        "workflow_history": _load_workflow_history(task),
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
                            # 兼容旧格式 severity (low/medium/high → green/yellow/orange/red)
                            raw_sev = data.get("severity", "green")
                            score_val = data.get("score", 0)
                            sev_map = {"low": "green", "medium": "yellow", "high": "red"}
                            normalized_sev = sev_map.get(raw_sev, raw_sev)
                            # 确保是合法值
                            if normalized_sev not in ("green", "yellow", "orange", "red"):
                                normalized_sev = "green" if score_val < 26 else ("yellow" if score_val < 51 else ("orange" if score_val < 76 else "red"))
                            dimensions.append({
                                "name": name,
                                "score": score_val,
                                "severity": normalized_sev,
                                "evidence": data.get("evidence", ""),
                                "evidence_source": data.get("evidence_source", {}),
                                "confidence": data.get("confidence", 0.8),
                                "suggestion": data.get("suggestion", ""),
                                "affected_groups": data.get("affected_groups", []),
                            })
                        elif isinstance(data, (int, float)):
                            score = int(data)
                            # 旧格式(仅分数)映射到 4 档 severity
                            if score >= 76:
                                severity = "red"
                            elif score >= 51:
                                severity = "orange"
                            elif score >= 26:
                                severity = "yellow"
                            else:
                                severity = "green"
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

        # 改写建议（表达优化建议，保留风险说明，不伪装原文）
        suggestions = []
        if summary.rewrites_json:
            try:
                rewrites = json.loads(summary.rewrites_json)
                for rw in rewrites:
                    if not isinstance(rw, dict):
                        continue
                    original = rw.get("original", "")
                    # 红线维度：仅输出「建议不予发布」，不提供改写版本
                    if rw.get("is_redline"):
                        suggestions.append({
                            "original": original,
                            "suggestion": rw.get("redline_note", "该内容建议不予发布"),
                            "dimension": "",
                            "rewrite_note": "",
                            "is_redline": True,
                        })
                        continue
                    # 新格式 rewrites 为 [{text, rewrite_note}] 列表
                    rewrites_list = rw.get("rewrites", [])
                    if isinstance(rewrites_list, list) and rewrites_list:
                        for item in rewrites_list:
                            if isinstance(item, dict):
                                suggestions.append({
                                    "original": original,
                                    "suggestion": item.get("text", ""),
                                    "dimension": rw.get("dimension", ""),
                                    "rewrite_note": item.get("rewrite_note", ""),
                                    "is_redline": False,
                                })
                            elif isinstance(item, str):
                                suggestions.append({
                                    "original": original,
                                    "suggestion": item,
                                    "dimension": rw.get("dimension", ""),
                                    "rewrite_note": "",
                                    "is_redline": False,
                                })
                    else:
                        # 兼容旧格式单条 suggestion 字段
                        suggestions.append({
                            "original": original,
                            "suggestion": rw.get("suggestion", ""),
                            "dimension": rw.get("dimension", ""),
                            "rewrite_note": rw.get("rewrite_note", ""),
                            "is_redline": False,
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

        # 仿真数据 (V2+ simulation_data)
        result["simulation_data"] = None
        if summary.platform_simulation_json:
            try:
                sim_data = json.loads(summary.platform_simulation_json)
                if sim_data:
                    result["simulation_data"] = sim_data
            except json.JSONDecodeError:
                pass

        # 实体风险链 (V2+ entity_chains)
        result["entity_chains"] = []
        try:
            from backend.models import EntityRiskChainRecord
            chains = db.query(EntityRiskChainRecord).filter(
                EntityRiskChainRecord.task_id == task_id
            ).all()
            for ch in chains:
                result["entity_chains"].append({
                    "id": f"entity_{ch.id}",
                    "name": ch.entity_name,
                    "risk_score": ch.total_risk_score,
                    "risk_level": ch.risk_level,
                    "dimensions": json.loads(ch.dimension_boosts).keys() if ch.dimension_boosts else [],
                    "timestamp": ch.created_at.isoformat() if ch.created_at else "",
                })
        except Exception:
            pass

        # 极化数据 (V2+ polarization_data) — 从传播快照聚合
        result["polarization_data"] = None
        try:
            from backend.models import SimulationSummaryRecord
            sim_summary = db.query(SimulationSummaryRecord).filter(
                SimulationSummaryRecord.task_id == task_id
            ).first()
            if sim_summary and sim_summary.polarization_index is not None:
                sentiment = json.loads(sim_summary.sentiment_summary) if sim_summary.sentiment_summary else {}
                result["polarization_data"] = {
                    "timeline": [{
                        "time": sim_summary.created_at.isoformat() if sim_summary.created_at else "",
                        "polarization_index": sim_summary.polarization_index,
                        "support_count": int(sentiment.get("positive", 0)),
                        "oppose_count": int(sentiment.get("negative", 0)),
                        "neutral_count": int(sentiment.get("neutral", 0)),
                    }],
                    "thresholds": {"low": 0.3, "medium": 0.6, "high": 0.8},
                }
        except Exception:
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


# ═══════════════════════════════════════════════════════════════════════════════
# R5 审核工作流 + 报告导出
# ═══════════════════════════════════════════════════════════════════════════════

def _load_workflow_history(task: Task) -> list[dict]:
    """解析任务上的工作流状态历史（JSON 字段留痕）"""
    if not task.workflow_history_json:
        return []
    try:
        history = json.loads(task.workflow_history_json)
        return history if isinstance(history, list) else []
    except json.JSONDecodeError:
        return []


def _check_task_access(task: Task, identity: AuthIdentity) -> None:
    """归属校验雏形：任务有归属且请求带不同用户身份时 403；无 token 行为兼容（放行）"""
    if task.owner_id and identity.owner_id and task.owner_id != identity.owner_id:
        raise HTTPException(status_code=403, detail="无权访问他人名下的审核任务")


@router.patch("/review/{task_id}/workflow")
async def update_review_workflow(
    task_id: str,
    req: WorkflowUpdateRequest,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(get_identity),
):
    """更新审核工作流状态（draft/pending_review/approved/rejected）

    每次流转写入状态历史留痕（from/to/note/actor/at）；同状态提交仅追加备注。
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_task_access(task, identity)

    target = (req.status or "").strip()
    if target not in WORKFLOW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"非法状态: {target or '(空)'}，仅支持 {'/'.join(WORKFLOW_STATUSES)}",
        )

    current = task.workflow_status or "draft"
    if target != current and target not in WORKFLOW_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=400, detail=f"非法状态流转: {current} → {target}")

    history = _load_workflow_history(task)
    history.append({
        "from": current,
        "to": target,
        "note": (req.note or "").strip(),
        "actor": identity.owner_id or identity.auth_type,
        "at": datetime.now(timezone.utc).isoformat(),
    })

    task.workflow_status = target
    task.workflow_history_json = json.dumps(history, ensure_ascii=False)
    db.commit()

    return {
        "task_id": task_id,
        "status": target,
        "previous_status": current,
        "workflow_history": history,
    }


class BatchWorkflowItem(BaseModel):
    task_id: str
    note: str = ""


class BatchWorkflowRequest(BaseModel):
    items: list[BatchWorkflowItem] = Field(..., min_length=1, max_length=50)
    status: str = Field(..., description="draft/pending_review/approved/rejected")


@router.patch("/review/workflow/batch")
async def update_review_workflow_batch(
    req: BatchWorkflowRequest,
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(get_identity),
):
    """批量审核流转（MCN）：多任务同状态，单条失败不阻断"""
    target = (req.status or "").strip()
    if target not in WORKFLOW_STATUSES:
        raise HTTPException(status_code=400, detail=f"非法状态: {target}")

    results = []
    for item in req.items:
        try:
            task = db.query(Task).filter(Task.id == item.task_id).first()
            if not task:
                results.append({"task_id": item.task_id, "status": "error", "error": "任务不存在"})
                continue
            _check_task_access(task, identity)
            current = task.workflow_status or "draft"
            if target != current and target not in WORKFLOW_TRANSITIONS.get(current, set()):
                results.append({
                    "task_id": item.task_id,
                    "status": "error",
                    "error": f"非法流转 {current}→{target}",
                })
                continue
            history = _load_workflow_history(task)
            history.append({
                "from": current,
                "to": target,
                "note": (item.note or "").strip(),
                "actor": identity.owner_id or identity.auth_type,
                "at": datetime.now(timezone.utc).isoformat(),
            })
            task.workflow_status = target
            task.workflow_history_json = json.dumps(history, ensure_ascii=False)
            results.append({"task_id": item.task_id, "status": "ok", "previous_status": current})
        except Exception as e:
            results.append({"task_id": item.task_id, "status": "error", "error": str(e)[:160]})

    db.commit()
    ok = sum(1 for r in results if r.get("status") == "ok")
    return {"total": len(req.items), "ok": ok, "failed": len(req.items) - ok, "results": results}


def _build_export_payload(task: Task, db: Session) -> dict[str, Any]:
    """汇总导出所需数据：结论 / 分数 / Top 风险 / 改写 / 工作流留痕"""
    summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task.id).first()
    risk_items = db.query(RiskItem).filter(RiskItem.task_id == task.id).all()

    dimensions: list[dict] = []
    rewrites: list[dict] = []
    overall_score: int | None = None
    suggestion = ""
    confidence: float | None = None
    if summary:
        overall_score = summary.overall_score
        suggestion = summary.suggestion or ""
        try:
            dims_data = json.loads(summary.dimensions_json) if summary.dimensions_json else {}
        except json.JSONDecodeError:
            dims_data = {}
        if isinstance(dims_data, dict):
            for name, data in dims_data.items():
                if isinstance(data, dict):
                    dimensions.append({
                        "name": name,
                        "score": data.get("score", 0),
                        "severity": data.get("severity", "green"),
                        "evidence": data.get("evidence", ""),
                        "suggestion": data.get("suggestion", ""),
                    })
                elif isinstance(data, (int, float)):
                    dimensions.append({"name": name, "score": int(data), "severity": "", "evidence": "", "suggestion": ""})
        try:
            rewrites = json.loads(summary.rewrites_json) if summary.rewrites_json else []
            if not isinstance(rewrites, list):
                rewrites = []
        except json.JSONDecodeError:
            rewrites = []
        try:
            conf_data = json.loads(summary.confidence_json) if summary.confidence_json else {}
            if isinstance(conf_data, dict):
                confidence = conf_data.get("overall_confidence")
        except json.JSONDecodeError:
            confidence = None

    # Top 风险：按 risk_score 降序取前 5，缺失分数的按 severity 权重兜底
    sev_weight = {"red": 4, "orange": 3, "yellow": 2, "green": 1, "high": 3, "medium": 2, "low": 1}
    top_risks = sorted(
        risk_items,
        key=lambda r: (
            r.risk_score if r.risk_score is not None else -1,
            sev_weight.get((r.severity or "").lower(), 0),
        ),
        reverse=True,
    )[:5]
    top_risk_payload = [
        {
            "sentence": r.sentence or "",
            "dimension": r.dimension or "",
            "severity": r.severity or "",
            "evidence": r.evidence or "",
            "risk_score": r.risk_score,
        }
        for r in top_risks
    ]

    risk_level = _score_to_risk_level(overall_score)
    return {
        "task_id": task.id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": task.owner_id,
        "analysis_status": task.status,
        "workflow_status": task.workflow_status or "draft",
        "workflow_history": _load_workflow_history(task),
        "verdict": {
            "overall_score": overall_score,
            "risk_level": risk_level,
            "suggestion": suggestion or ("可发" if overall_score is not None and overall_score <= 25 else ""),
            "confidence": confidence,
        },
        "dimensions": dimensions,
        "top_risks": top_risk_payload,
        "rewrites": rewrites,
        "disclaimer": EXPORT_DISCLAIMER,
    }


def _level_zh(level: str | None) -> str:
    """风险等级中文"""
    mapping = {
        "green": "安全",
        "yellow": "需留意",
        "orange": "较高风险",
        "red": "高风险",
        "low": "安全",
        "medium": "需留意",
        "high": "较高风险",
        "critical": "高风险",
    }
    return mapping.get((level or "").lower(), level or "N/A")


def _severity_zh(sev: str | None) -> str:
    return _level_zh(sev)


def _render_export_markdown(payload: dict[str, Any]) -> str:
    """Markdown 报告：Verdict + 分数 + Top 风险 + 改写 + 免责"""
    verdict = payload.get("verdict") or {}
    score = verdict.get("overall_score")
    score_text = f"{score}/100" if score is not None else "N/A"
    conf = verdict.get("confidence")
    conf_text = f"{conf}" if conf is not None else "N/A"

    lines: list[str] = [
        "# 内容预审报告",
        "",
        f"- **任务 ID**: `{payload.get('task_id', '')}`",
        f"- **导出时间**: {payload.get('exported_at', '')}",
        f"- **分析状态**: {payload.get('analysis_status', '')}",
        f"- **工作流状态**: {payload.get('workflow_status', '')}",
        f"- **归属**: {payload.get('owner_id') or '（无）'}",
        "",
        "## 一、结论（Verdict）",
        "",
        f"- **总风险分**: {score_text}",
        f"- **风险等级**: {_level_zh(verdict.get('risk_level', ''))}",
        f"- **发布建议**: {verdict.get('suggestion', '') or 'N/A'}",
        f"- **置信度**: {conf_text}",
        "",
        "## 二、维度得分",
        "",
    ]

    dims = payload.get("dimensions") or []
    if dims:
        lines.append("| 维度 | 得分 | 等级 | 证据 |")
        lines.append("|------|------|------|------|")
        for d in dims:
            evidence = (d.get("evidence") or "").replace("\n", " ").replace("|", "\\|")
            if len(evidence) > 60:
                evidence = evidence[:57] + "..."
            lines.append(
                f"| {d.get('name', '')} | {d.get('score', '')} | {_severity_zh(d.get('severity', ''))} | {evidence} |"
            )
    else:
        lines.append("（暂无维度数据）")

    lines.extend(["", "## 三、Top 风险", ""])
    top_risks = payload.get("top_risks") or []
    if top_risks:
        for i, r in enumerate(top_risks, 1):
            score_part = f"，风险分 {r['risk_score']}" if r.get("risk_score") is not None else ""
            lines.append(
                f"{i}. **[{r.get('dimension') or '未知维度'}]** {r.get('sentence', '')}"
                f"（{r.get('severity') or 'N/A'}{score_part}）"
            )
            if r.get("evidence"):
                lines.append(f"   - 证据：{r['evidence']}")
    else:
        lines.append("（暂无风险条目）")

    lines.extend(["", "## 四、改写建议", ""])
    rewrites = payload.get("rewrites") or []
    if rewrites:
        idx = 0
        for rw in rewrites:
            if not isinstance(rw, dict):
                continue
            idx += 1
            original = rw.get("original", "")
            lines.append(f"### {idx}. 原文")
            lines.append("")
            lines.append(f"> {original}" if original else "> （空）")
            lines.append("")
            if rw.get("is_redline"):
                lines.append(f"**红线说明**：{rw.get('redline_note') or '该内容建议不予发布'}")
                lines.append("")
                continue
            candidates = rw.get("rewrites") or []
            if isinstance(candidates, list) and candidates:
                for j, item in enumerate(candidates, 1):
                    if isinstance(item, dict):
                        lines.append(f"**改写方案 {j}**：{item.get('text', '')}")
                        if item.get("rewrite_note"):
                            lines.append(f"**说明**：{item['rewrite_note']}")
                    else:
                        lines.append(f"**改写方案 {j}**：{item}")
                lines.append("")
            else:
                lines.append(f"**建议**：{rw.get('suggestion', '')}")
                if rw.get("rewrite_note"):
                    lines.append(f"**说明**：{rw['rewrite_note']}")
                lines.append("")
    else:
        lines.append("（暂无改写建议）")

    history = payload.get("workflow_history") or []
    if history:
        lines.extend(["", "## 附、工作流留痕", ""])
        for h in history:
            lines.append(
                f"- `{h.get('at', '')}` {h.get('from', '')} → {h.get('to', '')}"
                f"（操作者: {h.get('actor', '')}"
                + (f"，备注: {h.get('note')}" if h.get("note") else "")
                + "）"
            )

    lines.extend(["", "## 五、免责声明", "", payload.get("disclaimer") or EXPORT_DISCLAIMER, ""])
    return "\n".join(lines)


def _render_export_pdf(payload: dict[str, Any]) -> bytes:
    """PDF 报告（fpdf2 + 系统中文字体；无字体时回退拉丁摘要）"""
    from fpdf import FPDF

    markdown = _render_export_markdown(payload)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_candidates = (
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    )
    font_ok = False
    for path in font_candidates:
        if os.path.exists(path):
            try:
                pdf.add_font("cjk", "", path)
                pdf.set_font("cjk", size=11)
                font_ok = True
                break
            except Exception:
                continue
    if not font_ok:
        pdf.set_font("Helvetica", size=11)

    for line in markdown.splitlines():
        text = line if font_ok else line.encode("ascii", "replace").decode("ascii")
        if not text.strip():
            pdf.ln(4)
            continue
        pdf.multi_cell(w=0, h=6, text=text, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def _render_export_html(payload: dict[str, Any]) -> str:
    """可打印 HTML 报告（浏览器打开后可另存为 PDF）"""
    md = _render_export_markdown(payload)
    # 轻量转义 + 段落/标题/列表，避免引入 markdown 依赖
    def esc(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body_lines: list[str] = []
    for line in md.splitlines():
        if line.startswith("# "):
            body_lines.append(f"<h1>{esc(line[2:])}</h1>")
        elif line.startswith("## "):
            body_lines.append(f"<h2>{esc(line[3:])}</h2>")
        elif line.startswith("### "):
            body_lines.append(f"<h3>{esc(line[4:])}</h3>")
        elif line.startswith("> "):
            body_lines.append(f"<blockquote>{esc(line[2:])}</blockquote>")
        elif line.startswith("|"):
            body_lines.append(f"<pre class='table-line'>{esc(line)}</pre>")
        elif line.strip() == "":
            body_lines.append("")
        else:
            body_lines.append(f"<p>{esc(line)}</p>")

    title = esc(str(payload.get("task_id", "report")))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>VibeUtopia 预审报告 {title}</title>
<style>
  body {{ font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
         max-width: 860px; margin: 32px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.65; }}
  h1 {{ font-size: 22px; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }}
  h2 {{ font-size: 17px; margin-top: 28px; color: #312e81; }}
  blockquote {{ border-left: 4px solid #c7d2fe; margin: 8px 0; padding: 8px 12px; background: #f5f5ff; }}
  .table-line {{ font-size: 12px; background: #fafafa; padding: 2px 6px; margin: 0; overflow-x: auto; }}
  @media print {{ body {{ margin: 12px; }} }}
</style>
</head>
<body>
{''.join(body_lines)}
</body>
</html>"""


@router.get("/review/{task_id}/export")
async def export_review(
    task_id: str,
    format: str = "md",
    db: Session = Depends(get_db),
    identity: AuthIdentity = Depends(get_identity),
):
    """导出审核报告：GET /api/v1/review/{task_id}/export?format=md|json|html

    - format=md：Markdown 报告（Verdict + 分数 + Top 风险 + 改写 + 免责）
    - format=json：结构化报告数据（含同一免责声明）
    - format=html：可打印 HTML（浏览器可另存 PDF）
    - format=pdf：PDF 文件（fpdf2 + 系统中文字体）
    """
    fmt = (format or "md").strip().lower()
    if fmt not in ("md", "json", "html", "pdf"):
        raise HTTPException(status_code=400, detail="format 仅支持 md、json、html 或 pdf")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_task_access(task, identity)

    payload = _build_export_payload(task, db)
    if fmt == "json":
        return payload

    if fmt == "pdf":
        try:
            pdf_bytes = _render_export_pdf(payload)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="review_{task_id}.pdf"',
            },
        )

    if fmt == "html":
        html = _render_export_html(payload)
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="review_{task_id}.html"',
            },
        )

    markdown = _render_export_markdown(payload)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="review_{task_id}.md"',
        },
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
    hardware_info: dict | None = None
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
        
        # 硬件详情单独字段返回（不混入 models，保持 dict[str, dict[str, str]] 类型）

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
        models=models,
        hardware_details=hardware_info,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 文件上传端点
# ═══════════════════════════════════════════════════════════════════════════════

# 允许的视频文件类型
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def _get_upload_dir() -> str:
    """获取上传目录绝对路径"""
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _sanitize_filename(filename: str) -> str:
    """消毒文件名：去除路径分隔符与危险字符，仅保留安全字符"""
    import re
    # 仅取 basename，防止 ../ 或绝对路径注入
    name = os.path.basename(filename or "video.mp4")
    # 替换危险字符，保留字母数字中文下划线连字符点
    name = re.sub(r'[^\w\u4e00-\u9fff.\-]', '_', name)
    # 防止隐藏文件或空名
    name = name.strip('.').lstrip('.') or 'video.mp4'
    return name[:120]


def _validate_video_path(video_path: str) -> str | None:
    """校验视频文件路径：必须位于上传目录内，拒绝路径穿越

    Returns:
        校验通过的绝对路径；不合法时返回 None
    """
    if not video_path or not isinstance(video_path, str):
        return None

    upload_dir = os.path.realpath(_get_upload_dir())

    # 拒绝含 null 字节的路径
    if "\x00" in video_path:
        return None

    # 解析为绝对路径并 realpath 消除符号链接/..穿越
    try:
        resolved = os.path.realpath(video_path)
    except (OSError, ValueError):
        return None

    # 必须位于上传目录内（防止读取系统任意文件）
    if not resolved.startswith(upload_dir + os.sep) and resolved != upload_dir:
        return None

    if not os.path.isfile(resolved):
        return None

    return resolved


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
    upload_dir = _get_upload_dir()

    # 生成唯一文件名；消毒原文件名，防路径遍历写到上传目录之外
    file_id = str(uuid.uuid4())[:8]
    original_name = _sanitize_filename(file.filename or "video.mp4")
    safe_filename = f"{file_id}_{original_name}"
    file_path = os.path.join(upload_dir, safe_filename)

    # 双保险：确认最终路径仍在上传目录内
    if os.path.commonpath([os.path.abspath(file_path), os.path.abspath(upload_dir)]) != os.path.abspath(upload_dir):
        raise HTTPException(status_code=400, detail="非法文件名")

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

# ═══════════════════════════════════════════════════════════════════════════════
# 人生故事人格系统端点 (T1)
# ═══════════════════════════════════════════════════════════════════════════════

# 人格工厂单例
_persona_factory: PersonaFactory | None = None


def get_persona_factory() -> PersonaFactory:
    """获取人格工厂单例"""
    global _persona_factory
    if _persona_factory is None:
        _persona_factory = PersonaFactory()
    return _persona_factory


@router.post("/persona/generate", response_model=PersonaResponse)
async def generate_persona(req: PersonaGenerateRequest):
    """生成单个人生故事人格

    Args:
        platform: 平台名 (bilibili/weibo/douyin...)
        archetype: 原型类型 (主流用户/争议用户/边缘用户/KOL/跨界用户)
        tier: 生成层级 (A/B/C)
        base_profile: 可选的基础人口统计信息

    Returns:
        完整人格对象，包含人生故事、7 层人格、Big Five 特质
    """
    factory = get_persona_factory()
    
    try:
        persona = await factory.generate(
            platform=req.platform,
            archetype=req.archetype,
            tier=req.tier,
            base_profile=req.base_profile,
        )
        
        return PersonaResponse(
            tier=persona.tier,
            life_story=persona.life_story,
            persona_7layers=persona.persona_7layers or {},
            big_five=persona.big_five or {},
            quality_score=persona.quality_score,
            platform=persona.platform,
            archetype=persona.archetype,
        )
    except Exception as e:
        logger.error("人格生成失败：%s", e)
        raise HTTPException(status_code=500, detail=f"人格生成失败：{str(e)}")


@router.post("/persona/generate-batch", response_model=list[PersonaResponse])
async def generate_persona_batch(req: PersonaGenerateBatchRequest):
    """批量生成人生故事人格

    Args:
        platform: 平台名
        count: 生成数量
        tier_distribution: 各层级数量 {"A": 1, "B": 3, "C": 6}

    Returns:
        人格列表
    """
    factory = get_persona_factory()
    
    try:
        personas = await factory.generate_batch(
            platform=req.platform,
            count=req.count,
            tier_distribution=req.tier_distribution,
        )
        
        return [
            PersonaResponse(
                tier=p.tier,
                life_story=p.life_story,
                persona_7layers=p.persona_7layers or {},
                big_five=p.big_five or {},
                quality_score=p.quality_score,
                platform=p.platform,
                archetype=p.archetype,
            )
            for p in personas
        ]
    except Exception as e:
        logger.error("批量人格生成失败：%s", e)
        raise HTTPException(status_code=500, detail=f"批量人格生成失败：{str(e)}")


@router.post("/memory/store")
async def store_memory(req: MemoryStoreRequest):
    """存储记忆到 Memory Stream

    Args:
        agent_id: Agent 唯一标识
        content: 记忆内容
        memory_type: 记忆类型 (observation/reflection/plan)
        importance: 重要性评分 (0-1)
        tags: 标签列表

    Returns:
        存储结果
    """
    from backend.services.persona.memory_stream import MemoryStreamStore
    
    store = MemoryStreamStore()
    
    try:
        memory_id = await store.store(
            agent_id=req.agent_id,
            content=req.content,
            memory_type=req.memory_type,
            importance=req.importance,
            tags=req.tags,
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "agent_id": req.agent_id,
        }
    except Exception as e:
        logger.error("记忆存储失败：%s", e)
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/memory/retrieve")
async def retrieve_memory(req: MemoryRetrieveRequest):
    """从 Memory Stream 检索记忆

    使用三因子检索：Recency(0.5) + Importance(0.3) + Relevance(0.2)

    Args:
        agent_id: Agent 唯一标识
        query: 查询文本
        top_k: 返回数量

    Returns:
        记忆列表，按相关性排序
    """
    from backend.services.persona.memory_stream import MemoryStreamStore
    
    store = MemoryStreamStore()
    
    try:
        memories = await store.retrieve(
            agent_id=req.agent_id,
            query=req.query,
            top_k=req.top_k,
        )
        
        return {
            "success": True,
            "agent_id": req.agent_id,
            "memories": memories,
            "count": len(memories),
        }
    except Exception as e:
        logger.error("记忆检索失败：%s", e)
        return {
            "success": False,
            "error": str(e),
            "memories": [],
        }


@router.get("/memory/status", response_model=MemoryStatusResponse)
async def get_memory_status():
    """获取 Memory Stream 状态

    Returns:
        ChromaDB 可用性、记忆总数、各 Agent 记忆数量
    """
    from backend.services.persona.memory_stream import MemoryStreamStore
    
    store = MemoryStreamStore()
    
    try:
        status = await store.get_status()
        
        return MemoryStatusResponse(
            chromadb_available=status.get("chromadb_available", False),
            total_memories=status.get("total_memories", 0),
            agent_memories=status.get("agent_memories", {}),
        )
    except Exception as e:
        logger.error("获取记忆状态失败：%s", e)
        return MemoryStatusResponse(
            chromadb_available=False,
            total_memories=0,
            agent_memories={},
        )


@router.get("/metrics/summary")
async def get_metrics_summary(n: int = 50):
    """LLM 调用计量汇总（成本/耗时/失败率）

    Query:
        n: 最近 N 次分析（无 analysis_id 时退化为最近 N 条调用），默认 50

    Returns:
        调用数 / 失败率 / 耗时分位（p50/p90/p99）/ token 合计；无记录时 available=False
    """
    from backend.services.llm_meter import meter as llm_meter

    try:
        window = max(1, min(int(n), 1000))
    except (TypeError, ValueError):
        window = 50
    try:
        return llm_meter.summarize(n=window)
    except Exception as e:
        logger.error("计量汇总失败：%s", e)
        return {"available": False, "error": str(e)}

