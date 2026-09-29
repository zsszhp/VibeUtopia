from __future__ import annotations

"""事件切分器 —— 帧差/场景边界 + 语义密度启发式

不依赖大模型即可运行：视觉边界用帧差/描述/OCR 文本差异，
语义边界用转写片段的词汇重叠与停顿，最后 peak-picking 得事件边界。
"""

import logging
import re
from typing import Iterable, Optional

from backend.services.video_understanding.models import (
    Event,
    FrameObservation,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

# 主张/展示类词表——用于事件 kind 的启发分类（非风控定论）
CLAIM_MARKERS = (
    "自研", "原创", "我们开发", "我们做的", "自主研发", "完全自己",
    "保证", "绝对", "一定是", "肯定是", "不可能", "从未", "没有过",
)
DISPLAY_MARKERS = (
    "github", "gitee", "文件夹", "目录", "代码", "仓库", "repo",
    "地图", "截图", "界面", "后台", "数据", "文档", "论文",
)
# 否定/反转标记（叙事冲突启发用，此处也用于事件摘要标注）
NEGATION_MARKERS = (
    "不", "没", "无", "非", "否认", "澄清", "反转", "其实", "实际上", "假的", "错误",
)

DEFAULT_CONFIG = {
    "min_event_duration": 2.0,      # 最短事件时长（秒）
    "max_event_duration": 90.0,     # 超长事件强制再切
    "visual_boundary_quantile": 0.75,   # 帧差尖峰判定分位
    "asr_overlap_threshold": 0.12,      # 相邻转写片段词重叠低于此值视为话题切换
    "silence_gap_seconds": 1.2,         # 转写停顿超过该值视为边界候选
    "min_boundary_gap": 2.0,            # peak-picking 最小边界间隔
    "density_window_seconds": 4.0,      # 语义密度统计窗
}


def _tokenize(text: str) -> set:
    """中英混合粗切词：英文按词、中文按二元组，足够做重叠启发。"""
    if not text:
        return set()
    text = text.lower()
    tokens = set(re.findall(r"[a-z0-9_]+", text))
    han = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(han) - 1):
        tokens.add(han[i] + han[i + 1])
    tokens.update(han)
    return tokens


def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))


