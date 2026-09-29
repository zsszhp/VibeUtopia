"""事件级视频理解（R3 P0 + L6/L7）

把 design/14 的「事件优先 / 语义密度选帧 / 叙事冲突」核心思想落成
可离线运行的最小实现：EventSegmenter + AnchorSelector + NarrativeConflictDetector，
并补 L6 叙事语用启发（NarrativePragmaticsAnalyzer）与 L7 风险涌现函数 Φ
（RiskEmergenceScorer）的最小可运行版。
"""

from backend.services.video_understanding.anchor_selector import AnchorSelector
from backend.services.video_understanding.event_segmenter import EventSegmenter
from backend.services.video_understanding.models import (
    Event,
    EventUnderstandingResult,
    FrameObservation,
    NarrativeConflict,
    PragmaticRisk,
    RiskAtom,
    SelectedFrame,
    TranscriptSegment,
)
from backend.services.video_understanding.narrative_conflict import NarrativeConflictDetector
from backend.services.video_understanding.narrative_pragmatics import NarrativePragmaticsAnalyzer
from backend.services.video_understanding.pipeline import (
    VideoEventUnderstandingPipeline,
    run_event_understanding,
)
from backend.services.video_understanding.risk_emergence import (
    RiskEmergenceScorer,
    build_risk_atoms,
    short_flash_indicators,
)

__all__ = [
    "AnchorSelector",
    "Event",
    "EventSegmenter",
    "EventUnderstandingResult",
    "FrameObservation",
    "NarrativeConflict",
    "NarrativeConflictDetector",
    "NarrativePragmaticsAnalyzer",
    "PragmaticRisk",
    "RiskAtom",
    "RiskEmergenceScorer",
    "SelectedFrame",
    "TranscriptSegment",
    "VideoEventUnderstandingPipeline",
    "build_risk_atoms",
    "run_event_understanding",
    "short_flash_indicators",
]
