"""本地模型部署 API 路由 (V3.2)

提供 Ollama / vLLM 本地模型的检测、管理、配置接口。
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.local_model_manager import (
    LocalModelManager,
    local_model_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v3/local-models", tags=["本地模型部署"])


# ===========================================================================
# 请求/响应模型
# ===========================================================================

class LocalModelStatusResponse(BaseModel):
    """本地模型状态响应"""
    hardware: dict
    ollama: dict
    vllm: dict
    suggestions: list[str]


class ModelPullRequest(BaseModel):
    model_id: str


class ModelConfigPatchResponse(BaseModel):
    config: dict
    message: str


# ===========================================================================
# API 端点
# ===========================================================================


@router.get("/status", response_model=LocalModelStatusResponse)
async def get_local_model_status():
    """获取本地模型部署完整状态

    包括：硬件信息(GPU/VRAM/RAM)、Ollama状态、vLLM状态、模型推荐
    """
    try:
        return local_model_manager.full_detection()
    except Exception as e:
        logger.error("本地模型状态检测失败: %s", e)
        raise HTTPException(status_code=500, detail=f"检测失败: {e}")


@router.get("/hardware")
async def get_hardware_info():
    """获取硬件信息（GPU/VRAM/RAM）"""
    from backend.services.local_model_manager import HardwareDetector
    hw = HardwareDetector()
    return {
        "gpu": hw.detect_gpu(),
        "ram_gb": hw.get_system_ram_gb(),
        "ollama_installed": hw.detect_ollama(),
        "vllm_installed": hw.detect_vllm(),
    }


@router.get("/ollama/status")
async def get_ollama_status():
    """获取 Ollama 服务状态"""
    ollama = local_model_manager.ollama
    running = ollama.is_running()
    result = {"running": running, "base_url": ollama.base_url}
    if running:
        result["installed_models"] = ollama.get_installed_models()
        gpu = local_model_manager.hardware.detect_gpu()
        result["recommended_models"] = ollama.get_recommended_models(gpu["vram_gb"])
    return result


@router.get("/ollama/models")
async def get_ollama_models():
    """获取 Ollama 已安装模型列表"""
    if not local_model_manager.ollama.is_running():
        raise HTTPException(status_code=503, detail="Ollama 服务未运行")
    return {"models": local_model_manager.ollama.get_installed_models()}


@router.post("/ollama/pull")
async def pull_ollama_model(req: ModelPullRequest):
    """拉取 Ollama 模型

    注意：这是一个长时间操作，可能需要几分钟到几十分钟。
    建议前端使用轮询或 WebSocket 跟踪进度。
    """
    if not local_model_manager.hardware.detect_ollama():
        raise HTTPException(status_code=503, detail="Ollama 未安装")

    success = local_model_manager.ollama.pull_model(req.model_id)
    if success:
        return {"message": f"模型 {req.model_id} 拉取成功", "model_id": req.model_id}
    else:
        raise HTTPException(status_code=500, detail=f"模型 {req.model_id} 拉取失败")


@router.get("/ollama/recommend")
async def get_ollama_recommendations():
    """根据硬件配置推荐 Ollama 模型"""
    gpu = local_model_manager.hardware.detect_gpu()
    return {
        "gpu": gpu,
        "recommended": local_model_manager.ollama.get_recommended_models(gpu["vram_gb"]),
    }


@router.get("/vllm/status")
async def get_vllm_status():
    """获取 vLLM 服务状态"""
    vllm = local_model_manager.vllm
    running = vllm.is_running()
    result = {"running": running, "base_url": vllm.base_url}
    if running:
        result["loaded_models"] = vllm.get_running_models()
    return result


@router.get("/vllm/models")
async def get_vllm_models():
    """获取 vLLM 当前加载的模型"""
    if not local_model_manager.vllm.is_running():
        raise HTTPException(status_code=503, detail="vLLM 服务未运行")
    return {"models": local_model_manager.vllm.get_running_models()}


@router.get("/config-patch", response_model=ModelConfigPatchResponse)
async def get_config_patch():
    """生成需要添加到 model_config.yaml 的配置补丁

    根据当前运行的本地服务自动生成配置。
    """
    patch = local_model_manager.generate_model_config_patch()
    if patch:
        return ModelConfigPatchResponse(
            config=patch,
            message="检测到本地服务，可将其添加到 model_config.yaml 中",
        )
    return ModelConfigPatchResponse(
        config={},
        message="未检测到运行的本地模型服务",
    )


@router.get("/setup-guide")
async def get_setup_guide():
    """获取本地模型部署指南"""
    return {
        "ollama": {
            "install": "https://ollama.com/download",
            "quick_start": [
                "# 1. 安装 Ollama",
                "curl -fsSL https://ollama.com/install.sh | sh",
                "# 2. 启动服务",
                "ollama serve",
                "# 3. 拉取模型",
                "ollama pull qwen2.5:7b",
                "# 4. 配置 .env",
                'OLLAMA_BASE_URL=http://localhost:11434/v1',
                'OLLAMA_API_KEY=ollama',
            ],
            "recommended_models": [
                {"id": "qwen2.5:7b", "desc": "7B 中文模型，适合 8GB VRAM"},
                {"id": "qwen2.5:14b", "desc": "14B 中文模型，适合 16GB VRAM"},
                {"id": "deepseek-r1:14b", "desc": "14B 推理模型"},
                {"id": "llama3.2:8b", "desc": "8B 通用模型"},
                {"id": "llama3.2-vision:11b", "desc": "11B 视觉模型（支持图片理解）"},
            ],
        },
        "vllm": {
            "install": "pip install vllm",
            "quick_start": [
                "# 1. 安装 vLLM",
                "pip install vllm",
                "# 2. 启动服务（以 Qwen2.5-7B 为例）",
                "python -m vllm.entrypoints.openai.api_server \\",
                "  --model Qwen/Qwen2.5-7B-Instruct \\",
                "  --host 0.0.0.0 --port 8000",
                "# 3. 配置 .env",
                'VLLM_BASE_URL=http://localhost:8000/v1',
                'VLLM_API_KEY=vllm',
            ],
            "notes": [
                "vLLM 需要 NVIDIA GPU，建议 16GB+ VRAM",
                "支持连续批处理，吞吐量比 Ollama 高 3-5 倍",
                "支持张量并行，可跨多 GPU 部署大模型",
            ],
        },
    }
