from __future__ import annotations

"""博主多视频知识引擎 API路由"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.services.blogger_video_indexer import BloggerVideoIndexer
from backend.services.blogger_knowledge_service import BloggerKnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blogger", tags=["blogger-knowledge"])

_indexer = BloggerVideoIndexer()
_knowledge_service = BloggerKnowledgeService()


class IndexRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    video_paths: List[str] = Field(..., description="视频文件路径列表")
    platform: str = Field("", description="平台标识")


class IncrementalIndexRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    new_video_paths: List[str] = Field(..., description="新视频文件路径列表")
    platform: str = Field("", description="平台标识")


class AskRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    question: str = Field(..., description="问题")


class SearchRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    query: str = Field(..., description="搜索查询")
    top_k: int = Field(10, description="返回结果数量")


class ContradictionRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    topic: str = Field("", description="限定话题（可选）")


class TimelineRequest(BaseModel):
    blogger_id: str = Field(..., description="博主ID")
    topic: str = Field(..., description="话题")


class StyleProfileRequest(BaseModel):
    """博主风格画像请求"""
    blogger_id: str = Field(default="", description="博主ID")
    blogger_name: str = Field(default="", description="博主名称")
    contents: List[str] = Field(default_factory=list, description="历史文案列表")
    video_metadata: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="视频元数据 [{title, duration, platform, publish_date}]"
    )


@router.post("/index", summary="创建博主视频索引")
async def create_index(request: IndexRequest, background_tasks: BackgroundTasks):
    """为博主建立全视频知识索引（异步后台执行）"""
    status = _indexer.get_index_status(request.blogger_id)

    background_tasks.add_task(
        _indexer.index_blogger,
        request.blogger_id,
        request.video_paths,
        request.platform,
    )

    return {
        "blogger_id": request.blogger_id,
        "status": "indexing",
        "message": f"开始索引 {len(request.video_paths)} 个视频",
        "current_videos": status.total_videos,
    }


@router.get("/{blogger_id}/status", summary="获取索引状态")
async def get_index_status(blogger_id: str):
    """获取博主视频索引状态"""
    status = _indexer.get_index_status(blogger_id)
    return {
        "blogger_id": status.blogger_id,
        "total_videos": status.total_videos,
        "total_segments": status.total_segments,
        "total_entities": status.total_entities,
        "total_relations": status.total_relations,
        "total_duration_hours": status.total_duration_hours,
        "last_updated": status.last_updated,
    }


@router.post("/incremental", summary="增量索引新视频")
async def incremental_index(request: IncrementalIndexRequest, background_tasks: BackgroundTasks):
    """增量索引新视频（不重建已有索引）"""
    background_tasks.add_task(
        _indexer.incremental_index,
        request.blogger_id,
        request.new_video_paths,
        request.platform,
    )

    return {
        "blogger_id": request.blogger_id,
        "status": "indexing",
        "message": f"开始增量索引 {len(request.new_video_paths)} 个新视频",
    }


@router.delete("/{blogger_id}/index", summary="删除博主索引")
async def delete_index(blogger_id: str):
    """删除博主的视频索引"""
    _indexer.delete_index(blogger_id)
    return {"blogger_id": blogger_id, "status": "deleted"}


@router.post("/ask", summary="博主知识问答")
async def ask_blogger(request: AskRequest):
    """对博主全部视频进行知识问答"""
    result = await _knowledge_service.ask(request.blogger_id, request.question)
    return {
        "question": result.question,
        "answer": result.answer,
        "confidence": result.confidence,
        "references": result.references,
        "retrieval_mode": result.retrieval_mode,
    }


@router.post("/search", summary="内容检索")
async def search_content(request: SearchRequest):
    """在博主视频中搜索特定内容"""
    results = await _knowledge_service.search_content(
        request.blogger_id, request.query, request.top_k
    )
    return {"blogger_id": request.blogger_id, "query": request.query, "results": results}


@router.get("/{blogger_id}/profile", summary="获取全知识画像")
async def get_blogger_profile(blogger_id: str):
    """获取博主全知识画像"""
    profile = await _knowledge_service.get_blogger_profile(blogger_id)
    return {
        "blogger_id": profile.blogger_id,
        "narrative_style": profile.narrative_style,
        "expression_style": profile.expression_style,
        "vocabulary_profile": profile.vocabulary_profile,
        "core_viewpoints": profile.core_viewpoints,
        "topic_stances": profile.topic_stances,
        "primary_topics": profile.primary_topics,
        "topic_distribution": profile.topic_distribution,
        "estimated_audience": profile.estimated_audience,
        "total_videos": profile.total_videos,
        "total_duration_hours": profile.total_duration_hours,
        "last_updated": profile.last_updated,
    }


@router.post("/style-profile", summary="博主风格画像")
async def generate_style_profile(request: StyleProfileRequest):
    """输入历史文案/视频元数据，生成风格维度画像

    输出话题/语气/节奏/风险偏好/人设等结构化字段，可直接供前端博主画像展示。
    LLM 不可用时自动降级为规则分析。
    """
    from backend.services.blogger_style_profiler import BloggerStyleProfiler

    profiler = BloggerStyleProfiler()
    result = await profiler.analyze(
        contents=request.contents,
        video_metadata=request.video_metadata,
        blogger_id=request.blogger_id,
        blogger_name=request.blogger_name,
    )
    return result.to_dict()


@router.post("/contradictions", summary="观点矛盾检测")
async def find_contradictions(request: ContradictionRequest):
    """发现博主在不同视频中对同一话题的矛盾观点"""
    results = await _knowledge_service.find_contradictions(
        request.blogger_id, request.topic
    )
    return {"blogger_id": request.blogger_id, "topic": request.topic, "contradictions": results}


@router.post("/timeline", summary="话题演变时间线")
async def get_topic_timeline(request: TimelineRequest):
    """追踪博主对某话题的观点演变时间线"""
    results = await _knowledge_service.get_topic_timeline(
        request.blogger_id, request.topic
    )
    return {"blogger_id": request.blogger_id, "topic": request.topic, "timeline": results}
