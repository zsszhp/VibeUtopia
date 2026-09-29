from __future__ import annotations

"""风险涌现函数 Φ 最小版（L7）

事件级风险原子聚合为全局内容风险分：

    R = clip( base + emergent , 0, 100 )
    base     = Σ w(type_i) · severity_i · conf_i          # 风险原子加权和
    emergent = λc·conflict_amplify + λp·narrative_pragmatic + λf·short_flash

    conflict_amplify = max(0, max_pair_conflict − mean_atom_risk)

反伪精确：输出分数区间 + 置信分解（detect/confirm/context/provenance），
不给单点伪精确结论；置信不足时只给"线索"级别，不得进入自动定级。
"""

import logging
from typing import Iterable, Optional

from backend.services.video_understanding.models import RiskAtom

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    # base 侧：风险原子类型权重（加权和，clip 到 100）
    "atom_weights": {
        "modality_conflict": 0.35,
        "narrative_pragmatic": 0.30,
        "claim_exposure": 0.25,
        "short_flash": 0.15,
    },
    # emergent 侧：涌现加权（与设计 §5.8 λ 项对应，短闪现替代历史模式项）
    "lambda_conflict": 0.35,
    "lambda_pragmatic": 0.30,
    "lambda_flash": 0.20,
    # 短闪现启发
    "flash_diff_threshold": 0.45,
    "flash_margin": 0.25,
    "flash_neighbor_window": 2.5,
    "flash_neighbor_max_mean": 0.20,
    "flash_event_max_duration": 2.5,
    # 区间宽度：置信越低区间越宽（上限 45 分）
    "interval_max_width": 45.0,
    "interval_base_width": 5.0,
}


def build_risk_atoms(
    events: Iterable = (),
    conflicts: Iterable = (),
    pragmatics: Iterable = (),
    frames: Iterable = (),
    config: Optional[dict] = None,
) -> list:
    """把事件级信号收成风险原子（可回溯时间轴，非最终定级）。"""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    atoms: list = []
    seq = 0

    def add(atom_type, start, end, severity, confidence, evidence, explanation, event_id=""):
        nonlocal seq
        seq += 1
        atoms.append(RiskAtom(
            atom_id=f"ra{seq:03d}",
            atom_type=atom_type,
            event_id=event_id,
            start=float(start),
            end=float(end),
            severity=max(0.0, min(1.0, float(severity))),
            confidence=max(0.0, min(1.0, float(confidence))),
            evidence=list(evidence or []),
            explanation=explanation,
        ))

    def covering_event_id(start: float, end: float) -> str:
        for ev in events:
            if getattr(ev, "end", -1) < start or getattr(ev, "start", 1e18) > end:
                continue
            return getattr(ev, "event_id", "") or ""
        return ""

    for c in (conflicts or []):
        add(
            "modality_conflict", c.start, c.end,
            severity=c.score, confidence=c.confidence,
            evidence=c.evidence, explanation=c.explanation,
            event_id=covering_event_id(c.start, c.end),
        )

    for p in (pragmatics or []):
        add(
            "narrative_pragmatic", p.start, p.end,
            severity=p.score, confidence=p.confidence,
            evidence=p.evidence, explanation=p.explanation,
            event_id=(p.trigger_events[0] if getattr(p, "trigger_events", None) else covering_event_id(p.start, p.end)),
        )

    for flash in short_flash_indicators(frames, events=events, config=cfg):
        add(
            "short_flash", flash["start"], flash["end"],
            severity=flash["intensity"], confidence=flash["confidence"],
            evidence=flash["evidence"], explanation=flash["explanation"],
            event_id=flash.get("event_id", ""),
        )

    return atoms


