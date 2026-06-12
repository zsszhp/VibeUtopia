from __future__ import annotations

"""Delta Frame Extractor - 借鉴视频压缩 I帧/P帧 分类策略

从视频中提取变化帧，支持两种模式：
1. delta 模式：仅提取与前一参考帧有差异的帧（I帧 + P帧），跳过相似帧
2. full 模式：按采样率提取所有帧

帧分类：
- I-frame（关键帧）：首帧、场景切换、周期性强制插入
- P-frame（预测帧）：与参考帧差异超过阈值的帧
- skipped：与参考帧几乎相同的帧，仅记录时间戳不保存图片

差异检测三级流水线：
1. 感知哈希(pHash 16x16) 快速粗筛
2. SSIM 精确确认（哈希差异处于边界时）
3. 像素差异比例兜底
"""

import asyncio
import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 可选依赖检测 ─────────────────────────────────────────────
_HAS_SCENEDETECT = False
_HAS_FFMPEG = False
_HAS_OPENCV = False
_HAS_NUMPY = False

try:
    from scenedetect import open_video, SceneManager
    _HAS_SCENEDETECT = True
except ImportError:
    pass

try:
    import ffmpeg
    _HAS_FFMPEG = True
except ImportError:
    pass

try:
    import cv2
    _HAS_OPENCV = True
except ImportError:
    pass

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    pass


# ─── 数据类 ──────────────────────────────────────────────────

@dataclass
class DeltaFrame:
    """单个帧的分类结果"""
    frame_type: str           # "I" | "P" | "skipped"
    index: int                # 原始视频中的帧序号
    timestamp: float          # 时间戳（秒）
    file_path: str            # 帧图片路径（skipped 帧为空）
    delta_score: float        # 与前一参考帧的差异分数
    reference_frame: str      # 参考帧路径
    skip_count: int           # 此帧之前连续跳过的帧数
    image_hash: str           # 感知哈希


@dataclass
class DeltaFrameResult:
    """Delta Frame 提取结果"""
    video_path: str = ""
    total_video_frames: int = 0
    duration: float = 0.0
    extracted_frames: list = field(default_factory=list)   # List[DeltaFrame] - 实际提取的帧
    skipped_frames: list = field(default_factory=list)     # List[DeltaFrame] - 跳过的帧
    i_frames: list = field(default_factory=list)           # I帧列表
    p_frames: list = field(default_factory=list)           # P帧列表
    compression_ratio: float = 0.0                         # extracted / total_video_frames
    method_used: str = ""
    error: Optional[str] = None


# ─── 默认配置 ────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "mode": "delta",              # "delta" | "full"
    "delta_threshold": 0.05,      # 5% 像素变化阈值
    "i_frame_interval": 30.0,     # 强制 I帧间隔（秒）
    "scene_threshold": 27.0,      # PySceneDetect 阈值
    "min_scene_length": 15,       # 最短场景长度（帧数）
    "frame_width": 640,
    "frame_height": 360,
    "image_format": "jpg",
    "image_quality": 85,
    "max_frames": None,           # None = 不限制
    "ssim_threshold": 0.95,       # SSIM 高于此值 = 跳过（非常相似）
    "hash_threshold": 8,          # 汉明距离低于此值 = 相似
    "dense_fps": 1.0,             # full 模式采样率
}


