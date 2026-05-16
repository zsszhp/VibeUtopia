from __future__ import annotations

"""博主视频批量索引服务 — VideoRAG驱动

核心流程：视频切分 → VLM描述 + ASR转录 + OCR → LLM实体抽取 → 知识图谱增量构建
支持跨视频实体对齐合并，增量索引新视频无需重建。
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

from backend.services.graph.graph_store import GraphStore
from backend.services.graph.graph_updater import GraphUpdater
from backend.services.graph.models import (
    Entity, IndexResult, IndexStatus, VideoSegment,
    EntityType, RelationType,
)
from backend.services.graph.entity_extractor import extract_from_event
from backend.services.multimodal_analyzer import VideoSegmentAnalyzer
from backend.services.video_embedding_store import VideoEmbeddingStore

logger = logging.getLogger(__name__)

SEGMENT_DURATION = 30.0
MAX_FRAMES_PER_SEGMENT = 10


class BloggerVideoIndexer:
    """博主视频批量索引器"""

    def __init__(self, store: GraphStore = None, working_dir: str = "./data/blogger_index"):
        self.store = store or GraphStore()
        self.updater = GraphUpdater(self.store)
        self.segment_analyzer = VideoSegmentAnalyzer()
        self.embedding_store = VideoEmbeddingStore(
            persist_dir=os.path.join(working_dir, "embeddings")
        )
        self.working_dir = working_dir
        os.makedirs(working_dir, exist_ok=True)

    async def index_blogger(
        self,
        blogger_id: str,
        video_paths: List[str],
        platform: str = "",
    ) -> IndexResult:
        """为博主建立全视频知识索引

        Args:
            blogger_id: 博主ID
            video_paths: 视频文件路径列表
            platform: 平台标识

        Returns:
            IndexResult
        """
        start_time = time.time()
        result = IndexResult(blogger_id=blogger_id)

        status = self._load_status(blogger_id)
        indexed_paths = set(status.indexed_video_paths)

        self.store.connect()

        for video_path in video_paths:
            if video_path in indexed_paths:
                logger.info("视频已索引，跳过: %s", video_path)
                continue

            if not os.path.exists(video_path):
                result.errors.append(f"视频文件不存在: {video_path}")
                continue

            try:
                video_result = await self._index_single_video(
                    blogger_id=blogger_id,
                    video_path=video_path,
                    platform=platform,
                )
                result.videos_indexed += 1
                result.segments_created += video_result["segments"]
                result.entities_extracted += video_result["entities"]
                result.relations_extracted += video_result["relations"]
                result.entities_merged += video_result["merged"]

                indexed_paths.add(video_path)

            except Exception as e:
                logger.error("索引视频失败 %s: %s", video_path, e)
                result.errors.append(f"{video_path}: {str(e)}")

        status.indexed_video_paths = list(indexed_paths)
        status.total_videos = len(indexed_paths)
        status.last_updated = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save_status(blogger_id, status)

        result.duration_seconds = time.time() - start_time
        logger.info(
            "博主 %s 索引完成: %d视频, %d片段, %d实体, %d关系, %.1f秒",
            blogger_id, result.videos_indexed, result.segments_created,
            result.entities_extracted, result.relations_extracted,
            result.duration_seconds,
        )
        return result

    async def incremental_index(
        self,
        blogger_id: str,
        new_video_paths: List[str],
        platform: str = "",
    ) -> IndexResult:
        """增量索引新视频（不重建已有索引）

        Args:
            blogger_id: 博主ID
            new_video_paths: 新视频文件路径列表
            platform: 平台标识

        Returns:
            IndexResult
        """
        return await self.index_blogger(blogger_id, new_video_paths, platform)

    def get_index_status(self, blogger_id: str) -> IndexStatus:
        """获取博主索引状态"""
        return self._load_status(blogger_id)

    def delete_index(self, blogger_id: str):
        """删除博主索引"""
        status_file = os.path.join(self.working_dir, f"{blogger_id}_status.json")
        if os.path.exists(status_file):
            os.remove(status_file)
        segments_dir = os.path.join(self.working_dir, blogger_id)
        if os.path.isdir(segments_dir):
            import shutil
            shutil.rmtree(segments_dir, ignore_errors=True)
        logger.info("博主 %s 索引已删除", blogger_id)

    async def _index_single_video(
        self,
        blogger_id: str,
        video_path: str,
        platform: str = "",
    ) -> Dict:
        """索引单个视频

        Returns:
            {segments, entities, relations, merged}
        """
        stats = {"segments": 0, "entities": 0, "relations": 0, "merged": 0}

        segments = await self._split_video(blogger_id, video_path)
        stats["segments"] = len(segments)

        all_entities = []
        all_relations = []

        for seg in segments:
            seg_result = await self._process_segment(seg, blogger_id, platform)
            all_entities.extend(seg_result.get("entities", []))
            all_relations.extend(seg_result.get("relations", []))

        merged_entities = await self.updater.align_and_merge_entities(
            all_entities, blogger_id
        )
        stats["entities"] = len(all_entities)
        stats["relations"] = len(all_relations)
        stats["merged"] = len(all_entities) - len(merged_entities)

        for relation in all_relations:
            self.store.save_relation(relation)

        self._save_segments(blogger_id, segments)

        return stats

    async def _split_video(
        self,
        blogger_id: str,
        video_path: str,
    ) -> List[VideoSegment]:
        """将视频切分为固定时长的片段，提取关键帧

        Args:
            blogger_id: 博主ID
            video_path: 视频文件路径

        Returns:
            VideoSegment列表
        """
        from backend.services.keyframe_extractor import KeyframeExtractor

        extractor = KeyframeExtractor()
        frame_result = await extractor.extract(video_path)

        if frame_result.error or not frame_result.frames:
            logger.warning("关键帧提取失败: %s", frame_result.error)
            return []

        duration = frame_result.duration
        segments = []
        current_time = 0.0

        while current_time < duration:
            end_time = min(current_time + SEGMENT_DURATION, duration)

            seg_frames = [
                f for f in frame_result.frames
                if current_time <= f.timestamp < end_time
            ]

            frame_paths = [f.file_path for f in seg_frames[:MAX_FRAMES_PER_SEGMENT]]

            segment = VideoSegment(
                video_path=video_path,
                blogger_id=blogger_id,
                start_time=current_time,
                end_time=end_time,
                frame_paths=frame_paths,
            )
            segments.append(segment)
            current_time = end_time

        logger.info("视频切分: %s → %d片段 (%.1f秒/片段)", video_path, len(segments), SEGMENT_DURATION)
        return segments

    async def _process_segment(
        self,
        segment: VideoSegment,
        blogger_id: str,
        platform: str = "",
    ) -> Dict:
        """处理单个视频片段：VLM描述 + ASR + OCR → 实体抽取

        Returns:
            {entities: List[Entity], relations: List[Relation]}
        """
        visual_desc = ""
        if segment.frame_paths:
            visual_desc = await self.segment_analyzer.generate_visual_description_batch(
                segment.frame_paths
            )
        segment.visual_description = visual_desc

        asr_text = await self._extract_asr(segment.video_path, segment.start_time, segment.end_time)
        segment.asr_text = asr_text

        ocr_text = await self._extract_ocr(segment.frame_paths)
        segment.ocr_text = ocr_text

        combined_parts = []
        if visual_desc:
            combined_parts.append(f"[视觉] {visual_desc}")
        if asr_text:
            combined_parts.append(f"[音频] {asr_text}")
        if ocr_text:
            combined_parts.append(f"[文字] {ocr_text}")
        segment.combined_text = "\n".join(combined_parts)

        if not segment.combined_text:
            return {"entities": [], "relations": []}

        analysis = await self.segment_analyzer.analyze_segment(
            visual_description=visual_desc,
            asr_text=asr_text,
            ocr_text=ocr_text,
        )

        entities = []
        for ent_data in analysis.get("entities", []):
            entity = Entity(
                entity_type=ent_data.get("type", "Concept"),
                name=ent_data.get("name", "未知"),
                properties={
                    "description": ent_data.get("description", ""),
                    "blogger_id": blogger_id,
                    "video_path": segment.video_path,
                    "segment_time": f"{segment.start_time:.0f}-{segment.end_time:.0f}s",
                    "platform": platform,
                },
            )
            entities.append(entity)

        for topic in analysis.get("topics", []):
            topic_entity = Entity(
                entity_type="Topic",
                name=topic,
                properties={
                    "blogger_id": blogger_id,
                    "video_path": segment.video_path,
                    "segment_time": f"{segment.start_time:.0f}-{segment.end_time:.0f}s",
                },
            )
            entities.append(topic_entity)

        for vp_data in analysis.get("viewpoints", []):
            vp_entity = Entity(
                entity_type="Viewpoint",
                name=vp_data.get("content", "")[:80],
                properties={
                    "stance": vp_data.get("stance", "neutral"),
                    "confidence": vp_data.get("confidence", 0.5),
                    "blogger_id": blogger_id,
                    "video_path": segment.video_path,
                    "segment_time": f"{segment.start_time:.0f}-{segment.end_time:.0f}s",
                },
            )
            entities.append(vp_entity)

        seg_entity = Entity(
            entity_type="VideoSegment",
            name=f"{os.path.basename(segment.video_path)} [{segment.start_time:.0f}-{segment.end_time:.0f}s]",
            properties={
                "video_path": segment.video_path,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "summary": analysis.get("summary", ""),
                "sentiment": analysis.get("sentiment", "neutral"),
                "blogger_id": blogger_id,
            },
        )
        entities.append(seg_entity)

        relations = []
        for ent in entities:
            if ent.entity_type != "VideoSegment":
                rel = Relation(
                    relation_type="APPEARS_IN",
                    source_id=ent.entity_id,
                    target_id=seg_entity.entity_id,
                    weight=0.8,
                    properties={
                        "blogger_id": blogger_id,
                        "segment_time": f"{segment.start_time:.0f}-{segment.end_time:.0f}s",
                    },
                )
                relations.append(rel)

        if segment.combined_text:
            await self.embedding_store.encode_and_store(
                segment_id=segment.segment_id,
                text=segment.combined_text,
                metadata={
                    "video_path": segment.video_path,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "blogger_id": blogger_id,
                    "platform": platform,
                },
            )

        return {"entities": entities, "relations": relations}

    async def _extract_asr(self, video_path: str, start_time: float, end_time: float) -> str:
        """提取视频片段的ASR转录文本"""
        try:
            from backend.services.audio_analyzer import AudioAnalyzer
            analyzer = AudioAnalyzer()
            transcription = await analyzer.analyze(video_path)
            if transcription and transcription.full_text:
                return transcription.full_text
        except Exception as e:
            logger.debug("ASR提取失败: %s", e)
        return ""

    async def _extract_ocr(self, frame_paths: List[str]) -> str:
        """提取关键帧的OCR文本"""
        if not frame_paths:
            return ""
        try:
            from backend.services.frame_ocr import FrameOCR
            ocr = FrameOCR()
            ocr_result = await ocr.extract_video_text(frame_paths)
            if ocr_result and ocr_result.all_text:
                return ocr_result.all_text
        except Exception as e:
            logger.debug("OCR提取失败: %s", e)
        return ""

    def _load_status(self, blogger_id: str) -> IndexStatus:
        """加载博主索引状态"""
        status_file = os.path.join(self.working_dir, f"{blogger_id}_status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return IndexStatus(**data)
            except Exception as e:
                logger.warning("加载索引状态失败: %s", e)
        return IndexStatus(blogger_id=blogger_id)

    def _save_status(self, blogger_id: str, status: IndexStatus):
        """保存博主索引状态"""
        status_file = os.path.join(self.working_dir, f"{blogger_id}_status.json")
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump({
                    "blogger_id": status.blogger_id,
                    "total_videos": status.total_videos,
                    "total_segments": status.total_segments,
                    "total_entities": status.total_entities,
                    "total_relations": status.total_relations,
                    "total_duration_hours": status.total_duration_hours,
                    "indexed_video_paths": status.indexed_video_paths,
                    "last_updated": status.last_updated,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存索引状态失败: %s", e)

    def _save_segments(self, blogger_id: str, segments: List[VideoSegment]):
        """保存视频片段数据"""
        segments_dir = os.path.join(self.working_dir, blogger_id)
        os.makedirs(segments_dir, exist_ok=True)

        for seg in segments:
            seg_file = os.path.join(
                segments_dir,
                f"seg_{seg.start_time:.0f}_{seg.end_time:.0f}.json",
            )
            try:
                with open(seg_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "segment_id": seg.segment_id,
                        "video_path": seg.video_path,
                        "blogger_id": seg.blogger_id,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "visual_description": seg.visual_description,
                        "asr_text": seg.asr_text,
                        "ocr_text": seg.ocr_text,
                        "combined_text": seg.combined_text,
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.debug("保存片段数据失败: %s", e)
