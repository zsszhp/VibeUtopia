"""阶段 3 新增 API 路由 — 多模态 API + 人格生成 + ChromaDB

包含：
1. 多模态分析 API（支持 Qwen-VL, DeepSeek-VL 等）
2. 音频转写 API（阿里 Paraformer）
3. 人格生成 API（A/B/C三级人格）
4. ChromaDB 向量检索 API
5. 模型路由控制 API
6. 硬件检测 API
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
from backend.services.llm_client import call_llm, call_vlm, parse_llm_json
from backend.services.persona.life_story_generator import PersonaFactory
from backend.services.persona.memory_stream import MemoryStreamStore, get_memory_stream_status

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


@router.post("/api/v3/generate-persona")
async def generate_persona(req: PersonaGenerationRequest) -> PersonaGenerationResponse:
    """生成人生故事驱动的人格"""
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


@router.post("/api/v3/generate-persona-batch")
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


@router.post("/api/v3/retrieve-memory")
async def retrieve_memory(req: MemoryRetrieveRequest) -> MemoryRetrieveResponse:
    """向量检索 Agent 记忆（ChromaDB）"""
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


@router.get("/api/v3/memory-stream-status")
async def get_memory_stream_status_api():
    """获取 Memory Stream 状态"""
    return get_memory_stream_status()


@router.post("/api/v3/store-memory")
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
