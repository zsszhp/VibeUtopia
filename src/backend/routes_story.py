"""人生故事生成 API 路由

提供人生故事生成相关的 API 端点。
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.services.story_generation import (
    TimelineBuilder,
    SceneGenerator,
    NarrativeIntegrator,
    PersonalityEvolver,
    LifeTimeline,
    ScenePackage,
    LifeNarrative,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/story", tags=["人生故事生成"])

# 存储生成任务的临时目录
STORY_STORAGE_DIR = Path(__file__).parent.parent / "data" / "stories"


class StoryGenerateRequest(BaseModel):
    """人生故事生成请求"""
    user_id: str = Field(..., description="用户 ID")
    persona_data: Dict[str, Any] = Field(..., description="完整人格画像")
    include_scenes: bool = Field(True, description="是否生成场景故事")
    include_analysis: bool = Field(True, description="是否包含心理分析")


class StoryGenerateResponse(BaseModel):
    """人生故事生成响应"""
    task_id: str
    status: str
    message: str
    estimated_time: int = Field(30, description="预计完成时间 (秒)")


class StoryStatusResponse(BaseModel):
    """人生故事状态响应"""
    user_id: str
    status: str
    timeline_events: int = 0
    scenes_generated: int = 0
    full_story_length: int = 0
    created_at: Optional[str] = None
    error: Optional[str] = None


class StoryQueryResponse(BaseModel):
    """人生故事查询响应"""
    user_id: str
    persona_id: str
    narrative_arc: str
    themes: List[str]
    timeline_summary: Dict[str, int]
    scenes_count: int
    full_story_available: bool
    summary_available: bool
    created_at: str


class StoryEvolveRequest(BaseModel):
    """人格演化模拟请求"""
    user_id: str
    event_ids: List[str] = Field(..., description="触发事件 ID 列表")
    simulate_years: int = Field(10, description="模拟年数")


class StoryEvolveResponse(BaseModel):
    """人格演化模拟响应"""
    user_id: str
    initial_persona: Dict[str, Any]
    evolved_persona: Dict[str, Any]
    trait_changes: Dict[str, float]
    key_turning_points: List[str]


@router.post("/generate", response_model=StoryGenerateResponse)
async def generate_story(
    request: StoryGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """生成单个人生故事"""
    task_id = f"story_{request.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    os.makedirs(STORY_STORAGE_DIR, exist_ok=True)

    background_tasks.add_task(
        _process_story_generation,
        task_id,
        request.user_id,
        request.persona_data,
        request.include_scenes,
        request.include_analysis,
    )

    return StoryGenerateResponse(
        task_id=task_id,
        status="processing",
        message="人生故事生成任务已启动",
        estimated_time=45,
    )


@router.get("/{user_id}", response_model=StoryQueryResponse)
async def get_story(user_id: str):
    """获取已生成的人生故事元数据"""
    story_dir = STORY_STORAGE_DIR / user_id

    if not story_dir.exists():
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 的人生故事尚未生成")

    narrative_path = story_dir / f"{user_id}_narrative.json"
    if not narrative_path.exists():
        raise HTTPException(status_code=404, detail="叙事文件不存在")

    with open(narrative_path, "r", encoding="utf-8") as f:
        narrative_data = json.load(f)

    timeline_events = {}
    timeline_path = story_dir / f"{user_id}_timeline.json"
    if timeline_path.exists():
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline_data = json.load(f)
            timeline_events = {
                stage: len(events)
                for stage, events in timeline_data.get("stages", {}).items()
            }

    scenes_count = 0
    scenes_path = story_dir / f"{user_id}_scenes.json"
    if scenes_path.exists():
        with open(scenes_path, "r", encoding="utf-8") as f:
            scenes_data = json.load(f)
            scenes_count = len(scenes_data.get("scenes", []))

    return StoryQueryResponse(
        user_id=user_id,
        persona_id=narrative_data.get("persona_id", "unknown"),
        narrative_arc=narrative_data.get("narrative_arc", "平凡之旅"),
        themes=narrative_data.get("themes", []),
        timeline_summary=timeline_events,
        scenes_count=scenes_count,
        full_story_available=bool(narrative_data.get("full_story")),
        summary_available=bool(narrative_data.get("summary")),
        created_at=narrative_data.get("generated_at", ""),
    )


@router.get("/{user_id}/timeline")
async def get_timeline(user_id: str):
    """获取人生时间线详情"""
    timeline_path = STORY_STORAGE_DIR / user_id / f"{user_id}_timeline.json"

    if not timeline_path.exists():
        raise HTTPException(status_code=404, detail="时间线不存在")

    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)

    return timeline_data


@router.get("/{user_id}/scenes")
async def get_scenes(user_id: str):
    """获取场景故事列表"""
    scenes_path = STORY_STORAGE_DIR / user_id / f"{user_id}_scenes.json"

    if not scenes_path.exists():
        raise HTTPException(status_code=404, detail="场景故事不存在")

    with open(scenes_path, "r", encoding="utf-8") as f:
        scenes_data = json.load(f)

    scenes_summary = []
    for scene in scenes_data.get("scenes", []):
        scenes_summary.append({
            "title": scene.get("title"),
            "age": scene.get("event", {}).get("age"),
            "stage": scene.get("event", {}).get("stage"),
            "event_type": scene.get("event", {}).get("event_type"),
            "word_count": scene.get("word_count"),
        })

    return {
        "user_id": user_id,
        "total_scenes": len(scenes_summary),
        "total_word_count": scenes_data.get("total_word_count", 0),
        "scenes": scenes_summary,
    }


@router.get("/{user_id}/full")
async def get_full_story(user_id: str):
    """获取完整人生故事内容"""
    narrative_path = STORY_STORAGE_DIR / user_id / f"{user_id}_narrative.json"

    if not narrative_path.exists():
        raise HTTPException(status_code=404, detail="叙事文件不存在")

    with open(narrative_path, "r", encoding="utf-8") as f:
        narrative_data = json.load(f)

    return {
        "user_id": user_id,
        "full_story": narrative_data.get("full_story", ""),
        "summary": narrative_data.get("summary", ""),
        "themes": narrative_data.get("themes", []),
        "narrative_arc": narrative_data.get("narrative_arc", "平凡之旅"),
        "psychological_analysis": narrative_data.get("psychological_analysis", ""),
    }


@router.post("/{user_id}/evolve", response_model=StoryEvolveResponse)
async def evolve_persona(user_id: str, request: StoryEvolveRequest):
    """模拟人格演化
    
    基于触发事件库，计算 Big Five 人格特质的动态变化。
    支持事件组合效应、依恋类型响应、MBTI 倾向性调整。
    """
    evolver = PersonalityEvolver()
    
    persona_path = STORY_STORAGE_DIR / user_id / f"{user_id}_narrative.json"
    if not persona_path.exists():
        raise HTTPException(status_code=404, detail="用户人格数据不存在")
    
    with open(persona_path, "r", encoding="utf-8") as f:
        persona_data = json.load(f)
    
    big_five_data = persona_data.get("big_five", {})
    initial_persona_full = {
        "big_five": big_five_data,
        "mbti_type": persona_data.get("mbti_type", "ENFP"),
        "attachment_style": persona_data.get("attachment_style", "secure"),
        "enneagram_type": persona_data.get("enneagram_type", 1),
        "archetype": persona_data.get("archetype", "探索者"),
    }
    
    result = evolver.evolve(
        initial_persona=initial_persona_full,
        event_ids=request.event_ids,
        simulate_years=request.simulate_years,
    )
    
    response_dict = evolver.to_response_dict(result)
    response_dict["user_id"] = user_id
    response_dict["simulate_years"] = request.simulate_years
    
    return StoryEvolveResponse(**response_dict)


async def _process_story_generation(
    task_id: str,
    user_id: str,
    persona_data: Dict[str, Any],
    include_scenes: bool,
    include_analysis: bool,
):
    """后台处理人生故事生成"""
    logger.info("开始生成人生故事，task_id: %s, user_id: %s", task_id, user_id)

    try:
        user_dir = STORY_STORAGE_DIR / user_id
        os.makedirs(user_dir, exist_ok=True)

        timeline_builder = TimelineBuilder()
        timeline = await timeline_builder.build_timeline(persona_data, user_id)
        timeline_builder.save_timeline(timeline, str(user_dir))

        scene_package = None
        if include_scenes:
            scene_generator = SceneGenerator()
            scene_package = await scene_generator.generate_all_scenes(timeline, persona_data)
            scene_generator.save_scene_package(scene_package, str(user_dir))

        if include_analysis:
            narrative_integrator = NarrativeIntegrator()
            narrative = await narrative_integrator.integrate_narrative(
                timeline,
                scene_package if include_scenes else ScenePackage(
                    user_id=user_id,
                    persona_id=persona_data.get("id", "unknown"),
                    scenes=[],
                    total_word_count=0,
                ),
                persona_data,
            )
            narrative_integrator.save_narrative(narrative, str(user_dir))

        logger.info("人生故事生成完成，task_id: %s", task_id)

    except Exception as e:
        logger.error("人生故事生成失败，task_id: %s, error: %s", task_id, e)
