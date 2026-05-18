from __future__ import annotations

"""敏感符号检测器 - V3.4 细粒度视频理解

检测视频中短暂出现的争议性标志、旗帜、手势等。
即使仅出现几帧、仅占画面小区域也能检测。

方案：VLM全帧扫描 + 区域放大细审
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SymbolRiskResult:
    """敏感符号检测结果"""
    frame_path: str = ""
    timestamp: float = 0.0
    has_sensitive_symbol: bool = False
    symbols: list = field(default_factory=list)
    risk_level: str = "safe"
    confidence: float = 0.0
    description: str = ""


@dataclass
class VideoSymbolResult:
    """视频敏感符号检测总结果"""
    video_path: str = ""
    frames_with_symbols: int = 0
    symbol_results: list = field(default_factory=list)
    has_symbol_risk: bool = False
    max_risk_level: str = "safe"
    error: Optional[str] = None


SYMBOL_AUDIT_PROMPT = """你是一个视觉内容安全审核专家。请仔细检查这张图片中是否存在以下敏感视觉元素：

1. 争议性旗帜或标志（如特定国家/组织的旗帜、军旗、政治标志等）
2. 不当手势（如纳粹礼、侮辱性手势等）
3. 敏感组织的徽章、纹章或标识
4. 含有争议信息的贴图、水印或覆盖层
5. 地图中可能存在的领土争议标识

如果发现任何敏感元素，请描述其位置、类型和风险等级。

请严格以JSON格式输出：
{
    "has_sensitive_symbol": true/false,
    "symbols": [
        {
            "type": "旗帜/标志/手势/徽章/贴图/地图争议",
            "description": "详细描述",
            "position": "位置描述",
            "risk_level": "low/medium/high",
            "confidence": 0.0-1.0
        }
    ],
    "overall_risk_level": "safe/low/medium/high",
    "description": "整体审核描述"
}"""


class SensitiveSymbolDetector:
    """敏感符号检测器——检测视频中的争议性标志/旗帜/手势"""

    SYMBOL_CATEGORIES = [
        "争议性旗帜",
        "争议性标志",
        "争议性手势",
        "争议性徽章/纹章",
        "不当贴图/水印",
    ]

    def __init__(self, config: dict | None = None, vlm_client=None):
        self.config = config or {}
        self.vlm_client = vlm_client

    async def detect_frame(self, frame_path: str, timestamp: float = 0.0) -> SymbolRiskResult:
        """检测单帧中的敏感符号

        Args:
            frame_path: 帧图片路径
            timestamp: 时间戳

        Returns:
            SymbolRiskResult
        """
        if not os.path.exists(frame_path):
            return SymbolRiskResult(
                frame_path=frame_path,
                timestamp=timestamp,
                description=f"帧图片不存在: {frame_path}",
            )

        vlm_result = await self._vlm_detect_symbols(frame_path)

        if not vlm_result:
            return SymbolRiskResult(
                frame_path=frame_path,
                timestamp=timestamp,
                risk_level="safe",
                description="VLM检测失败",
            )

        has_sensitive = vlm_result.get("has_sensitive_symbol", False)
        symbols = vlm_result.get("symbols", [])
        risk_level = vlm_result.get("overall_risk_level", "safe")
        confidence = max(
            (s.get("confidence", 0.0) for s in symbols),
            default=0.0,
        )

        return SymbolRiskResult(
            frame_path=frame_path,
            timestamp=timestamp,
            has_sensitive_symbol=has_sensitive,
            symbols=symbols,
            risk_level=risk_level,
            confidence=confidence,
            description=vlm_result.get("description", ""),
        )

    async def detect_video_frames(
        self, frame_paths: list[str], timestamps: list[float] = None
    ) -> VideoSymbolResult:
        """检测视频多帧中的敏感符号"""
        if timestamps is None:
            timestamps = [0.0] * len(frame_paths)

        symbol_results = []
        frames_with_symbols = 0
        has_symbol_risk = False
        max_risk_level = "safe"
        risk_order = {"safe": 0, "low": 1, "medium": 2, "high": 3}

        for frame_path, timestamp in zip(frame_paths, timestamps):
            result = await self.detect_frame(frame_path, timestamp)
            symbol_results.append(result)

            if result.has_sensitive_symbol:
                frames_with_symbols += 1

            if result.risk_level not in ("safe", "low"):
                has_symbol_risk = True
                if risk_order.get(result.risk_level, 0) > risk_order.get(max_risk_level, 0):
                    max_risk_level = result.risk_level

        return VideoSymbolResult(
            frames_with_symbols=frames_with_symbols,
            symbol_results=symbol_results,
            has_symbol_risk=has_symbol_risk,
            max_risk_level=max_risk_level,
        )

    async def _vlm_detect_symbols(self, frame_path: str) -> Optional[dict]:
        """使用VLM检测敏感符号"""
        try:
            from backend.services.llm_client import call_vlm, parse_llm_json

            with open(frame_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            response = await call_vlm(
                prompt=SYMBOL_AUDIT_PROMPT,
                image_base64=img_data,
                task_type="symbol_detect",
            )

            result = parse_llm_json(response)
            if result:
                return result

            return {"has_sensitive_symbol": False}
        except Exception as e:
            logger.warning("VLM敏感符号检测失败: %s", e)
            return None

    def get_status(self) -> dict:
        """获取检测器可用状态"""
        return {
            "available": True,
            "categories": self.SYMBOL_CATEGORIES,
            "vlm_required": True,
        }
