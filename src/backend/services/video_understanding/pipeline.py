from __future__ import annotations

"""事件级视频理解管线 —— 串接切分 / 选帧 / 冲突 / 语用(L6) / 涌现(L7)

输入帧序列（时间戳 + 可选描述/OCR）与转写，输出事件级摘要、
选帧理由、叙事语用线索与风险涌现分，供主流程写入分析结果
（events_summary / selected_frame_reasons / narrative_pragmatics / emergence_summary）。
全程离线可跑；LLM 增强可选且失败降级。
"""

import logging
from typing import Iterable, Optional

from backend.services.video_understanding.anchor_selector import AnchorSelector
from backend.services.video_understanding.event_segmenter import EventSegmenter
from backend.services.video_understanding.models import (
    EventUnderstandingResult,
    FrameObservation,
    TranscriptSegment,
)
from backend.services.video_understanding.narrative_conflict import NarrativeConflictDetector
from backend.services.video_understanding.narrative_pragmatics import NarrativePragmaticsAnalyzer
from backend.services.video_understanding.risk_emergence import RiskEmergenceScorer, build_risk_atoms

logger = logging.getLogger(__name__)


class VideoEventUnderstandingPipeline:
    """事件级理解编排：EventSegmenter → AnchorSelector → NarrativeConflictDetector
    → NarrativePragmaticsAnalyzer(L6) → RiskEmergenceScorer(L7)"""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.segmenter = EventSegmenter(config.get("segmenter"))
        self.selector = AnchorSelector(config.get("selector"))
        self.conflict_detector = NarrativeConflictDetector(config.get("conflict"))
        self.pragmatics_analyzer = NarrativePragmaticsAnalyzer(config.get("pragmatics"))
        self.emergence_scorer = RiskEmergenceScorer(config.get("emergence"))

    async def run(
        self,
        frames: Iterable[FrameObservation],
        transcript: Iterable[TranscriptSegment] | str = (),
        frame_budget: Optional[int] = None,
    ) -> EventUnderstandingResult:
        """运行事件级理解。

        Args:
            frames: 帧观测序列（可空——仅转写时仍可做事件切分）
            transcript: 转写片段列表，或纯文本（无时间戳时整体作为单段）
            frame_budget: 选帧预算（默认取 selector 配置）
        """
        result = EventUnderstandingResult()
        try:
            segments = self._normalize_transcript(transcript)
            obs = self._normalize_frames(frames)

            if not obs and not segments:
                result.degraded = True
                result.degrade_reason = "empty_input"
                return result

            events = self.segmenter.segment(obs, segments)
            selected = self.selector.select(obs, events, budget=frame_budget)
            conflicts = await self.conflict_detector.detect(segments, obs)
            pragmatics = await self.pragmatics_analyzer.analyze(segments, obs, events)
            atoms = build_risk_atoms(
                events, conflicts, pragmatics, obs,
                config=self.emergence_scorer.config,
            )
            emergence = self.emergence_scorer.aggregate(
                atoms, conflicts=conflicts, pragmatics=pragmatics, frames=obs, events=events,
            )

            result.events = events
            result.selected_frames = selected
            result.conflicts = conflicts
            result.narrative_pragmatics = pragmatics
            result.emergence_summary = emergence
            result.events_summary = [self._event_summary(e) for e in events]
            result.selected_frame_reasons = [
                {
                    "frame_id": s.frame_id,
                    "timestamp": s.timestamp,
                    "image_path": s.image_path,
                    "reason": s.reason,
                    "score": s.score,
                    "event_id": s.event_id,
                }
                for s in selected
            ]
            result.method_used = "heuristic_segmenter+anchor_selector+rule_conflict+rule_pragmatics+phi_emergence"
            if self.conflict_detector.config.get("enable_llm") or self.pragmatics_analyzer.config.get("enable_llm"):
                result.method_used += "+llm_enhance"
        except Exception as e:
            logger.warning("事件级理解失败(降级): %s", e)
            result.degraded = True
            result.degrade_reason = str(e)
        return result

    @staticmethod
    def _normalize_frames(frames) -> list:
        out: list = []
        for f in (frames or []):
            if isinstance(f, FrameObservation):
                out.append(f)
            elif isinstance(f, dict):
                out.append(FrameObservation(
                    timestamp=float(f.get("timestamp", 0.0)),
                    frame_id=str(f.get("frame_id", "")),
                    image_path=str(f.get("image_path", "")),
                    description=str(f.get("description", "")),
                    ocr_text=str(f.get("ocr_text", "")),
                    diff_score=float(f.get("diff_score", 0.0)),
                    source=str(f.get("source", "")),
                ))
            elif isinstance(f, (list, tuple)) and len(f) >= 2:
                out.append(FrameObservation(timestamp=float(f[0]), diff_score=float(f[1])))
        out.sort(key=lambda x: x.timestamp)
        return out

    @staticmethod
    def _normalize_transcript(transcript) -> list:
        if not transcript:
            return []
        if isinstance(transcript, str):
            text = transcript.strip()
            if not text:
                return []
            # 无时间戳文本按句切分并均摊时长，保证切分器有时序可用
            import re
            parts = [p.strip() for p in re.split(r"[。！？!?\n；;]+", text) if p.strip()]
            if not parts:
                parts = [text]
            seg_len = 3.0
            return [
                TranscriptSegment(start=i * seg_len, end=(i + 1) * seg_len, text=p)
                for i, p in enumerate(parts)
            ]
        out: list = []
        for seg in transcript:
            if isinstance(seg, TranscriptSegment):
                out.append(seg)
            elif isinstance(seg, dict):
                out.append(TranscriptSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=str(seg.get("text", "")),
                ))
            elif isinstance(seg, str):
                out.append(TranscriptSegment(start=0.0, end=0.0, text=seg))
        out.sort(key=lambda s: s.start)
        return out

    @staticmethod
    def _event_summary(event) -> dict:
        return {
            "event_id": event.event_id,
            "start": event.start,
            "end": event.end,
            "kind": event.kind,
            "score": event.score,
            "density": event.density,
            "anchors": list(event.anchors),
            "summary": event.summary,
            "modalities": list(event.modalities),
        }


async def run_event_understanding(
    frames,
    transcript,
    frame_budget: Optional[int] = None,
    config: Optional[dict] = None,
) -> EventUnderstandingResult:
    """模块级便捷入口。"""
    pipeline = VideoEventUnderstandingPipeline(config=config)
    return await pipeline.run(frames, transcript, frame_budget=frame_budget)


def frames_from_delta_frames(delta_frames) -> list:
    """把 DeltaFrameExtractor 产出的帧对象转成 FrameObservation（只取元数据，不碰图像）。"""
    out = []
    for f in (delta_frames or []):
        ts = float(getattr(f, "timestamp", 0.0) or 0.0)
        out.append(FrameObservation(
            timestamp=ts,
            frame_id=str(getattr(f, "frame_id", "") or getattr(f, "index", "") or f"t{ts}"),
            image_path=str(getattr(f, "file_path", "") or getattr(f, "image_path", "") or ""),
            diff_score=float(getattr(f, "delta_score", 0.0) or getattr(f, "diff_score", 0.0) or 0.0),
            source="delta",
        ))
    return out