class DeltaFrameExtractor:
    """Delta Frame 提取器

    借鉴视频压缩的 I帧/P帧 分类策略，仅提取与参考帧有差异的帧，
    跳过几乎相同的帧，从而大幅减少输出帧数。
    """

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def extract(self, video_path: str, output_dir: str | None = None) -> DeltaFrameResult:
        """从视频提取 Delta Frame

        Args:
            video_path: 本地视频文件路径
            output_dir: 帧图片输出目录（默认临时目录）

        Returns:
            DeltaFrameResult
        """
        if not os.path.exists(video_path):
            return DeltaFrameResult(
                video_path=video_path,
                error=f"视频文件不存在: {video_path}",
            )

        if not _HAS_OPENCV:
            return DeltaFrameResult(
                video_path=video_path,
                error="OpenCV 不可用，无法提取帧",
            )

        # 准备输出目录
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="vibe_delta_frames_")
        os.makedirs(output_dir, exist_ok=True)

        # 获取视频信息
        video_info = self._get_video_info(video_path)
        if video_info is None:
            return DeltaFrameResult(
                video_path=video_path,
                error="无法读取视频信息",
            )

        # 在线程池中执行同步提取
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._extract_sync,
            video_path,
            output_dir,
            video_info,
        )

        return result

    def _extract_sync(
        self,
        video_path: str,
        output_dir: str,
        video_info: dict,
    ) -> DeltaFrameResult:
        """同步执行帧提取与分类"""

        duration = video_info.get("duration", 0.0)
        total_frames = video_info.get("total_frames", 0)
        fps = video_info.get("fps", 25.0)

        result = DeltaFrameResult(
            video_path=video_path,
            total_video_frames=total_frames,
            duration=duration,
        )

        mode = self.config["mode"]

        # ── PySceneDetect 场景切换点（如果可用）──
        scene_change_indices: set[int] = set()
        method_used = "opencv"

        if _HAS_SCENEDETECT and mode == "delta":
            try:
                scene_change_indices = self._detect_scene_changes(video_path)
                if scene_change_indices:
                    method_used = "scenedetect+opencv"
                    logger.info(
                        "PySceneDetect 检测到 %d 个场景切换点",
                        len(scene_change_indices),
                    )
            except Exception as e:
                logger.warning("PySceneDetect 场景检测失败: %s", e)

        # ── 打开视频 ──
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result.error = "无法打开视频文件"
            return result

        # 采样间隔：delta 模式逐帧读取（由差异判断跳过），full 模式按 dense_fps 采样
        if mode == "full":
            dense_fps = self.config["dense_fps"]
            sample_interval = max(1, int(fps / dense_fps)) if fps > 0 else 1
        else:
            sample_interval = 1

        i_frame_interval_frames = int(fps * self.config["i_frame_interval"]) if fps > 0 else 750
        fmt = self.config["image_format"]
        quality = self.config["image_quality"]
        max_frames = self.config["max_frames"]

        # ── 状态变量 ──
        prev_gray: Optional[object] = None          # 前一参考帧灰度图
        prev_hash: str = ""                          # 前一参考帧哈希
        reference_frame_path: str = ""               # 当前参考帧图片路径
        consecutive_skips: int = 0                   # 连续跳过帧计数
        last_i_frame_index: int = -i_frame_interval_frames  # 上次 I帧位置

        extracted_frames: list[DeltaFrame] = []
        skipped_frames: list[DeltaFrame] = []
        i_frames: list[DeltaFrame] = []
        p_frames: list[DeltaFrame] = []

        frame_idx = 0
        extracted_count = 0

        while cap.isOpened():
            ret, img = cap.read()
            if not ret:
                break

            # full 模式下跳过非采样帧
            if mode == "full" and frame_idx % sample_interval != 0:
                frame_idx += 1
                continue

            timestamp = frame_idx / fps if fps > 0 else 0.0
            img_resized = self._resize_frame(img)

            # 转灰度
            if len(img_resized.shape) == 3:
                gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            else:
                gray = img_resized

            current_hash = self._compute_image_hash(gray)

            # ── 帧分类决策 ──
            frame_type = "P"
            delta_score = 0.0

            if frame_idx == 0:
                # 首帧 → I帧
                frame_type = "I"
                delta_score = 1.0
            elif frame_idx in scene_change_indices:
                # 场景切换 → I帧
                frame_type = "I"
                delta_score = 1.0
            elif (frame_idx - last_i_frame_index) >= i_frame_interval_frames:
                # 周期性 I帧
                frame_type = "I"
                delta_score = self._compute_frame_diff(gray, prev_gray) if prev_gray is not None else 1.0
            elif prev_gray is not None:
                # 差异检测三级流水线
                delta_score = self._classify_frame_diff(gray, prev_gray, current_hash, prev_hash)

                if delta_score < self.config["delta_threshold"]:
                    frame_type = "skipped"
            else:
                # 无参考帧时当作 I帧
                frame_type = "I"
                delta_score = 1.0

            # ── 处理帧 ──
            if frame_type == "skipped":
                skipped_frames.append(DeltaFrame(
                    frame_type="skipped",
                    index=frame_idx,
                    timestamp=round(timestamp, 2),
                    file_path="",
                    delta_score=delta_score,
                    reference_frame=reference_frame_path,
                    skip_count=0,
                    image_hash=current_hash,
                ))
                consecutive_skips += 1
            else:
                # 保存帧图片
                frame_filename = (
                    f"{frame_type}_{extracted_count:04d}_{timestamp:.1f}s.{fmt}"
                )
                frame_path = os.path.join(output_dir, frame_filename)
                cv2.imwrite(frame_path, img_resized, [cv2.IMWRITE_JPEG_QUALITY, quality])

                delta_frame = DeltaFrame(
                    frame_type=frame_type,
                    index=frame_idx,
                    timestamp=round(timestamp, 2),
                    file_path=frame_path,
                    delta_score=round(delta_score, 4),
                    reference_frame=reference_frame_path,
                    skip_count=consecutive_skips,
                    image_hash=current_hash,
                )

                extracted_frames.append(delta_frame)
                extracted_count += 1

                if frame_type == "I":
                    i_frames.append(delta_frame)
                    last_i_frame_index = frame_idx
                else:
                    p_frames.append(delta_frame)

                # 更新参考帧
                prev_gray = gray
                prev_hash = current_hash
                reference_frame_path = frame_path
                consecutive_skips = 0

                # 检查最大帧数限制
                if max_frames is not None and extracted_count >= max_frames:
                    logger.info("达到最大帧数限制: %d", max_frames)
                    break

            frame_idx += 1

        cap.release()

        # ── 更新跳过帧的 skip_count ──
        # 为每个跳过帧设置其前方连续跳过数（反向扫描更高效）
        _update_skip_counts(skipped_frames)

        # ── 填充结果 ──
        result.extracted_frames = extracted_frames
        result.skipped_frames = skipped_frames
        result.i_frames = i_frames
        result.p_frames = p_frames
        result.method_used = method_used if mode == "delta" else f"{method_used}:full"

        if total_frames > 0:
            result.compression_ratio = round(extracted_count / total_frames, 4)
        else:
            result.compression_ratio = 0.0

        logger.info(
            "Delta Frame 提取完成: I帧=%d, P帧=%d, 跳过=%d, 压缩比=%.2f%%",
            len(i_frames),
            len(p_frames),
            len(skipped_frames),
            result.compression_ratio * 100,
        )

        return result

    # ─── 差异检测 ────────────────────────────────────────────

    def _classify_frame_diff(
        self,
        current_gray,
        prev_gray,
        current_hash: str,
        prev_hash: str,
    ) -> float:
        """三级差异检测流水线

        1. 感知哈希快速粗筛 → 明显不同直接返回高分
        2. 哈希差异处于边界 → 用 SSIM 精确确认
        3. SSIM 也不确定 → 像素差异比例兜底

        Returns:
            归一化差异分数 [0.0, 1.0]
        """
        hash_threshold = self.config["hash_threshold"]

        # 第一级：感知哈希
        hamming = self._hamming_distance(current_hash, prev_hash)
        max_hash_bits = len(current_hash) * 4 if current_hash else 64  # 每个hex字符4位

        if max_hash_bits > 0:
            normalized_hash_diff = hamming / max_hash_bits
        else:
            normalized_hash_diff = 1.0

        # 哈希差异大 → 明显不同，直接返回
        if hamming > hash_threshold * 2:
            return normalized_hash_diff

        # 哈希差异小 → 可能相似，用 SSIM 确认
        ssim_val = self._compute_ssim(current_gray, prev_gray)
        ssim_threshold = self.config["ssim_threshold"]

        if ssim_val >= ssim_threshold:
            # SSIM 很高 → 非常相似，返回低分
            return 1.0 - ssim_val

        # SSIM 确认不相似 → 返回 SSIM 差异
        if ssim_val < 0:
            return 1.0

        return 1.0 - ssim_val

    def _compute_frame_diff(self, current_gray, prev_gray) -> float:
        """计算两帧之间的归一化像素差异比例

        Returns:
            差异比例 [0.0, 1.0]
        """
        if current_gray is None or prev_gray is None:
            return 1.0

        if current_gray.shape != prev_gray.shape:
            return 1.0

        if _HAS_NUMPY:
            diff = np.abs(current_gray.astype(np.float32) - prev_gray.astype(np.float32))
            # 像素差异超过 30 算作"显著不同"
            significant = np.count_nonzero(diff > 30)
            total = current_gray.size
            return float(significant) / float(total)
        else:
            # OpenCV fallback
            diff = cv2.absdiff(current_gray, prev_gray)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            significant = cv2.countNonZero(thresh)
            total = current_gray.size
            return float(significant) / float(total) if total > 0 else 0.0

    def _compute_ssim(self, img1, img2) -> float:
        """计算简化版 SSIM（不依赖 scikit-image）

        使用 numpy 实现均值、方差、协方差计算。
        如果 numpy 不可用，退回到像素差异。

        Returns:
            SSIM 值 [-1.0, 1.0]，1.0 表示完全相同
        """
        if img1 is None or img2 is None:
            return 0.0

        if img1.shape != img2.shape:
            return 0.0

        if not _HAS_NUMPY:
            # 退回到像素差异
            pixel_diff = self._compute_frame_diff(img1, img2)
            return 1.0 - pixel_diff

        # 转为 float32
        a = img1.astype(np.float64)
        b = img2.astype(np.float64)

        # SSIM 参数
        C1 = (0.01 * 255) ** 2  # 亮度稳定常数
        C2 = (0.03 * 255) ** 2  # 对比度稳定常数

        # 在整张图上计算统计量（相当于 window=size 的 SSIM）
        mu_a = a.mean()
        mu_b = b.mean()
        sigma_a_sq = a.var()
        sigma_b_sq = b.var()
        sigma_ab = ((a - mu_a) * (b - mu_b)).mean()

        numerator = (2.0 * mu_a * mu_b + C1) * (2.0 * sigma_ab + C2)
        denominator = (mu_a ** 2 + mu_b ** 2 + C1) * (sigma_a_sq + sigma_b_sq + C2)

        if denominator == 0:
            return 1.0 if numerator == 0 else 0.0

        return float(numerator / denominator)

    def _compute_image_hash(self, gray_img) -> str:
        """计算 16x16 感知哈希（pHash 简化版）

        将灰度图缩放到 16x16，根据均值生成 256 位哈希。

        Returns:
            十六进制哈希字符串
        """
        try:
            if _HAS_OPENCV:
                small = cv2.resize(gray_img, (16, 16), interpolation=cv2.INTER_AREA)
            elif _HAS_NUMPY:
                # 简单最近邻缩放
                h, w = gray_img.shape[:2]
                y_indices = (np.arange(16) * h / 16).astype(int)
                x_indices = (np.arange(16) * w / 16).astype(int)
                small = gray_img[np.ix_(y_indices, x_indices)]
            else:
                return hashlib.md5(gray_img.tobytes()[:1024]).hexdigest()[:16]

            if _HAS_NUMPY:
                mean_val = small.mean()
                bits = "".join("1" if v > mean_val else "0" for v in small.flatten())
            else:
                mean_val = sum(small.flatten()) / small.size
                bits = "".join("1" if v > mean_val else "0" for v in small.flatten())

            # 256位 → 64个hex字符
            return hex(int(bits, 2))[2:].zfill(64)

        except Exception:
            try:
                return hashlib.md5(gray_img.tobytes()[:1024]).hexdigest()[:16]
            except Exception:
                return "0" * 16

    @staticmethod
    def _hamming_distance(hash1: str, hash2: str) -> int:
        """计算两个十六进制哈希的汉明距离"""
        try:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
            xor = val1 ^ val2
            return bin(xor).count("1")
        except (ValueError, TypeError):
            return 256  # 最大距离，视为完全不同

    def _resize_frame(self, img):
        """缩放帧到目标尺寸"""
        w = self.config["frame_width"]
        h = self.config["frame_height"]
        if img.shape[1] != w or img.shape[0] != h:
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        return img

    def _get_video_info(self, video_path: str) -> Optional[dict]:
        """获取视频基本信息"""
        info = {}

        if _HAS_OPENCV:
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap.release()

                    info["fps"] = fps if fps > 0 else 25.0
                    info["total_frames"] = frame_count
                    info["width"] = width
                    info["height"] = height
                    info["duration"] = frame_count / info["fps"] if fps > 0 else 0.0
                    return info
            except Exception:
                pass

        if _HAS_FFMPEG:
            try:
                probe = ffmpeg.probe(video_path)
                video_stream = next(
                    (s for s in probe["streams"] if s["codec_type"] == "video"),
                    None,
                )
                if video_stream:
                    info["width"] = int(video_stream.get("width", 0))
                    info["height"] = int(video_stream.get("height", 0))
                    info["fps"] = self._parse_frame_rate(
                        video_stream.get("r_frame_rate", "25/1")
                    )
                    duration_str = probe.get("format", {}).get("duration", "0")
                    info["duration"] = float(duration_str)
                    info["total_frames"] = int(info["duration"] * info["fps"])
                    return info
            except Exception:
                pass

        # 降级：ffprobe 命令行
        try:
            import json as _json
            import subprocess

            proc = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", video_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                probe_data = _json.loads(proc.stdout)
                video_stream = next(
                    (
                        s
                        for s in probe_data.get("streams", [])
                        if s.get("codec_type") == "video"
                    ),
                    None,
                )
                if video_stream:
                    info["width"] = int(video_stream.get("width", 0))
                    info["height"] = int(video_stream.get("height", 0))
                    r_frame = video_stream.get("r_frame_rate", "25/1")
                    if "/" in str(r_frame):
                        num, den = r_frame.split("/")
                        info["fps"] = float(num) / float(den) if float(den) > 0 else 25.0
                    else:
                        info["fps"] = float(r_frame)
                    duration_str = probe_data.get("format", {}).get("duration", "0")
                    info["duration"] = float(duration_str)
                    info["total_frames"] = int(info["duration"] * info["fps"])
                    return info
        except Exception:
            pass

        return None

    def _detect_scene_changes(self, video_path: str) -> set[int]:
        """使用 PySceneDetect 检测场景切换帧索引

        Returns:
            场景切换点的帧索引集合
        """
        if not _HAS_SCENEDETECT:
            return set()

        from scenedetect import ContentDetector

        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(
                threshold=self.config["scene_threshold"],
                min_scene_len=self.config["min_scene_length"],
            )
        )

        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        # 收集每个场景的起始帧索引
        change_indices: set[int] = set()
        for start, _end in scene_list:
            change_indices.add(start.get_frames())

        return change_indices

    @staticmethod
    def _parse_frame_rate(rate_str: str) -> float:
        """安全解析帧率字符串（如 '25/1', '30000/1001'）"""
        try:
            if "/" in rate_str:
                num, den = rate_str.split("/")
                return float(num) / float(den) if float(den) != 0 else 25.0
            return float(rate_str)
        except (ValueError, ZeroDivisionError):
            return 25.0


# ─── 辅助函数 ────────────────────────────────────────────────

def _update_skip_counts(skipped_frames: list[DeltaFrame]) -> None:
    """为跳过帧计算连续跳过计数

    从前往后扫描，统计每个跳过帧之前连续跳过的帧数。
    """
    count = 0
    for frame in skipped_frames:
        count += 1
        frame.skip_count = count


def get_extractor_status() -> dict:
    """获取提取器可用状态"""
    return {
        "scenedetect": _HAS_SCENEDETECT,
        "ffmpeg": _HAS_FFMPEG,
        "opencv": _HAS_OPENCV,
        "numpy": _HAS_NUMPY,
        "recommended": (
            "scenedetect+opencv" if _HAS_SCENEDETECT and _HAS_OPENCV else
            "opencv" if _HAS_OPENCV else
            "none"
        ),
    }
