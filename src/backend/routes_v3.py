"""阶段 3+6 新增 API 路由

包含：
1. 多模态分析 API（支持 Qwen-VL, DeepSeek-VL 等）
2. 音频转写 API（阿里 Paraformer）
3. 人格生成 API（A/B/C三级人格）
4. ChromaDB 向量检索 API
5. 模型路由控制 API
6. 硬件检测 API
7. 信号采集面板 API（阶段6）
8. 知识图谱可视化 API（阶段6）
9. 博主历史分析 API（阶段6）
10. 竞品对比 API（阶段6）
11. 反事实仿真 API（阶段6）
12. 决策辅助 API（阶段6）
"""

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.audio_transcriber import get_transcriber, transcribe_audio
from backend.services.hardware_detector import (
    get_hardware_detector,
    get_hardware_info,
    get_recommended_model_tier,
)
from backend.services.llm_client import call_llm, call_vlm, call_image_gen, parse_llm_json
from backend.services.persona.life_story_generator import PersonaFactory
from backend.services.persona.memory_stream import MemoryStreamStore, get_memory_stream_status
from backend.services.report_optimizer import (
    get_risk_dimensions,
    get_risk_level_info,
    optimize_report,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 多模态分析 API ====================

class MultimodalAnalysisRequest(BaseModel):
    """多模态分析请求"""
    image_urls: List[str] = Field(default_factory=list, description="图片 URL 列表")
    text_prompt: str = Field(..., description="分析提示词")
    task_type: str = Field(default="multimodal_analysis", description="任务类型")
    model_provider: Optional[str] = Field(default=None, description="指定厂商（可选）")


class MultimodalAnalysisResponse(BaseModel):
    """多模态分析响应"""
    task_id: str
    analysis: str
    model_used: str
    confidence: float


@router.post("/api/v3/analyze-multimodal")
async def analyze_multimodal(req: MultimodalAnalysisRequest) -> MultimodalAnalysisResponse:
    """多模态内容分析（支持图片 + 文本）

    自动路由到最优视觉模型（Qwen-VL / DeepSeek-VL / GLM-VL）
    """
    task_id = str(uuid.uuid4())

    if not req.image_urls:
        raise HTTPException(status_code=400, detail="至少需要一张图片")

    try:
        # 下载并编码第一张图片（简化示例，实际应支持多图）
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(req.image_urls[0])
            resp.raise_for_status()
            image_base64 = base64.b64encode(resp.content).decode("utf-8")

        # 调用视觉模型
        analysis = await call_vlm(
            prompt=req.text_prompt,
            image_base64=image_base64,
            task_type=req.task_type,
        )

        # 解析置信度（从分析结果中提取）
        confidence = 0.85  # 简化处理

        return MultimodalAnalysisResponse(
            task_id=task_id,
            analysis=analysis,
            model_used="auto-routed",
            confidence=confidence,
        )

    except Exception as e:
        logger.error("多模态分析失败：%s", e)
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


@router.post("/api/v3/upload-image-analyze")
async def upload_image_analyze(
    image: UploadFile = File(..., description="上传图片"),
    prompt: str = Form(..., description="分析提示词"),
) -> MultimodalAnalysisResponse:
    """上传图片并分析"""
    task_id = str(uuid.uuid4())

    try:
        # 读取图片
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode("utf-8")

        # 调用视觉模型
        analysis = await call_vlm(
            prompt=prompt,
            image_base64=image_base64,
            task_type="multimodal_analysis",
        )

        return MultimodalAnalysisResponse(
            task_id=task_id,
            analysis=analysis,
            model_used="auto-routed",
            confidence=0.85,
        )

    except Exception as e:
        logger.error("图片上传分析失败：%s", e)
        raise HTTPException(status_code=500, detail=f"分析失败：{str(e)}")


# ==================== 音频转写 API ====================

class AudioTranscribeRequest(BaseModel):
    """音频转写请求"""
    audio_url: Optional[str] = Field(default=None, description="音频 URL")
    speaker_separation: bool = Field(default=True, description="是否说话人分离")


class AudioTranscribeResponse(BaseModel):
    """音频转写响应"""
    task_id: str
    text: str
    sentences: List[Dict[str, Any]]
    duration: float
    language: str


@router.post("/api/v3/transcribe-audio")
async def transcribe_audio_api(
    audio_file: UploadFile = File(..., description="音频文件"),
    speaker_separation: bool = Form(default=True, description="是否说话人分离"),
) -> AudioTranscribeResponse:
    """音频转写（阿里 Paraformer）"""
    task_id = str(uuid.uuid4())

    try:
        # 保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            content = await audio_file.read()
            f.write(content)
            temp_path = f.name

        # 调用 Paraformer 转写
        transcriber = get_transcriber()
        result = await transcriber.transcribe(
            audio_file_path=temp_path,
            speaker_separation=speaker_separation,
        )

        # 清理临时文件
        import os
        os.unlink(temp_path)

        return AudioTranscribeResponse(
            task_id=task_id,
            text=result["text"],
            sentences=result["sentences"],
            duration=result["duration"],
            language=result["language"],
        )

    except Exception as e:
        logger.error("音频转写失败：%s", e)
        raise HTTPException(status_code=500, detail=f"转写失败：{str(e)}")


# ==================== 人格生成 API ====================

class PersonaGenerationRequest(BaseModel):
    """人格生成请求"""
    platform: str = Field(..., description="平台名称")
    archetype: str = Field(..., description="原型类型（主流用户/争议用户/边缘用户/KOL/跨界用户）")
    tier: str = Field(default="C", description="生成层级 A/B/C")
    count: int = Field(default=1, ge=1, le=10, description="生成数量")


class PersonaGenerationResponse(BaseModel):
    """人格生成响应"""
    personas: List[Dict[str, Any]]
    quality_score: float


@router.post("/api/v3/generate-persona", deprecated=True,
             summary="[DEPRECATED] 生成人生故事驱动的人格，请使用 /api/v1/persona/generate")
async def generate_persona(req: PersonaGenerationRequest) -> PersonaGenerationResponse:
    """生成人生故事驱动的人格

    .. deprecated:: v2.0
        请使用 ``POST /api/v1/persona/generate`` 替代
    """
    factory = PersonaFactory()

    personas = []
    total_quality = 0.0

    for _ in range(req.count):
        persona = await factory.generate(
            platform=req.platform,
            archetype=req.archetype,
            tier=req.tier,
        )
        personas.append({
            "tier": persona.tier,
            "life_story": persona.life_story[:500] + "..." if len(persona.life_story) > 500 else persona.life_story,
            "persona_7layers": persona.persona_7layers,
            "big_five": persona.big_five,
            "platform": persona.platform,
            "archetype": persona.archetype,
        })
        total_quality += persona.quality_score

    avg_quality = total_quality / len(personas) if personas else 0.0

    return PersonaGenerationResponse(
        personas=personas,
        quality_score=avg_quality,
    )


@router.post("/api/v3/generate-persona-batch", deprecated=True,
             summary="[DEPRECATED] 批量生成人格，请使用 /api/v1/persona/generate-batch")
async def generate_persona_batch(
    platform: str = Form(...),
    count: int = Form(default=10),
    tier_distribution: str = Form(default='{"A": 1, "B": 3, "C": 6}'),
) -> PersonaGenerationResponse:
    """批量生成人格（混合 A/B/C 三级）"""
    import json
    factory = PersonaFactory()

    try:
        tier_dist = json.loads(tier_distribution)
    except json.JSONDecodeError:
        tier_dist = {"A": 1, "B": 3, "C": count - 4}

    archetypes = ["主流用户", "争议用户", "边缘用户", "KOL/大 V", "跨界用户"]
    personas = []
    total_quality = 0.0

    import random
    for tier_name, tier_count in tier_dist.items():
        for _ in range(tier_count):
            archetype = random.choice(archetypes)
            persona = await factory.generate(
                platform=platform,
                archetype=archetype,
                tier=tier_name,
            )
            personas.append({
                "tier": persona.tier,
                "archetype": persona.archetype,
                "life_story_preview": persona.life_story[:200] + "..." if len(persona.life_story) > 200 else persona.life_story,
                "quality_score": persona.quality_score,
            })
            total_quality += persona.quality_score

    avg_quality = total_quality / len(personas) if personas else 0.0

    return PersonaGenerationResponse(
        personas=personas,
        quality_score=avg_quality,
    )


# ==================== ChromaDB 向量检索 API ====================

class MemoryRetrieveRequest(BaseModel):
    """记忆检索请求"""
    agent_id: str = Field(..., description="Agent ID")
    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=10, ge=1, le=50, description="返回数量")


