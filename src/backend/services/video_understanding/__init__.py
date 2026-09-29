"""事件级视频理解（R3 P0）

把 design/31 的「事件优先 / 语义密度选帧 / 叙事冲突」核心思想落成
可离线运行的最小实现：EventSegmenter + AnchorSelector + NarrativeConflictDetector。
"""

from backend.services.video_understanding.anchor_selector import AnchorSelector
from backend.services.video_understanding.event_segmenter import EventSegmenter
from backend.services.video_understanding.models import (
    Event,
    EventUnderstandingResult,
    FrameObservation,
    NarrativeConflict,
    SelectedFrame,
    TranscriptSegment,
)
from backend.services.video_understanding.narrative_conflict import NarrativeConflictDetector
from backend.services.video_understanding.pipeline import (
    VideoEventUnderstandingPipeline,
    run_event_understanding,
)

__all__ = [
    "AnchorSelector",
    "Event",
    "EventSegmenter",
    "EventUnderstandingResult",
    "FrameObservation",
    "NarrativeConflict",
    "NarrativeConflictDetector",
    "SelectedFrame",
    "TranscriptSegment",
    "VideoEventUnderstandingPipeline",
    "run_event_understanding",
]
