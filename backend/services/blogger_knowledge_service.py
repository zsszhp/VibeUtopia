from __future__ import annotations

"""博主知识问答服务 — VideoRAG驱动的博主全视频知识引擎

第1步基础版：基于知识图谱的文本检索通道
第2步升级：视觉检索通道 + 混合检索（HybridRetriever）
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from backend.services.graph.graph_store import GraphStore
from backend.services.graph.models import (
    AnswerResult, BloggerKnowledgeProfile, IndexStatus,
)
from backend.services.hybrid_retriever import HybridRetriever
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

ASK_SYSTEM_PROMPT = """你是一个博主内容分析专家。请根据以下从博主视频中检索到的知识信息，回答用户的问题。

要求：
1. 回答必须基于提供的知识信息，不要编造
2. 如果信息不足，明确说明
3. 引用具体的视频来源和时间
4. 用中文回答"""

ASK_PROMPT_TEMPLATE = """博主ID: {blogger_id}

【检索到的知识信息】
{context}

【用户问题】
{question}

请基于以上知识信息回答问题。输出JSON：
{{
    "answer": "回答内容",
    "confidence": 0.0-1.0,
    "references": [
        {{"video": "视频名", "time": "时间段", "content": "相关内容摘要"}}
    ]
}}"""

PROFILE_PROMPT = """你是一个博主画像分析专家。请根据以下从博主视频中提取的知识信息，生成博主的全面知识画像。

【博主知识信息】
{context}

请输出JSON：
{{
    "narrative_style": "叙事风格描述",
    "expression_style": "表达风格描述",
    "vocabulary_profile": {{"特征1": "描述", "特征2": "描述"}},
    "core_viewpoints": [{{"topic": "话题", "viewpoint": "观点", "confidence": 0.8}}],
    "topic_stances": {{"话题1": "positive/negative/neutral"}},
    "primary_topics": ["话题1", "话题2"],
    "topic_distribution": {{"话题1": 0.3, "话题2": 0.2}},
    "estimated_audience": {{"age": "年龄段", "interests": ["兴趣1"]}},
    "summary": "一句话总结博主特征"
}}"""


class BloggerKnowledgeService:
    """博主知识问答服务"""

    def __init__(self, store: GraphStore = None, working_dir: str = "./data/blogger_index"):
        self.store = store or GraphStore()
        self.working_dir = working_dir
        self.retriever = HybridRetriever(
            graph_store=self.store,
            working_dir=working_dir,
        )

    async def ask(self, blogger_id: str, question: str) -> AnswerResult:
        """对博主全部视频进行知识问答

        Args:
            blogger_id: 博主ID
            question: 用户问题

        Returns:
            AnswerResult
        """
        retrieval = await self.retriever.retrieve(question, blogger_id, mode="auto")
        context = retrieval.context_text

        if not context:
            return AnswerResult(
                question=question,
                answer="暂无该博主的索引数据，请先创建视频索引。",
                confidence=0.0,
                retrieval_mode="hybrid",
            )

        prompt = ASK_PROMPT_TEMPLATE.format(
            blogger_id=blogger_id,
            context=context,
            question=question,
        )

        try:
            response = await call_llm(
                prompt,
                system=ASK_SYSTEM_PROMPT,
                task_type="default",
            )

            result = parse_llm_json(response, fallback={
                "answer": response,
                "confidence": 0.5,
                "references": [],
            })

            return AnswerResult(
                question=question,
                answer=result.get("answer", response),
                confidence=float(result.get("confidence", 0.5)),
                references=result.get("references", []),
                retrieval_mode=f"hybrid(text={retrieval.total_text_results},visual={retrieval.total_visual_results})",
            )

        except Exception as e:
            logger.error("博主知识问答失败: %s", e)
            return AnswerResult(
                question=question,
                answer=f"问答失败: {str(e)}",
                confidence=0.0,
                retrieval_mode="hybrid",
            )

    async def search_content(
        self,
        blogger_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """在博主视频中搜索特定内容

        Args:
            blogger_id: 博主ID
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            匹配的内容片段列表
        """
        retrieval = await self.retriever.retrieve(query, blogger_id, mode="auto", top_k=top_k)
        context = retrieval.context_text

        if not context:
            return []

        search_prompt = f"""在以下博主视频内容中搜索与"{query}"相关的片段：