class MemoryRetrieveResponse(BaseModel):
    """记忆检索响应"""
    memories: List[Dict[str, Any]]
    chromadb_used: bool


@router.post("/api/v3/retrieve-memory", deprecated=True,
             summary="[DEPRECATED] 向量检索 Agent 记忆，请使用 /api/v1/memory/retrieve")
async def retrieve_memory(req: MemoryRetrieveRequest) -> MemoryRetrieveResponse:
    """向量检索 Agent 记忆（ChromaDB）

    .. deprecated:: v2.0
        请使用 ``POST /api/v1/memory/retrieve`` 替代
    """
    store = MemoryStreamStore()

    memories = store.retrieve(
        agent_id=req.agent_id,
        query=req.query,
        top_k=req.top_k,
    )

    return MemoryRetrieveResponse(
        memories=memories,
        chromadb_used=store.is_chroma_available,
    )


@router.get("/api/v3/memory-stream-status", deprecated=True,
            summary="[DEPRECATED] 获取 Memory Stream 状态，请使用 /api/v1/memory/status")
async def get_memory_stream_status_api():
    """获取 Memory Stream 状态

    .. deprecated:: v2.0
        请使用 ``GET /api/v1/memory/status`` 替代
    """
    return get_memory_stream_status()


@router.post("/api/v3/store-memory", deprecated=True,
             summary="[DEPRECATED] 存储记忆到向量数据库，请使用 /api/v1/memory/store")
