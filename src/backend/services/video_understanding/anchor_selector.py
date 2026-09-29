from __future__ import annotations

"""自适应锚点选帧 —— 替代均匀 1fps 一把梭

强制保留：事件边界、高密度窗、差异尖峰；剩余预算按语义密度
分配，并用覆盖度约束防止时间盲区。每个选中帧带 reason 元数据。
"""

import logging
from typing import Iterable, Optional

from backend.services.video_understanding.models import (
    Event,
    FrameObservation,
    SelectedFrame,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "budget": 60,                  # 默认选帧预算
    "anchor_budget_ratio": 0.4,    # 强制锚点至少占预算比例（设计 P0 §5.4）
    "spike_zscore": 1.5,           # 帧差尖峰判定：均值 + z*std
    "density_window_seconds": 4.0,
    "coverage_gap_seconds": 30.0,  # 覆盖度约束：任意 30s 窗至少 1 帧
    "max_per_event": 8,
    "time_match_epsilon": 0.51,    # 时间戳对齐容差
}


class AnchorSelector:
    """语义密度驱动的自适应选帧"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def select(
        self,
        frames: Iterable[FrameObservation],
        events: Iterable[Event],
        budget: Optional[int] = None,
    ) -> list:
        """返回按时间排序的 SelectedFrame 列表，每项含 reason。"""
        frames = sorted(list(frames or []), key=lambda f: f.timestamp)
        events = list(events or [])
        budget = int(budget or self.config["budget"])
        if not frames:
            return []
        budget = max(1, min(budget, len(frames)))

        forced: list = []   # list[tuple[FrameObservation, reason, score, event_id]]
        forced += self._boundary_anchors(frames, events)
        forced += self._spike_anchors(frames, events)
        forced += self._density_anchors(frames, events)

        picked: dict = {}   # frame_id/timestamp key -> SelectedFrame

        def key_of(f: FrameObservation):
            return f.frame_id or f"t{round(f.timestamp, 3)}"

        def add(f: FrameObservation, reason: str, score: float, event_id: str):
            k = key_of(f)
            if k in picked:
                # 同帧多理由时保留更高分，reason 追加
                old = picked[k]
                if score > old.score:
                    old.score = round(score, 3)
                if reason not in old.reason.split("+"):
                    old.reason = old.reason + "+" + reason
                return
            picked[k] = SelectedFrame(
                timestamp=f.timestamp,
                frame_id=f.frame_id,
                image_path=f.image_path,
                reason=reason,
                score=round(score, 3),
                event_id=event_id,
            )

        # 1) 强制锚点全部保留
        for f, reason, score, ev_id in forced:
            add(f, reason, score, ev_id)

        # 2) 剩余预算按密度启发排序补足（确定性 top-k，离线可复现）
        remain = budget - len(picked)
        if remain > 0:
            ranked = self._rank_by_density(frames, events)
            for f, score, ev_id, reason in ranked:
                if remain <= 0:
                    break
                k = key_of(f)
                if k in picked:
                    continue
                add(f, reason, score, ev_id)
                remain -= 1

        # 3) 覆盖度约束
        selected_list = list(picked.values())
        gaps = self._find_coverage_gaps(frames, selected_list)
        for f, ev_id in gaps:
            add(f, "coverage", 0.2, ev_id)

        result = sorted(picked.values(), key=lambda s: s.timestamp)
        logger.debug(
            "选帧完成: 输入=%d, 选中=%d, 强制=%d",
            len(frames), len(result), len(forced),
        )
        return result

    # ─── 强制锚点 ───────────────────────────────────────────

    def _boundary_anchors(self, frames: list, events: list) -> list:
        """事件边界强制选帧。"""
        out = []
        eps = self.config["time_match_epsilon"]
        for ev in events:
            for t, tag in ((ev.start, "start"), (ev.end, "end")):
                f = self._nearest_frame(frames, t, eps)
                if f is not None:
                    score = 0.7 + 0.3 * max(0.0, min(1.0, ev.score))
                    out.append((f, "event_boundary", score, ev.event_id))
        return out

    def _spike_anchors(self, frames: list, events: list) -> list:
        """帧差尖峰强制选帧（短暂画面/闪现高概率落点）。"""
        diffs = [max(0.0, f.diff_score) for f in frames]
        if len(diffs) < 3:
            return []
        mean = sum(diffs) / len(diffs)
        var = sum((d - mean) ** 2 for d in diffs) / len(diffs)
        std = var ** 0.5
        threshold = mean + self.config["spike_zscore"] * std
        # 极小方差时不误伤：要求绝对差也够大
        if std < 1e-9 and threshold <= 0.15:
            return []
        out = []
        for f in frames:
            d = max(0.0, f.diff_score)
            if d >= max(threshold, 0.15) and d > mean:
                out.append((f, "diff_spike", min(1.0, 0.5 + 0.5 * d), self._event_id_at(events, f.timestamp)))
        return out

    def _density_anchors(self, frames: list, events: list) -> list:
        """高密度窗强制选帧：每个高密度事件内取密度最高帧。"""
        out = []
        if not events:
            return sorted(frames, key=lambda f: -max(0.0, f.diff_score))[:3] and [
                (f, "high_density", 0.5, "") for f in sorted(frames, key=lambda f: -max(0.0, f.diff_score))[:3]
            ]
        ranked = sorted(events, key=lambda e: -e.score)
        top_n = max(1, min(5, len(ranked)))
        for ev in ranked[:top_n]:
            if ev.score <= 0:
                continue
            inner = [f for f in frames if ev.start - 1e-6 <= f.timestamp <= ev.end + 1e-6]
            if not inner:
                continue
            peak = max(inner, key=lambda f: max(0.0, f.diff_score))
            out.append((peak, "high_density", 0.5 + 0.5 * ev.score, ev.event_id))
        return out

    def _rank_by_density(self, frames: list, events: list) -> list:
        """非强制帧按 窗密度×帧差 排序，返回 (frame, score, event_id, reason)。"""
        win = self.config["density_window_seconds"]
        scored = []
        for f in frames:
            ev_id = self._event_id_at(events, f.timestamp)
            ev = next((e for e in events if e.event_id == ev_id), None)
            local_density = ev.score if ev else 0.0
            # 局部窗密度：邻近帧差均值
            near = [max(0.0, g.diff_score) for g in frames if abs(g.timestamp - f.timestamp) <= win / 2]
            local = sum(near) / max(1, len(near))
            score = 0.55 * local_density + 0.45 * min(1.0, max(0.0, f.diff_score) + local * 0.5)
            scored.append((f, score, ev_id, "budget_fill"))
        scored.sort(key=lambda x: (-x[1], x[0].timestamp))
        return scored

    # ─── 覆盖度 ─────────────────────────────────────────────

    def _find_coverage_gaps(self, frames: list, selected: list) -> list:
        """任意 coverage_gap 秒窗内至少 1 帧，缺则补该窗差分最大帧。"""
        if not frames:
            return []
        gap = self.config["coverage_gap_seconds"]
        t0 = frames[0].timestamp
        t1 = frames[-1].timestamp
        selected_times = [s.timestamp for s in selected]
        out = []
        t = t0
        while t < t1 - 1e-6:
            window_end = min(t + gap, t1 + 1e-6)
            hit = any(t - 1e-6 <= st < window_end - 1e-6 for st in selected_times)
            if not hit:
                inner = [f for f in frames if t - 1e-6 <= f.timestamp < window_end + 1e-6]
                if inner:
                    best = max(inner, key=lambda f: max(0.0, f.diff_score))
                    out.append((best, ""))
            t = window_end
        return out

    # ─── 工具 ───────────────────────────────────────────────

    @staticmethod
    def _nearest_frame(frames: list, t: float, eps: float) -> Optional[FrameObservation]:
        best = None
        best_dt = None
        for f in frames:
            dt = abs(f.timestamp - t)
            if dt <= eps and (best_dt is None or dt < best_dt):
                best, best_dt = f, dt
        return best

    @staticmethod
    def _event_id_at(events: list, t: float) -> str:
        for ev in events:
            if ev.start - 1e-6 <= t <= ev.end + 1e-6:
                return ev.event_id
        return ""
