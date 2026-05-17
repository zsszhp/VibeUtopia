"""VRAM管理器 - 视频内存管理模块

负责多模态风控中各模型的加载/卸载顺序控制,优化显存使用:
- 画面理解模型(Qwen3-VL-Plus/GLM-5V-Turbo)
- OCR模型(GLM-OCR/PaddleOCR)
- 音频转写模型(faster-whisper)

支持策略:
1. 按需加载: 仅在需要时加载模型
2. 优先级队列: 按任务优先级管理模型驻留
3. 自动卸载: 使用完毕后释放显存
4. 显存监控: 实时监控VRAM使用情况
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ModelPriority(Enum):
    """模型优先级"""
    CRITICAL = 0    # 关键路径,必须驻留
    HIGH = 1        # 高优先级,尽量驻留
    MEDIUM = 2      # 中等优先级,按需加载
    LOW = 3         # 低优先级,用完即卸


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    model_id: str
    priority: ModelPriority
    vram_required_mb: float  # 所需显存(MB)
    is_loaded: bool = False
    last_used: float = 0.0   # 最后使用时间戳
    load_count: int = 0      # 加载次数统计
    total_usage_time: float = 0.0  # 总使用时长


@dataclass
class VRAMStatus:
    """VRAM状态"""
    total_mb: float
    used_mb: float
    free_mb: float
    utilization_percent: float
    loaded_models: list[str] = field(default_factory=list)


class VRAMManager:
    """VRAM管理器 - 单例模式
    
    管理多模态模型的显存分配,避免OOM(Out of Memory)
    """
    
    _instance: VRAMManager | None = None
    _models: dict[str, ModelInfo] = {}
    _vram_limit_mb: float = 0.0
    _vram_used_mb: float = 0.0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._detect_hardware()
        self._register_default_models()
    
    def _detect_hardware(self):
        """检测硬件配置,确定可用VRAM"""
        try:
            import torch
            if torch.cuda.is_available():
                # 获取GPU显存
                device_count = torch.cuda.device_count()
                if device_count > 0:
                    props = torch.cuda.get_device_properties(0)
                    self._vram_limit_mb = props.total_memory / (1024 * 1024)
                    logger.info("检测到GPU: %s, 显存: %.0f MB", props.name, self._vram_limit_mb)
                else:
                    self._vram_limit_mb = 0
                    logger.warning("未检测到CUDA设备,将使用CPU模式")
            else:
                self._vram_limit_mb = 0
                logger.info("CUDA不可用,使用CPU模式")
        except ImportError:
            self._vram_limit_mb = 0
            logger.info("PyTorch未安装,使用CPU模式")
        
        # CPU模式预留少量内存作为"虚拟VRAM"
        if self._vram_limit_mb == 0:
            self._vram_limit_mb = 2048  # 假设2GB可用内存
            logger.info("CPU模式,虚拟VRAM: %.0f MB", self._vram_limit_mb)
    
    def _register_default_models(self):
        """注册默认多模态模型"""
        default_models = [
            ModelInfo(
                name="画面理解-Qwen3-VL-Plus",
                model_id="qwen-vl-plus",
                priority=ModelPriority.HIGH,
                vram_required_mb=4096,  # 4GB
            ),
            ModelInfo(
                name="画面理解-GLM-5V-Turbo",
                model_id="glm-5v-turbo",
                priority=ModelPriority.HIGH,
                vram_required_mb=3072,  # 3GB
            ),
            ModelInfo(
                name="OCR-GLM-OCR",
                model_id="glm-ocr",
                priority=ModelPriority.MEDIUM,
                vram_required_mb=2048,  # 2GB
            ),
            ModelInfo(
                name="OCR-PaddleOCR-VL",
                model_id="paddleocr-vl",
                priority=ModelPriority.LOW,
                vram_required_mb=1536,  # 1.5GB
            ),
            ModelInfo(
                name="音频转写-Whisper-Large",
                model_id="whisper-large-v3",
                priority=ModelPriority.MEDIUM,
                vram_required_mb=3072,  # 3GB
            ),
        ]
        
        for model in default_models:
            self._models[model.model_id] = model
    
    def get_vram_status(self) -> VRAMStatus:
        """获取当前VRAM状态"""
        try:
            import torch
            if torch.cuda.is_available():
                used = torch.cuda.memory_allocated(0) / (1024 * 1024)
                total = self._vram_limit_mb
                free = total - used
                utilization = (used / total * 100) if total > 0 else 0
                
                loaded = [m.name for m in self._models.values() if m.is_loaded]
                
                return VRAMStatus(
                    total_mb=total,
                    used_mb=round(used, 1),
                    free_mb=round(free, 1),
                    utilization_percent=round(utilization, 1),
                    loaded_models=loaded,
                )
        except Exception:
            pass
        
        # 降级: 返回估算值
        loaded = [m.name for m in self._models.values() if m.is_loaded]
        return VRAMStatus(
            total_mb=self._vram_limit_mb,
            used_mb=self._vram_used_mb,
            free_mb=self._vram_limit_mb - self._vram_used_mb,
            utilization_percent=(self._vram_used_mb / self._vram_limit_mb * 100) if self._vram_limit_mb > 0 else 0,
            loaded_models=loaded,
        )
    
    def can_load_model(self, model_id: str) -> bool:
        """检查是否可以加载指定模型
        
        Args:
            model_id: 模型ID
            
        Returns:
            True表示可以加载,False表示显存不足
        """
        if model_id not in self._models:
            logger.warning("未知模型: %s", model_id)
            return False
        
        model = self._models[model_id]
        status = self.get_vram_status()
        
        # 检查是否有足够显存
        if status.free_mb < model.vram_required_mb:
            logger.warning(
                "显存不足: 需要%.0f MB, 可用%.0f MB",
                model.vram_required_mb, status.free_mb
            )
            return False
        
        return True
    
    def load_model(self, model_id: str) -> bool:
        """加载模型到VRAM
        
        Args:
            model_id: 模型ID
            
        Returns:
            True表示加载成功
        """
        if model_id not in self._models:
            logger.error("未知模型: %s", model_id)
            return False
        
        model = self._models[model_id]
        
        # 已加载则直接返回
        if model.is_loaded:
            model.last_used = time.time()
            model.load_count += 1
            return True
        
        # 检查显存
        if not self.can_load_model(model_id):
            # 尝试卸载低优先级模型
            if not self._evict_low_priority_models(model.vram_required_mb):
                logger.error("无法为模型 %s 释放足够显存", model.name)
                return False
        
        # 加载模型(实际加载逻辑由调用方执行)
        model.is_loaded = True
        model.last_used = time.time()
        model.load_count += 1
        
        # 更新已使用显存
        self._vram_used_mb += model.vram_required_mb
        
        logger.info("模型已加载: %s (%.0f MB)", model.name, model.vram_required_mb)
        return True
    
    def unload_model(self, model_id: str) -> bool:
        """卸载模型释放VRAM
        
        Args:
            model_id: 模型ID
            
        Returns:
            True表示卸载成功
        """
        if model_id not in self._models:
            return False
        
        model = self._models[model_id]
        
        if not model.is_loaded:
            return True
        
        # 卸载模型(实际清理逻辑由调用方执行)
        model.is_loaded = False
        self._vram_used_mb = max(0, self._vram_used_mb - model.vram_required_mb)
        
        logger.info("模型已卸载: %s (释放%.0f MB)", model.name, model.vram_required_mb)
        return True
    
    def use_model(self, model_id: str):
        """标记模型正在使用
        
        更新最后使用时间,用于LRU淘汰策略
        """
        if model_id in self._models:
            self._models[model_id].last_used = time.time()
    
    def _evict_low_priority_models(self, required_mb: float) -> bool:
        """卸载低优先级模型以释放显存
        
        Args:
            required_mb: 需要释放的显存量
            
        Returns:
            True表示成功释放足够显存
        """
        status = self.get_vram_status()
        if status.free_mb >= required_mb:
            return True
        
        # 按优先级和最后使用时间排序,优先卸载低优先级且久未使用的模型
        loaded_models = [
            m for m in self._models.values()
            if m.is_loaded and m.priority > ModelPriority.CRITICAL
        ]
        
        # 按优先级降序、最后使用时间升序排序
        loaded_models.sort(key=lambda m: (m.priority.value, m.last_used))
        
        freed_mb = 0.0
        for model in loaded_models:
            if status.free_mb + freed_mb >= required_mb:
                break
            
            logger.info("自动卸载低优先级模型: %s", model.name)
            self.unload_model(model.model_id)
            freed_mb += model.vram_required_mb
        
        return (status.free_mb + freed_mb) >= required_mb
    
    def unload_all(self):
        """卸载所有模型"""
        for model_id in list(self._models.keys()):
            if self._models[model_id].is_loaded:
                self.unload_model(model_id)
        
        logger.info("所有模型已卸载")
    
    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """获取模型信息"""
        return self._models.get(model_id)
    
    def list_loaded_models(self) -> list[str]:
        """列出已加载的模型"""
        return [m.name for m in self._models.values() if m.is_loaded]
    
    def get_usage_stats(self) -> dict[str, Any]:
        """获取使用统计"""
        stats = {
            "total_models": len(self._models),
            "loaded_models": sum(1 for m in self._models.values() if m.is_loaded),
            "vram_limit_mb": self._vram_limit_mb,
            "vram_used_mb": self._vram_used_mb,
            "vram_free_mb": self._vram_limit_mb - self._vram_used_mb,
            "models": []
        }
        
        for model in self._models.values():
            stats["models"].append({
                "name": model.name,
                "is_loaded": model.is_loaded,
                "load_count": model.load_count,
                "priority": model.priority.name,
                "vram_required_mb": model.vram_required_mb,
            })
        
        return stats