async def store_memory(
    agent_id: str = Form(...),
    content: str = Form(...),
    memory_type: str = Form(default="observation"),
    importance: float = Form(default=0.5, ge=0, le=1),
    tags: str = Form(default="[]"),
) -> Dict[str, str]:
    """存储记忆到向量数据库"""
    import json
    store = MemoryStreamStore()

    try:
        tags_list = json.loads(tags)
    except json.JSONDecodeError:
        tags_list = []

    memory_id = store.store(
        agent_id=agent_id,
        content=content,
        memory_type=memory_type,
        importance=importance,
        tags=tags_list,
    )

    return {"memory_id": memory_id, "status": "stored"}


# ==================== 模型路由控制 API ====================

class ModelRouteRequest(BaseModel):
    """模型路由请求"""
    task_type: str = Field(default="default", description="任务类型")
    exclude_models: List[str] = Field(default_factory=list, description="排除的模型")


class ModelRouteResponse(BaseModel):
    """模型路由响应"""
    provider: str
    model: str
    tier: str
    base_url: str


@router.post("/api/v3/route-model")
async def route_model(req: ModelRouteRequest) -> ModelRouteResponse:
    """获取最优模型路由"""
    from backend.services.llm_client import registry, router as model_router

    exclude = set(req.exclude_models)
    endpoint = model_router.route(req.task_type, exclude=exclude)

    if not endpoint:
        raise HTTPException(status_code=404, detail="无可用模型")

    return ModelRouteResponse(
        provider=endpoint.provider,
        model=endpoint.model_id,
        tier=endpoint.tier,
        base_url=endpoint.base_url,
    )


@router.get("/api/v3/available-models")
async def list_available_models():
    """列出所有可用模型"""
    from backend.services.llm_client import registry

    return {
        "providers": registry.get_available_providers(),
        "total_endpoints": len(registry.endpoints),
    }


@router.post("/api/v3/set-model-override")
async def set_model_override(
    provider: str = Form(...),
    model: str = Form(...),
):
    """设置模型运行时覆盖（强制使用指定模型）"""
    from backend.services.llm_client import router as model_router

    model_router.set_override(provider=provider, model=model)

    return {
        "status": "ok",
        "override": {
            "provider": provider,
            "model": model,
        },
    }


# ==================== 硬件检测 API ====================

@router.get("/api/v3/hardware-info")
async def get_hardware_info_api():
    """获取硬件信息"""
    info = get_hardware_info()

    return {
        "gpu_available": info.gpu_available,
        "gpu_name": info.gpu_name,
        "vram_total_gb": info.vram_total_gb,
        "cpu_cores": info.cpu_cores,
        "memory_total_gb": info.memory_total_gb,
        "recommended_tier": info.recommended_tier,
    }


@router.get("/api/v3/recommended-models")
async def list_recommended_models():
    """获取推荐的模型列表"""
    detector = get_hardware_detector()
    return detector.get_recommended_models()


# ==================== 模型状态监控 API ====================

@router.get("/api/v3/model-status")
async def get_model_status():
    """获取模型 Key 池状态"""
    from backend.services.llm_client import router as model_router

    return {
        "key_pool": model_router.get_key_pool_status(),
    }