{context}

请列出所有相关片段，输出JSON数组：
[{{"video": "视频名", "time": "时间段", "content": "相关内容", "relevance": 0.0-1.0}}]"""

        try:
            response = await call_llm(
                search_prompt,
                system="你是一个内容检索专家。",
                task_type="default",
            )

            results = parse_llm_json(response, fallback=[])
            if isinstance(results, dict):
                results = [results]
            return results[:top_k]

        except Exception as e:
            logger.error("内容检索失败: %s", e)
            return [m.to_dict() for m in retrieval.matches[:top_k]]

    async def get_blogger_profile(self, blogger_id: str) -> BloggerKnowledgeProfile:
        """获取博主全知识画像

        Args:
            blogger_id: 博主ID

        Returns:
            BloggerKnowledgeProfile
        """
        context = self._load_all_segments_text(blogger_id)

        if not context:
            return BloggerKnowledgeProfile(blogger_id=blogger_id)

        prompt = PROFILE_PROMPT.format(context=context[:8000])

        try:
            response = await call_llm(
                prompt,
                system="你是一个博主画像分析专家，擅长从视频内容中提取博主特征。",
                task_type="default",
            )

            result = parse_llm_json(response, fallback={})

            status = self._get_index_status(blogger_id)

            return BloggerKnowledgeProfile(
                blogger_id=blogger_id,
                narrative_style=result.get("narrative_style", ""),
                expression_style=result.get("expression_style", ""),
                vocabulary_profile=result.get("vocabulary_profile", {}),
                core_viewpoints=result.get("core_viewpoints", []),
                topic_stances=result.get("topic_stances", {}),
                primary_topics=result.get("primary_topics", []),
                topic_distribution=result.get("topic_distribution", {}),
                estimated_audience=result.get("estimated_audience", {}),
                total_videos=status.total_videos,
                total_duration_hours=status.total_duration_hours,
                last_updated=status.last_updated,
            )

        except Exception as e:
            logger.error("博主画像生成失败: %s", e)
            return BloggerKnowledgeProfile(blogger_id=blogger_id)

    async def find_contradictions(self, blogger_id: str, topic: str = "") -> List[Dict[str, Any]]:
        """发现博主在不同视频中对同一话题的矛盾观点

        Args:
            blogger_id: 博主ID
            topic: 可选，限定特定话题

        Returns:
            矛盾观点列表
        """
        context = self._load_all_segments_text(blogger_id)

        if not context:
            return []

        topic_filter = f"关于「{topic}」" if topic else ""
        prompt = f"""分析以下博主视频内容，找出{topic_filter}矛盾的观点：

{context[:8000]}

请列出所有矛盾的观点对，输出JSON数组：
[{{"topic": "话题", "viewpoint1": "观点1", "source1": "来源视频", "viewpoint2": "矛盾观点2", "source2": "来源视频2", "contradiction_type": "直接矛盾/态度转变/条件限定"}}]"""

        try:
            response = await call_llm(
                prompt,
                system="你是一个观点分析专家，擅长发现文本中的逻辑矛盾。",
                task_type="default",
            )

            results = parse_llm_json(response, fallback=[])
            if isinstance(results, dict):
                results = [results]
            return results

        except Exception as e:
            logger.error("矛盾检测失败: %s", e)
            return []

    async def get_topic_timeline(self, blogger_id: str, topic: str) -> List[Dict[str, Any]]:
        """追踪博主对某话题的观点演变时间线

        Args:
            blogger_id: 博主ID
            topic: 话题

        Returns:
            观点演变时间线
        """
        context = self._load_all_segments_text(blogger_id)

        if not context:
            return []

        prompt = f"""分析以下博主视频内容，追踪博主对「{topic}」话题的观点演变：

