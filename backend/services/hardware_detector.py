"""硬件自适应检测模块

检测当前硬件配置,自动选择合适的模型和参数层级:
- Lite: CPU模式,零外部依赖
- Standard: 入门GPU(4-6GB VRAM)
- Pro: 中端GPU(8-12GB VRAM)
- Ultra: 高端GPU(16GB+ VRAM)

根据硬件层级自动:
1. 选择合适的多模态模型
2. 调整批处理大小
3. 优化内存使用策略
4. 设置并发限制
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HardwareTier(Enum):
    """硬件层级"""
    LITE = "lite"           # CPU模式,零外部依赖
    STANDARD = "standard"   # 入门GPU(4-6GB)
    PRO = "pro"             # 中端GPU(8-12GB)
    ULTRA = "ultra"         # 高端GPU(16GB+)


@dataclass
class HardwareInfo:
    """硬件信息"""
    tier: HardwareTier
    cpu_cores: int
    ram_gb: float
    gpu_name: str = ""
    vram_gb: float = 0.0
    cuda_available: bool = False
    platform: str = ""


@dataclass
class ModelRecommendation:
    """模型推荐配置"""
    vision_model: str           # 画面理解模型
    ocr_model: str              # OCR模型
    audio_model: str            # 音频转写模型
    risk_assessment_model: str  # 风险评估模型
    agent_simulation_model: str # Agent仿真模型
    batch_size: int             # 批处理大小
    max_concurrent: int         # 最大并发数


# 各硬件层级的推荐配置
TIER_CONFIGS = {
    HardwareTier.LITE: ModelRecommendation(
        vision_model="api-qwen-vl-plus",      # 使用API
        ocr_model="api-glm-ocr",              # 使用API
        audio_model="local-whisper-tiny",     # 本地小模型
        risk_assessment_model="api-deepseek", # 使用API
        agent_simulation_model="api-qwen-8b", # 使用API
        batch_size=1,
        max_concurrent=2,
    ),
    HardwareTier.STANDARD: ModelRecommendation(
        vision_model="api-qwen-vl-plus",
        ocr_model="local-paddleocr",          # 本地OCR
        audio_model="local-whisper-medium",
        risk_assessment_model="api-deepseek",
        agent_simulation_model="api-qwen-8b",
        batch_size=2,
        max_concurrent=4,
    ),
    HardwareTier.PRO: ModelRecommendation(
        vision_model="local-qwen-vl-8b",      # 本地模型
        ocr_model="local-paddleocr",
        audio_model="local-whisper-large",
        risk_assessment_model="api-deepseek-pro",
        agent_simulation_model="local-qwen-8b",
        batch_size=4,
        max_concurrent=8,
    ),
    HardwareTier.ULTRA: ModelRecommendation(
        vision_model="local-qwen-vl-72b",     # 本地大模型
        ocr_model="local-paddleocr-vl",
        audio_model="local-whisper-large-v3",
        risk_assessment_model="local-deepseek-32b",
        agent_simulation_model="local-qwen-32b",
        batch_size=8,
        max_concurrent=16,
    ),
}


def detect_tier() -> HardwareInfo:
    """检测当前硬件配置并返回层级
    
    Returns:
        HardwareInfo: 硬件信息包含层级和详细配置
    """
    import platform
    import psutil
    
    # 基础信息
    cpu_cores = psutil.cpu_count(logical=True)
    ram_gb = psutil.virtual_memory().total / (1024**3)
    platform_name = platform.system()
    
    # 检测GPU
    gpu_name = ""
    vram_gb = 0.0
    cuda_available = False
    
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            if device_count > 0:
                props = torch.cuda.get_device_properties(0)
                gpu_name = props.name
                vram_gb = props.total_memory / (1024**3)
                logger.info("检测到GPU: %s, VRAM: %.1f GB", gpu_name, vram_gb)
    except ImportError:
        logger.info("PyTorch未安装,使用CPU模式")
    
    # 判定层级
    tier = _classify_tier(vram_gb, cuda_available, cpu_cores, ram_gb)
    
    hardware_info = HardwareInfo(
        tier=tier,
        cpu_cores=cpu_cores,
        ram_gb=round(ram_gb, 1),
        gpu_name=gpu_name,
        vram_gb=round(vram_gb, 1),
        cuda_available=cuda_available,
        platform=platform_name,
    )
    
    logger.info(
        "硬件检测完成: 层级=%s, GPU=%s, VRAM=%.1fGB, CPU=%d核, 内存=%.1fGB",
        tier.name, gpu_name or "CPU", vram_gb, cpu_cores, ram_gb
    )
    
    return hardware_info


def _classify_tier(
    vram_gb: float,
    cuda_available: bool,
    cpu_cores: int,
    ram_gb: float,
) -> HardwareTier:
    """根据硬件配置分类层级
    
    Args:
        vram_gb: 显存大小(GB)
        cuda_available: CUDA是否可用
        cpu_cores: CPU核心数
        ram_gb: 内存大小(GB)
        
    Returns:
        HardwareTier: 硬件层级
    """
    if not cuda_available or vram_gb < 4:
        # 无GPU或显存小于4GB → Lite
        return HardwareTier.LITE
    elif vram_gb < 8:
        # 4-8GB → Standard
        return HardwareTier.STANDARD
    elif vram_gb < 16:
        # 8-16GB → Pro
        return HardwareTier.PRO
    else:
        # 16GB+ → Ultra
        return HardwareTier.ULTRA


def get_model_recommendation(tier: HardwareTier | None = None) -> ModelRecommendation:
    """获取推荐模型配置
    
    Args:
        tier: 硬件层级,如不指定则自动检测
        
    Returns:
        ModelRecommendation: 推荐配置
    """
    if tier is None:
        hardware = detect_tier()
        tier = hardware.tier
    
    return TIER_CONFIGS[tier]


def get_hardware_summary() -> dict:
    """获取硬件配置摘要(用于API响应)
    
    Returns:
        包含硬件信息和推荐配置的字典
    """
    hardware = detect_tier()
    recommendation = get_model_recommendation(hardware.tier)
    
    return {
        "hardware": {
            "tier": hardware.tier.value,
            "tier_name": {
                "lite": "Lite (CPU模式)",
                "standard": "Standard (入门GPU)",
                "pro": "Pro (中端GPU)",
                "ultra": "Ultra (高端GPU)",
            }.get(hardware.tier.value, "Unknown"),
            "cpu_cores": hardware.cpu_cores,
            "ram_gb": hardware.ram_gb,
            "gpu_name": hardware.gpu_name or "N/A",
            "vram_gb": hardware.vram_gb,
            "cuda_available": hardware.cuda_available,
            "platform": hardware.platform,
        },
        "recommendation": {
            "vision_model": recommendation.vision_model,
            "ocr_model": recommendation.ocr_model,
            "audio_model": recommendation.audio_model,
            "risk_assessment_model": recommendation.risk_assessment_model,
            "agent_simulation_model": recommendation.agent_simulation_model,
            "batch_size": recommendation.batch_size,
            "max_concurrent": recommendation.max_concurrent,
        },
    }