@router.get("/api/v3/llm-test")
async def test_llm(
    prompt: str = "你好，请做一个简单的自我介绍。",
    task_type: str = "default",
):
    """测试 LLM 调用"""
    try:
        response = await call_llm(prompt, task_type=task_type)
        return {
            "status": "ok",
            "response": response,
            "task_type": task_type,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 测试失败：{str(e)}")


# ==================== 报告质量优化 API ====================

class ReportOptimizeRequest(BaseModel):
    """报告优化请求"""
    report: Dict[str, Any] = Field(..., description="原始风险报告")


class ReportOptimizeResponse(BaseModel):
    """报告优化响应"""
    optimized_report: Dict[str, Any]
    actionability_score: float


@router.post("/api/v3/optimize-report")
async def optimize_report_api(req: ReportOptimizeRequest) -> ReportOptimizeResponse:
    """优化风险报告质量（细化风险等级 + 句子级建议 + 平台差异化建议）"""
    optimized = await optimize_report(req.report)

    return ReportOptimizeResponse(
        optimized_report=optimized,
        actionability_score=optimized.get("actionability_score", 0.0),
    )


@router.get("/api/v3/risk-levels")
async def list_risk_levels():
    """获取风险等级定义"""
    return {
        "levels": {
            level: info
            for level, info in [
                ("critical", get_risk_level_info("critical")),
                ("high", get_risk_level_info("high")),
                ("medium", get_risk_level_info("medium")),
                ("low", get_risk_level_info("low")),
            ]
        },
    }


@router.get("/api/v3/risk-dimensions")
async def list_risk_dimensions():
    """获取风险维度列表"""
    return {
        "dimensions": get_risk_dimensions(),
    }


# ==================== 信号采集面板 API（阶段6） ====================

@router.get("/api/v3/signals/hotlist")
async def get_signal_hotlist(
    platform: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """获取当前热榜"""
    from backend.models import SignalRecord

    query = db.query(SignalRecord).filter(SignalRecord.signal_type == "hotlist")
    if platform:
        query = query.filter(SignalRecord.source_platform == platform)
    query = query.order_by(SignalRecord.last_seen.desc()).limit(limit)

    records = query.all()
    return {
        "hotlist": [
            {
                "signal_id": r.signal_id,
                "title": r.title,
                "platform": r.source_platform,
                "rank": r.rank,
                "url": r.url,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "appearance_count": r.appearance_count,
                "is_new": r.is_new,
                "category": r.category,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/api/v3/signals/events")
async def get_signal_events(
    status: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """获取检测到的事件"""
    from backend.models import SeedEventRecord

    query = db.query(SeedEventRecord)
    if status:
        query = query.filter(SeedEventRecord.status == status)
    query = query.order_by(SeedEventRecord.updated_at.desc()).limit(limit)

    records = query.all()
    return {
        "events": [
            {
                "event_id": r.event_id,
                "title": r.title,
                "description": r.description,
                "category": r.category,
                "signal_strength": r.signal_strength,
                "status": r.status,
                "crawl_depth": r.crawl_depth,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/api/v3/signals/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    from backend.main import signal_scheduler

    return {
        "is_running": signal_scheduler.is_running,
        "current_mode": signal_scheduler.current_mode,
        "platform_count": len(signal_scheduler._platform_map),
    }


class SchedulerControlRequest(BaseModel):
    """调度器控制请求"""
    mode: str = Field(default="standard", description="调度模式: realtime/standard/economy/manual")


@router.post("/api/v3/signals/scheduler/start")
async def start_scheduler(req: SchedulerControlRequest):
    """启动调度器"""
    from backend.main import signal_scheduler

    if signal_scheduler.is_running:
        return {"status": "already_running", "mode": signal_scheduler.current_mode}

    success = signal_scheduler.start(mode=req.mode)
    if success:
        return {"status": "started", "mode": req.mode}
    raise HTTPException(status_code=400, detail=f"启动失败，未知模式: {req.mode}")


@router.post("/api/v3/signals/scheduler/stop")
async def stop_scheduler():
    """停止调度器"""
    from backend.main import signal_scheduler

    signal_scheduler.stop()
    return {"status": "stopped"}


# ==================== 知识图谱可视化 API（阶段6） ====================

@router.get("/api/v3/graph/overview")
async def get_graph_overview():
    """图谱概览（节点数、边数、社区数）"""
    from backend.main import graph_store

    if not graph_store.is_connected:
        return {
            "connected": False,
            "node_count": 0,
            "edge_count": 0,
            "community_count": 0,
            "labels": [],
            "relationship_types": [],
        }

    stats = graph_store.get_stats()
    return {
        "connected": stats.get("connected", False),
        "node_count": stats.get("node_count", 0),
        "edge_count": stats.get("relation_count", 0),
        "community_count": 0,
        "labels": stats.get("labels", []),
        "relationship_types": stats.get("relationship_types", []),
    }


@router.get("/api/v3/graph/entity/{entity_id}")
async def get_graph_entity(entity_id: str):
    """实体详情"""
    from backend.main import graph_store

    if not graph_store.is_connected:
        raise HTTPException(status_code=503, detail="知识图谱服务不可用")

    entity = graph_store.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    relations = graph_store.get_relations(entity_id)

    return {
        "entity": entity,
        "relations": relations,
    }


class GraphPathsRequest(BaseModel):
    """实体间路径查询请求"""
    from_id: str = Field(..., description="起始实体ID")
    to_id: str = Field(..., description="目标实体ID")
    max_depth: int = Field(default=5, ge=1, le=10, description="最大搜索深度")


@router.get("/api/v3/graph/paths")
async def get_graph_paths(
    from_id: str,
    to_id: str,
    max_depth: int = 5,
):
    """实体间路径查询"""
    from backend.main import graph_store

    if not graph_store.is_connected:
        raise HTTPException(status_code=503, detail="知识图谱服务不可用")

    path = graph_store.get_shortest_path(from_id, to_id, max_depth=max_depth)
    return {
        "from_id": from_id,
        "to_id": to_id,
        "path": path,
        "found": len(path) > 0,
    }


@router.get("/api/v3/graph/neighbors/{entity_id}")
async def get_graph_neighbors(
    entity_id: str,
    depth: int = 1,
    limit: int = 50,
):
    """实体邻居"""
    from backend.main import graph_store

    if not graph_store.is_connected:
        raise HTTPException(status_code=503, detail="知识图谱服务不可用")

    subgraph = graph_store.get_subgraph(entity_id, depth=depth, limit=limit)
    return {
        "entity_id": entity_id,
        "depth": depth,
        "nodes": subgraph.get("nodes", []),
        "edges": subgraph.get("edges", []),
    }


# ==================== 博主历史分析 API（阶段6） ====================

@router.get("/api/v3/blogger/{blogger_id}/history")
async def get_blogger_history(blogger_id: str, db: Session = Depends(get_db)):
    """博主历史分析"""
    from backend.services.blogger_history import BloggerHistoryAnalyzer

    analyzer = BloggerHistoryAnalyzer()
    profile = analyzer.analyze_history(blogger_id, db=db)

    return {
        "blogger_id": profile.blogger_id,
        "total_analyses": profile.total_analyses,
        "avg_risk_score": profile.avg_risk_score,
        "risk_level_distribution": profile.risk_level_distribution,
        "high_risk_dimensions": profile.high_risk_dimensions,
        "risk_tolerance": profile.risk_tolerance,
        "risk_pattern": profile.risk_pattern,
        "trend_summary": profile.trend_summary,
        "dimension_changes": [
            {
                "dimension": c.dimension,
                "direction": c.direction,
                "current_score": c.current_score,
                "previous_score": c.previous_score,
                "change_rate": c.change_rate,
                "trend_description": c.trend_description,
            }
            for c in profile.dimension_changes
        ],
        "trend_data": [
            {
                "date": t.date,
                "overall_score": t.overall_score,
                "dimensions": t.dimensions,
                "risk_level": t.risk_level,
            }
            for t in profile.trend_data
        ],
        "prediction": profile.prediction,
        "confidence": profile.confidence,
    }


@router.get("/api/v3/blogger/{blogger_id}/risk-profile")
async def get_blogger_risk_profile(blogger_id: str, db: Session = Depends(get_db)):
    """博主风险画像"""
    from backend.services.blogger_history import BloggerHistoryAnalyzer

    analyzer = BloggerHistoryAnalyzer()
    profile = analyzer.get_risk_profile(blogger_id, db=db)

    return {
        "blogger_id": profile.blogger_id,
        "risk_tolerance": profile.risk_tolerance,
        "risk_pattern": profile.risk_pattern,
        "high_risk_dimensions": profile.high_risk_dimensions,
        "avg_risk_score": profile.avg_risk_score,
        "risk_level_distribution": profile.risk_level_distribution,
        "trend_summary": profile.trend_summary,
        "prediction": profile.prediction,
        "confidence": profile.confidence,
    }


# ==================== 竞品对比 API（阶段6） ====================

class CompetitorCompareRequest(BaseModel):
    """竞品对比请求"""
    blogger_id: str = Field(..., description="博主ID")
    competitor_ids: List[str] = Field(..., description="竞品ID列表")
    field_name: str = Field(default="", description="所属领域")


@router.post("/api/v3/competitor/compare")
async def competitor_compare(req: CompetitorCompareRequest, db: Session = Depends(get_db)):
    """竞品对比"""
    from backend.services.competitor_comparator import CompetitorComparator

    comparator = CompetitorComparator()
    report = comparator.compare(
        blogger_id=req.blogger_id,
        competitor_ids=req.competitor_ids,
        field_name=req.field_name,
        db=db,
    )

    return {
        "blogger_id": report.blogger_id,
        "competitor_ids": report.competitor_ids,
        "field_name": report.field_name,
        "dimension_comparisons": [
            {
                "dimension": c.dimension,
                "blogger_score": c.blogger_score,
                "competitor_score": c.competitor_score,
                "field_average": c.field_average,
                "relative_position": c.relative_position,
                "advantage": c.advantage,
                "gap_value": c.gap_value,
            }
            for c in report.dimension_comparisons
        ],
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "overall_risk_rank": report.overall_risk_rank,
        "total_in_field": report.total_in_field,
        "risk_position": report.risk_position,
        "summary": report.summary,
        "error": report.error,
    }


# ==================== 反事实仿真 API（阶段6） ====================

class CounterfactualSimulateRequest(BaseModel):
    """反事实仿真请求"""
    text: str = Field(..., description="原始文案")
    risk_items: List[Dict[str, Any]] = Field(..., description="风险项列表")
    strategy_type: str = Field(default="soften", description="修改策略: delete/replace/soften/rephrase")


@router.post("/api/v3/counterfactual/simulate")
async def counterfactual_simulate(req: CounterfactualSimulateRequest):
    """反事实仿真"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    simulator = CounterfactualSimulator()
    result = await simulator.simulate(
        text=req.text,
        risk_items=req.risk_items,
        strategy_type=req.strategy_type,
    )

    return {
        "result_id": result.result_id,
        "original_text": result.original_text,
        "modified_text": result.modified_text,
        "strategy": {
            "strategy_type": result.strategy.strategy_type if result.strategy else "",
            "target_sentence": result.strategy.target_sentence if result.strategy else "",
            "modified_sentence": result.strategy.modified_sentence if result.strategy else "",
            "description": result.strategy.description if result.strategy else "",
        } if result.strategy else None,
        "before": {
            "overall_risk_score": result.before.overall_risk_score if result.before else 0,
            "risk_level": result.before.risk_level if result.before else "green",
            "dimension_scores": result.before.dimension_scores if result.before else {},
        } if result.before else None,
        "after": {
            "overall_risk_score": result.after.overall_risk_score if result.after else 0,
            "risk_level": result.after.risk_level if result.after else "green",
            "dimension_scores": result.after.dimension_scores if result.after else {},
        } if result.after else None,
        "comparisons": [
            {
                "dimension": c.dimension,
                "before_score": c.before_score,
                "after_score": c.after_score,
                "change": c.change,
                "change_direction": c.change_direction,
            }
            for c in result.comparisons
        ],
        "overall_improvement": result.overall_improvement,
        "recommendation": result.recommendation,
        "error": result.error,
    }


# ==================== 决策辅助 API（阶段6） ====================

class DecisionAdviseRequest(BaseModel):
    """决策辅助请求"""
    task_id: str = Field(default="", description="任务ID")
    risk_report: Dict[str, Any] = Field(..., description="风险评估报告")


@router.post("/api/v3/decision/advise")
async def decision_advise(req: DecisionAdviseRequest):
    """决策辅助"""
    from backend.services.decision_advisor import DecisionAdvisor

    advisor = DecisionAdvisor()
    report = advisor.generate_report(req.task_id, req.risk_report)

    return {
        "report_id": report.report_id,
        "task_id": report.task_id,
        "advice": {
            "advice_type": report.advice.advice_type if report.advice else "",
            "advice_label": report.advice.advice_label if report.advice else "",
            "confidence": report.advice.confidence if report.advice else 0,
            "overall_risk_score": report.advice.overall_risk_score if report.advice else 0,
            "risk_level": report.advice.risk_level if report.advice else "green",
            "modification_priorities": [
                {
                    "priority": p.priority,
                    "dimension": p.dimension,
                    "sentence": p.sentence,
                    "severity": p.severity,
                    "suggested_action": p.suggested_action,
                    "estimated_risk_reduction": p.estimated_risk_reduction,
                    "effort": p.effort,
                }
                for p in (report.advice.modification_priorities if report.advice else [])
            ],
            "estimated_final_risk": report.advice.estimated_final_risk if report.advice else 0,
            "estimated_risk_reduction": report.advice.estimated_risk_reduction if report.advice else 0,
            "key_risk_factors": report.advice.key_risk_factors if report.advice else [],
            "reasoning": report.advice.reasoning if report.advice else "",
        } if report.advice else None,
        "risk_summary": report.risk_summary,
        "recommendations": report.recommendations,
        "created_at": report.created_at,
    }


# ==================== 阶段5 规模化仿真 API ====================

class SimulationScaleRequest(BaseModel):
    """仿真规模设置请求"""
    level: str = Field(default="lightweight", description="规模级别: lightweight/standard/deep/massive")
    overrides: Optional[Dict[str, Any]] = Field(default=None, description="自定义配置覆盖")


class SimulationScaleResponse(BaseModel):
    """仿真规模设置响应"""
    level: str
    level_label: str
    total_agents: int
    equivalent_individuals: int
    estimated_duration_min: float
    estimated_duration_max: float
    estimated_cost_min: float
    estimated_cost_max: float
    group_agent_enabled: bool
    tier_breakdown: Dict[str, Any]


@router.post("/api/v3/simulation/scale")
async def set_simulation_scale(req: SimulationScaleRequest) -> SimulationScaleResponse:
    """设置仿真规模"""
    from backend.services.simulation.scale_manager import ScaleManager, ScaleLevel, SCALE_LABELS

    manager = ScaleManager()

    try:
        level = ScaleLevel(req.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的规模级别: {req.level}")

    # 自定义配置
    if req.overrides:
        manager.customize_config(level, req.overrides)

    manager.set_level(level)
    cost = manager.get_cost_estimate(level)

    return SimulationScaleResponse(
        level=cost["level"],
        level_label=cost["level_label"],
        total_agents=cost["total_agents"],
        equivalent_individuals=cost["equivalent_individuals"],
        estimated_duration_min=cost["estimated_duration_min"],
        estimated_duration_max=cost["estimated_duration_max"],
        estimated_cost_min=cost["estimated_cost_min"],
        estimated_cost_max=cost["estimated_cost_max"],
        group_agent_enabled=cost["group_agent_enabled"],
        tier_breakdown=cost["tier_breakdown"],
    )


@router.get("/api/v3/simulation/scale-levels")
async def get_simulation_scale_levels():
    """获取所有仿真规模级别"""
    from backend.services.simulation.scale_manager import ScaleManager

    manager = ScaleManager()
    return {"levels": manager.get_all_levels()}


@router.get("/api/v3/simulation/scale-feasibility")
async def check_scale_feasibility(level: str = "massive"):
    """验证仿真规模可行性"""
    from backend.services.simulation.scale_manager import ScaleManager, ScaleLevel

    manager = ScaleManager()
    try:
        scale_level = ScaleLevel(level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的规模级别: {level}")

    return manager.validate_feasibility(scale_level)


class BatchSubmitRequest(BaseModel):
    """批量分析提交请求"""
    contents: List[str] = Field(..., description="待分析内容列表")
    mode: str = Field(default="quick", description="分析模式: quick/deep")
    batch_id: Optional[str] = Field(default=None, description="批次ID（可选）")


class BatchSubmitResponse(BaseModel):
    """批量分析提交响应"""
    batch_id: str
    total_items: int
    status: str
    progress: float


@router.post("/api/v3/batch/submit")
async def submit_batch_analysis(req: BatchSubmitRequest) -> BatchSubmitResponse:
    """批量分析提交"""
    from backend.services.batch_analyzer import BatchAnalyzer

    analyzer = BatchAnalyzer()
    await analyzer.start()

    result = await analyzer.submit(
        contents=req.contents,
        mode=req.mode,
        batch_id=req.batch_id or "",
    )

    return BatchSubmitResponse(
        batch_id=result.batch_id,
        total_items=result.total_items,
        status=result.status.value,
        progress=result.get_progress(),
    )


@router.get("/api/v3/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """批量分析状态"""
    from backend.services.batch_analyzer import BatchAnalyzer

    analyzer = BatchAnalyzer()
    status = analyzer.get_status(batch_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"批次 {batch_id} 不存在")

    return status


@router.get("/api/v3/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """批量分析结果"""
    from backend.services.batch_analyzer import BatchAnalyzer

    analyzer = BatchAnalyzer()
    results = analyzer.get_results(batch_id)

    if not results:
        raise HTTPException(status_code=404, detail=f"批次 {batch_id} 不存在")

    return results


@router.get("/api/v3/batch/cache-stats")
async def get_batch_cache_stats():
    """获取批量分析缓存统计"""
    from backend.services.batch_analyzer import BatchAnalyzer

    analyzer = BatchAnalyzer()
    return analyzer.get_cache_stats()


# ==================== 阶段5 极化预警 API ====================

@router.get("/api/v3/polarization/warning")
async def get_polarization_warning(
    polarization_index: float = 0.0,
    trend: str = "stable",
):
    """获取极化预警"""
    from backend.services.simulation.propagation.polarization import generate_polarization_warning

    warning = generate_polarization_warning(polarization_index, trend)
    return warning.to_dict()


@router.get("/api/v3/polarization/levels")
async def get_polarization_levels():
    """获取极化预警等级定义"""
    from backend.services.simulation.propagation.polarization import (
        POLARIZATION_LEVEL_LABELS,
        POLARIZATION_LEVEL_THRESHOLDS,
    )

    return {
        "levels": {
            level.value: {
                "label": label,
                "threshold": POLARIZATION_LEVEL_THRESHOLDS.get(level, 0.0),
            }
            for level, label in POLARIZATION_LEVEL_LABELS.items()
        },
    }


# ==================== 阶段5 回测增强 API ====================

@router.post("/api/v3/backtest/consistency")
async def run_backtest_consistency(
    case_id: str = "bt_10",
    run_count: int = 3,
):
    """运行回测多轮一致性检查"""
    from backend.services.backtest import BacktestConsistencyChecker, PREDEFINED_CASES

    case = None
    for c in PREDEFINED_CASES:
        if c.case_id == case_id:
            case = c
            break

    if not case:
        raise HTTPException(status_code=404, detail=f"案例 {case_id} 不存在")

    checker = BacktestConsistencyChecker(run_count=run_count)
    result = await checker.check_case(case)

    return result.to_dict()


@router.post("/api/v3/backtest/v2-vs-mvp")
async def generate_v2_vs_mvp_report(
    enable_consistency: bool = True,
):
    """生成 V2 vs MVP 对比报告"""
    from backend.services.backtest import V2VsMVPComparator

    comparator = V2VsMVPComparator(consistency_run_count=3)
    report = await comparator.generate_report(enable_consistency=enable_consistency)

    return report.to_dict()


# ==================== V3.4 细粒度视频理解 API ====================

class FineGrainedAnalysisRequest(BaseModel):
    """细粒度视频分析请求"""
    video_path: str = Field(..., description="本地视频文件路径")
    enable_map_audit: bool = Field(default=True, description="启用地图完整性审核")
    enable_code_trace: bool = Field(default=True, description="启用代码溯源检测")
    enable_symbol_detect: bool = Field(default=True, description="启用敏感符号检测")
    enable_temporal_anomaly: bool = Field(default=True, description="启用时序异常检测")


class FineGrainedStatusResponse(BaseModel):
    """细粒度视频理解状态响应"""
    available: bool
    modules: Dict[str, Any]
    config: Dict[str, Any]


@router.get("/fine-grained/status")
async def get_fine_grained_status():
    """获取细粒度视频理解管线状态"""
    from backend.services.fine_grained import FineGrainedPipeline

    pipeline = FineGrainedPipeline()
    return pipeline.get_status()


@router.post("/fine-grained/analyze")
async def analyze_fine_grained(req: FineGrainedAnalysisRequest):
    """对视频进行细粒度理解分析

    检测视频中短暂画面和小区域细节的风险：
    - 地图完整性审核（缺失台湾/南海诸岛等）
    - 代码溯源检测（视频中的代码是否来自开源项目）
    - 敏感符号检测（争议性标志/旗帜/手势）
    - 时序异常检测（短暂异常画面）
    """
    import os

    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {req.video_path}")

    from backend.services.fine_grained import FineGrainedPipeline

    pipeline = FineGrainedPipeline({
        "enable_map_audit": req.enable_map_audit,
        "enable_code_trace": req.enable_code_trace,
        "enable_symbol_detect": req.enable_symbol_detect,
        "enable_temporal_anomaly": req.enable_temporal_anomaly,
    })

    report = await pipeline.analyze(req.video_path)

    return {
        "video_path": report.video_path,
        "has_fine_grained_risk": report.has_fine_grained_risk,
        "risk_upgrade": report.risk_upgrade,
        "max_risk_level": report.max_risk_level,
        "key_findings": report.key_findings,
        "evidence_frames": report.evidence_frames,
        "map_audit": {
            "has_map_risk": report.map_audit.has_map_risk if report.map_audit else False,
            "max_risk_level": report.map_audit.max_risk_level if report.map_audit else "safe",
            "map_frames_found": report.map_audit.map_frames_found if report.map_audit else 0,
        } if report.map_audit else None,
        "code_trace": {
            "has_opensource_risk": report.code_trace.has_opensource_risk if report.code_trace else False,
            "max_risk_level": report.code_trace.max_risk_level if report.code_trace else "safe",
            "frames_with_code": report.code_trace.frames_with_code if report.code_trace else 0,
        } if report.code_trace else None,
        "symbol_detect": {
            "has_symbol_risk": report.symbol_detect.has_symbol_risk if report.symbol_detect else False,
            "max_risk_level": report.symbol_detect.max_risk_level if report.symbol_detect else "safe",
        } if report.symbol_detect else None,
        "temporal_anomaly": {
            "has_anomaly": report.temporal_anomaly.has_anomaly if report.temporal_anomaly else False,
            "max_risk_level": report.temporal_anomaly.max_risk_level if report.temporal_anomaly else "safe",
            "anomaly_count": len(report.temporal_anomaly.anomalies) if report.temporal_anomaly else 0,
        } if report.temporal_anomaly else None,
        "error": report.error,
    }


# ==================== 图像生成 API (Agnes AI) ====================

class ImageGenRequest(BaseModel):
    """图像生成请求"""
    prompt: str = Field(..., description="图像描述提示词")
    size: str = Field(default="1024x1024", description="图像尺寸: 1024x1024 / 1024x768 / 768x1024")
    image_mode: str = Field(default="t2i", description="生成模式: t2i(文生图) / img2img(图生图)")
    image_urls: Optional[List[str]] = Field(default=None, description="图生图参考图片URL列表")
    model: Optional[str] = Field(default=None, description="指定模型（可选，不指定自动路由）")


class ImageGenResponse(BaseModel):
    """图像生成响应"""
    task_id: str
    model: str
    provider: str
    images: List[Dict[str, Any]]


@router.post("/api/v3/image/generate")
async def generate_image(req: ImageGenRequest) -> ImageGenResponse:
    """图像生成（支持文生图和图生图）

    自动路由到 Agnes Image 2.1 Flash (文生图) 或 Agnes Image 2.0 Flash (图生图)。
    也支持通过 model 参数指定模型。

    文生图示例:
        prompt="一只可爱的柴犬在樱花树下", image_mode="t2i"

    图生图示例:
        prompt="改成水彩画风格", image_mode="img2img", image_urls=["https://example.com/photo.png"]
    """
    task_id = str(uuid.uuid4())

    try:
        result = await call_image_gen(
            prompt=req.prompt,
            size=req.size,
            image_mode=req.image_mode,
            image_urls=req.image_urls,
            model=req.model,
        )

        return ImageGenResponse(
            task_id=task_id,
            model=result["model"],
            provider=result["provider"],
            images=result["images"],
        )

    except RuntimeError as e:
        logger.error("图像生成失败：%s", e)
        raise HTTPException(status_code=500, detail=f"图像生成失败：{str(e)}")
    except Exception as e:
        logger.error("图像生成异常：%s", e)
        raise HTTPException(status_code=500, detail=f"图像生成异常：{str(e)}")


@router.get("/api/v3/image/models")
async def list_image_gen_models():
    """列出所有可用的图像生成模型"""
    from backend.services.llm_client import registry

    endpoints = registry.get_image_gen_endpoints()
    models = []
    seen = set()
    for ep in endpoints:
        key = f"{ep.provider}:{ep.model_id}"
        if key not in seen:
            seen.add(key)
            models.append({
                "provider": ep.provider,
                "provider_name": ep.provider_name,
                "model_id": ep.model_id,
                "tier": ep.tier,
                "image_mode": ep.image_mode,
            })

    return {"models": models, "total": len(models)}
