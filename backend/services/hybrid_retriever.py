from __future__ import annotations

"""混合多模态检索器 — VideoRAG核心检索逻辑

融合文本检索（知识图谱+文本嵌入）和视觉检索（多模态嵌入），
自适应选择最优检索策略。
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from backend.services.graph.graph_store import GraphStore
from backend.services.video_embedding_store import VideoEmbeddingStore, VideoSegmentMatch
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


class FusedMatch:
    """融合后的匹配结果"""

    def __init__(
        self,
        segment_id: str = "",
        video_path: str = "",
        start_time: float = 0.0,
        end_time: float = 0.0,
        text_score: float = 0.0,
        visual_score: float = 0.0,
        fused_score: float = 0.0,
        source: str = "",
        blogger_id: str = "",
        context_text: str = "",
        entity_names: List[str] = None,
    ):
        self.segment_id = segment_id
        self.video_path = video_path
        self.start_time = start_time
        self.end_time = end_time
        self.text_score = text_score
        self.visual_score = visual_score
        self.fused_score = fused_score
        self.source = source
        self.blogger_id = blogger_id
        self.context_text = context_text
        self.entity_names = entity_names or []

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "video_path": self.video_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text_score": round(self.text_score, 4),
            "visual_score": round(self.visual_score, 4),
            "fused_score": round(self.fused_score, 4),
            "source": self.source,
            "context_text": self.context_text[:300],
            "entity_names": self.entity_names,
        }


class RetrievalResult:
    """检索结果"""

    def __init__(
        self,
        query: str = "",
        mode: str = "auto",
        matches: List[FusedMatch] = None,
        context_text: str = "",
        total_text_results: int = 0,
        total_visual_results: int = 0,
    ):
        self.query = query
        self.mode = mode
        self.matches = matches or []
        self.context_text = context_text
        self.total_text_results = total_text_results
        self.total_visual_results = total_visual_results

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "mode": self.mode,
            "total_matches": len(self.matches),
            "total_text_results": self.total_text_results,
            "total_visual_results": self.total_visual_results,
            "context_text": self.context_text[:2000],
            "matches": [m.to_dict() for m in self.matches[:10]],
        }


class HybridRetriever:
    """混合多模态检索器"""

    def __init__(
        self,
        graph_store: GraphStore = None,
        embedding_store: VideoEmbeddingStore = None,
        working_dir: str = "./data/blogger_index",
    ):
        self.graph_store = graph_store or GraphStore()
        self.embedding_store = embedding_store or VideoEmbeddingStore()
        self.working_dir = working_dir

    async def retrieve(
        self,
        query: str,
        blogger_id: str,
        mode: str = "auto",
        top_k: int = 15,
    ) -> RetrievalResult:
        """混合检索：文本通道 + 视觉通道 → 自适应融合

        Args:
            query: 查询文本
            blogger_id: 博主ID
            mode: 检索模式
                - "text": 仅文本检索（知识图谱 + 片段文本匹配）
                - "visual": 仅视觉检索（多模态嵌入）
                - "auto": 自适应融合（默认）
            top_k: 返回结果数量

        Returns:
            RetrievalResult
        """
        if mode == "text":
            text_matches = await self._text_retrieval(query, blogger_id, top_k)
            context = self._build_context(text_matches, [])
            return RetrievalResult(
                query=query, mode="text", matches=text_matches,
                context_text=context, total_text_results=len(text_matches),
            )

        elif mode == "visual":
            visual_matches = await self._visual_retrieval(query, blogger_id, top_k)
            context = self._build_context([], visual_matches)
            return RetrievalResult(
                query=query, mode="visual", matches=visual_matches,
                context_text=context, total_visual_results=len(visual_matches),
            )

        else:
            text_matches = await self._text_retrieval(query, blogger_id, top_k)
            visual_matches = await self._visual_retrieval(query, blogger_id, top_k)
            fused = self._adaptive_fusion(text_matches, visual_matches, query, top_k)
            context = self._build_context(text_matches, visual_matches)
            return RetrievalResult(
                query=query, mode="auto", matches=fused,
                context_text=context,
                total_text_results=len(text_matches),
                total_visual_results=len(visual_matches),
            )

    async def _text_retrieval(
        self,
        query: str,
        blogger_id: str,
        top_k: int = 15,
    ) -> List[FusedMatch]:
        """文本检索通道：知识图谱遍历 + 片段文本匹配"""
        matches = []

        try:
            self.graph_store.connect()

            entities = self.graph_store.search_entities(query, limit=10)
            for ent in entities:
                ent_props = ent.get("properties", {})
                if isinstance(ent_props, str):
                    try:
                        ent_props = json.loads(ent_props)
                    except Exception:
                        ent_props = {}

                ent_blogger = ent_props.get("blogger_id", "")
                if blogger_id and ent_blogger and ent_blogger != blogger_id:
                    continue

                video_path = ent_props.get("video_path", "")
                seg_time = ent_props.get("segment_time", "0-0s")
                try:
                    parts = seg_time.replace("s", "").split("-")
                    start_t = float(parts[0]) if parts[0] else 0.0
                    end_t = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
                except Exception:
                    start_t, end_t = 0.0, 0.0

                matches.append(FusedMatch(
                    segment_id=ent.get("entity_id", ""),
                    video_path=video_path,
                    start_time=start_t,
                    end_time=end_t,
                    text_score=0.7,
                    source="graph",
                    blogger_id=blogger_id,
                    context_text=f"{ent.get('name', '')}: {ent_props.get('description', '')}",
                    entity_names=[ent.get("name", "")],
                ))

            relations = self.graph_store.search_relations(query, limit=10)
            for rel in relations:
                source_name = rel.get("source_name", "")
                target_name = rel.get("target_name", "")
                rel_type = rel.get("relation_type", "")
                matches.append(FusedMatch(
                    text_score=0.5,
                    source="graph_relation",
                    blogger_id=blogger_id,
                    context_text=f"{source_name} → {rel_type} → {target_name}",
                    entity_names=[source_name, target_name],
                ))

        except Exception as e:
            logger.debug("知识图谱检索失败: %s", e)

        segment_matches = self._text_match_segments(query, blogger_id, top_k)
        for sm in segment_matches:
            matches.append(FusedMatch(
                segment_id=sm.get("segment_id", ""),
                video_path=sm.get("video_path", ""),
                start_time=sm.get("start_time", 0),
                end_time=sm.get("end_time", 0),
                text_score=sm.get("score", 0.5),
                source="segment_text",
                blogger_id=blogger_id,
                context_text=sm.get("combined_text", ""),
            ))

        matches.sort(key=lambda x: -x.text_score)
        return matches[:top_k]

    async def _visual_retrieval(
        self,
        query: str,
        blogger_id: str,
        top_k: int = 10,
    ) -> List[FusedMatch]:
        """视觉检索通道：多模态嵌入相似度"""
        results = await self.embedding_store.search(query, blogger_id, top_k)

        matches = []
        for r in results:
            matches.append(FusedMatch(
                segment_id=r.segment_id,
                video_path=r.video_path,
                start_time=r.start_time,
                end_time=r.end_time,
                visual_score=r.score,
                source="embedding",
                blogger_id=r.blogger_id,
                context_text=r.combined_text,
            ))

        return matches

    def _adaptive_fusion(
        self,
        text_results: List[FusedMatch],
        visual_results: List[FusedMatch],
        query: str,
        top_k: int = 15,
    ) -> List[FusedMatch]:
        """自适应融合：根据查询类型调整文本/视觉权重

        规则：
        - 视觉相关查询（"画面""场景""看到""出现"）→ 视觉权重0.7
        - 事实性查询（"观点""看法""提到""说了"）→ 文本权重0.7
        - 默认：文本0.6，视觉0.4
        """
        visual_keywords = ["画面", "场景", "看到", "出现", "展示", "展示", "展示", "背景", "穿着", "颜色"]
        text_keywords = ["观点", "看法", "提到", "说了", "认为", "主张", "讨论", "分析", "评价"]

        visual_count = sum(1 for kw in visual_keywords if kw in query)
        text_count = sum(1 for kw in text_keywords if kw in query)

        if visual_count > text_count:
            text_weight, visual_weight = 0.3, 0.7
        elif text_count > visual_count:
            text_weight, visual_weight = 0.7, 0.3
        else:
            text_weight, visual_weight = 0.6, 0.4

        segment_map: Dict[str, FusedMatch] = {}

        for m in text_results:
            key = m.segment_id or f"text_{m.video_path}_{m.start_time}"
            if key in segment_map:
                segment_map[key].text_score = max(segment_map[key].text_score, m.text_score)
                if m.context_text and not segment_map[key].context_text:
                    segment_map[key].context_text = m.context_text
            else:
                m_copy = FusedMatch(
                    segment_id=m.segment_id,
                    video_path=m.video_path,
                    start_time=m.start_time,
                    end_time=m.end_time,
                    text_score=m.text_score,
                    visual_score=0.0,
                    source=m.source,
                    blogger_id=m.blogger_id,
                    context_text=m.context_text,
                    entity_names=m.entity_names,
                )
                segment_map[key] = m_copy

        for m in visual_results:
            key = m.segment_id or f"visual_{m.video_path}_{m.start_time}"
            if key in segment_map:
                segment_map[key].visual_score = max(segment_map[key].visual_score, m.visual_score)
                if m.source == "embedding" and segment_map[key].source != "embedding":
                    segment_map[key].source = "hybrid"
            else:
                m_copy = FusedMatch(
                    segment_id=m.segment_id,
                    video_path=m.video_path,
                    start_time=m.start_time,
                    end_time=m.end_time,
                    text_score=0.0,
                    visual_score=m.visual_score,
                    source=m.source,
                    blogger_id=m.blogger_id,
                    context_text=m.context_text,
                )
                segment_map[key] = m_copy

        for m in segment_map.values():
            m.fused_score = text_weight * m.text_score + visual_weight * m.visual_score

        fused = sorted(segment_map.values(), key=lambda x: -x.fused_score)
        return fused[:top_k]

    def _text_match_segments(
        self,
        query: str,
        blogger_id: str,
        top_k: int = 10,
    ) -> List[Dict]:
        """从片段JSON文件中进行文本匹配"""
        segments_dir = os.path.join(self.working_dir, blogger_id)
        if not os.path.isdir(segments_dir):
            return []

        query_words = set(query.split())
        results = []

        for filename in os.listdir(segments_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(segments_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            combined = data.get("combined_text", "")
            if not combined:
                continue

            text_words = set(combined.split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                score = overlap / max(len(query_words), 1)
                results.append({
                    "segment_id": data.get("segment_id", ""),
                    "video_path": data.get("video_path", ""),
                    "start_time": data.get("start_time", 0),
                    "end_time": data.get("end_time", 0),
                    "combined_text": combined,
                    "score": score,
                })

        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def _build_context(
        self,
        text_matches: List[FusedMatch],
        visual_matches: List[FusedMatch],
    ) -> str:
        """构建检索上下文文本"""
        parts = []

        seen_segments = set()
        all_matches = text_matches + visual_matches

        for m in all_matches:
            key = f"{m.video_path}_{m.start_time}"
            if key in seen_segments:
                continue
            seen_segments.add(key)

            if m.context_text:
                video_name = os.path.basename(m.video_path) if m.video_path else ""
                time_range = f"{m.start_time:.0f}-{m.end_time:.0f}s"
                parts.append(f"[{video_name} {time_range}]\n{m.context_text}")

        return "\n\n".join(parts[:20])
