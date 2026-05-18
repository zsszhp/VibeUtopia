from __future__ import annotations

"""地图完整性审核器 - V3.4 细粒度视频理解

检测视频中地图是否缺失关键区域（如台湾、南海诸岛等）。
即使地图仅出现几帧、仅占画面一小部分也能检测。

方案：VLM理解地图内容 + 地理知识库比对 + OCR文字标注检查
"""

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RequiredRegion:
    """必须包含的地理区域"""
    name: str
    lat_range: tuple
    lon_range: tuple
    keywords: list = field(default_factory=list)
    description: str = ""


@dataclass
class MapAuditResult:
    """地图完整性审核结果"""
    is_map: bool = False
    country: str = ""
    is_complete: bool = True
    missing_regions: list = field(default_factory=list)
    has_boundary_issue: bool = False
    risk_level: str = "safe"
    confidence: float = 0.0
    description: str = ""
    ocr_texts: list = field(default_factory=list)
    timestamp: float = 0.0
    frame_path: str = ""


@dataclass
class VideoMapAuditResult:
    """视频地图审核总结果"""
    video_path: str = ""
    map_frames_found: int = 0
    audit_results: list = field(default_factory=list)
    has_map_risk: bool = False
    max_risk_level: str = "safe"
    error: Optional[str] = None


CHINA_REQUIRED_REGIONS = [
    RequiredRegion(
        name="台湾",
        lat_range=(21.9, 25.3),
        lon_range=(120.0, 122.0),
        keywords=["台湾", "台灣", "Taiwan", "台"],
        description="中国台湾省，必须在中国地图中显示",
    ),
    RequiredRegion(
        name="南海诸岛",
        lat_range=(3.5, 21.0),
        lon_range=(109.5, 117.5),
        keywords=["南海", "南海诸岛", "South China Sea", "九段线", "十段线"],
        description="南海诸岛，通常在地图右下角附图显示",
    ),
    RequiredRegion(
        name="钓鱼岛",
        lat_range=(25.7, 26.0),
        lon_range=(123.0, 124.5),
        keywords=["钓鱼岛", "釣魚島", "Diaoyu"],
        description="钓鱼岛及其附属岛屿",
    ),
    RequiredRegion(
        name="藏南地区",
        lat_range=(26.5, 29.5),
        lon_range=(92.0, 97.0),
        keywords=["藏南", "阿鲁纳恰尔", "Arunachal"],
        description="藏南地区，中国固有领土",
    ),
    RequiredRegion(
        name="阿克赛钦",
        lat_range=(34.5, 37.5),
        lon_range=(76.5, 80.0),
        keywords=["阿克赛钦", "Aksai Chin"],
        description="阿克赛钦地区",
    ),
]

MAP_AUDIT_PROMPT = """你是一个地图合规性审核专家。请仔细检查这张地图图片，回答以下问题：

1. 这张图片是否是地图？（如果不是地图，直接输出is_map: false）
2. 如果是地图，展示的是哪个国家/地区？
3. 如果是中国地图，请逐一检查以下区域是否在地图中正确标注：
   - 台湾（必须显示，不能缺失）
   - 南海诸岛（必须显示，通常在右下角附图）
   - 钓鱼岛
   - 藏南地区
   - 阿克赛钦
4. 地图中是否有任何区域被异常空白、模糊处理或故意省略？
5. 地图的边界线是否正确（特别是国界线）？

请严格以JSON格式输出：
{
    "is_map": true/false,
    "country": "国家名",
    "map_type": "中国地图/世界地图/其他/非地图",
    "missing_regions": ["缺失的区域名"],
    "has_boundary_issue": true/false,
    "boundary_description": "边界问题描述",
    "has_blank_area": true/false,
    "blank_description": "空白区域描述",
    "risk_level": "safe/medium/critical",
    "confidence": 0.0-1.0,
    "description": "详细审核描述"
}"""


