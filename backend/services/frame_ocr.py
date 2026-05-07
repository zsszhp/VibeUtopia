"""OCR文字识别模块 - V2.R4

从视频关键帧中识别字幕、水印、贴图文字。
支持多级降级策略：PaddleOCR → EasyOCR → 跳过。
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 检测可用OCR引擎
_HAS_PADDLEOCR = False
_HAS_EASYOCR = False

try:
    from paddleocr import PaddleOCR
    _HAS_PADDLEOCR = True
except ImportError:
    pass

try:
    import easyocr
    _HAS_EASYOCR = True
except ImportError:
    pass


@dataclass
class OCRItem:
    """单个OCR识别结果"""
    text: str                      # 识别文字
    confidence: float              # 置信度 0-1
    bbox: list = field(default_factory=list)  # 边界框 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
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


# ─── 默认配置 ────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "ocr_languages": ["ch_sim", "en"],   # OCR语言（PaddleOCR）
    "easyocr_languages": ["ch_sim", "en"],  # EasyOCR语言
    "min_confidence": 0.5,               # 最低置信度阈值
    "dedup_text": True,                   # 帧间文字去重
    "dedup_similarity": 0.85,             # 去重相似度阈值
}


class FrameOCR:
    """帧OCR识别器"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._paddle_engine = None
        self._easyocr_engine = None

    def _get_paddle_engine(self):
        """懒加载PaddleOCR引擎"""
        if self._paddle_engine is None and _HAS_PADDLEOCR:
            try:
                self._paddle_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    show_log=False,
                    use_gpu=False,
                )
            except Exception as e:
                logger.warning("PaddleOCR初始化失败: %s", e)
                self._paddle_engine = None
        return self._paddle_engine

    def _get_easyocr_engine(self):
        """懒加载EasyOCR引擎"""
        if self._easyocr_engine is None and _HAS_EASYOCR:
            try:
                self._easyocr_engine = easyocr.Reader(
                    self.config["easyocr_languages"],
                    gpu=False,
                )
            except Exception as e:
                logger.warning("EasyOCR初始化失败: %s", e)
                self._easyocr_engine = None
        return self._easyocr_engine

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

        loop = asyncio.get_event_loop()
        items = []
        engine_used = ""

        # 优先PaddleOCR
        engine = self._get_paddle_engine()
        if engine is not None:
            try:
                result = await loop.run_in_executor(
                    None,
                    self._paddle_ocr_sync,
                    engine,
                    frame_path,
                )
                if result is not None:
                    items = result
                    engine_used = "paddleocr"
            except Exception as e:
                logger.warning("PaddleOCR识别失败: %s", e)

        # 降级EasyOCR
        if not items:
            engine = self._get_easyocr_engine()
            if engine is not None:
                try:
                    result = await loop.run_in_executor(
                        None,
                        self._easyocr_ocr_sync,
                        engine,
                        frame_path,
                    )
                    if result is not None:
                        items = result
                        engine_used = "easyocr"
                except Exception as e:
                    logger.warning("EasyOCR识别失败: %s", e)

        if not items and not engine_used:
            return FrameOCRResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                error="无可用OCR引擎（需要paddleocr或easyocr）"
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
        video_result.engine_used = (
            "paddleocr" if _HAS_PADDLEOCR else
            "easyocr" if _HAS_EASYOCR else
            "none"
        )

        return video_result

    def _paddle_ocr_sync(self, engine, frame_path: str) -> Optional[list[OCRItem]]:
        """同步PaddleOCR识别"""
        result = engine.ocr(frame_path, cls=True)
        if not result or not result[0]:
            return []

        items = []
        for line in result[0]:
            bbox = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = line[1][0]
            confidence = line[1][1]

            position = self._infer_position(bbox)

            items.append(OCRItem(
                text=text,
                confidence=confidence,
                bbox=bbox,
                position=position,
            ))

        return items

    def _easyocr_ocr_sync(self, engine, frame_path: str) -> Optional[list[OCRItem]]:
        """同步EasyOCR识别"""
        results = engine.readtext(frame_path)
        if not results:
            return []

        items = []
        for detection in results:
            bbox = detection[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = detection[1]
            confidence = detection[2]

            position = self._infer_position(bbox)

            items.append(OCRItem(
                text=text,
                confidence=confidence,
                bbox=bbox,
                position=position,
            ))

        return items

    @staticmethod
    def _infer_position(bbox: list) -> str:
        """根据边界框推断文字位置"""
        if not bbox or len(bbox) < 4:
            return "unknown"

        # 计算中心y坐标
        y_coords = [point[1] for point in bbox]
        x_coords = [point[0] for point in bbox]
        y_center = sum(y_coords) / len(y_coords)
        x_center = sum(x_coords) / len(x_coords)

        # 需要知道图片尺寸来判断，这里用相对位置
        y_range = max(y_coords) - min(y_coords)
        x_range = max(x_coords) - min(x_coords)

        # 简单启发式：y坐标越小越靠上
        # 这里只做粗略判断，实际需要图片高度
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
        "paddleocr": _HAS_PADDLEOCR,
        "easyocr": _HAS_EASYOCR,
        "recommended": (
            "paddleocr" if _HAS_PADDLEOCR else
            "easyocr" if _HAS_EASYOCR else
            "none"
        ),
    }
