"""
可恢复分析管线 —— 集成断点续传能力的视频分析编排器

解决长视频分析中 API 限流/中断导致需要从头重跑的问题。

核心能力：
  1. 检查点持久化：每完成一个分析阶段自动保存进度
  2. 断点续传：中断后自动从上次停止处继续
  3. 限流感知：检测到 429 限流时暂停并保存状态，等待后继续
  4. 帧级细粒度检查点：视频分析中最小恢复单元为单帧
  5. 多阶段管道：Phase 1-4 每个阶段都可独立恢复

使用方式：
  analyzer = ResumableAnalyzer(task_id, video_path)
  result = await analyzer.run(text, mode="deep")

  # 如果中断了，再次调用 run() 会自动从检查点恢复
  result = await analyzer.run(text, mode="deep")  # 自动续传
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.services.checkpoint_manager import (
    CheckpointManager,
    AnalysisCheckpoint,
    StageStatus,
)
from backend.services.llm_client import QuotaExhaustedError

logger = logging.getLogger(__name__)


# 分析阶段定义（顺序执行）
ANALYSIS_STAGES = [
    "text_extraction",       # 视频文案提取（OCR + 音频转写）
    "text_risk_assessment",  # 文本风险评估（LLM 调用密集）
    "signal_matching",       # 信号关联
    "entity_risk_chain",     # 实体风险链
    "platform_simulation",   # 平台仿真
    "cross_modal_detection", # 跨模态检测
    "fine_grained_video",    # 细粒度视频理解（V3.4，最耗时）
    "report_compilation",    # 报告生成
]


@dataclass
class StageResult:
    """阶段执行结果"""
    stage_name: str = ""
    success: bool = False
    result: dict = field(default_factory=dict)
    error: str = ""
    llm_calls: int = 0
    duration_seconds: float = 0.0
    was_resumed: bool = False  # 是否从检查点恢复（跳过执行）


class ResumableAnalyzer:
    """可恢复分析管线

    包装现有分析流程，加入断点续传能力。
    对现有代码的侵入最小——主要通过检查点跳过已完成阶段。
    """

    def __init__(
        self,
        task_id: str,
        video_path: str = "",
        mode: str = "standard",
        auto_resume: bool = True,
        quota_retry_wait: int = 60,  # 限流后等待秒数
        max_quota_retries: int = 5,  # 最大限流重试次数
    ):
        self.task_id = task_id
        self.video_path = video_path
        self.mode = mode
        self.auto_resume = auto_resume
        self.quota_retry_wait = quota_retry_wait
        self.max_quota_retries = max_quota_retries

        # 检查点管理器
        self._checkpoint_mgr = CheckpointManager(task_id)
        self._checkpoint: Optional[AnalysisCheckpoint] = None

        # 统计
        self._llm_calls_total = 0
        self._stages_executed = 0
        self._stages_skipped = 0

    async def run(
        self,
        text: str,
        mode: str | None = None,
        force_restart: bool = False,
    ) -> dict:
        """运行分析（自动处理断点续传）

        Args:
            text: 要分析的文本内容
            mode: 分析模式（覆盖构造时的 mode）
            force_restart: 是否强制从头开始（忽略已有检查点）

        Returns:
            分析结果 dict
        """
        mode = mode or self.mode
        start_time = time.time()

        # 加载或创建检查点
        if not force_restart:
            self._checkpoint = self._checkpoint_mgr.load()

        if self._checkpoint and self._checkpoint.is_resumable and self.auto_resume:
            # 验证视频文件未变更
            if self.video_path and not self._checkpoint_mgr.verify_video_unchanged(self._checkpoint):
                logger.warning("视频文件已变更，强制重新开始")
                self._checkpoint = None

        if not self._checkpoint:
            # 创建新检查点
            stage_names = list(ANALYSIS_STAGES)
            if not self.video_path:
                stage_names = [s for s in stage_names if s != "fine_grained_video"]
            self._checkpoint = self._checkpoint_mgr.create(
                video_path=self.video_path or "",
                mode=mode,
                stage_names=stage_names,
            )
        else:
            logger.info(
                "从检查点恢复: %s, 进度=%.0f%%, 跳过已完成阶段",
                self.task_id, self._checkpoint.progress * 100,
            )

        # 收集各阶段结果
        stage_results: dict[str, Any] = {}
        self._checkpoint.overall_status = "running"

        try:
            # ─── 阶段 1: 文案提取 ───
            r = await self._run_stage("text_extraction", stage_results, lambda: self._extract_text())
            stage_results["text_extraction"] = r

            # ─── 阶段 2: 文本风险评估 ───
            r = await self._run_stage(
                "text_risk_assessment", stage_results,
                lambda: self._assess_text_risks(text),
            )
            stage_results["text_risk_assessment"] = r

            # ─── 阶段 3: 信号关联 ───
            r = await self._run_stage(
                "signal_matching", stage_results,
                lambda: self._match_signals(text),
            )
            stage_results["signal_matching"] = r

            # ─── 阶段 4: 实体风险链 ───
            r = await self._run_stage(
                "entity_risk_chain", stage_results,
                lambda: self._analyze_entity_chain(text),
            )
            stage_results["entity_risk_chain"] = r

            # ─── 阶段 5: 平台仿真 ───
            r = await self._run_stage(
                "platform_simulation", stage_results,
                lambda: self._simulate_platforms(text, stage_results),
            )
            stage_results["platform_simulation"] = r

            # ─── 阶段 6: 跨模态检测 ───
            r = await self._run_stage(
                "cross_modal_detection", stage_results,
                lambda: self._detect_cross_modal(text, stage_results),
            )
            stage_results["cross_modal_detection"] = r

            # ─── 阶段 7: 细粒度视频理解（限流敏感）───
            if self.video_path and os.path.exists(self.video_path):
                r = await self._run_stage(
                    "fine_grained_video", stage_results,
                    lambda: self._analyze_fine_grained(self.video_path, stage_results),
                )
                stage_results["fine_grained_video"] = r

            # ─── 阶段 8: 报告生成 ───
            r = await self._run_stage(
                "report_compilation", stage_results,
                lambda: self._compile_report(text, stage_results),
            )
            stage_results["report_compilation"] = r

            # 标记完成
            self._checkpoint_mgr.mark_completed(self._checkpoint)

            total_time = round(time.time() - start_time, 2)
            logger.info(
                "分析完成: task=%s, 耗时=%.1fs, LLM调用=%d, 执行阶段=%d, 跳过阶段=%d",
                self.task_id, total_time, self._llm_calls_total,
                self._stages_executed, self._stages_skipped,
            )

            return {
                "task_id": self.task_id,
                "status": "completed",
                "mode": mode,
                "total_time_seconds": total_time,
                "llm_calls_total": self._llm_calls_total,
                "stages_executed": self._stages_executed,
                "stages_skipped": self._stages_skipped,
                "was_resumed": self._stages_skipped > 0,
                "results": stage_results,
                "checkpoint_path": str(self._checkpoint_mgr.checkpoint_path),
            }

        except QuotaExhaustedError as e:
            # 限流耗尽 → 保存检查点，等待后重试
            self._checkpoint.quota_exhausted_count += 1
            self._checkpoint_mgr.mark_interrupted(self._checkpoint, f"API 限流: {e}")
            logger.warning(
                "API 限流，已保存检查点: task=%s, 进度=%.0f%%, 等待 %ds 后重试（第%d次）",
                self.task_id, self._checkpoint.progress * 100,
                self.quota_retry_wait, self._checkpoint.quota_exhausted_count,
            )

            if self._checkpoint.quota_exhausted_count < self.max_quota_retries:
                logger.info("等待 %d 秒后重试...", self.quota_retry_wait)
                await asyncio.sleep(self.quota_retry_wait)
                # 递归重试（会从检查点恢复）
                return await self.run(text, mode=mode, force_restart=False)
            else:
                logger.error("达到最大限流重试次数 (%d)，分析失败", self.max_quota_retries)
                return {
                    "task_id": self.task_id,
                    "status": "failed",
                    "error": f"API 限流超过最大重试次数 ({self.max_quota_retries})",
                    "checkpoint_path": str(self._checkpoint_mgr.checkpoint_path),
                    "resumable": True,
                    "results": stage_results,
                }

        except Exception as e:
            # 其他异常 → 保存检查点
            self._checkpoint_mgr.mark_interrupted(self._checkpoint, str(e))
            logger.error("分析异常: task=%s, 错误=%s", self.task_id, e, exc_info=True)
            return {
                "task_id": self.task_id,
                "status": "failed",
                "error": str(e),
                "checkpoint_path": str(self._checkpoint_mgr.checkpoint_path),
                "resumable": True,
                "results": stage_results,
            }

    async def _run_stage(
        self,
        stage_name: str,
        stage_results: dict,
        stage_func,
    ) -> StageResult:
        """运行单个阶段（带检查点跳过和限流重试）"""
        sr = StageResult(stage_name=stage_name)

        # 检查是否已完成
        if self._checkpoint.is_stage_completed(stage_name):
            completed = self._checkpoint.get_stage(stage_name)
            sr.success = True
            sr.result = completed.result if completed else {}
            sr.was_resumed = True
            self._stages_skipped += 1
            logger.info("跳过已完成阶段: %s/%s", self.task_id, stage_name)
            return sr

        # 标记阶段开始
        stage = self._checkpoint.stages.get(stage_name)
        if stage:
            stage.status = StageStatus.RUNNING
            stage.started_at = datetime.now(timezone.utc).isoformat()
            self._checkpoint_mgr.save(self._checkpoint)

        stage_start = time.time()

        try:
            # 执行阶段（带限流重试）
            result = await self._execute_with_quota_retry(stage_func, stage_name)

            sr.success = True
            sr.result = result if isinstance(result, dict) else {}
            sr.llm_calls = result.get("_llm_calls", 0) if isinstance(result, dict) else 0
            self._llm_calls_total += sr.llm_calls
            self._stages_executed += 1

            # 保存检查点
            self._checkpoint_mgr.complete_stage(
                self._checkpoint,
                stage_name,
                result=sr.result,
                summary=result.get("_summary", "") if isinstance(result, dict) else "",
                llm_calls=sr.llm_calls,
            )

        except Exception as e:
            sr.success = False
            sr.error = str(e)
            self._checkpoint_mgr.fail_stage(self._checkpoint, stage_name, str(e))
            logger.error("阶段执行失败: %s/%s, 错误=%s", self.task_id, stage_name, e)

        sr.duration_seconds = round(time.time() - stage_start, 2)
        return sr

    async def _execute_with_quota_retry(self, func, stage_name: str) -> dict:
        """执行函数，遇到限流自动重试"""
        last_error = None
        for attempt in range(self.max_quota_retries):
            try:
                result = await func()
                if isinstance(result, dict):
                    result["_llm_calls"] = result.get("_llm_calls", 1)
                return result or {}
            except QuotaExhaustedError as e:
                last_error = e
                wait_time = self.quota_retry_wait * (attempt + 1)  # 递增等待
                logger.warning(
                    "阶段 %s 限流 (第%d次), 等待 %ds: %s",
                    stage_name, attempt + 1, wait_time, e,
                )
                await asyncio.sleep(wait_time)
            except Exception as e:
                # 非限流错误直接抛出
                raise

        raise QuotaExhaustedError(f"阶段 {stage_name} 限流超过最大重试次数: {last_error}")

    # ─── 各阶段具体实现（包装现有服务）───

    async def _extract_text(self) -> dict:
        """阶段 1: 文案提取"""
        if not self.video_path or not os.path.exists(self.video_path):
            return {"text": "", "_summary": "无视频文件"}

        from backend.services.video_extractor import extract_video_text
        result = await extract_video_text(self.video_path)
        return {
            "text": result.get("text", ""),
            "source": result.get("source", ""),
            "_summary": f"文案提取: {result.get('source','')}, {len(result.get('text',''))}字",
        }

    async def _assess_text_risks(self, text: str) -> dict:
        """阶段 2: 文本风险评估"""
        from backend.services.risk_assessor import assess_risks
        from backend.services.transcript_detector import detect_transcript_quality
        from backend.services.text_splitter import split_text

        sentences = split_text(text)
        transcript_quality = await detect_transcript_quality(text, sentences)
        risk_results = await assess_risks(text, transcript_quality=transcript_quality)

        dimensions = risk_results.get("dimensions", [])
        return {
            "dimensions": dimensions,
            "risk_sentences": risk_results.get("risk_sentences", []),
            "transcript_quality": transcript_quality,
            "_llm_calls": 1,
            "_summary": f"风险评估: {len(dimensions)}个维度",
        }

    async def _match_signals(self, text: str) -> dict:
        """阶段 3: 信号关联"""
        try:
            from backend.services.signal_matcher import SignalMatcher
            matcher = SignalMatcher()
            result = await matcher.match(text)
            return {
                "matches": [{"title": m.title, "relevance": m.relevance_score} for m in result.matches],
                "_llm_calls": 0,
                "_summary": f"信号关联: {len(result.matches)}条匹配",
            }
        except Exception as e:
            return {"matches": [], "error": str(e), "_summary": "信号关联失败(降级)"}

    async def _analyze_entity_chain(self, text: str) -> dict:
        """阶段 4: 实体风险链"""
        try:
            from backend.services.entity_risk_chain import analyze_entity_risk_chain
            result = await analyze_entity_risk_chain(text)
            return {
                "chains": [{"source": c.source_entity, "score": c.total_risk_score} for c in (result.chains if result else [])],
                "_llm_calls": 1,
                "_summary": f"实体风险链: {len(result.chains) if result else 0}条",
            }
        except Exception as e:
            return {"chains": [], "error": str(e), "_summary": "实体风险链失败(降级)"}

    async def _simulate_platforms(self, text: str, stage_results: dict) -> dict:
        """阶段 5: 平台仿真"""
        from backend.services.agent_simulator import simulate_all_platforms_with_agents
        platform_results = await simulate_all_platforms_with_agents(text)
        return {
            "platforms": [
                {"platform": pr.get("platform", ""), "positive": pr.get("positive", 0), "negative": pr.get("negative", 0)}
                for pr in platform_results
            ],
            "_llm_calls": len(platform_results),
            "_summary": f"平台仿真: {len(platform_results)}个平台",
        }

    async def _detect_cross_modal(self, text: str, stage_results: dict) -> dict:
        """阶段 6: 跨模态检测"""
        try:
            from backend.services.cross_modal_detector import CrossModalConflictDetector
            detector = CrossModalConflictDetector()
            result = await detector.detect_conflicts(text=text)
            return {
                "conflict_score": result.get("overall_conflict_score", 0),
                "has_hidden_risk": result.get("has_hidden_risk", False),
                "_llm_calls": 1,
                "_summary": f"跨模态: 冲突分={result.get('overall_conflict_score', 0)}",
            }
        except Exception as e:
            return {"conflict_score": 0, "error": str(e), "_summary": "跨模态检测失败(降级)"}

    async def _analyze_fine_grained(self, video_path: str, stage_results: dict) -> dict:
        """阶段 7: 细粒度视频理解（最耗时，LLM 调用最多）"""
        try:
            from backend.services.fine_grained import FineGrainedPipeline

            pipeline = FineGrainedPipeline()
            report = await pipeline.analyze(video_path)

            return {
                "has_risk": report.has_fine_grained_risk,
                "risk_upgrade": report.risk_upgrade,
                "max_risk_level": report.max_risk_level,
                "key_findings": report.key_findings,
                "_llm_calls": 5,  # 估算：地图审核+代码溯源+敏感符号+时序异常+密集扫描
                "_summary": f"细粒度: risk_upgrade={report.risk_upgrade}, level={report.max_risk_level}",
            }
        except Exception as e:
            return {"has_risk": False, "error": str(e), "_summary": "细粒度分析失败(降级)"}

    async def _compile_report(self, text: str, stage_results: dict) -> dict:
        """阶段 8: 报告生成（汇总所有阶段结果）"""
        from backend.services.analyzer import calculate_overall_score, get_suggestion

        # 从各阶段结果中汇总
        risk_data = stage_results.get("text_risk_assessment", {})
        dimensions = risk_data.get("dimensions", [])

        overall_score, dimension_weights, cross_effects = calculate_overall_score(dimensions)
        suggestion = get_suggestion(overall_score)

        # 应用细粒度风险升级
        fine_grained = stage_results.get("fine_grained_video", {})
        if fine_grained.get("has_risk"):
            overall_score = min(100, overall_score + fine_grained.get("risk_upgrade", 0))

        risk_level = "green"
        if overall_score > 75:
            risk_level = "red"
        elif overall_score > 55:
            risk_level = "orange"
        elif overall_score > 25:
            risk_level = "yellow"

        return {
            "overall_score": overall_score,
            "risk_level": risk_level,
            "suggestion": suggestion,
            "dimensions": dimensions,
            "cross_effects": cross_effects,
            "_llm_calls": 0,
            "_summary": f"报告: 总分={overall_score}, 等级={risk_level}, 建议={suggestion}",
        }

    def get_status(self) -> dict:
        """获取当前分析状态"""
        if not self._checkpoint:
            self._checkpoint = self._checkpoint_mgr.load()

        if not self._checkpoint:
            return {"task_id": self.task_id, "status": "not_started"}

        return {
            "task_id": self.task_id,
            "status": self._checkpoint.overall_status,
            "progress": self._checkpoint.progress,
            "current_stage": self._checkpoint.next_pending_stage,
            "last_completed_stage": self._checkpoint.last_completed_stage,
            "total_llm_calls": self._checkpoint.total_llm_calls,
            "quota_exhausted_count": self._checkpoint.quota_exhausted_count,
            "stages": {
                name: {"status": s.status.value, "summary": s.summary}
                for name, s in self._checkpoint.stages.items()
            },
            "checkpoint_path": str(self._checkpoint_mgr.checkpoint_path),
        }