{context[:8000]}

请按时间顺序列出观点变化，输出JSON数组：
[{{"time": "时间点", "video": "视频名", "viewpoint": "观点内容", "stance": "positive/negative/neutral", "evolution_type": "首次提及/态度转变/深化/弱化"}}]"""

        try:
            response = await call_llm(
                prompt,
                system="你是一个观点演变分析专家。",
                task_type="default",
            )

            results = parse_llm_json(response, fallback=[])
            if isinstance(results, dict):
                results = [results]
            return results

        except Exception as e:
            logger.error("话题时间线生成失败: %s", e)
            return []

    async def _retrieve_context(
        self,
        blogger_id: str,
        query: str,
        max_segments: int = 15,
    ) -> str:
        """从知识图谱和片段数据中检索与查询相关的上下文

        第1步：基于文本的知识图谱遍历 + 片段文本匹配
        第2步将增加：视觉嵌入检索通道
        """
        context_parts = []

        try:
            self.store.connect()

            entities = self.store.search_entities(query, limit=10)
            if entities:
                entity_desc = "\n".join(
                    f"- {e.get('name', '')} ({e.get('entity_type', '')}): {e.get('properties', {}).get('description', '')}"
                    for e in entities[:10]
                )
                context_parts.append(f"【相关实体】\n{entity_desc}")

            relations = self.store.search_relations(query, limit=10)
            if relations:
                rel_desc = "\n".join(
                    f"- {r.get('source_name', '')} → {r.get('relation_type', '')} → {r.get('target_name', '')}"
                    for r in relations[:10]
                )
                context_parts.append(f"【相关关系】\n{rel_desc}")

        except Exception as e:
            logger.debug("知识图谱检索失败: %s", e)

        segments_text = self._load_all_segments_text(blogger_id)
        if segments_text:
            relevant = self._simple_text_match(segments_text, query, max_segments)
            if relevant:
                context_parts.append(f"【相关视频片段】\n{relevant}")

        return "\n\n".join(context_parts)

    def _load_all_segments_text(self, blogger_id: str) -> str:
        """加载博主所有视频片段的文本数据"""
        segments_dir = os.path.join(self.working_dir, blogger_id)
        if not os.path.isdir(segments_dir):
            return ""

        all_texts = []
        for filename in sorted(os.listdir(segments_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(segments_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                combined = data.get("combined_text", "")
                video = os.path.basename(data.get("video_path", ""))
                time_range = f"{data.get('start_time', 0):.0f}-{data.get('end_time', 0):.0f}s"
                if combined:
                    all_texts.append(f"[{video} {time_range}]\n{combined}")
            except Exception:
                continue

        return "\n\n".join(all_texts)

    def _simple_text_match(self, text: str, query: str, max_segments: int) -> str:
        """简单的文本匹配：按关键词相关性筛选片段"""
        query_words = set(query.replace("？", "").replace("？", "").split())
        segments = text.split("\n\n")
        scored = []
        for seg in segments:
            if not seg.strip():
                continue
            seg_words = set(seg)
            overlap = len(query_words & seg_words)
            if overlap > 0:
                scored.append((overlap, seg))

        scored.sort(key=lambda x: -x[0])
        return "\n\n".join(seg for _, seg in scored[:max_segments])

    def _get_index_status(self, blogger_id: str) -> IndexStatus:
        """获取索引状态"""
        status_file = os.path.join(self.working_dir, f"{blogger_id}_status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return IndexStatus(**data)
            except Exception:
                pass
        return IndexStatus(blogger_id=blogger_id)
