from __future__ import annotations

"""事件级视频理解 —— 数据模型

帧降级为证据原子，事件（Event）是推理基本单位。
所有时间量单位为秒，span 一律闭开区间 [start, end)。
"""

from dataclasses import dataclass, field


@dataclass
class FrameObservation:
    """帧观测——帧序列输入的统一形态（可来自密扫/Delta/关键帧）"""
    timestamp: float = 0.0
    frame_id: str = ""
    image_path: str = ""
    description: str = ""
    ocr_text: str = ""
    diff_score: float = 0.0
    source: str = ""


@dataclass
class TranscriptSegment:
    """转写片段——带时间定位的口播文本"""
    start: float = 0.0
    end: float = 0.0
    text: str = ""


@dataclass
class Event:
    """事件节点——理解与风险推理的基本单位"""
    event_id: str = ""
    start: float = 0.0
    end: float = 0.0
    kind: str = "scene"          # scene / action / claim / display / speech_act
    score: float = 0.0           # 事件显著性 0-1
    anchors: list = field(default_factory=list)   # 锚点帧 id
    summary: str = ""
    density: float = 0.0         # 语义密度启发分
    modalities: list = field(default_factory=list)


@dataclass
class SelectedFrame:
    """选中帧元数据——reason 供 UI 证据下钻"""
    timestamp: float = 0.0
    frame_id: str = ""
    image_path: str = ""
    reason: str = ""    # event_boundary / high_density / diff_spike / coverage / budget_fill
    score: float = 0.0
    event_id: str = ""


@dataclass
class NarrativeConflict:
    """叙事冲突线索——只给线索与置信，不自动定罪"""
    kind: str = ""      # polarity_reversal / ocr_asr_mismatch / claim_contradiction
    start: float = 0.0
    end: float = 0.0
    score: float = 0.0
    evidence: list = field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.5


@dataclass
class EventUnderstandingResult:
    """事件级理解总结果"""
    events: list = field(default_factory=list)
    selected_frames: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    events_summary: list = field(default_factory=list)
    selected_frame_reasons: list = field(default_factory=list)
    method_used: str = "heuristic"
    degraded: bool = False
    degrade_reason: str = ""

    def to_output_dict(self) -> dict:
        """分析输出的新增字段（只增不删，保持 API 兼容）"""
        return {
            "events_summary": self.events_summary,
            "selected_frame_reasons": self.selected_frame_reasons,
            "narrative_conflicts": [
                {
                    "kind": c.kind,
                    "start": c.start,
                    "end": c.end,
                    "score": c.score,
                    "evidence": c.evidence,
                    "explanation": c.explanation,
                    "confidence": c.confidence,
                }
                for c in self.conflicts
            ],
            "event_understanding": {
                "event_count": len(self.events),
                "selected_frame_count": len(self.selected_frames),
                "conflict_count": len(self.conflicts),
                "method_used": self.method_used,
                "degraded": self.degraded,
                "degrade_reason": self.degrade_reason,
            },
        }
