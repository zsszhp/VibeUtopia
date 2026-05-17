from __future__ import annotations

"""OCR文字识别模块

从视频关键帧中识别字幕、水印、贴图文字。
支持API优先策略：Qwen3-VL-Plus / GLM-OCR → 本地PaddleOCR-VL降级 → 跳过。
按设计文档(12_多模态风控设计)移除PaddlePaddle框架依赖。
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OCRItem:
    """单个OCR识别结果"""
    text: str                      # 识别文字
    confidence: float              # 置信度 0-1
    bbox: list = field(default_factory=list)  # 边界框
    position: str = ""             # 位置描述: top/center/bottom/left/right


@dataclass
class FrameOCRResult:
    """单帧OCR结果"""
    frame_path: str = ""
    frame_index: int = 0
    timestamp: float = 0.0
    items: list = field(default_factory=list)  # List[OCRItem]
    full_text: str = ""            # 合并后全文
    error: Optional[str] = None


@dataclass
class VideoOCRResult:
    """视频全部帧OCR结果"""
    video_path: str = ""
    total_frames: int = 0
    frame_results: list = field(default_factory=list)  # List[FrameOCRResult]
    all_text: str = ""             # 所有帧合并文字（去重）
    engine_used: str = ""          # 实际使用的OCR引擎
    error: Optional[str] = None


DEFAULT_CONFIG = {
    "min_confidence": 0.5,               # 最低置信度阈值
    "dedup_text": True,                   # 帧间文字去重
    "dedup_similarity": 0.85,             # 去重相似度阈值
}


class FrameOCR:
    """帧OCR识别器 — API优先，本地降级"""

    def __init__(self, config: dict | None = None, llm_client=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        # llm_client 参数保留以兼容旧调用方式，但不再使用
        # OCR 现在通过模块级 call_vlm() 函数调用视觉模型

    async def extract_text(self, frame_path: str, frame_index: int = 0,
                           timestamp: float = 0.0) -> FrameOCRResult:
        """从单帧图片提取文字

        Args:
            frame_path: 帧图片路径
            frame_index: 帧序号
            timestamp: 时间戳

        Returns:
            FrameOCRResult
        """
        if not os.path.exists(frame_path):
            return FrameOCRResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                error=f"帧图片不存在: {frame_path}"
            )

        items = []
        engine_used = ""

        # 优先使用API OCR (通过 call_vlm 调用视觉模型)
        try:
            from backend.services.llm_client import registry as _llm_registry
            has_vision = len(_llm_registry.get_vision_endpoints()) > 0
        except Exception:
            has_vision = False

        if has_vision:
            try:
                result = await self._api_ocr(frame_path)
                if result:
                    items = result
                    engine_used = "api_ocr"
            except Exception as e:
                logger.warning("API OCR识别失败: %s，将跳过OCR", e)
        else:
            logger.info("无可用视觉模型，跳过OCR")

        if not items and not engine_used:
            return FrameOCRResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                error="无可用OCR引擎（需要配置LLM API Key，或安装本地OCR模型）"
            )

        # 过滤低置信度
        min_conf = self.config["min_confidence"]
        items = [item for item in items if item.confidence >= min_conf]

        # 合并全文
        full_text = " ".join(item.text for item in items)

        return FrameOCRResult(
            frame_path=frame_path,
            frame_index=frame_index,
            timestamp=timestamp,
            items=items,
            full_text=full_text,
        )

    async def _api_ocr(self, frame_path: str) -> Optional[list[OCRItem]]:
        """使用多模态API进行OCR识别"""
        from backend.services.llm_client import call_vlm

        # 将图片编码为base64
        with open(frame_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "请识别图片中的所有文字，包括字幕、水印、贴图文字、背景文字等。"
            "按从上到下、从左到右的顺序列出。"
            "对每段文字标注：1.文字内容 2.大致位置(顶部/中部/底部/左侧/右侧) 3.文字类型(字幕/水印/贴图/背景文字)\n"
            "输出JSON格式：{\"texts\": [{\"text\": \"...\", \"position\": \"...\", \"type\": \"...\"}]}"
        )

        try:
            response = await call_vlm(
                prompt=prompt,
                image_base64=img_data,
                task_type="ocr",
            )

            import json
            result = json.loads(response)
            items = []
            for t in result.get("texts", []):
                items.append(OCRItem(
                    text=t.get("text", ""),
                    confidence=0.85,  # API OCR默认置信度
                    position=t.get("position", "center"),
                ))
            return items
        except Exception as e:
            logger.warning("API OCR调用失败: %s", e)
            return None

    async def extract_video_text(self, frame_results: list) -> VideoOCRResult:
        """从视频的所有关键帧提取文字

        Args:
            frame_results: KeyFrameResult.frames 列表

        Returns:
            VideoOCRResult
        """
        from backend.services.keyframe_extractor import KeyFrame

        video_result = VideoOCRResult(total_frames=len(frame_results))
        all_texts = []
        seen_texts = set()

        for frame in frame_results:
            if not isinstance(frame, KeyFrame):
                continue

            result = await self.extract_text(
                frame.file_path,
                frame.index,
                frame.timestamp,
            )

            if result.error:
                continue

            video_result.frame_results.append(result)

            # 去重合并
            if self.config["dedup_text"] and result.full_text:
                text_key = result.full_text.strip()
                if text_key and text_key not in seen_texts:
                    seen_texts.add(text_key)
                    all_texts.append(result.full_text)
            elif result.full_text:
                all_texts.append(result.full_text)

        video_result.all_text = "\n".join(all_texts)
        video_result.engine_used = "api_ocr"

        return video_result

    @staticmethod
    def _infer_position(bbox: list) -> str:
        """根据边界框推断文字位置"""
        if not bbox or len(bbox) < 4:
            return "unknown"

        y_coords = [point[1] for point in bbox]
        x_coords = [point[0] for point in bbox]
        y_center = sum(y_coords) / len(y_coords)
        x_center = sum(x_coords) / len(x_coords)

        positions = []
        if y_center < 100:
            positions.append("top")
        elif y_center > 300:
            positions.append("bottom")
        else:
            positions.append("center")

        if x_center < 150:
            positions.append("left")
        elif x_center > 500:
            positions.append("right")

        return "-".join(positions) if positions else "center"


def get_ocr_status() -> dict:
    """获取OCR引擎可用状态"""
    return {
        "api_ocr": True,  # API OCR始终可用（需配置API Key）
        "recommended": "api_ocr",
    }