def short_flash_indicators(frames: Iterable, events: Iterable = (), config: Optional[dict] = None) -> list:
    """短闪现启发：孤立帧差尖峰 + 超短高显著事件。

    对应设计「B. 时间结构涌现」的最小可测子集（3 帧闪现/关键帧故意短暂）。
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    out: list = []
    frames = sorted(list(frames or []), key=lambda f: f.timestamp)
    win = cfg["flash_neighbor_window"]

    for i, f in enumerate(frames):
        diff = float(getattr(f, "diff_score", 0.0) or 0.0)
        if diff < cfg["flash_diff_threshold"]:
            continue
        neighbors = [
            float(getattr(o, "diff_score", 0.0) or 0.0)
            for j, o in enumerate(frames)
            if j != i and abs(o.timestamp - f.timestamp) <= win
        ]
        mean_nb = sum(neighbors) / len(neighbors) if neighbors else 0.0
        if neighbors and mean_nb > cfg["flash_neighbor_max_mean"]:
            continue
        if neighbors and diff < mean_nb + cfg["flash_margin"]:
            continue
        intensity = max(0.0, min(1.0, diff))
        out.append({
            "start": float(f.timestamp),
            "end": float(f.timestamp),
            "intensity": intensity,
            # 无邻域对照时降低置信，避免单帧绝对定罪
            "confidence": 0.6 if neighbors else 0.45,
            "explanation": "孤立帧差尖峰，疑似短暂闪现画面（短闪现线索）",
            "evidence": [{
                "modality": "visual",
                "span": [f.timestamp, f.timestamp],
                "frame_id": getattr(f, "frame_id", ""),
                "diff_score": diff,
                "neighbor_mean": round(mean_nb, 3),
            }],
            "event_id": "",
        })

    for ev in (events or []):
        dur = float(getattr(ev, "end", 0.0)) - float(getattr(ev, "start", 0.0))
        score = float(getattr(ev, "score", 0.0) or 0.0)
        if dur <= 0 or dur > cfg["flash_event_max_duration"] or score < 0.6:
            continue
        # 已有同窗帧级闪现则不重复计
        if any(abs(o["start"] - ev.start) < 1.0 for o in out):
            for o in out:
                if abs(o["start"] - ev.start) < 1.0 and not o.get("event_id"):
                    o["event_id"] = getattr(ev, "event_id", "")
            continue
        out.append({
            "start": float(ev.start),
            "end": float(ev.end),
            "intensity": max(0.0, min(1.0, score)),
            "confidence": 0.5,
            "explanation": "超短高显著事件，疑似故意短暂呈现（短闪现线索）",
            "evidence": [{
                "modality": "event",
                "span": [ev.start, ev.end],
                "event_id": getattr(ev, "event_id", ""),
                "duration": round(dur, 3),
            }],
            "event_id": getattr(ev, "event_id", ""),
        })
    return out


class RiskEmergenceScorer:
    """涌现聚合 Φ：base 加权和 + emergent 交互项，带区间与置信分解"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.weights = dict(DEFAULT_CONFIG["atom_weights"])
        if config and isinstance(config.get("atom_weights"), dict):
            self.weights.update(config["atom_weights"])

    def aggregate(
        self,
        atoms: Iterable[RiskAtom],
        conflicts: Iterable = (),
        pragmatics: Iterable = (),
        frames: Iterable = (),
        events: Iterable = (),
    ) -> dict:
        """返回 emergence_summary（反伪精确：点分 + 区间 + 置信分解）。"""
        atoms = list(atoms or [])
        conflicts = list(conflicts or [])
        pragmatics = list(pragmatics or [])
        frames = list(frames or [])
        events = list(events or [])

        base = self._base_score(atoms)
        components = self._emergent_components(atoms, conflicts, pragmatics, frames)
        emergent = (
            self.config["lambda_conflict"] * components["conflict_amplify"]
            + self.config["lambda_pragmatic"] * components["narrative_pragmatic"]
            + self.config["lambda_flash"] * components["short_flash"]
        ) * 100.0
        score = max(0.0, min(100.0, base + emergent))

        confidence = self._confidence_decomposition(atoms, frames, events)
        half_width = self._interval_half_width(confidence["conf_total"])
        interval = [
            max(0.0, score - half_width),
            min(100.0, score + half_width),
        ]

        return {
            "risk_score": round(score, 2),
            "risk_interval": [round(interval[0], 2), round(interval[1], 2)],
            "base_score": round(base, 2),
            "emergent_score": round(emergent, 2),
            "components": {k: round(v, 4) for k, v in components.items()},
            "weights": {
                "atom_weights": dict(self.weights),
                "lambda_conflict": self.config["lambda_conflict"],
                "lambda_pragmatic": self.config["lambda_pragmatic"],
                "lambda_flash": self.config["lambda_flash"],
            },
            "confidence": confidence,
            "confidence_label": self._confidence_label(confidence["conf_total"]),
            "risk_level": self._risk_level(score),
            "risk_atoms": [
                {
                    "atom_id": a.atom_id,
                    "atom_type": a.atom_type,
                    "event_id": a.event_id,
                    "start": a.start,
                    "end": a.end,
                    "severity": round(a.severity, 3),
                    "confidence": round(a.confidence, 3),
                    "explanation": a.explanation,
                }
                for a in atoms
            ],
            "atom_count": len(atoms),
            "method": "phi_min_base_plus_emergent",
        }

    # ─── base：风险原子加权和 ────────────────────────────────

    def _base_score(self, atoms: list) -> float:
        total = 0.0
        for a in atoms:
            w = self.weights.get(a.atom_type, 0.2)
            total += w * a.severity * a.confidence
        return max(0.0, min(100.0, total * 100.0))

    # ─── emergent 三项 ───────────────────────────────────────

    def _emergent_components(self, atoms: list, conflicts: list, pragmatics: list, frames: list) -> dict:
        # conflict_amplify = max(0, max_pair_conflict − mean_atom_risk)
        # mean_atom_risk 只统计非冲突原子：冲突本身抬高均值会抵消放大项，
        # 破坏「冲突↑ → emergent↑」的单调性。
        max_pair_conflict = max((float(getattr(c, "score", 0.0) or 0.0) for c in conflicts), default=0.0)
        baseline = [
            a.severity * a.confidence
            for a in atoms
            if a.atom_type != "modality_conflict"
        ]
        mean_atom_risk = (sum(baseline) / len(baseline)) if baseline else 0.0
        conflict_amplify = max(0.0, max_pair_conflict - mean_atom_risk)

        narrative_pragmatic = max(
            (float(getattr(p, "score", 0.0) or 0.0) * float(getattr(p, "confidence", 0.5) or 0.5)
             for p in pragmatics),
            default=0.0,
        )

        flash_flags = short_flash_indicators(frames, config=self.config)
        short_flash = max((float(f["intensity"]) * float(f["confidence"]) for f in flash_flags), default=0.0)

        return {
            "conflict_amplify": max(0.0, min(1.0, conflict_amplify)),
            "narrative_pragmatic": max(0.0, min(1.0, narrative_pragmatic)),
            "short_flash": max(0.0, min(1.0, short_flash)),
            "max_pair_conflict": round(max_pair_conflict, 4),
            "mean_atom_risk": round(mean_atom_risk, 4),
        }

    # ─── 置信分解（反伪精确）─────────────────────────────────

    @staticmethod
    def _confidence_decomposition(atoms: list, frames: list, events: list) -> dict:
        if atoms:
            conf_detect = sum(a.confidence for a in atoms) / len(atoms)
        else:
            conf_detect = 0.5

        # 未确认 = 0.5 中性，不假装 1.0；多模态证据交叉才给上浮
        modalities = set()
        for a in atoms:
            for e in a.evidence:
                if isinstance(e, dict) and e.get("modality"):
                    modalities.add(e["modality"])
        conf_confirm = 0.65 if len(modalities) >= 2 else 0.5

        has_asr = bool(events) or bool(atoms)
        has_visual = bool(frames)
        if has_asr and has_visual:
            conf_context = 0.9
        elif has_asr or has_visual:
            conf_context = 0.7
        else:
            conf_context = 0.4

        if not atoms:
            conf_provenance = 0.5
        else:
            with_locator = 0
            for a in atoms:
                if any(
                    isinstance(e, dict) and (e.get("frame_id") or e.get("span") or e.get("modality") != "llm")
                    for e in a.evidence
                ):
                    with_locator += 1
            ratio = with_locator / len(atoms)
            conf_provenance = 0.5 + 0.5 * ratio

        conf_total = conf_detect * conf_confirm * conf_context * conf_provenance
        return {
            "conf_detect": round(conf_detect, 3),
            "conf_confirm": round(conf_confirm, 3),
            "conf_context": round(conf_context, 3),
            "conf_provenance": round(conf_provenance, 3),
            "conf_total": round(conf_total, 3),
        }

    def _interval_half_width(self, conf_total: float) -> float:
        width = self.config["interval_base_width"] + (1.0 - max(0.0, min(1.0, conf_total))) * self.config["interval_max_width"]
        return max(self.config["interval_base_width"], min(self.config["interval_max_width"], width))

    @staticmethod
    def _confidence_label(conf_total: float) -> str:
        if conf_total >= 0.75:
            return "高置信结论"
        if conf_total >= 0.5:
            return "疑似，建议人工复核"
        return "线索"

    @staticmethod
    def _risk_level(score: float) -> str:
        if score > 75:
            return "red"
        if score > 55:
            return "orange"
        if score > 25:
            return "yellow"
        return "green"