class EventSegmenter:
    """事件切分：帧差/场景边界 + 语义密度启发"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def segment(
        self,
        frames: Iterable[FrameObservation],
        transcript: Optional[Iterable[TranscriptSegment]] = None,
    ) -> list:
        """切分事件。frames 按时间戳升序；transcript 可为空。"""
        frames = sorted(list(frames or []), key=lambda f: f.timestamp)
        transcript = sorted(list(transcript or []), key=lambda s: s.start)

        if not frames and not transcript:
            return []

        candidates = self._boundary_candidates(frames, transcript)
        boundaries = self._peak_pick(candidates, frames, transcript)
        events = self._build_events(frames, transcript, boundaries)
        return events

    # ─── 边界候选打分 ───────────────────────────────────────

    def _boundary_candidates(self, frames: list, transcript: list) -> dict:
        """返回 {时间点: 边界分}，融合视觉差分与转写话题切换。"""
        scores: dict = {}

        def bump(t: float, value: float):
            if t is None or t < 0:
                return
            key = round(float(t), 2)
            scores[key] = max(scores.get(key, 0.0), float(value))

        # 视觉：帧差 / 描述差异 / OCR 差异
        if len(frames) >= 2:
            diffs = [max(0.0, f.diff_score) for f in frames]
            sorted_d = sorted(diffs)
            q = self.config["visual_boundary_quantile"]
            idx = min(len(sorted_d) - 1, max(0, int(q * (len(sorted_d) - 1))))
            threshold = sorted_d[idx]
            # 分位阈值过低时给一个绝对地板，避免平凡帧差也被当边界
            threshold = max(threshold, 0.15)
            for i in range(1, len(frames)):
                prev, cur = frames[i - 1], frames[i]
                delta = max(0.0, cur.diff_score)
                desc_flip = 1.0 if (
                    prev.description and cur.description
                    and prev.description.strip() != cur.description.strip()
                    and _overlap(_tokenize(prev.description), _tokenize(cur.description)) < 0.3
                ) else 0.0
                ocr_flip = 1.0 if (
                    prev.ocr_text and cur.ocr_text
                    and prev.ocr_text.strip() != cur.ocr_text.strip()
                    and _overlap(_tokenize(prev.ocr_text), _tokenize(cur.ocr_text)) < 0.3
                ) else 0.0
                visual_score = 0.0
                if delta >= threshold:
                    visual_score = min(1.0, delta / (threshold + 1e-6)) * 0.7 + 0.3
                if desc_flip or ocr_flip:
                    visual_score = max(visual_score, 0.55)
                if visual_score > 0:
                    bump(cur.timestamp, visual_score)

        # 语义：相邻转写片段话题切换 + 停顿
        for i in range(1, len(transcript)):
            prev, cur = transcript[i - 1], transcript[i]
            ov = _overlap(_tokenize(prev.text), _tokenize(cur.text))
            gap = cur.start - prev.end
            sem = 0.0
            if ov < self.config["asr_overlap_threshold"]:
                sem = 0.6 + 0.3 * (1.0 - ov)
            if gap >= self.config["silence_gap_seconds"]:
                sem = max(sem, 0.5)
            if sem > 0:
                bump(cur.start, sem)

        return scores

    def _peak_pick(self, candidates: dict, frames: list, transcript: list) -> list:
        """在候选分上 peak-picking，保证最小间隔，并强制首尾边界。"""
        min_gap = self.config["min_boundary_gap"]
        ordered = sorted(candidates.items(), key=lambda kv: (-kv[1], kv[0]))
        picked: list = []
        for t, s in ordered:
            if s <= 0:
                continue
            if all(abs(t - p) >= min_gap for p in picked):
                picked.append(t)
        picked.sort()

        # 首尾强制
        start_t = self._timeline_start(frames, transcript)
        end_t = self._timeline_end(frames, transcript)
        boundaries = [start_t]
        for t in picked:
            if t - boundaries[-1] >= min_gap and end_t - t >= min_gap * 0.5:
                boundaries.append(t)
        if end_t > boundaries[-1]:
            boundaries.append(end_t)
        return boundaries

    @staticmethod
    def _timeline_start(frames: list, transcript: list) -> float:
        cands = []
        if frames:
            cands.append(frames[0].timestamp)
        if transcript:
            cands.append(transcript[0].start)
        return min(cands) if cands else 0.0

    @staticmethod
    def _timeline_end(frames: list, transcript: list) -> float:
        cands = []
        if frames:
            cands.append(frames[-1].timestamp)
        if transcript:
            cands.append(transcript[-1].end)
        return max(cands) if cands else 0.0

    # ─── 事件构建 ───────────────────────────────────────────

    def _build_events(self, frames: list, transcript: list, boundaries: list) -> list:
        events: list = []
        min_dur = self.config["min_event_duration"]
        max_dur = self.config["max_event_duration"]

        raw_spans = []
        for i in range(len(boundaries) - 1):
            raw_spans.append((boundaries[i], boundaries[i + 1]))
        # 超长事件强制均分再切
        spans: list = []
        for s, e in raw_spans:
            if e - s > max_dur:
                n = int((e - s) // max_dur) + 1
                step = (e - s) / n
                for k in range(n):
                    spans.append((s + k * step, s + (k + 1) * step))
            else:
                spans.append((s, e))

        # 过短事件并入前一个
        merged: list = []
        for s, e in spans:
            if merged and (e - s) < min_dur:
                merged[-1] = (merged[-1][0], e)
            elif merged and (s - merged[-1][1]) < 1e-6 and (e - merged[-1][0]) < min_dur:
                merged[-1] = (merged[-1][0], e)
            else:
                merged.append((s, e))

        for idx, (s, e) in enumerate(merged):
            ev_frames = [f for f in frames if s - 1e-6 <= f.timestamp < e - 1e-6 or (idx == len(merged) - 1 and abs(f.timestamp - e) < 1e-6)]
            # 边界帧归到后一事件，但首帧归首事件
            if idx > 0:
                ev_frames = [f for f in frames if s - 1e-6 <= f.timestamp < e + 1e-6]
                if ev_frames and abs(ev_frames[0].timestamp - s) < 1e-6:
                    pass
            ev_trans = [
                t for t in transcript
                if t.start < e - 1e-6 and t.end > s + 1e-6
            ]
            kind = self._classify_kind(ev_frames, ev_trans)
            density = self._semantic_density(ev_frames, ev_trans, e - s)
            anchors = self._pick_anchors(ev_frames, ev_trans)
            events.append(Event(
                event_id=f"E{idx + 1}",
                start=round(s, 3),
                end=round(e, 3),
                kind=kind,
                score=round(min(1.0, density), 3),
                anchors=anchors,
                summary=self._summarize(kind, ev_frames, ev_trans),
                density=round(density, 3),
                modalities=self._modalities(ev_frames, ev_trans),
            ))
        return events

    @staticmethod
    def _classify_kind(frames: list, trans: list) -> str:
        text_blob = " ".join(t.text for t in trans) + " " + " ".join(
            (f.ocr_text or "") + " " + (f.description or "") for f in frames
        ).lower()
        has_claim = any(m in text_blob for m in CLAIM_MARKERS)
        has_display = any(m in text_blob.lower() for m in DISPLAY_MARKERS)
        if has_claim and has_display:
            return "claim"
        if has_display and (not trans or not any(t.text.strip() for t in trans)):
            return "display"
        if has_claim and trans:
            return "claim"
        if trans and frames:
            return "speech_act"
        if trans:
            return "speech_act"
        if has_display:
            return "display"
        # 纯视觉：帧差大视作动作，否则场景
        mean_diff = sum(max(0.0, f.diff_score) for f in frames) / max(1, len(frames))
        return "action" if mean_diff >= 0.3 else "scene"

    def _semantic_density(self, frames: list, trans: list, duration: float) -> float:
        """语义密度启发：视觉新颖度 + OCR 信息量 + 转写信息量 + 异常尖峰。"""
        if not frames and not trans:
            return 0.0
        novelty = 0.0
        anomaly = 0.0
        ocr_info = 0.0
        if frames:
            diffs = [max(0.0, f.diff_score) for f in frames]
            novelty = min(1.0, sum(diffs) / len(frames))
            anomaly = min(1.0, max(diffs))
            ocr_tokens = set()
            for f in frames:
                ocr_tokens |= _tokenize(f.ocr_text)
            ocr_info = min(1.0, len(ocr_tokens) / 20.0)
        asr_info = 0.0
        if trans:
            tokens = set()
            for t in trans:
                tokens |= _tokenize(t.text)
            asr_info = min(1.0, len(tokens) / 40.0)
        dur_factor = 0.5 if duration <= 0 else min(1.0, (self.config["density_window_seconds"] / max(duration, 1e-6)))
        density = 0.3 * novelty + 0.2 * ocr_info + 0.25 * asr_info + 0.25 * anomaly
        # 信息密度随过长事件摊薄
        density *= (0.6 + 0.4 * dur_factor)
        return max(0.0, min(1.0, density))

    @staticmethod
    def _pick_anchors(frames: list, trans: list) -> list:
        anchors: list = []
        if frames:
            # 首帧 + 帧差最大帧
            anchors.append(frames[0].frame_id or f"t{frames[0].timestamp}")
            peak = max(frames, key=lambda f: max(0.0, f.diff_score))
            pid = peak.frame_id or f"t{peak.timestamp}"
            if pid not in anchors:
                anchors.append(pid)
        if trans and not anchors:
            anchors.append(f"t{trans[0].start}")
        return anchors

    @staticmethod
    def _summarize(kind: str, frames: list, trans: list) -> str:
        parts = []
        if trans:
            joined = "；".join(t.text.strip() for t in trans if t.text.strip())[:60]
            if joined:
                parts.append(f"口播:{joined}")
        ocr = " ".join(f.ocr_text.strip() for f in frames if f.ocr_text.strip())[:40]
        if ocr:
            parts.append(f"画面字:{ocr}")
        if not parts:
            parts.append(f"纯视觉片段({len(frames)}帧)")
        return f"[{kind}] " + " | ".join(parts)

    @staticmethod
    def _modalities(frames: list, trans: list) -> list:
        mods = []
        if frames:
            mods.append("visual")
            if any(f.ocr_text.strip() for f in frames):
                mods.append("ocr")
            if any(f.description.strip() for f in frames):
                mods.append("description")
        if trans:
            mods.append("asr")
        return mods
