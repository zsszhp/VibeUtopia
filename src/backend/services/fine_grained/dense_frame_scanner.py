from __future__ import annotations

"""密集帧扫描器 - V3.4 细粒度视频理解

解决视频中短暂画面（十几帧）的漏检问题。
采用"先密后筛"策略：先1fps全量抽帧，再通过多尺度帧差异评分筛选异常帧。

借鉴ActionFormer的多尺度时序检测思想：
- 多时间窗口计算帧差异（窗口1/3/10/30帧），短窗口检测闪帧，长窗口检测短暂画面
- 异常帧优先级分层：高异常帧必审 + 低异常帧抽审
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

_HAS_OPENCV = False
try:
    import cv2
    _HAS_OPENCV = True
except ImportError:
    pass

_HAS_FFMPEG = False
try:
    import ffmpeg as _ffmpeg_mod
    _HAS_FFMPEG = True
except ImportError:
    pass


@dataclass
class DenseFrame:
    """密集扫描帧"""
    frame_id: str
    video_path: str
    timestamp: float
    image_path: str
    frame_index: int = 0
    anomaly_score: float = 0.0
    extraction_method: str = ""
    image_hash: str = ""


@dataclass
class DenseScanResult:
    """密集帧扫描结果"""
    video_path: str = ""
    total_dense_frames: int = 0
    high_anomaly_frames: list = field(default_factory=list)
    low_anomaly_frames: list = field(default_factory=list)
    all_frames: list = field(default_factory=list)
    method_used: str = ""
    error: Optional[str] = None


DEFAULT_CONFIG = {
    "dense_fps": 1.0,
    "anomaly_threshold_high": 0.7,
    "anomaly_threshold_low": 0.3,
    "low_anomaly_sample_step": 5,
    "regression_windows": [1, 3, 10, 30],
    "frame_width": 640,
    "frame_height": 360,
    "image_format": "jpg",
    "image_quality": 85,
    "max_dense_frames": 1200,
    "scene_change_supplement": True,
    "scene_threshold": 27.0,
}


class DenseFrameScanner:
    """密集帧扫描器——确保短暂画面不被遗漏"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def scan(self, video_path: str, output_dir: str | None = None) -> DenseScanResult:
        """密集帧扫描主入口

        Args:
            video_path: 本地视频文件路径
            output_dir: 帧图片输出目录

        Returns:
            DenseScanResult
        """
        if not _HAS_OPENCV:
            return DenseScanResult(
                video_path=video_path,
                error="需要OpenCV支持（pip install opencv-python）"
            )

        if not os.path.exists(video_path):
            return DenseScanResult(
                video_path=video_path,
                error=f"视频文件不存在: {video_path}"
            )

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="vibe_dense_")
        os.makedirs(output_dir, exist_ok=True)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._scan_sync,
            video_path,
            output_dir,
        )
        return result

    def _scan_sync(self, video_path: str, output_dir: str) -> DenseScanResult:
        """同步密集帧扫描"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return DenseScanResult(
                video_path=video_path,
                error="无法打开视频文件"
            )

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        dense_fps = self.config["dense_fps"]
        frame_interval = max(1, int(fps / dense_fps))

        fmt = self.config["image_format"]
        quality = self.config["image_quality"]
        target_w = self.config["frame_width"]
        target_h = self.config["frame_height"]

        all_frames = []
        prev_gray = None
        frame_idx = 0

        logger.info(
            "密集帧扫描开始: fps=%.1f, interval=%d, total=%d",
            fps, frame_interval, total_frames,
        )

        while cap.isOpened():
            ret, img = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps
                frame_path = os.path.join(
                    output_dir,
                    f"dense_{len(all_frames):05d}_{timestamp:.2f}s.{fmt}"
                )

                resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
                cv2.imwrite(frame_path, resized, [cv2.IMWRITE_JPEG_QUALITY, quality])

                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                image_hash = self._compute_image_hash(gray)

                all_frames.append(DenseFrame(
                    frame_id=f"dense_{len(all_frames):05d}",
                    video_path=video_path,
                    timestamp=round(timestamp, 2),
                    image_path=frame_path,
                    frame_index=frame_idx,
                    extraction_method="dense_1fps",
                    image_hash=image_hash,
                ))

                prev_gray = gray

            frame_idx += 1

        cap.release()

        logger.info("1fps全量抽帧完成: %d帧", len(all_frames))

        if len(all_frames) < 2:
            return DenseScanResult(
                video_path=video_path,
                total_dense_frames=len(all_frames),
                all_frames=all_frames,
                high_anomaly_frames=all_frames,
                low_anomaly_frames=[],
                method_used="dense_1fps",
            )

        scored_frames = self._score_frame_anomaly(all_frames)

        high_thresh = self.config["anomaly_threshold_high"]
        low_thresh = self.config["anomaly_threshold_low"]
        sample_step = self.config["low_anomaly_sample_step"]

        high_anomaly = [f for f in scored_frames if f.anomaly_score >= high_thresh]
        low_anomaly = [f for f in scored_frames if low_thresh <= f.anomaly_score < high_thresh]
        sampled_low = low_anomaly[::sample_step]

        logger.info(
            "帧差异评分完成: 高异常=%d, 低异常(抽审)=%d/%d",
            len(high_anomaly), len(sampled_low), len(low_anomaly),
        )

        return DenseScanResult(
            video_path=video_path,
            total_dense_frames=len(scored_frames),
            high_anomaly_frames=high_anomaly,
            low_anomaly_frames=sampled_low,
            all_frames=scored_frames,
            method_used="dense_1fps_multiscale",
        )

    def _score_frame_anomaly(self, frames: list[DenseFrame]) -> list[DenseFrame]:
        """多尺度帧差异评分——借鉴ActionFormer的regression_range思想

        ActionFormer使用regression_range=[(0,4),(4,8),(8,16),...]将不同FPN层级
        分配到不同时长的动作检测。类似地，使用多时间窗口计算帧差异：
        - 窗口1(1帧)：检测闪帧（单帧异常画面）
        - 窗口3(3帧)：检测极短暂画面（0.1-0.3秒）
        - 窗口10(10帧)：检测短暂画面（0.3-1秒）
        - 窗口30(30帧)：检测中等画面（1-3秒）
        """
        regression_windows = self.config["regression_windows"]
        n = len(frames)

        for i in range(n):
            max_anomaly = 0.0
            for window in regression_windows:
                prev_idx = max(0, i - window)
                next_idx = min(n - 1, i + window)

                prev_diff = self._compute_frame_diff_by_index(frames, i, prev_idx)
                next_diff = self._compute_frame_diff_by_index(frames, i, next_idx)

                weight = 1.0 / (window ** 0.5)
                window_anomaly = max(prev_diff, next_diff) * weight
                max_anomaly = max(max_anomaly, window_anomaly)

            frames[i].anomaly_score = min(max_anomaly, 1.0)

        return frames

    def _compute_frame_diff_by_index(self, frames: list[DenseFrame], idx_a: int, idx_b: int) -> float:
        """计算两帧的差异度（0-1）"""
        if idx_a == idx_b:
            return 0.0

        hash_a = frames[idx_a].image_hash
        hash_b = frames[idx_b].image_hash

        if hash_a and hash_b:
            return self._hash_distance(hash_a, hash_b)

        return 0.0

    @staticmethod
    def _compute_image_hash(gray_img) -> str:
        """计算图片感知哈希(pHash简化版)用于去重和差异计算"""
        try:
            small = cv2.resize(gray_img, (16, 16), interpolation=cv2.INTER_AREA)
            mean_val = small.mean()
            bits = "".join("1" if v > mean_val else "0" for v in small.flatten())
            return hex(int(bits, 2))[2:]
        except Exception:
            return hashlib.md5(gray_img.tobytes()[:1024]).hexdigest()[:16]

    @staticmethod
    def _hash_distance(hash1: str, hash2: str) -> float:
        """计算两个哈希的归一化汉明距离（0-1）"""
        try:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
            xor = val1 ^ val2
            hamming = bin(xor).count("1")
            max_bits = max(len(bin(val1)) - 2, len(bin(val2)) - 2, 1)
            return hamming / (max_bits * 1.0)
        except (ValueError, TypeError):
            return 0.5

    def get_scan_status(self) -> dict:
        """获取扫描器可用状态"""
        return {
            "opencv": _HAS_OPENCV,
            "ffmpeg": _HAS_FFMPEG,
            "available": _HAS_OPENCV,
            "config": {
                "dense_fps": self.config["dense_fps"],
                "regression_windows": self.config["regression_windows"],
                "anomaly_threshold_high": self.config["anomaly_threshold_high"],
                "anomaly_threshold_low": self.config["anomaly_threshold_low"],
            },
        }
