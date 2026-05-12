from __future__ import annotations

"""关键帧提取模块 - V2.R4

从视频中提取关键帧，支持三种策略：
1. PySceneDetect 场景切换检测（首选）
2. FFmpeg 固定间隔提取（备选）
3. OpenCV 降级提取（兜底）

提取后合并去重，最多保留50帧。
"""

import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 检测可用工具
_HAS_SCENEDETECT = False
_HAS_FFMPEG = False
_HAS_OPENCV = False

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


@dataclass
class KeyFrame:
    """单个关键帧"""
    index: int                    # 帧序号
    timestamp: float              # 时间戳(秒)
    file_path: str                # 帧图片路径
    method: str = ""              # 提取方式: scenedetect/interval/opencv
    scene_index: int = -1         # 场景序号(-1表示非场景切换帧)
    image_hash: str = ""          # 图片感知哈希，用于去重


@dataclass
class KeyFrameResult:
    """关键帧提取结果"""
    video_path: str = ""
    total_frames: int = 0
    duration: float = 0.0
    frames: list = field(default_factory=list)  # List[KeyFrame]
    method_used: str = ""         # 实际使用的提取方法
    scene_count: int = 0          # 检测到的场景数
    error: Optional[str] = None


# ─── 默认配置 ────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "max_frames": 50,             # 最多保留帧数
    "interval_seconds": 5.0,      # 固定间隔提取的间隔秒数
    "scene_threshold": 27.0,      # PySceneDetect 内容检测阈值
    "min_scene_length": 15,       # 最短场景长度(帧数)
    "frame_width": 640,           # 输出帧宽度
    "frame_height": 360,          # 输出帧高度
    "image_format": "jpg",        # 输出图片格式
    "image_quality": 85,          # JPEG质量
    "dedup_threshold": 8,         # 感知哈希去重汉明距离阈值
}


