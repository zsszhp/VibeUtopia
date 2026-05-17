"""硬件自适应检测模块 + 本地模型管理

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

LocalModelManager:
- 管理 Ollama 本地模型检测和配置
- 支持 vLLM 本地推理服务检测
- 模型下载和缓存管理
- 与 ModelRouter 集成
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ═══════════════════════════════════════════════════════════════════════════════
# 本地模型管理器
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LocalModelInfo:
    """本地模型信息"""
    model_id: str
    model_name: str
    provider: str              # ollama / vllm / local
    size_gb: float = 0.0
    quantization: str = ""     # q4_0, q8_0, fp16, etc.
    status: str = "not_installed"  # not_installed / downloading / ready / error
    vram_required_gb: float = 0.0
    task_types: List[str] = field(default_factory=list)
    local_path: str = ""


@dataclass
class OllamaModelConfig:
    """Ollama 模型配置"""
    model_name: str
    tag: str = "latest"
    size_gb: float = 0.0
    vram_required_gb: float = 0.0
    task_types: List[str] = field(default_factory=list)
    quantization: str = ""


@dataclass
class VLLMModelConfig:
    """vLLM 模型配置"""
    model_name: str
    model_path: str = ""       # HuggingFace 模型ID或本地路径
    tensor_parallel: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 4096
    dtype: str = "auto"
    vram_required_gb: float = 0.0
    task_types: List[str] = field(default_factory=list)


# 预定义的推荐本地模型
RECOMMENDED_OLLAMA_MODELS = {
    "qwen2.5:7b": OllamaModelConfig(
        model_name="qwen2.5", tag="7b", size_gb=4.7,
        vram_required_gb=6.0, task_types=["risk_assessment", "agent_simulation"],
        quantization="q4_0",
    ),
    "qwen2.5:14b": OllamaModelConfig(
        model_name="qwen2.5", tag="14b", size_gb=9.0,
        vram_required_gb=12.0, task_types=["risk_assessment", "agent_simulation"],
        quantization="q4_0",
    ),
    "deepseek-r1:7b": OllamaModelConfig(
        model_name="deepseek-r1", tag="7b", size_gb=4.7,
        vram_required_gb=6.0, task_types=["risk_assessment", "reasoning"],
        quantization="q4_0",
    ),
    "deepseek-r1:14b": OllamaModelConfig(
        model_name="deepseek-r1", tag="14b", size_gb=9.0,
        vram_required_gb=12.0, task_types=["risk_assessment", "reasoning"],
        quantization="q4_0",
    ),
    "llama3.1:8b": OllamaModelConfig(
        model_name="llama3.1", tag="8b", size_gb=4.9,
        vram_required_gb=6.0, task_types=["agent_simulation", "text_generation"],
        quantization="q4_0",
    ),
    "gemma2:9b": OllamaModelConfig(
        model_name="gemma2", tag="9b", size_gb=5.4,
        vram_required_gb=7.0, task_types=["agent_simulation", "text_generation"],
        quantization="q4_0",
    ),
}

RECOMMENDED_VLLM_MODELS = {
    "Qwen/Qwen2.5-7B-Instruct": VLLMModelConfig(
        model_name="Qwen2.5-7B-Instruct",
        model_path="Qwen/Qwen2.5-7B-Instruct",
        vram_required_gb=8.0,
        task_types=["risk_assessment", "agent_simulation"],
    ),
    "Qwen/Qwen2.5-14B-Instruct": VLLMModelConfig(
        model_name="Qwen2.5-14B-Instruct",
        model_path="Qwen/Qwen2.5-14B-Instruct",
        vram_required_gb=16.0,
        task_types=["risk_assessment", "agent_simulation"],
    ),
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": VLLMModelConfig(
        model_name="DeepSeek-R1-Distill-Qwen-7B",
        model_path="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        vram_required_gb=8.0,
        task_types=["risk_assessment", "reasoning"],
    ),
}


class LocalModelManager:
    """本地模型生命周期管理器

    功能：
    - Ollama 本地模型检测和配置
    - vLLM 本地推理服务检测
    - 模型下载和缓存管理
    - 与 ModelRouter 集成
    """

    def __init__(self, cache_dir: str | None = None):
        self._cache_dir = cache_dir or os.path.join(
            os.path.expanduser("~"), ".vibeutopia", "models"
        )
        self._ollama_available: bool | None = None
        self._vllm_available: bool | None = None
        self._installed_models: Dict[str, LocalModelInfo] = {}
        self._ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._vllm_base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000")

    # ── Ollama 检测与管理 ──────────────────────────────

    def detect_ollama(self) -> bool:
        """检测 Ollama 是否已安装并运行

        Returns:
            Ollama 是否可用
        """
        if self._ollama_available is not None:
            return self._ollama_available

        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("Ollama 已安装: %s", result.stdout.strip())
                self._ollama_available = True
                return True
        except FileNotFoundError:
            logger.info("Ollama 未安装")
        except subprocess.TimeoutExpired:
            logger.warning("Ollama 检测超时")
        except Exception as e:
            logger.debug("Ollama 检测异常: %s", e)

        try:
            import httpx
            resp = httpx.get(f"{self._ollama_base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                self._ollama_available = True
                return True
        except Exception:
            pass

        self._ollama_available = False
        return False

    def list_ollama_models(self) -> List[LocalModelInfo]:
        """列出 Ollama 已安装的模型

        Returns:
            已安装模型信息列表
        """
        if not self.detect_ollama():
            return []

        models = []
        try:
            import httpx
            resp = httpx.get(f"{self._ollama_base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    model_id = f"ollama:{m['name']}"
                    info = LocalModelInfo(
                        model_id=model_id,
                        model_name=m["name"],
                        provider="ollama",
                        size_gb=m.get("size", 0) / (1024**3),
                        status="ready",
                        local_path=m.get("modified_at", ""),
                    )
                    models.append(info)
                    self._installed_models[model_id] = info
        except Exception as e:
            logger.error("获取 Ollama 模型列表失败: %s", e)

        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        model_id = f"ollama:{name}"
                        if model_id not in self._installed_models:
                            info = LocalModelInfo(
                                model_id=model_id,
                                model_name=name,
                                provider="ollama",
                                status="ready",
                            )
                            models.append(info)
                            self._installed_models[model_id] = info
        except Exception:
            pass

        return models

    def pull_ollama_model(self, model_name: str) -> Dict[str, Any]:
        """下载 Ollama 模型

        Args:
            model_name: 模型名称，如 "qwen2.5:7b"

        Returns:
            下载结果
        """
        if not self.detect_ollama():
            return {"success": False, "error": "Ollama 未安装或未运行"}

        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                model_id = f"ollama:{model_name}"
                self._installed_models[model_id] = LocalModelInfo(
                    model_id=model_id,
                    model_name=model_name,
                    provider="ollama",
                    status="ready",
                )
                logger.info("Ollama 模型 %s 下载完成", model_name)
                return {"success": True, "model_name": model_name}
            else:
                return {"success": False, "error": result.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "下载超时（模型较大，请耐心等待）"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_ollama_model(self, model_name: str) -> Dict[str, Any]:
        """删除 Ollama 模型

        Args:
            model_name: 模型名称

        Returns:
            删除结果
        """
        try:
            result = subprocess.run(
                ["ollama", "rm", model_name],
                capture_output=True, text=True, timeout=30,
            )
            model_id = f"ollama:{model_name}"
            self._installed_models.pop(model_id, None)
            if result.returncode == 0:
                return {"success": True, "model_name": model_name}
            else:
                return {"success": False, "error": result.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── vLLM 检测与管理 ────────────────────────────────

    def detect_vllm(self) -> bool:
        """检测 vLLM 是否已安装并运行

        Returns:
            vLLM 是否可用
        """
        if self._vllm_available is not None:
            return self._vllm_available

        try:
            import httpx
            resp = httpx.get(f"{self._vllm_base_url}/v1/models", timeout=3)
            if resp.status_code == 200:
                self._vllm_available = True
                logger.info("vLLM 服务已运行: %s", self._vllm_base_url)
                return True
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["python", "-m", "vllm", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("vLLM 已安装: %s", result.stdout.strip())
                self._vllm_available = True
                return True
        except Exception:
            pass

        self._vllm_available = False
        return False

    def list_vllm_models(self) -> List[LocalModelInfo]:
        """列出 vLLM 已加载的模型

        Returns:
            已加载模型信息列表
        """
        if not self.detect_vllm():
            return []

        models = []
        try:
            import httpx
            resp = httpx.get(f"{self._vllm_base_url}/v1/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    model_id = f"vllm:{m['id']}"
                    info = LocalModelInfo(
                        model_id=model_id,
                        model_name=m["id"],
                        provider="vllm",
                        status="ready",
                    )
                    models.append(info)
                    self._installed_models[model_id] = info
        except Exception as e:
            logger.error("获取 vLLM 模型列表失败: %s", e)

        return models

    def start_vllm_server(self, model_path: str,
                          tensor_parallel: int = 1,
                          gpu_memory_utilization: float = 0.9,
                          max_model_len: int = 4096,
                          port: int = 8000) -> Dict[str, Any]:
        """启动 vLLM 推理服务器

        Args:
            model_path: HuggingFace 模型ID或本地路径
            tensor_parallel: 张量并行数
            gpu_memory_utilization: GPU内存利用率
            max_model_len: 最大模型长度
            port: 服务端口

        Returns:
            启动结果
        """
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_path,
            "--tensor-parallel-size", str(tensor_parallel),
            "--gpu-memory-utilization", str(gpu_memory_utilization),
            "--max-model-len", str(max_model_len),
            "--port", str(port),
        ]

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            logger.info("vLLM 服务器启动中: model=%s, port=%d", model_path, port)
            return {
                "success": True,
                "model_path": model_path,
                "port": port,
                "message": "vLLM 服务器启动中，请稍等片刻后检查状态",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 模型缓存管理 ───────────────────────────────────

    def get_cache_dir(self) -> str:
        """获取模型缓存目录"""
        os.makedirs(self._cache_dir, exist_ok=True)
        return self._cache_dir

    def get_cache_size(self) -> Dict[str, float]:
        """获取模型缓存大小

        Returns:
            各缓存目录的大小信息
        """
        sizes = {}
        cache_dirs = {
            "ollama": os.path.join(os.path.expanduser("~"), ".ollama"),
            "huggingface": os.path.join(os.path.expanduser("~"), ".cache", "huggingface"),
            "vibeutopia": self._cache_dir,
        }

        for name, path in cache_dirs.items():
            if os.path.exists(path):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            total_size += os.path.getsize(fp)
                        except OSError:
                            pass
                sizes[name] = round(total_size / (1024**3), 2)
            else:
                sizes[name] = 0.0

        return sizes

    def clear_cache(self, cache_type: str = "vibeutopia") -> Dict[str, Any]:
        """清理模型缓存

        Args:
            cache_type: 缓存类型 ollama/huggingface/vibeutopia

        Returns:
            清理结果
        """
        cache_dirs = {
            "vibeutopia": self._cache_dir,
        }

        if cache_type not in cache_dirs:
            return {"success": False, "error": f"不支持的缓存类型: {cache_type}"}

        path = cache_dirs[cache_type]
        if not os.path.exists(path):
            return {"success": True, "message": "缓存目录不存在，无需清理"}

        try:
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
            return {"success": True, "message": f"已清理 {cache_type} 缓存"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 综合管理 ───────────────────────────────────────

    def get_all_local_models(self) -> List[LocalModelInfo]:
        """获取所有已安装的本地模型

        Returns:
            已安装模型列表
        """
        models = []
        models.extend(self.list_ollama_models())
        models.extend(self.list_vllm_models())
        return models

    def get_recommended_local_models(self, tier: HardwareTier | None = None) -> List[Dict[str, Any]]:
        """根据硬件层级推荐可用的本地模型

        Args:
            tier: 硬件层级，不指定则自动检测

        Returns:
            推荐模型列表
        """
        if tier is None:
            hardware = detect_tier()
            tier = hardware.tier

        vram_limit = {
            HardwareTier.LITE: 0,
            HardwareTier.STANDARD: 6,
            HardwareTier.PRO: 12,
            HardwareTier.ULTRA: 999,
        }.get(tier, 0)

        recommendations = []

        for model_id, config in RECOMMENDED_OLLAMA_MODELS.items():
            recommendations.append({
                "model_id": f"ollama:{model_id}",
                "model_name": model_id,
                "provider": "ollama",
                "size_gb": config.size_gb,
                "vram_required_gb": config.vram_required_gb,
                "can_run": config.vram_required_gb <= vram_limit,
                "task_types": config.task_types,
                "quantization": config.quantization,
                "status": "installed" if f"ollama:{model_id}" in self._installed_models else "available",
            })

        for model_id, config in RECOMMENDED_VLLM_MODELS.items():
            recommendations.append({
                "model_id": f"vllm:{model_id}",
                "model_name": model_id,
                "provider": "vllm",
                "size_gb": 0,
                "vram_required_gb": config.vram_required_gb,
                "can_run": config.vram_required_gb <= vram_limit,
                "task_types": config.task_types,
                "tensor_parallel": config.tensor_parallel,
                "status": "installed" if f"vllm:{model_id}" in self._installed_models else "available",
            })

        return recommendations

    def get_status(self) -> Dict[str, Any]:
        """获取本地模型管理器状态

        Returns:
            状态信息
        """
        ollama_ok = self.detect_ollama()
        vllm_ok = self.detect_vllm()
        installed = self.get_all_local_models()
        cache_sizes = self.get_cache_size()

        return {
            "ollama_available": ollama_ok,
            "vllm_available": vllm_ok,
            "installed_models_count": len(installed),
            "installed_models": [
                {
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "provider": m.provider,
                    "status": m.status,
                    "size_gb": round(m.size_gb, 2),
                }
                for m in installed
            ],
            "cache_sizes_gb": cache_sizes,
            "ollama_base_url": self._ollama_base_url,
            "vllm_base_url": self._vllm_base_url,
        }

    # ── 与 ModelRouter 集成 ────────────────────────────

    def register_to_model_router(self) -> Dict[str, Any]:
        """将本地模型注册到 ModelRouter

        Returns:
            注册结果
        """
        registered = []
        errors = []

        try:
            from backend.services.llm_client import registry
        except ImportError:
            return {"success": False, "error": "ModelRouter 未可用"}

        for model_info in self.get_all_local_models():
            if model_info.status != "ready":
                continue

            try:
                if model_info.provider == "ollama":
                    base_url = f"{self._ollama_base_url}/v1"
                    api_key = "ollama"
                    model_id = model_info.model_name
                elif model_info.provider == "vllm":
                    base_url = f"{self._vllm_base_url}/v1"
                    api_key = "vllm"
                    model_id = model_info.model_name
                else:
                    continue

                from backend.services.llm_client import ModelEndpoint
                endpoint = ModelEndpoint(
                    provider=model_info.provider,
                    model_id=model_id,
                    base_url=base_url,
                    api_key=api_key,
                    tier="local",
                    provider_name=f"本地{model_info.provider.upper()}",
                )
                registry.endpoints.append(endpoint)
                registered.append(model_info.model_id)
                logger.info("注册本地模型到 ModelRouter: %s", model_info.model_id)
            except Exception as e:
                errors.append({"model_id": model_info.model_id, "error": str(e)})

        return {
            "success": True,
            "registered_count": len(registered),
            "registered": registered,
            "errors": errors,
        }

    def get_local_model_for_task(self, task_type: str) -> Optional[LocalModelInfo]:
        """根据任务类型查找最合适的本地模型

        Args:
            task_type: 任务类型

        Returns:
            最合适的本地模型信息，无可用则返回 None
        """
        for model_info in self.get_all_local_models():
            if model_info.status != "ready":
                continue
            config = self._get_model_config(model_info)
            if config and task_type in config.get("task_types", []):
                return model_info
        return None

    def _get_model_config(self, model_info: LocalModelInfo) -> Optional[Dict[str, Any]]:
        """获取模型的推荐配置"""
        name = model_info.model_name

        for model_id, config in RECOMMENDED_OLLAMA_MODELS.items():
            if name == model_id or name.startswith(model_id.split(":")[0]):
                return {
                    "task_types": config.task_types,
                    "vram_required_gb": config.vram_required_gb,
                    "quantization": config.quantization,
                }

        for model_id, config in RECOMMENDED_VLLM_MODELS.items():
            if name == model_id or name in model_id:
                return {
                    "task_types": config.task_types,
                    "vram_required_gb": config.vram_required_gb,
                    "tensor_parallel": config.tensor_parallel,
                }

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 全局单例和便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

_local_model_manager: LocalModelManager | None = None


def get_local_model_manager() -> LocalModelManager:
    """获取 LocalModelManager 全局单例"""
    global _local_model_manager
    if _local_model_manager is None:
        _local_model_manager = LocalModelManager()
    return _local_model_manager


# 兼容 routes_v3.py 中已有的导入
def get_hardware_detector():
    """获取硬件检测器（兼容接口）"""
    return type("HardwareDetector", (), {
        "get_recommended_models": lambda: get_hardware_summary(),
    })()


@dataclass
class HardwareInfoV3:
    """routes_v3 兼容的硬件信息"""
    gpu_available: bool
    gpu_name: str
    vram_total_gb: float
    cpu_cores: int
    memory_total_gb: float
    recommended_tier: str


def get_hardware_info() -> HardwareInfoV3:
    """获取硬件信息（兼容 routes_v3 接口）"""
    hardware = detect_tier()
    return HardwareInfoV3(
        gpu_available=hardware.cuda_available,
        gpu_name=hardware.gpu_name,
        vram_total_gb=hardware.vram_gb,
        cpu_cores=hardware.cpu_cores,
        memory_total_gb=hardware.ram_gb,
        recommended_tier=hardware.tier.value,
    )


def get_recommended_model_tier() -> str:
    """获取推荐模型层级"""
    hardware = detect_tier()
    return hardware.tier.value
