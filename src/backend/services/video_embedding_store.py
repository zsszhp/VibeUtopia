from __future__ import annotations

"""视觉嵌入存储 — Chinese-CLIP驱动

存储和检索视频片段的多模态嵌入向量，支持文本→视觉跨模态检索。
API模式：使用远程Embedding API（如阿里/智谱）
本地模式：使用Chinese-CLIP模型
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VideoSegmentMatch:
    """视频片段匹配结果"""

    def __init__(
        self,
        segment_id: str,
        video_path: str,
        start_time: float,
        end_time: float,
        score: float,
        blogger_id: str = "",
        combined_text: str = "",
    ):
        self.segment_id = segment_id
        self.video_path = video_path
        self.start_time = start_time
        self.end_time = end_time
        self.score = score
        self.blogger_id = blogger_id
        self.combined_text = combined_text

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "video_path": self.video_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "score": round(self.score, 4),
            "blogger_id": self.blogger_id,
            "combined_text": self.combined_text[:200],
        }


class VideoEmbeddingStore:
    """视觉嵌入存储

    支持两种模式：
    1. API模式（默认）：使用远程Embedding API进行文本→文本嵌入检索
    2. 本地模式：使用Chinese-CLIP进行文本→视觉嵌入检索

    第2步先用API模式快速落地，后续可切换到Chinese-CLIP获得更好的跨模态效果。
    """

    def __init__(self, persist_dir: str = "./data/blogger_embeddings"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self._embeddings: Dict[str, Dict[str, Any]] = {}
        self._load_index()

    async def encode_and_store(
        self,
        segment_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """编码文本并存储嵌入

        Args:
            segment_id: 片段ID
            text: 要编码的文本（视觉描述+ASR+OCR合并文本）
            metadata: 元数据（video_path, start_time, end_time, blogger_id等）

        Returns:
            是否存储成功
        """
        if not text.strip():
            return False

        embedding = await self._encode_text(text)
        if not embedding:
            return False

        self._embeddings[segment_id] = {
            "segment_id": segment_id,
            "text": text[:500],
            "embedding": embedding,
            "metadata": metadata,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        self._save_index()
        return True

    async def encode_and_store_batch(
        self,
        items: List[Dict[str, Any]],
    ) -> int:
        """批量编码并存储

        Args:
            items: [{segment_id, text, metadata}]

        Returns:
            成功存储的数量
        """
        success_count = 0
        for item in items:
            ok = await self.encode_and_store(
                segment_id=item["segment_id"],
                text=item["text"],
                metadata=item.get("metadata", {}),
            )
            if ok:
                success_count += 1
        return success_count

    async def search(
        self,
        query: str,
        blogger_id: str = "",
        top_k: int = 10,
    ) -> List[VideoSegmentMatch]:
        """文本查询 → 嵌入匹配 → 返回最相关的视频片段

        Args:
            query: 查询文本
            blogger_id: 限定博主ID（可选）
            top_k: 返回结果数量

        Returns:
            VideoSegmentMatch列表，按相似度降序
        """
        query_embedding = await self._encode_text(query)
        if not query_embedding:
            return []

        results = []
        for seg_id, data in self._embeddings.items():
            if blogger_id and data.get("metadata", {}).get("blogger_id") != blogger_id:
                continue

            stored_embedding = data.get("embedding", [])
            if not stored_embedding:
                continue

            score = self._cosine_similarity(query_embedding, stored_embedding)
            if score > 0.1:
                meta = data.get("metadata", {})
                results.append(VideoSegmentMatch(
                    segment_id=seg_id,
                    video_path=meta.get("video_path", ""),
                    start_time=meta.get("start_time", 0),
                    end_time=meta.get("end_time", 0),
                    score=score,
                    blogger_id=meta.get("blogger_id", ""),
                    combined_text=data.get("text", ""),
                ))

        results.sort(key=lambda x: -x.score)
        return results[:top_k]

    async def search_by_image(
        self,
        image_path: str,
        blogger_id: str = "",
        top_k: int = 10,
    ) -> List[VideoSegmentMatch]:
        """图片查询 → 视觉嵌入匹配

        当前使用OCR+文本嵌入的降级方案。
        后续接入Chinese-CLIP后可实现真正的图片→视觉嵌入匹配。
        """
        try:
            from backend.services.frame_ocr import FrameOCR
            ocr = FrameOCR()
            ocr_result = await ocr.extract_video_text([image_path])
            if ocr_result and ocr_result.all_text:
                return await self.search(ocr_result.all_text, blogger_id, top_k)
        except Exception as e:
            logger.warning("图片查询降级处理失败: %s", e)

        return []

    def delete_by_blogger(self, blogger_id: str):
        """删除指定博主的所有嵌入"""
        to_delete = [
            seg_id for seg_id, data in self._embeddings.items()
            if data.get("metadata", {}).get("blogger_id") == blogger_id
        ]
        for seg_id in to_delete:
            del self._embeddings[seg_id]
        if to_delete:
            self._save_index()
        logger.info("删除博主 %s 的 %d 个嵌入", blogger_id, len(to_delete))

    async def _encode_text(self, text: str) -> List[float]:
        """编码文本为嵌入向量

        优先使用API，降级使用简单TF-IDF风格编码。
        """
        try:
            return await self._encode_via_api(text)
        except Exception as e:
            logger.debug("API编码失败，降级为本地编码: %s", e)
            return self._encode_local(text)

    async def _encode_via_api(self, text: str) -> List[float]:
        """通过远程Embedding API编码"""
        from backend.services.llm_client import registry

        if not registry.is_loaded:
            raise RuntimeError("模型配置未加载")

        import httpx

        for ep in registry.endpoints:
            if not ep.base_url:
                continue
            embedding_url = ep.base_url.replace("/chat/completions", "").rstrip("/")
            embedding_url = f"{embedding_url}/embeddings"

            headers = {
                "Authorization": f"Bearer {ep.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": ep.model_id,
                "input": text[:512],
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(embedding_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        embedding = data.get("data", [{}])[0].get("embedding", [])
                        if embedding:
                            return embedding
            except Exception:
                continue

        raise RuntimeError("无可用Embedding API")

    def _encode_local(self, text: str) -> List[float]:
        """本地降级编码：基于字符频率的简单哈希嵌入

        维度=128，每个维度由字符n-gram的哈希值决定。
        这不是语义嵌入，但可以用于关键词匹配场景。
        """
        dim = 128
        embedding = [0.0] * dim

        for i in range(len(text) - 2):
            ngram = text[i:i + 3]
            h = hash(ngram) % dim
            embedding[h] += 1.0

        for i in range(min(len(text) - 2, 50)):
            ngram = text[i:i + 2]
            h = hash(ngram) % dim
            embedding[h] += 0.5

        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _load_index(self):
        """加载嵌入索引"""
        index_file = os.path.join(self.persist_dir, "embedding_index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    self._embeddings = json.load(f)
                logger.info("加载嵌入索引: %d 条", len(self._embeddings))
            except Exception as e:
                logger.warning("加载嵌入索引失败: %s", e)
                self._embeddings = {}

    def _save_index(self):
        """保存嵌入索引"""
        index_file = os.path.join(self.persist_dir, "embedding_index.json")
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(self._embeddings, f, ensure_ascii=False)
        except Exception as e:
            logger.error("保存嵌入索引失败: %s", e)
