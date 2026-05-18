"""
检查点管理器 —— 断点续传核心模块

为长视频分析提供类似 YOLO 训练断点续训的能力：
  - 分析进度持久化到磁盘
  - API 限流/中断后可从上次停止处继续
  - 支持多级检查点（帧级、模块级、任务级）

核心设计：
  1. 每个分析任务在 data/checkpoints/ 下有一个 .json 检查点文件
  2. 分析过程中每完成一个阶段就写入检查点
  3. 重新启动时检查是否存在有效检查点，有则跳过已完成阶段
  4. 检查点包含足够信息以精确恢复（已完成帧索引、中间结果、LLM 调用计数等）

使用方式：
  checkpoint_mgr = CheckpointManager(task_id)
  checkpoint = checkpoint_mgr.load()
  if checkpoint and checkpoint.is_resumable:
      # 从检查点恢复
      resume_from = checkpoint.last_completed_stage
  else:
      # 从头开始
      checkpoint = checkpoint_mgr.create()

  for stage in stages:
      if checkpoint.is_stage_completed(stage.name):
          continue  # 跳过已完成阶段
      result = await run_stage(stage)
      checkpoint.complete_stage(stage.name, result)
      checkpoint_mgr.save(checkpoint)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 检查点存储目录
CHECKPOINT_DIR = Path(os.environ.get("CHECKPOINT_DIR", "./data/checkpoints"))


class StageStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageCheckpoint:
    """单个阶段的检查点数据"""
    name: str = ""
    status: StageStatus = StageStatus.PENDING
    started_at: str = ""
    completed_at: str = ""
    result: dict = field(default_factory=dict)
    error: str = ""
    # 帧级进度（用于视频分析）
    frames_total: int = 0
    frames_completed: int = 0
    # LLM 调用计数（用于限流后恢复）
    llm_calls_made: int = 0
    llm_calls_failed: int = 0
    # 中间结果摘要（用于恢复上下文）
    summary: str = ""


@dataclass
class AnalysisCheckpoint:
    """完整分析任务的检查点"""
    task_id: str = ""
    video_path: str = ""
    video_hash: str = ""           # 视频文件哈希，用于校验
    mode: str = "standard"         # quick / standard / deep
    created_at: str = ""
    updated_at: str = ""
    version: int = 1               # 检查点格式版本

    # 阶段列表
    stages: dict = field(default_factory=dict)  # stage_name -> StageCheckpoint

    # 全局状态
    overall_status: str = "pending"  # pending / running / completed / failed / interrupted
    total_llm_calls: int = 0
    total_llm_retries: int = 0
    quota_exhausted_count: int = 0   # 配额耗尽次数
    last_error: str = ""

    # 合并后的中间结果（用于恢复时重建上下文）
    intermediate_results: dict = field(default_factory=dict)

    @property
    def is_resumable(self) -> bool:
        """检查是否可恢复"""
        if self.overall_status in ("completed",):
            return False  # 已完成，不需要恢复
        if not self.stages:
            return False  # 无阶段数据
        # 至少有一个阶段已完成
        return any(
            s.status == StageStatus.COMPLETED
            for s in self.stages.values()
        )

    @property
    def progress(self) -> float:
        """整体进度 0-1"""
        if not self.stages:
            return 0.0
        completed = sum(
            1 for s in self.stages.values()
            if s.status == StageStatus.COMPLETED
        )
        return round(completed / len(self.stages), 3)

    @property
    def last_completed_stage(self) -> str:
        """获取最后完成的阶段名"""
        last = None
        last_time = ""
        for name, stage in self.stages.items():
            if stage.status == StageStatus.COMPLETED and stage.completed_at:
                if not last_time or stage.completed_at > last_time:
                    last = name
                    last_time = stage.completed_at
        return last or ""

    @property
    def next_pending_stage(self) -> str:
        """获取下一个待执行的阶段名"""
        for name, stage in self.stages.items():
            if stage.status in (StageStatus.PENDING, StageStatus.FAILED):
                return name
        return ""

    def is_stage_completed(self, stage_name: str) -> bool:
        """检查阶段是否已完成"""
        stage = self.stages.get(stage_name)
        return stage is not None and stage.status == StageStatus.COMPLETED

    def get_stage(self, stage_name: str) -> Optional[StageCheckpoint]:
        """获取阶段检查点"""
        return self.stages.get(stage_name)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_id": self.task_id,
            "video_path": self.video_path,
            "video_hash": self.video_hash,
            "mode": self.mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "stages": {
                name: {
                    "name": s.name,
                    "status": s.status.value,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "result": s.result,
                    "error": s.error,
                    "frames_total": s.frames_total,
                    "frames_completed": s.frames_completed,
                    "llm_calls_made": s.llm_calls_made,
                    "llm_calls_failed": s.llm_calls_failed,
                    "summary": s.summary,
                }
                for name, s in self.stages.items()
            },
            "overall_status": self.overall_status,
            "total_llm_calls": self.total_llm_calls,
            "total_llm_retries": self.total_llm_retries,
            "quota_exhausted_count": self.quota_exhausted_count,
            "last_error": self.last_error,
            "intermediate_results": self.intermediate_results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisCheckpoint":
        """从字典反序列化"""
        checkpoint = cls(
            task_id=data.get("task_id", ""),
            video_path=data.get("video_path", ""),
            video_hash=data.get("video_hash", ""),
            mode=data.get("mode", "standard"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
            overall_status=data.get("overall_status", "pending"),
            total_llm_calls=data.get("total_llm_calls", 0),
            total_llm_retries=data.get("total_llm_retries", 0),
            quota_exhausted_count=data.get("quota_exhausted_count", 0),
            last_error=data.get("last_error", ""),
            intermediate_results=data.get("intermediate_results", {}),
        )
        for name, s_data in data.get("stages", {}).items():
            checkpoint.stages[name] = StageCheckpoint(
                name=s_data.get("name", name),
                status=StageStatus(s_data.get("status", "pending")),
                started_at=s_data.get("started_at", ""),
                completed_at=s_data.get("completed_at", ""),
                result=s_data.get("result", {}),
                error=s_data.get("error", ""),
                frames_total=s_data.get("frames_total", 0),
                frames_completed=s_data.get("frames_completed", 0),
                llm_calls_made=s_data.get("llm_calls_made", 0),
                llm_calls_failed=s_data.get("llm_calls_failed", 0),
                summary=s_data.get("summary", ""),
            )
        return checkpoint


class CheckpointManager:
    """检查点管理器 —— 负责检查点的创建、保存、加载和清理"""

    def __init__(self, task_id: str, checkpoint_dir: str | Path = CHECKPOINT_DIR):
        self.task_id = task_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_file = self.checkpoint_dir / f"{task_id}.json"

    @property
    def checkpoint_path(self) -> Path:
        return self._checkpoint_file

    def create(
        self,
        video_path: str = "",
        mode: str = "standard",
        stage_names: list[str] | None = None,
    ) -> AnalysisCheckpoint:
        """创建新检查点"""
        now = datetime.now(timezone.utc).isoformat()

        # 计算视频哈希（如果提供了路径）
        video_hash = ""
        if video_path and os.path.exists(video_path):
            video_hash = self._compute_file_hash(video_path)

        checkpoint = AnalysisCheckpoint(
            task_id=self.task_id,
            video_path=video_path,
            video_hash=video_hash,
            mode=mode,
            created_at=now,
            updated_at=now,
            overall_status="running",
        )

        # 初始化阶段
        if stage_names:
            for name in stage_names:
                checkpoint.stages[name] = StageCheckpoint(name=name, status=StageStatus.PENDING)

        self.save(checkpoint)
        logger.info("检查点已创建: %s, 阶段数=%d", self.task_id, len(checkpoint.stages))
        return checkpoint

    def save(self, checkpoint: AnalysisCheckpoint):
        """保存检查点到磁盘"""
        checkpoint.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            # 先写临时文件，再原子性重命名，防止写入过程中断导致文件损坏
            tmp_path = self._checkpoint_file.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            tmp_path.replace(self._checkpoint_file)
            logger.debug("检查点已保存: %s (进度=%.0f%%)", self.task_id, checkpoint.progress * 100)
        except Exception as e:
            logger.error("检查点保存失败: %s, 错误: %s", self.task_id, e)

    def load(self) -> Optional[AnalysisCheckpoint]:
        """从磁盘加载检查点"""
        if not self._checkpoint_file.exists():
            return None
        try:
            with open(self._checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            checkpoint = AnalysisCheckpoint.from_dict(data)
            logger.info(
                "检查点已加载: %s, 进度=%.0f%%, 可恢复=%s",
                self.task_id, checkpoint.progress * 100, checkpoint.is_resumable,
            )
            return checkpoint
        except Exception as e:
            logger.error("检查点加载失败: %s, 错误: %s", self.task_id, e)
            return None

    def delete(self):
        """删除检查点"""
        if self._checkpoint_file.exists():
            self._checkpoint_file.unlink()
            logger.info("检查点已删除: %s", self.task_id)

    def complete_stage(
        self,
        checkpoint: AnalysisCheckpoint,
        stage_name: str,
        result: dict | None = None,
        summary: str = "",
        llm_calls: int = 0,
    ):
        """标记阶段完成"""
        stage = checkpoint.stages.get(stage_name)
        if stage:
            stage.status = StageStatus.COMPLETED
            stage.completed_at = datetime.now(timezone.utc).isoformat()
            stage.result = result or {}
            stage.summary = summary
            stage.llm_calls_made += llm_calls
            checkpoint.total_llm_calls += llm_calls
            self.save(checkpoint)
            logger.info("阶段完成: %s/%s (%.0f%%)", self.task_id, stage_name, checkpoint.progress * 100)

    def fail_stage(
        self,
        checkpoint: AnalysisCheckpoint,
        stage_name: str,
        error: str,
        llm_calls_failed: int = 0,
    ):
        """标记阶段失败"""
        stage = checkpoint.stages.get(stage_name)
        if stage:
            stage.status = StageStatus.FAILED
            stage.error = error
            stage.llm_calls_failed += llm_calls_failed
            checkpoint.total_llm_retries += llm_calls_failed
            checkpoint.last_error = error
            self.save(checkpoint)
            logger.warning("阶段失败: %s/%s, 错误: %s", self.task_id, stage_name, error)

    def mark_interrupted(self, checkpoint: AnalysisCheckpoint, error: str = ""):
        """标记任务被中断"""
        checkpoint.overall_status = "interrupted"
        checkpoint.last_error = error
        # 将正在运行的阶段标记为失败
        for stage in checkpoint.stages.values():
            if stage.status == StageStatus.RUNNING:
                stage.status = StageStatus.FAILED
                stage.error = error or "任务被中断"
        self.save(checkpoint)
        logger.warning("任务被中断: %s, 错误: %s", self.task_id, error)

    def mark_completed(self, checkpoint: AnalysisCheckpoint):
        """标记任务完成"""
        checkpoint.overall_status = "completed"
        self.save(checkpoint)
        logger.info("任务完成: %s, 总LLM调用=%d", self.task_id, checkpoint.total_llm_calls)

    def verify_video_unchanged(self, checkpoint: AnalysisCheckpoint) -> bool:
        """验证视频文件是否未变更"""
        if not checkpoint.video_hash or not checkpoint.video_path:
            return True  # 无哈希信息，跳过验证
        if not os.path.exists(checkpoint.video_path):
            return False
        current_hash = self._compute_file_hash(checkpoint.video_path)
        return current_hash == checkpoint.video_hash

    @staticmethod
    def _compute_file_hash(file_path: str, chunk_size: int = 8192) -> str:
        """计算文件哈希（用于校验视频文件是否变更）"""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            # 读取前 1MB + 后 1MB + 文件大小，快速哈希
            file_size = os.path.getsize(file_path)
            h.update(str(file_size).encode())
            h.update(f.read(min(chunk_size * 128, file_size)))  # 前 1MB
            if file_size > chunk_size * 256:
                f.seek(-chunk_size * 128, 2)  # 后 1MB
                h.update(f.read())
        return h.hexdigest()

    @staticmethod
    def list_checkpoints(checkpoint_dir: str | Path = CHECKPOINT_DIR) -> list[dict]:
        """列出所有检查点"""
        checkpoint_dir = Path(checkpoint_dir)
        if not checkpoint_dir.exists():
            return []
        results = []
        for f in checkpoint_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                results.append({
                    "task_id": data.get("task_id", ""),
                    "status": data.get("overall_status", ""),
                    "progress": data.get("stages", {}),
                    "updated_at": data.get("updated_at", ""),
                    "file": str(f),
                })
            except Exception:
                pass
        return results

    @staticmethod
    def cleanup_old_checkpoints(
        checkpoint_dir: str | Path = CHECKPOINT_DIR,
        max_age_hours: int = 72,
        keep_completed: bool = True,
    ) -> int:
        """清理过期检查点"""
        checkpoint_dir = Path(checkpoint_dir)
        if not checkpoint_dir.exists():
            return 0
        now = time.time()
        removed = 0
        for f in checkpoint_dir.glob("*.json"):
            try:
                file_age_hours = (now - f.stat().st_mtime) / 3600
                if file_age_hours > max_age_hours:
                    if keep_completed:
                        with open(f, "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        if data.get("overall_status") == "completed":
                            continue
                    f.unlink()
                    removed += 1
            except Exception:
                pass
        if removed:
            logger.info("清理了 %d 个过期检查点", removed)
        return removed
