from __future__ import annotations

"""时序异常检测器 - V3.4 细粒度视频理解

检测视频中短暂出现的异常画面（闪过的争议图片、瞬间切换的不当内容等）。
使用帧级差异分析定位异常区间，再对异常区间进行VLM审核。
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TemporalAnomaly:
    """时序异常"""
    start_time: float
    end_time: float
    duration: float
    anomaly_type: str = ""
    description: str = ""
    confidence: float = 0.0
    risk_level: str = "safe"
    frame_path: str = ""


@dataclass
class TemporalAnomalyResult:
    """时序异常检测结果"""
    video_path: str = ""
    anomalies: list = field(default_factory=list)
    has_anomaly: bool = False
    max_risk_level: str = "safe"
    error: Optional[str] = None


ANOMALY_REVIEW_PROMPT = """你是一个视频内容安全审核专家。请仔细检查这帧视频画面，判断是否存在以下异常：

1. 突然出现的不当内容（色情/暴力/恐怖画面）
2. 短暂闪过的争议性图片或符号
3. 与视频前后内容明显不相关的异常画面
4. 被故意插入的隐藏帧或闪帧

请严格以JSON格式输出：
{
    "has_anomaly": true/false,
    "anomaly_type": "不当内容/争议图片/异常画面/隐藏帧/无",
    "description": "异常描述",
    "risk_level": "safe/medium/high/critical",
    "confidence": 0.0-1.0
}"""


class TemporalAnomalyDetector:
    """时序异常检测器——定位视频中的短暂异常画面"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def detect_from_scan(
        self,
        dense_scan_result,
    ) -> TemporalAnomalyResult:
        """从密集帧扫描结果中检测时序异常

        Args:
            dense_scan_result: DenseScanResult

        Returns:
            TemporalAnomalyResult
        """
        if dense_scan_result is None or dense_scan_result.error:
            return TemporalAnomalyResult(
                error=dense_scan_result.error if dense_scan_result else "无扫描结果",
            )

        all_frames = dense_scan_result.all_frames
        if len(all_frames) < 3:
            return TemporalAnomalyResult(
                video_path=dense_scan_result.video_path,
            )

        anomaly_segments = self._cluster_anomaly_frames(all_frames)

        anomalies = []
        for segment_frames in anomaly_segments:
            if not segment_frames:
                continue

            start_time = segment_frames[0].timestamp
            end_time = segment_frames[-1].timestamp
            duration = end_time - start_time

            peak_frame = max(segment_frames, key=lambda f: f.anomaly_score)

            vlm_result = await self._vlm_review_frame(peak_frame.image_path)

            if vlm_result and vlm_result.get("has_anomaly", False):
                anomalies.append(TemporalAnomaly(
                    start_time=start_time,
                    end_time=end_time,
                    duration=round(duration, 2),
                    anomaly_type=vlm_result.get("anomaly_type", "unknown"),
                    description=vlm_result.get("description", ""),
                    confidence=vlm_result.get("confidence", 0.5),
                    risk_level=vlm_result.get("risk_level", "medium"),
                    frame_path=peak_frame.image_path,
                ))

        has_anomaly = len(anomalies) > 0
        risk_order = {"safe": 0, "medium": 1, "high": 2, "critical": 3}
        max_risk = "safe"
        for a in anomalies:
            if risk_order.get(a.risk_level, 0) > risk_order.get(max_risk, 0):
                max_risk = a.risk_level

        return TemporalAnomalyResult(
            video_path=dense_scan_result.video_path,
            anomalies=anomalies,
            has_anomaly=has_anomaly,
            max_risk_level=max_risk,
        )

    def _cluster_anomaly_frames(self, frames, threshold: float = 0.5, gap_seconds: float = 2.0) -> list:
        """聚类异常帧为连续区间"""
        anomaly_frames = [f for f in frames if f.anomaly_score >= threshold]

        if not anomaly_frames:
            return []

        segments = []
        current_segment = [anomaly_frames[0]]

        for i in range(1, len(anomaly_frames)):
            time_gap = anomaly_frames[i].timestamp - anomaly_frames[i - 1].timestamp
            if time_gap <= gap_seconds:
                current_segment.append(anomaly_frames[i])
            else:
                segments.append(current_segment)
                current_segment = [anomaly_frames[i]]

        segments.append(current_segment)
        return segments

    async def _vlm_review_frame(self, frame_path: str) -> Optional[dict]:
        """使用VLM审核异常帧"""
        if not os.path.exists(frame_path):
            return None

        try:
            from backend.services.llm_client import call_vlm, parse_llm_json

            with open(frame_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            response = await call_vlm(
                prompt=ANOMALY_REVIEW_PROMPT,
                image_base64=img_data,
                task_type="temporal_anomaly",
            )

            result = parse_llm_json(response)
            if result:
                return result

            return {"has_anomaly": False}
        except Exception as e:
            logger.warning("VLM异常帧审核失败: %s", e)
            return None

    def get_status(self) -> dict:
        """获取检测器可用状态"""
        return {
            "available": True,
            "vlm_required": True,
        }