class KeyframeExtractor:
    """关键帧提取器"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def extract(self, video_path: str, output_dir: str | None = None) -> KeyFrameResult:
        """从视频提取关键帧

        Args:
            video_path: 本地视频文件路径（仅支持本地文件）
            output_dir: 帧图片输出目录(默认临时目录)

        Returns:
            KeyFrameResult
        """
        if not os.path.exists(video_path):
            return KeyFrameResult(
                video_path=video_path,
                error=f"视频文件不存在: {video_path}（仅支持本地视频文件）"
            )

        # 准备输出目录
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="vibe_keyframes_")
        os.makedirs(output_dir, exist_ok=True)

        # 获取视频信息
        video_info = self._get_video_info(video_path)
        if video_info is None:
            return KeyFrameResult(
                video_path=video_path,
                error="无法读取视频信息"
            )

        duration = video_info.get("duration", 0.0)
        total_frames = video_info.get("total_frames", 0)

        result = KeyFrameResult(
            video_path=video_path,
            total_frames=total_frames,
            duration=duration,
        )

        # 按优先级尝试提取
        frames = []
        method_used = ""

        if _HAS_SCENEDETECT:
            try:
                frames = await self._extract_by_scenedetect(video_path, output_dir)
                method_used = "scenedetect"
                logger.info("PySceneDetect提取完成: %d帧", len(frames))
            except Exception as e:
                logger.warning("PySceneDetect提取失败: %s", e)

        if not frames and _HAS_FFMPEG:
            try:
                frames = await self._extract_by_ffmpeg(video_path, output_dir)
                method_used = "ffmpeg"
                logger.info("FFmpeg提取完成: %d帧", len(frames))
            except Exception as e:
                logger.warning("FFmpeg提取失败: %s", e)

        if not frames and _HAS_OPENCV:
            try:
                frames = await self._extract_by_opencv(video_path, output_dir)
                method_used = "opencv"
                logger.info("OpenCV提取完成: %d帧", len(frames))
            except Exception as e:
                logger.warning("OpenCV提取失败: %s", e)

        if not frames:
            result.error = "无可用提取工具（需要scenedetect/ffmpeg/opencv之一）"
            return result

        # 去重
        frames = self._dedup_frames(frames)
        logger.info("去重后剩余: %d帧", len(frames))

        # 限制最大帧数
        max_frames = self.config["max_frames"]
        if len(frames) > max_frames:
            # 均匀采样
            step = len(frames) / max_frames
            frames = [frames[int(i * step)] for i in range(max_frames)]
            logger.info("裁剪到最大帧数: %d", max_frames)

        result.frames = frames
        result.method_used = method_used
        result.scene_count = sum(1 for f in frames if f.scene_index >= 0)

        return result

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
                    info["fps"] = self._parse_frame_rate(video_stream.get("r_frame_rate", "25/1"))
                    duration_str = probe.get("format", {}).get("duration", "0")
                    info["duration"] = float(duration_str)
                    info["total_frames"] = int(info["duration"] * info["fps"])
                    return info
            except Exception:
                pass

        # 降级：用ffprobe命令行
        try:
            import subprocess
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", video_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                import json as _json
                probe_data = _json.loads(result.stdout)
                video_stream = next(
                    (s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"),
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

    async def _extract_by_scenedetect(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """使用PySceneDetect场景切换检测提取关键帧"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._scenedetect_sync,
            video_path,
            output_dir,
        )

    def _scenedetect_sync(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """同步PySceneDetect提取"""
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

        frames = []
        cap = cv2.VideoCapture(video_path) if _HAS_OPENCV else None

        for scene_idx, (start, end) in enumerate(scene_list):
            # 每个场景取中间帧
            mid_frame_num = (start.get_frames() + end.get_frames()) // 2
            timestamp = mid_frame_num / (float(video.frame_rate) if video.frame_rate > 0 else 25.0)

            frame_path = os.path.join(
                output_dir,
                f"scene_{scene_idx:04d}_{timestamp:.1f}s.{self.config['image_format']}"
            )

            if cap and cap.isOpened():
                cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_num)
                ret, img = cap.read()
                if ret:
                    img = self._resize_frame(img)
                    cv2.imwrite(frame_path, img, [cv2.IMWRITE_JPEG_QUALITY, self.config["image_quality"]])
                    image_hash = self._compute_image_hash(img)
                    frames.append(KeyFrame(
                        index=mid_frame_num,
                        timestamp=timestamp,
                        file_path=frame_path,
                        method="scenedetect",
                        scene_index=scene_idx,
                        image_hash=image_hash,
                    ))

        if cap:
            cap.release()

        # 如果场景太少，补充固定间隔帧
        if len(frames) < 3:
            frames.extend(self._interval_frames_sync(video_path, output_dir, cap_reuse=None))

        return frames

    async def _extract_by_ffmpeg(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """使用FFmpeg固定间隔提取关键帧"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._ffmpeg_sync,
            video_path,
            output_dir,
        )

    def _ffmpeg_sync(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """同步FFmpeg提取"""
        interval = self.config["interval_seconds"]
        w = self.config["frame_width"]
        h = self.config["frame_height"]
        fmt = self.config["image_format"]
        quality = self.config["image_quality"]

        output_pattern = os.path.join(output_dir, f"frame_%04d.{fmt}")

        try:
            (
                ffmpeg
                .input(video_path)
                .filter("fps", fps=1.0 / interval)
                .filter("scale", w, h)
                .output(
                    output_pattern,
                    **{"q:v": str(quality // 10)} if fmt == "jpg" else {},
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as e:
            logger.error("FFmpeg运行失败: %s", e.stderr.decode() if e.stderr else str(e))
            return []

        return self._load_extracted_frames(output_dir, "interval")

    async def _extract_by_opencv(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """使用OpenCV降级提取关键帧"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._opencv_sync,
            video_path,
            output_dir,
        )

    def _opencv_sync(self, video_path: str, output_dir: str) -> list[KeyFrame]:
        """同步OpenCV提取"""
        interval = self.config["interval_seconds"]
        fmt = self.config["image_format"]
        quality = self.config["image_quality"]

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        frame_interval = int(fps * interval)

        frames = []
        frame_idx = 0

        while cap.isOpened():
            ret, img = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / fps
                frame_path = os.path.join(
                    output_dir,
                    f"frame_{len(frames):04d}_{timestamp:.1f}s.{fmt}"
                )
                img = self._resize_frame(img)
                cv2.imwrite(frame_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
                image_hash = self._compute_image_hash(img)
                frames.append(KeyFrame(
                    index=frame_idx,
                    timestamp=round(timestamp, 2),
                    file_path=frame_path,
                    method="opencv",
                    image_hash=image_hash,
                ))

            frame_idx += 1

        cap.release()
        return frames

    def _interval_frames_sync(self, video_path: str, output_dir: str, cap_reuse=None) -> list[KeyFrame]:
        """固定间隔提取补充帧"""
        interval = self.config["interval_seconds"]
        fmt = self.config["image_format"]
        quality = self.config["image_quality"]

        if cap_reuse and cap_reuse.isOpened():
            cap = cap_reuse
        else:
            cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = int(fps * interval)

        frames = []
        frame_idx = 0
        existing_timestamps = set()

        while cap.isOpened():
            ret, img = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / fps, 2)
                if timestamp not in existing_timestamps:
                    frame_path = os.path.join(
                        output_dir,
                        f"interval_{len(frames):04d}_{timestamp:.1f}s.{fmt}"
                    )
                    img = self._resize_frame(img)
                    cv2.imwrite(frame_path, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    image_hash = self._compute_image_hash(img)
                    frames.append(KeyFrame(
                        index=frame_idx,
                        timestamp=timestamp,
                        file_path=frame_path,
                        method="interval",
                        image_hash=image_hash,
                    ))
                    existing_timestamps.add(timestamp)

            frame_idx += 1

        if not cap_reuse:
            cap.release()

        return frames

    def _resize_frame(self, img) -> object:
        """缩放帧到目标尺寸"""
        w = self.config["frame_width"]
        h = self.config["frame_height"]
        if img.shape[1] != w or img.shape[0] != h:
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        return img

    def _compute_image_hash(self, img) -> str:
        """计算图片感知哈希(pHash简化版)用于去重"""
        try:
            # 缩小到8x8灰度图
            small = cv2.resize(img, (8, 8), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small
            mean_val = gray.mean()
            # 生成64位哈希
            bits = "".join("1" if v > mean_val else "0" for v in gray.flatten())
            return hex(int(bits, 2))[2:]
        except Exception:
            # 降级：使用文件大小+部分像素
            return hashlib.md5(img.tobytes()[:1024]).hexdigest()[:16]

    def _dedup_frames(self, frames: list[KeyFrame]) -> list[KeyFrame]:
        """基于感知哈希去重相似帧"""
        if len(frames) <= 1:
            return frames

        threshold = self.config["dedup_threshold"]
        unique = [frames[0]]

        for frame in frames[1:]:
            is_dup = False
            for existing in unique:
                hamming = self._hamming_distance(frame.image_hash, existing.image_hash)
                if hamming < threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique.append(frame)

        return unique

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

    @staticmethod
    def _hamming_distance(hash1: str, hash2: str) -> int:
        """计算两个哈希的汉明距离"""
        try:
            val1 = int(hash1, 16)
            val2 = int(hash2, 16)
            xor = val1 ^ val2
            return bin(xor).count("1")
        except (ValueError, TypeError):
            return 64  # 最大距离，视为不同

    def _load_extracted_frames(self, output_dir: str, method: str) -> list[KeyFrame]:
        """从已提取的帧目录加载帧信息"""
        frames = []
        fmt = self.config["image_format"]

        for fname in sorted(os.listdir(output_dir)):
            if not fname.endswith(f".{fmt}"):
                continue

            # 从文件名解析时间戳: frame_0005_12.3s.jpg 或 scene_0002_8.5s.jpg
            timestamp = 0.0
            parts = fname.replace(f".{fmt}", "").split("_")
            for part in parts:
                if part.endswith("s"):
                    try:
                        timestamp = float(part[:-1])
                    except ValueError:
                        pass

            frame_path = os.path.join(output_dir, fname)
            image_hash = ""
            if _HAS_OPENCV:
                try:
                    img = cv2.imread(frame_path, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        image_hash = self._compute_image_hash(img)
                except Exception:
                    pass

            frames.append(KeyFrame(
                index=len(frames),
                timestamp=timestamp,
                file_path=frame_path,
                method=method,
                image_hash=image_hash,
            ))

        return frames


def get_extractor_status() -> dict:
    """获取提取器可用状态"""
    return {
        "scenedetect": _HAS_SCENEDETECT,
        "ffmpeg": _HAS_FFMPEG,
        "opencv": _HAS_OPENCV,
        "recommended": (
            "scenedetect" if _HAS_SCENEDETECT else
            "ffmpeg" if _HAS_FFMPEG else
            "opencv" if _HAS_OPENCV else
            "none"
        ),
    }