class MapCompletenessAuditor:
    """地图完整性审核器——检测地图中是否缺失特定区域"""

    def __init__(self, config: dict | None = None, vlm_client=None):
        self.config = config or {}
        self.vlm_client = vlm_client
        self.required_regions = CHINA_REQUIRED_REGIONS

    async def audit_frame(self, frame_path: str, timestamp: float = 0.0) -> MapAuditResult:
        """审核单帧的地图完整性

        Args:
            frame_path: 帧图片路径
            timestamp: 时间戳

        Returns:
            MapAuditResult
        """
        if not os.path.exists(frame_path):
            return MapAuditResult(
                frame_path=frame_path,
                timestamp=timestamp,
                risk_level="safe",
                description=f"帧图片不存在: {frame_path}",
            )

        vlm_result = await self._vlm_audit_map(frame_path)

        if not vlm_result:
            return MapAuditResult(
                frame_path=frame_path,
                timestamp=timestamp,
                risk_level="safe",
                confidence=0.0,
                description="VLM审核失败",
            )

        is_map = vlm_result.get("is_map", False)
        if not is_map:
            return MapAuditResult(
                frame_path=frame_path,
                timestamp=timestamp,
                is_map=False,
                is_complete=True,
                risk_level="safe",
                confidence=vlm_result.get("confidence", 0.5),
                description="该帧不是地图",
            )

        missing_regions = vlm_result.get("missing_regions", [])
        has_boundary_issue = vlm_result.get("has_boundary_issue", False)
        risk_level = vlm_result.get("risk_level", "safe")
        confidence = vlm_result.get("confidence", 0.5)

        ocr_texts = await self._ocr_map_texts(frame_path)
        keyword_missing = self._check_keywords(ocr_texts)

        all_missing = list(set(missing_regions + keyword_missing))

        if all_missing and risk_level == "safe":
            risk_level = "critical"

        if has_boundary_issue and risk_level != "critical":
            risk_level = "medium"

        return MapAuditResult(
            frame_path=frame_path,
            timestamp=timestamp,
            is_map=True,
            country=vlm_result.get("country", ""),
            is_complete=len(all_missing) == 0 and not has_boundary_issue,
            missing_regions=all_missing,
            has_boundary_issue=has_boundary_issue,
            risk_level=risk_level,
            confidence=confidence,
            description=vlm_result.get("description", ""),
            ocr_texts=ocr_texts,
        )

    async def audit_video_frames(self, frame_paths: list[str], timestamps: list[float] = None) -> VideoMapAuditResult:
        """审核视频多帧的地图完整性

        Args:
            frame_paths: 帧图片路径列表
            timestamps: 对应时间戳列表

        Returns:
            VideoMapAuditResult
        """
        if timestamps is None:
            timestamps = [0.0] * len(frame_paths)

        audit_results = []
        map_frames_found = 0
        has_map_risk = False
        max_risk_level = "safe"

        risk_order = {"safe": 0, "medium": 1, "high": 2, "critical": 3}

        for frame_path, timestamp in zip(frame_paths, timestamps):
            result = await self.audit_frame(frame_path, timestamp)
            audit_results.append(result)

            if result.is_map:
                map_frames_found += 1

            if result.risk_level != "safe":
                has_map_risk = True
                if risk_order.get(result.risk_level, 0) > risk_order.get(max_risk_level, 0):
                    max_risk_level = result.risk_level

        return VideoMapAuditResult(
            map_frames_found=map_frames_found,
            audit_results=audit_results,
            has_map_risk=has_map_risk,
            max_risk_level=max_risk_level,
        )

    async def _vlm_audit_map(self, frame_path: str) -> Optional[dict]:
        """使用VLM审核地图完整性"""
        try:
            from backend.services.llm_client import call_vlm, parse_llm_json

            with open(frame_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            response = await call_vlm(
                prompt=MAP_AUDIT_PROMPT,
                image_base64=img_data,
                task_type="map_audit",
            )

            result = parse_llm_json(response)
            if result:
                return result

            return {"is_map": False, "confidence": 0.0}

        except Exception as e:
            logger.warning("VLM地图审核失败: %s", e)
            return None

    async def _ocr_map_texts(self, frame_path: str) -> list[str]:
        """OCR提取地图上的文字标注"""
        try:
            from backend.services.frame_ocr import FrameOCR

            ocr = FrameOCR()
            result = await ocr.extract_text(frame_path)
            if result.error:
                return []
            return [item.text for item in result.items]
        except Exception as e:
            logger.debug("地图OCR失败: %s", e)
            return []

    def _check_keywords(self, ocr_texts: list[str]) -> list[str]:
        """检查OCR文字中是否包含必须区域的关键词"""
        missing = []
        all_text = " ".join(ocr_texts).lower()

        for region in self.required_regions:
            found = False
            for keyword in region.keywords:
                if keyword.lower() in all_text:
                    found = True
                    break
            if not found:
                missing.append(region.name)

        return missing

    def get_status(self) -> dict:
        """获取审核器可用状态"""
        return {
            "available": True,
            "required_regions": [r.name for r in self.required_regions],
            "vlm_required": True,
        }
