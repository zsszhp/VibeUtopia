"""人生故事生成服务模块

T7 人生故事生成模块包含三个子服务：
- T7.1: TimelineBuilder - 人生时间线构建
- T7.2: SceneGenerator - 关键场景故事生成
- T7.3: NarrativeIntegrator - 人生叙事整合
"""

from .narrative_integrator import LifeNarrative, NarrativeIntegrator
from .scene_generator import SceneGenerator, ScenePackage, SceneStory
from .timeline_builder import (
    EventType,
    LifeEvent,
    LifeStage,
    LifeTimeline,
    TimelineBuilder,
)
from .personality_evolver import (
    PersonalityEvolver,
    PersonalityState,
    TraitChange,
    EvolutionResult,
)

__all__ = [
    "TimelineBuilder",
    "SceneGenerator",
    "NarrativeIntegrator",
    "PersonalityEvolver",
    "LifeTimeline",
    "LifeEvent",
    "LifeStage",
    "EventType",
    "SceneStory",
    "ScenePackage",
    "LifeNarrative",
    "PersonalityState",
    "TraitChange",
    "EvolutionResult",
]
