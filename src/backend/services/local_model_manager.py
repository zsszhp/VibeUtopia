"""本地模型部署管理器 (V3.2)

支持 Ollama 和 vLLM 两种本地部署方案：
- Ollama: 一键部署，支持 llama3/qwen2.5/deepseek-r1 等开源模型
- vLLM: 高性能推理，支持连续批处理、张量并行

自动检测本地模型可用性，无缝集成到现有 ModelRegistry/ModelRouter 体系。
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalProviderType(Enum):
    OLLAMA = "ollama"
    VLLM = "vllm"


@dataclass
class LocalModelInfo:
    """本地模型信息"""
    provider: LocalProviderType
    model_id: str
    base_url: str
    is_available: bool
    vram_gb: float = 0.0
    context_length: int = 4096
    supports_vision: bool = False
    supports_tool_use: bool = False


# ===========================================================================
# Ollama 管理
# ===========================================================================

class OllamaManager:
    """Ollama 本地模型管理器"""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(self, base_url: str = ""):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", self.DEFAULT_BASE_URL)
        self.api_key = os.getenv("OLLAMA_API_KEY", "ollama")  # Ollama 默认不需要 key

    def is_running(self) -> bool:
        """检查 Ollama 服务是否运行"""
        try:
            import httpx
            with httpx.Client(timeout=3) as client:
                resp = client.get(f"{self.base_url.replace('/v1', '')}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> list[dict]:
        """获取已安装的模型列表"""
        try:
            import httpx
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url.replace('/v1', '')}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("models", [])
        except Exception as e:
            logger.warning("获取 Ollama 模型列表失败: %s", e)
        return []

    def get_recommended_models(self, vram_gb: float = 0) -> list[dict]:
        """根据 VRAM 推荐模型"""
        if vram_gb <= 0:
            return [
                {"id": "qwen3:1.7b", "size_gb": 1.2, "reason": "轻量中文模型，CPU 可跑"},
            ]
        elif vram_gb < 8:
            return [
                {"id": "qwen3-vl:4b", "size_gb": 3.0, "reason": "4B视觉模型，适合 4-8GB VRAM"},
                {"id": "qwen3:4b", "size_gb": 2.8, "reason": "4B中文文本模型"},
            ]
        elif vram_gb < 16:
            return [
                {"id": "qwen3-vl:8b", "size_gb": 6.1, "reason": "8B视觉模型，2026最佳本地VLM，256K上下文+2h视频理解"},
                {"id": "openbmb/minicpm-o2.6", "size_gb": 4.4, "reason": "8B多模态模型，GPT-4o级，端侧优化"},
                {"id": "qwen3:8b", "size_gb": 5.0, "reason": "8B中文文本模型"},
            ]
        elif vram_gb < 24:
            return [
                {"id": "qwen3-vl:8b", "size_gb": 6.1, "reason": "8B视觉模型（主力）"},
                {"id": "qwen3-vl:30b", "size_gb": 18.0, "reason": "30B MoE视觉模型，3B激活参数"},
            ]
        else:
            return [
                {"id": "qwen3-vl:32b", "size_gb": 20.0, "reason": "32B旗舰视觉模型"},
                {"id": "qwen3-vl:235b", "size_gb": 130.0, "reason": "235B MoE SOTA视觉模型"},
            ]

    def pull_model(self, model_id: str) -> bool:
        """拉取模型"""
        try:
            result = subprocess.run(
                ["ollama", "pull", model_id],
                capture_output=True, text=True, timeout=600
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("拉取模型 %s 失败: %s", model_id, e)
            return False

    def get_model_config(self) -> dict:
        """获取 Ollama 在 model_config.yaml 中的配置格式"""
        return {
            "ollama": {
                "name": "Ollama (本地部署)",
                "api_key_env": "OLLAMA_API_KEY",
                "base_url": self.base_url,
                "models": [
                    {"id": "qwen3-vl:8b", "tier": "advanced", "vision": True, "text": True},
                    {"id": "openbmb/minicpm-o2.6", "tier": "standard", "vision": True, "text": True},
                    {"id": "qwen3:8b", "tier": "advanced", "vision": False, "text": True},
                    {"id": "qwen3-vl:4b", "tier": "standard", "vision": True, "text": True},
                    {"id": "qwen3:4b", "tier": "standard", "vision": False, "text": True},
                ],
            }
        }


# ===========================================================================
# vLLM 管理
# ===========================================================================

class VLLMManager:
    """vLLM 本地模型管理器"""

    DEFAULT_BASE_URL = "http://localhost:8000/v1"

    def __init__(self, base_url: str = ""):
        self.base_url = base_url or os.getenv("VLLM_BASE_URL", self.DEFAULT_BASE_URL)

    def is_running(self) -> bool:
        """检查 vLLM 服务是否运行"""
        try:
            import httpx
            with httpx.Client(timeout=3) as client:
                resp = client.get(f"{self.base_url}/models")
                return resp.status_code == 200
        except Exception:
            return False

    def get_running_models(self) -> list[str]:
        """获取当前加载的模型"""
        try:
            import httpx
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning("获取 vLLM 模型列表失败: %s", e)
        return []

    def get_model_config(self, model_id: str = "", tier: str = "advanced") -> dict:
        """获取 vLLM 在 model_config.yaml 中的配置格式"""
        models = []
        if model_id:
            models.append({"id": model_id, "tier": tier, "vision": False, "text": True})
        return {
            "vllm": {
                "name": "vLLM (本地高性能推理)",
                "api_key_env": "VLLM_API_KEY",
                "base_url": self.base_url,
                "models": models,
            }
        }


# ===========================================================================
# 硬件检测
# ===========================================================================

class HardwareDetector:
    """本地硬件检测器"""

    @staticmethod
    def detect_gpu() -> dict:
        """检测 GPU 信息"""
        gpu_info = {"has_gpu": False, "vram_gb": 0, "gpu_name": "", "cuda_version": ""}

        # 检测 NVIDIA GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    gpu_info["has_gpu"] = True
                    gpu_info["gpu_name"] = parts[0].strip()
                    gpu_info["vram_gb"] = round(float(parts[1].strip()) / 1024, 1)
                    gpu_info["cuda_version"] = parts[2].strip() if len(parts) > 2 else ""
                    logger.info("检测到 GPU: %s, VRAM: %.1f GB", gpu_info["gpu_name"], gpu_info["vram_gb"])
                    return gpu_info
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 检测 Apple MPS (Mac)
        try:
            import platform
            if platform.system() == "Darwin":
                import torch
                if torch.backends.mps.is_available():
                    gpu_info["has_gpu"] = True
                    gpu_info["gpu_name"] = "Apple MPS"
                    gpu_info["vram_gb"] = 16  # 统一内存，估算值
                    logger.info("检测到 Apple MPS")
                    return gpu_info
        except ImportError:
            pass

        logger.info("未检测到 GPU，将使用 CPU 模式")
        return gpu_info

    @staticmethod
    def detect_ollama() -> bool:
        """检测 Ollama 是否安装"""
        return shutil.which("ollama") is not None

    @staticmethod
    def detect_vllm() -> bool:
        """检测 vLLM 是否安装"""
        try:
            import vllm  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def get_system_ram_gb() -> float:
        """获取系统内存大小"""
        try:
            import psutil
            return round(psutil.virtual_memory().total / (1024**3), 1)
        except ImportError:
            return 0.0


# ===========================================================================
# 统一本地模型管理器
# ===========================================================================

class LocalModelManager:
    """统一本地模型管理器

    自动检测并管理 Ollama 和 vLLM 服务，
    提供一键配置生成、健康检查、模型推荐等功能。
    """

    def __init__(self):
        self.ollama = OllamaManager()
        self.vllm = VLLMManager()
        self.hardware = HardwareDetector()

    def full_detection(self) -> dict:
        """执行完整检测，返回所有信息"""
        gpu = self.hardware.detect_gpu()
        ram = self.hardware.get_system_ram_gb()
        ollama_installed = self.hardware.detect_ollama()
        vllm_installed = self.hardware.detect_vllm()

        result = {
            "hardware": {
                "gpu": gpu,
                "ram_gb": ram,
                "ollama_installed": ollama_installed,
                "vllm_installed": vllm_installed,
            },
            "ollama": {
                "running": False,
                "installed_models": [],
                "recommended_models": [],
            },
            "vllm": {
                "running": False,
                "loaded_models": [],
            },
            "suggestions": [],
        }

        # Ollama 状态
        if ollama_installed:
            result["ollama"]["running"] = self.ollama.is_running()
            if result["ollama"]["running"]:
                result["ollama"]["installed_models"] = self.ollama.get_installed_models()
            result["ollama"]["recommended_models"] = self.ollama.get_recommended_models(gpu["vram_gb"])

        # vLLM 状态
        if vllm_installed:
            result["vllm"]["running"] = self.vllm.is_running()
            if result["vllm"]["running"]:
                result["vllm"]["loaded_models"] = self.vllm.get_running_models()

        # 建议
        if not ollama_installed and not vllm_installed:
            result["suggestions"].append("未检测到本地模型引擎，建议安装 Ollama: https://ollama.com/download")
        if ollama_installed and not result["ollama"]["running"]:
            result["suggestions"].append("Ollama 已安装但未运行，请执行: ollama serve")
        if result["ollama"]["running"] and not result["ollama"]["installed_models"]:
            result["suggestions"].append("Ollama 运行中但无模型，建议拉取: ollama pull qwen2.5:7b")
        if gpu["has_gpu"] and gpu["vram_gb"] >= 8:
            result["suggestions"].append(f"检测到 {gpu['gpu_name']} ({gpu['vram_gb']}GB VRAM)，可运行 {result['ollama']['recommended_models'][0]['id'] if result['ollama']['recommended_models'] else '7B+'} 模型")

        return result

    def generate_model_config_patch(self) -> dict:
        """生成需要添加到 model_config.yaml 的配置"""
        patch = {}
        if self.ollama.is_running():
            patch.update(self.ollama.get_model_config())
        if self.vllm.is_running():
            running = self.vllm.get_running_models()
            model_id = running[0] if running else ""
            patch.update(self.vllm.get_model_config(model_id))
        return patch

    def get_status_summary(self) -> str:
        """获取状态摘要文本"""
        info = self.full_detection()
        lines = ["=== 本地模型部署状态 ==="]
        hw = info["hardware"]
        lines.append(f"GPU: {hw['gpu']['gpu_name'] or '无'} ({hw['gpu']['vram_gb']}GB VRAM)")
        lines.append(f"RAM: {hw['ram_gb']}GB")
        lines.append(f"Ollama: {'已安装' if hw['ollama_installed'] else '未安装'} | 运行中: {info['ollama']['running']}")
        lines.append(f"vLLM: {'已安装' if hw['vllm_installed'] else '未安装'} | 运行中: {info['vllm']['running']}")
        if info["ollama"]["installed_models"]:
            models = [m["name"] for m in info["ollama"]["installed_models"]]
            lines.append(f"已安装模型: {', '.join(models)}")
        if info["vllm"]["loaded_models"]:
            lines.append(f"vLLM 模型: {', '.join(info['vllm']['loaded_models'])}")
        if info["suggestions"]:
            lines.append("建议:")
            for s in info["suggestions"]:
                lines.append(f"  - {s}")
        return "\n".join(lines)


# ===========================================================================
# 全局实例
# ===========================================================================

local_model_manager = LocalModelManager()
