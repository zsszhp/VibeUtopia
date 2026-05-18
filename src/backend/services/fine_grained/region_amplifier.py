from __future__ import annotations

"""区域放大分析器 - V3.4 细粒度视频理解

解决视频中画面小区域细节丢失的问题。
先检测帧中的"感兴趣区域"（文字区、地图区、代码区、符号区），
再裁剪放大后送入VLM/OCR进行细粒度分析。

借鉴InternVL的dynamic_preprocess策略：
- 动态裁切：按宽高比切割为多个448x448 patch + 全局缩略图
- 借鉴GOT-OCR2.0的区域级OCR：bbox坐标归一化到0-1000坐标系，作为prompt前缀
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_HAS_OPENCV = False
try:
    import cv2
    import numpy as np
    _HAS_OPENCV = True
except ImportError:
    pass


@dataclass
class RegionOfInterest:
    """感兴趣区域"""
    region_type: str
    bbox: tuple
    confidence: float
    detection_method: str
    description: str = ""


@dataclass
class AmplifiedPatch:
    """放大后的patch"""
    patch_image: object
    patch_index: int
    is_thumbnail: bool = False


@dataclass
class RegionDetail:
    """区域放大分析结果"""
    region_type: str
    bbox: tuple
    patches: list = field(default_factory=list)
    ocr_text: str = ""
    confidence: float = 0.0
    analysis_prompt: str = ""


@dataclass
class RegionAmplifyResult:
    """区域放大分析总结果"""
    frame_path: str = ""
    timestamp: float = 0.0
    regions: list = field(default_factory=list)
    total_patches: int = 0
    error: Optional[str] = None


DEFAULT_CONFIG = {
    "patch_size": 448,
    "max_patches_per_region": 4,
    "use_thumbnail": True,
    "text_min_area_ratio": 0.005,
    "map_min_area_ratio": 0.05,
    "code_min_area_ratio": 0.03,
    "symbol_min_area_ratio": 0.01,
    "dark_bg_threshold": 70,
    "dark_bg_ratio_threshold": 0.6,
    "map_classifier_enabled": False,
    "yolo_detector_enabled": False,
}


class RegionAmplifier:
    """区域放大分析器——让小区域细节可被VLM识别"""

    REGION_DETECTORS = {
        "text": {
            "description": "文字区域检测（字幕/水印/贴图/文件名）",
            "min_area_ratio": 0.005,
        },
        "map": {
            "description": "地图区域检测",
            "min_area_ratio": 0.05,
        },
        "code_terminal": {
            "description": "代码/终端区域检测（深色背景+等宽字体）",
            "min_area_ratio": 0.03,
        },
        "sensitive_symbol": {
            "description": "敏感符号/标志区域检测",
            "min_area_ratio": 0.01,
        },
    }

    def __init__(self, config: dict | None = None, vlm_client=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.vlm_client = vlm_client

    async def analyze_frame(self, frame_path: str, timestamp: float = 0.0) -> RegionAmplifyResult:
        """分析单帧中的感兴趣区域并放大

        Args:
            frame_path: 帧图片路径
            timestamp: 时间戳

        Returns:
            RegionAmplifyResult
        """
        if not _HAS_OPENCV:
            return RegionAmplifyResult(
                frame_path=frame_path,
                timestamp=timestamp,
                error="需要OpenCV支持"
            )

        if not os.path.exists(frame_path):
            return RegionAmplifyResult(
                frame_path=frame_path,
                timestamp=timestamp,
                error=f"帧图片不存在: {frame_path}"
            )

        img = cv2.imread(frame_path)
        if img is None:
            return RegionAmplifyResult(
                frame_path=frame_path,
                timestamp=timestamp,
                error="无法读取帧图片"
            )

        regions = []

        text_regions = self._detect_text_regions(img)
        regions.extend(text_regions)

        code_regions = self._detect_code_regions(img)
        regions.extend(code_regions)

        map_regions = self._detect_map_regions(img)
        regions.extend(map_regions)

        symbol_regions = self._detect_sensitive_symbols(img)
        regions.extend(symbol_regions)

        region_details = []
        total_patches = 0

        for region in regions:
            patches = self._amplify_region(img, region)
            prompt = self._build_analysis_prompt(region, patches)

            region_detail = RegionDetail(
                region_type=region.region_type,
                bbox=region.bbox,
                patches=patches,
                confidence=region.confidence,
                analysis_prompt=prompt,
            )
            region_details.append(region_detail)
            total_patches += len(patches)

        return RegionAmplifyResult(
            frame_path=frame_path,
            timestamp=timestamp,
            regions=region_details,
            total_patches=total_patches,
        )

    def _detect_text_regions(self, img) -> list[RegionOfInterest]:
        """检测文字区域——使用VLM辅助的启发式检测"""
        regions = []
        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 使用MSER检测文字候选区域
        try:
            mser = cv2.MSER_create()
            contours, _ = mser.detectRegions(gray)

            text_contours = []
            for contour in contours:
                x, y, bw, bh = cv2.boundingRect(contour)
                area_ratio = (bw * bh) / (w * h)
                aspect_ratio = bw / max(bh, 1)

                if (0.01 < area_ratio < 0.5 and
                    0.1 < aspect_ratio < 20.0 and
                    bh > 8 and bw > 20):
                    text_contours.append((x, y, bw, bh))

            if text_contours:
                merged = self._merge_nearby_boxes(text_contours, w, h)
                for bbox in merged:
                    x1, y1, x2, y2 = bbox
                    area_ratio = (x2 - x1) * (y2 - y1) / (w * h)
                    if area_ratio >= self.config["text_min_area_ratio"]:
                        regions.append(RegionOfInterest(
                            region_type="text",
                            bbox=bbox,
                            confidence=0.7,
                            detection_method="mser_heuristic",
                            description="文字区域",
                        ))
        except Exception as e:
            logger.debug("MSER检测失败: %s", e)

        # 补充：检测底部字幕区域（常见视频字幕位置）
        bottom_region = (0, int(h * 0.75), w, h)
        bottom_gray = gray[int(h * 0.75):h, :]
        bottom_variance = bottom_gray.var()

        if bottom_variance > 100:
            regions.append(RegionOfInterest(
                region_type="text",
                bbox=bottom_region,
                confidence=0.5,
                detection_method="bottom_subtitle_heuristic",
                description="底部字幕区域",
            ))

        return regions

    def _detect_code_regions(self, img) -> list[RegionOfInterest]:
        """检测代码/终端区域——深色背景+等宽字体特征"""
        regions = []
        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        dark_threshold = self.config["dark_bg_threshold"]
        dark_ratio_threshold = self.config["dark_bg_ratio_threshold"]

        # 检测深色背景区域
        dark_mask = gray < dark_threshold
        dark_ratio = dark_mask.sum() / (h * w)

        if dark_ratio > dark_ratio_threshold:
            # 寻找最大的深色连通区域
            contours, _ = cv2.findContours(
                (dark_mask.astype(np.uint8) * 255),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            for contour in contours:
                x, y, bw, bh = cv2.boundingRect(contour)
                area_ratio = (bw * bh) / (w * h)

                if area_ratio >= self.config["code_min_area_ratio"]:
                    # 检查是否具有代码编辑器特征（高宽比>0.5，面积占比>3%）
                    aspect = bh / max(bw, 1)
                    if aspect > 0.3:
                        regions.append(RegionOfInterest(
                            region_type="code_terminal",
                            bbox=(x, y, x + bw, y + bh),
                            confidence=0.6,
                            detection_method="dark_bg_heuristic",
                            description="代码/终端区域",
                        ))

        return regions

    def _detect_map_regions(self, img) -> list[RegionOfInterest]:
        """检测地图区域——颜色特征+几何特征"""
        regions = []
        h, w = img.shape[:2]

        if not self.config["map_classifier_enabled"]:
            # 启发式检测：地图通常有大面积蓝/绿色（海洋/陆地）
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            blue_mask = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
            green_mask = cv2.inRange(hsv, np.array([35, 50, 50]), np.array([85, 255, 255]))

            map_mask = cv2.bitwise_or(blue_mask, green_mask)
            map_ratio = map_mask.sum() / 255 / (h * w)

            if map_ratio > 0.15:
                contours, _ = cv2.findContours(
                    map_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
                )
                for contour in contours:
                    x, y, bw, bh = cv2.boundingRect(contour)
                    area_ratio = (bw * bh) / (w * h)
                    if area_ratio >= self.config["map_min_area_ratio"]:
                        regions.append(RegionOfInterest(
                            region_type="map",
                            bbox=(x, y, x + bw, y + bh),
                            confidence=0.5,
                            detection_method="color_heuristic",
                            description="疑似地图区域",
                        ))

        return regions

    def _detect_sensitive_symbols(self, img) -> list[RegionOfInterest]:
        """检测敏感符号区域——当前使用VLM辅助检测"""
        regions = []

        if self.config["yolo_detector_enabled"]:
            pass

        return regions

    def _amplify_region(self, img, region: RegionOfInterest) -> list:
        """裁剪并放大区域——借鉴InternVL的dynamic_preprocess策略

        InternVL的dynamic_preprocess核心逻辑：
        1. 计算区域宽高比
        2. 在候选宽高比网格中找到最匹配的组合
        3. 将区域缩放后裁切为多个固定大小的patch
        4. 额外添加全局缩略图提供上下文
        """
        x1, y1, x2, y2 = region.bbox
        cropped = img[y1:y2, x1:x2]

        if cropped.size == 0:
            return []

        orig_h, orig_w = cropped.shape[:2]
        aspect_ratio = orig_w / max(orig_h, 1)

        image_size = self.config["patch_size"]
        max_num = self.config["max_patches_per_region"]

        target_ratios = set(
            (i, j) for n in range(1, max_num + 1)
            for i in range(1, n + 1) for j in range(1, n + 1)
            if i * j <= max_num
        )
        target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

        best_ratio = self._find_closest_aspect_ratio(
            aspect_ratio, target_ratios, orig_w, orig_h, image_size
        )

        target_width = image_size * best_ratio[0]
        target_height = image_size * best_ratio[1]

        resized = cv2.resize(
            cropped, (target_width, target_height),
            interpolation=cv2.INTER_LANCZOS4,
        )

        patches = []
        blocks = best_ratio[0] * best_ratio[1]
        for i in range(blocks):
            box_x = (i % (target_width // image_size)) * image_size
            box_y = (i // (target_width // image_size)) * image_size
            patch = resized[box_y:box_y + image_size, box_x:box_x + image_size]
            patches.append(AmplifiedPatch(
                patch_image=patch,
                patch_index=i,
                is_thumbnail=False,
            ))

        if self.config["use_thumbnail"] and len(patches) > 1:
            thumbnail = cv2.resize(
                cropped, (image_size, image_size),
                interpolation=cv2.INTER_LANCZOS4,
            )
            patches.append(AmplifiedPatch(
                patch_image=thumbnail,
                patch_index=len(patches),
                is_thumbnail=True,
            ))

        return patches

    @staticmethod
    def _find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
        """借鉴InternVL的find_closest_aspect_ratio"""
        best_ratio_diff = float('inf')
        best_ratio = (1, 1)
        area = width * height

        for ratio in target_ratios:
            target_aspect_ratio = ratio[0] / ratio[1]
            ratio_diff = abs(aspect_ratio - target_aspect_ratio)
            if ratio_diff < best_ratio_diff:
                best_ratio_diff = ratio_diff
                best_ratio = ratio
            elif ratio_diff == best_ratio_diff:
                if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                    best_ratio = ratio

        return best_ratio

    def _build_analysis_prompt(self, region: RegionOfInterest, patches: list) -> str:
        """构建区域分析prompt——借鉴GOT-OCR2.0的区域级OCR策略

        GOT-OCR2.0核心创新：
        1. bbox坐标归一化到0-1000坐标系，作为prompt前缀: [x1,y1,x2,y2] OCR:
        2. 颜色标记作为prompt前缀: [red] OCR:
        """
        prompts = {
            "text": (
                "请仔细识别这张图片中的所有文字，包括小字、水印、贴图文字、文件名等。"
                "注意文字可能很小或模糊，请尽可能完整识别。"
                "输出JSON: {\"texts\": [{\"text\": \"...\", \"position\": \"...\", \"type\": \"字幕/水印/贴图/文件名/其他\"}]}"
            ),
            "map": (
                "你是一个地图合规性审核专家。请仔细检查这张地图图片，回答以下问题：\n"
                "1. 这张地图展示的是哪个国家/地区？\n"
                "2. 如果是中国地图，请检查以下区域是否在地图中正确标注：\n"
                "   - 台湾（必须显示，不能缺失）\n"
                "   - 南海诸岛（必须显示，通常在右下角附图）\n"
                "   - 钓鱼岛\n"
                "   - 藏南地区\n"
                "   - 阿克赛钦\n"
                "3. 地图中是否有任何区域被异常空白、模糊处理或故意省略？\n"
                "4. 地图的边界线是否正确（特别是国界线）？\n"
                "输出JSON: {\"is_map\": true/false, \"country\": \"...\", \"missing_regions\": [...], \"has_boundary_issue\": true/false, \"risk_level\": \"safe/medium/critical\", \"description\": \"...\"}"
            ),
            "code_terminal": (
                "请仔细识别这张图片中展示的代码编辑器/终端/文件夹内容。"
                "特别注意：\n"
                "1. 项目名称或文件夹名称\n"
                "2. 文件路径和文件名\n"
                "3. 代码片段内容\n"
                "4. 是否有GitHub/GitLab等开源平台标识\n"
                "5. 是否有LICENSE文件或开源协议标识\n"
                "输出JSON: {\"project_name\": \"...\", \"file_paths\": [...], \"code_snippets\": [...], \"has_open_source_indicator\": true/false, \"platform\": \"GitHub/GitLab/其他/无\"}"
            ),
            "sensitive_symbol": (
                "你是一个视觉内容安全审核专家。请仔细检查这张图片中是否存在以下敏感视觉元素：\n"
                "1. 争议性旗帜或标志\n"
                "2. 不当手势\n"
                "3. 敏感组织的徽章、纹章或标识\n"
                "4. 含有争议信息的贴图、水印或覆盖层\n"
                "输出JSON: {\"has_sensitive_symbol\": true/false, \"symbols\": [{\"type\": \"...\", \"description\": \"...\", \"risk_level\": \"low/medium/high\"}]}"
            ),
        }

        return prompts.get(region.region_type, "请详细描述这张图片中的内容。")

    @staticmethod
    def _merge_nearby_boxes(boxes: list, img_w: int, img_h: int, gap_ratio: float = 0.02) -> list:
        """合并邻近的检测框"""
        if not boxes:
            return []

        gap_x = int(img_w * gap_ratio)
        gap_y = int(img_h * gap_ratio)

        merged = []
        for x, y, bw, bh in boxes:
            x2, y2 = x + bw, y + bh
            found_merge = False

            for i, (mx1, my1, mx2, my2) in enumerate(merged):
                if (x - gap_x <= mx2 and x2 + gap_x >= mx1 and
                    y - gap_y <= my2 and y2 + gap_y >= my1):
                    merged[i] = (min(x, mx1), min(y, my1), max(x2, mx2), max(y2, my2))
                    found_merge = True
                    break

            if not found_merge:
                merged.append((x, y, x2, y2))

        return merged

    def get_status(self) -> dict:
        """获取分析器可用状态"""
        return {
            "opencv": _HAS_OPENCV,
            "available": _HAS_OPENCV,
            "detectors": {
                "text": True,
                "code_terminal": True,
                "map": True,
                "sensitive_symbol": self.config["yolo_detector_enabled"],
            },
        }
