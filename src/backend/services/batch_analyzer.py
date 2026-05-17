"""批量分析优化 — 队列处理 + 结果缓存 + 增量分析 + 异步流水线

支持批量提交分析任务，通过 asyncio.Queue 管理队列，
结果缓存避免重复分析，增量分析只处理变化部分，
异步流水线 + 信号量并发控制优化 LLM 调用。
"""

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BatchStatus(str, Enum):
    """批量任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ItemStatus(str, Enum):
    """单项任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"
    SKIPPED = "skipped"


@dataclass
class BatchItem:
    """批量分析中的单项"""
    item_id: str = ""
    content: str = ""
    mode: str = "quick"
    status: ItemStatus = ItemStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    content_hash: str = ""
    processing_time: float = 0.0

    def __post_init__(self):
        if not self.item_id:
            self.item_id = f"item_{uuid.uuid4().hex[:8]}"
        if not self.content_hash:
            self.content_hash = self._compute_hash(self.content)

    @staticmethod
    def _compute_hash(content: str) -> str:
        """计算内容哈希（用于缓存和增量检测）"""
        normalized = content.strip().lower()
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()


@dataclass
class BatchResult:
    """批量分析结果"""
    batch_id: str = ""
    status: BatchStatus = BatchStatus.PENDING
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    cached_items: int = 0
    skipped_items: int = 0
    items: List[BatchItem] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    total_processing_time: float = 0.0
    llm_calls_saved: int = 0

    def get_progress(self) -> float:
        """获取完成进度 (0-1)"""
        if self.total_items == 0:
            return 0.0
        done = self.completed_items + self.failed_items + self.cached_items + self.skipped_items
        return round(done / self.total_items, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "cached_items": self.cached_items,
            "skipped_items": self.skipped_items,
            "progress": self.get_progress(),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_processing_time": round(self.total_processing_time, 2),
            "llm_calls_saved": self.llm_calls_saved,
        }


class ResultCache:
    """结果缓存 — 相同内容不重复分析"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, content_hash: str, mode: str = "quick") -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        cache_key = f"{content_hash}_{mode}"
        result = self._cache.get(cache_key)
        if result is not None:
            self._hits += 1
            return result
        self._misses += 1
        return None

    def put(self, content_hash: str, mode: str, result: Dict[str, Any]):
        """存储结果到缓存"""
        if len(self._cache) >= self._max_size:
            # 简单 LRU：删除最早的 20%
            keys_to_remove = list(self._cache.keys())[:self._max_size // 5]
            for k in keys_to_remove:
                del self._cache[k]

        cache_key = f"{content_hash}_{mode}"
        self._cache[cache_key] = result

    def has(self, content_hash: str, mode: str = "quick") -> bool:
        """检查缓存是否存在"""
        cache_key = f"{content_hash}_{mode}"
        return cache_key in self._cache

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }


class IncrementalDetector:
    """增量分析检测器 — 只分析变化部分"""

    def __init__(self):
        self._previous_hashes: Dict[str, str] = {}  # batch_id -> hash of all contents

    def detect_changes(self, batch_id: str, items: List[BatchItem]) -> List[BatchItem]:
        """检测变化的项（与上次同批次对比）

        降级机制：如果没有历史记录，所有项都视为变化
        """
        if batch_id not in self._previous_hashes:
            return items

        # 计算当前批次的内容指纹
        changed = []
        for item in items:
            prev_hash = self._previous_hashes.get(f"{batch_id}_{item.item_id}")
            if prev_hash is None or prev_hash != item.content_hash:
                changed.append(item)

        return changed if changed else items

    def record_batch(self, batch_id: str, items: List[BatchItem]):
        """记录批次内容指纹"""
        for item in items:
            self._previous_hashes[f"{batch_id}_{item.item_id}"] = item.content_hash

    def clear(self, batch_id: str = ""):
        """清除记录"""
        if batch_id:
            keys_to_remove = [k for k in self._previous_hashes if k.startswith(f"{batch_id}_")]
            for k in keys_to_remove:
                del self._previous_hashes[k]
        else:
            self._previous_hashes.clear()


class BatchAnalyzer:
    """批量分析管理器

    支持：
    - 批量提交 + 队列处理（asyncio.Queue）
    - 结果缓存（相同内容不重复分析）
    - 增量分析（只分析变化部分）
    - LLM 调用量优化：异步流水线 + 并发控制（信号量限制）
    - 进度追踪和回调
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        cache_size: int = 1000,
        enable_cache: bool = True,
        enable_incremental: bool = True,
    ):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # 结果缓存
        self._cache = ResultCache(max_size=cache_size)
        self._enable_cache = enable_cache

        # 增量检测
        self._incremental = IncrementalDetector()
        self._enable_incremental = enable_incremental

        # 批次管理
        self._batches: Dict[str, BatchResult] = {}

        # 进度回调
        self._progress_callbacks: Dict[str, List[Callable]] = {}

        # 处理任务
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动批量处理器"""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("BatchAnalyzer: 启动，最大并发=%d", self._max_concurrent)

    async def stop(self):
        """停止批量处理器"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("BatchAnalyzer: 已停止")

    async def submit(
        self,
        contents: List[str],
        mode: str = "quick",
        batch_id: str = "",
        on_progress: Optional[Callable] = None,
    ) -> BatchResult:
        """提交批量分析任务

        Args:
            contents: 待分析内容列表
            mode: 分析模式 quick/deep
            batch_id: 批次ID（可选，自动生成）
            on_progress: 进度回调函数

        Returns:
            BatchResult: 批次结果（初始状态为 PENDING）
        """
        batch_id = batch_id or f"batch_{uuid.uuid4().hex[:8]}"

        items = []
        for content in contents:
            item = BatchItem(content=content, mode=mode)
            items.append(item)

        result = BatchResult(
            batch_id=batch_id,
            total_items=len(items),
            items=items,
        )

        # 增量检测
        if self._enable_incremental:
            changed_items = self._incremental.detect_changes(batch_id, items)
            unchanged_hashes = {item.content_hash for item in items} - {item.content_hash for item in changed_items}

            for item in items:
                if item.content_hash in unchanged_hashes and self._cache.has(item.content_hash, mode):
                    cached = self._cache.get(item.content_hash, mode)
                    if cached:
                        item.status = ItemStatus.CACHED
                        item.result = cached
                        result.cached_items += 1
                        result.llm_calls_saved += 1

        # 注册回调
        if on_progress:
            self._progress_callbacks.setdefault(batch_id, []).append(on_progress)

        # 入队
        self._batches[batch_id] = result
        for item in items:
            if item.status not in (ItemStatus.CACHED,):
                await self._queue.put((batch_id, item))

        # 如果队列为空（全部缓存），直接完成
        if result.cached_items == result.total_items:
            result.status = BatchStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc).isoformat()
            self._notify_progress(batch_id, result)

        logger.info(
            "BatchAnalyzer: 提交批次 %s, %d 项（缓存 %d 项）",
            batch_id, result.total_items, result.cached_items,
        )
        return result

    def get_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批次状态"""
        result = self._batches.get(batch_id)
        if not result:
            return None
        return result.to_dict()

    def get_results(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批次结果"""
        result = self._batches.get(batch_id)
        if not result:
            return None

        return {
            "batch_id": result.batch_id,
            "status": result.status.value,
            "total_items": result.total_items,
            "completed_items": result.completed_items,
            "failed_items": result.failed_items,
            "cached_items": result.cached_items,
            "progress": result.get_progress(),
            "total_processing_time": round(result.total_processing_time, 2),
            "llm_calls_saved": result.llm_calls_saved,
            "items": [
                {
                    "item_id": item.item_id,
                    "content_hash": item.content_hash,
                    "status": item.status.value,
                    "result": item.result,
                    "error": item.error,
                    "processing_time": round(item.processing_time, 3),
                }
                for item in result.items
            ],
        }

    def on_progress(self, batch_id: str, callback: Callable):
        """注册进度回调"""
        self._progress_callbacks.setdefault(batch_id, []).append(callback)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self._cache.get_stats()

    async def _process_loop(self):
        """批量处理主循环"""
        while self._running:
            try:
                batch_id, item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                asyncio.create_task(self._process_item(batch_id, item))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("BatchAnalyzer: 处理循环异常: %s", e)

    async def _process_item(self, batch_id: str, item: BatchItem):
        """处理单个分析项（异步流水线 + 并发控制）"""
        async with self._semaphore:
            result = self._batches.get(batch_id)
            if not result:
                return

            item.status = ItemStatus.PROCESSING
            start_time = time.time()

            try:
                # 缓存检查
                if self._enable_cache:
                    cached = self._cache.get(item.content_hash, item.mode)
                    if cached:
                        item.status = ItemStatus.CACHED
                        item.result = cached
                        item.processing_time = time.time() - start_time
                        result.cached_items += 1
                        result.llm_calls_saved += 1
                        self._update_batch_status(result)
                        self._notify_progress(batch_id, result)
                        return

                # 执行分析
                analysis_result = await self._run_analysis(item)

                item.status = ItemStatus.COMPLETED
                item.result = analysis_result
                item.processing_time = time.time() - start_time
                result.completed_items += 1

                # 缓存结果
                if self._enable_cache and analysis_result:
                    self._cache.put(item.content_hash, item.mode, analysis_result)

            except Exception as e:
                logger.error("BatchAnalyzer: 处理项 %s 失败: %s", item.item_id, e)
                item.status = ItemStatus.FAILED
                item.error = str(e)
                item.processing_time = time.time() - start_time
                result.failed_items += 1

            # 记录增量指纹
            if self._enable_incremental:
                self._incremental.record_batch(batch_id, [item])

            result.total_processing_time += item.processing_time
            self._update_batch_status(result)
            self._notify_progress(batch_id, result)

    async def _run_analysis(self, item: BatchItem) -> Dict[str, Any]:
        """执行单次分析（调用增强风控分析器）

        降级机制：如果增强分析器不可用，回退到基础分析
        """
        try:
            from backend.services.enhanced_analyzer import run_enhanced_analysis
            from backend.database import SessionLocal
            from backend.models import Task

            task_id = f"batch_{item.item_id}_{uuid.uuid4().hex[:6]}"
            db = SessionLocal()
            try:
                task = Task(id=task_id, text=item.content[:500], status="processing", model=f"batch-{item.mode}")
                db.add(task)
                db.commit()
            finally:
                db.close()

            analysis = await run_enhanced_analysis(
                task_id=task_id,
                text=item.content,
                mode=item.mode,
                enable_signal=True,
                enable_entity_chain=True,
                enable_simulation=False,
            )

            return {
                "task_id": task_id,
                "mvp_score": analysis.mvp_overall_score,
                "v2_score": analysis.v2_overall_score,
                "mvp_suggestion": analysis.mvp_suggestion,
                "v2_suggestion": analysis.v2_suggestion,
                "mvp_dimensions": analysis.mvp_dimensions,
                "v2_dimensions": analysis.v2_dimensions,
                "confidence": analysis.confidence,
            }

        except ImportError:
            # 降级：增强分析器不可用时使用基础分析
            logger.warning("BatchAnalyzer: 增强分析器不可用，降级到基础分析")
            return await self._fallback_analysis(item)

        except Exception as e:
            logger.error("BatchAnalyzer: 分析执行失败: %s", e)
            return await self._fallback_analysis(item)

    async def _fallback_analysis(self, item: BatchItem) -> Dict[str, Any]:
        """降级分析（基础规则分析，无 LLM 调用）"""
        content = item.content

        # 简单关键词风险评分
        high_risk_keywords = ["造假", "欺诈", "违法", "抄袭", "歧视", "暴力", "色情"]
        medium_risk_keywords = ["争议", "质疑", "批评", "不满", "反对", "抵制"]
        low_risk_keywords = ["关注", "讨论", "建议", "不同", "看法"]

        score = 0
        for kw in high_risk_keywords:
            if kw in content:
                score += 20
        for kw in medium_risk_keywords:
            if kw in content:
                score += 10
        for kw in low_risk_keywords:
            if kw in content:
                score += 5

        score = min(score, 100)

        return {
            "task_id": f"fallback_{item.item_id}",
            "mvp_score": score,
            "v2_score": score,
            "mvp_suggestion": "高风险" if score > 60 else ("中风险" if score > 30 else "低风险"),
            "v2_suggestion": "降级分析结果，建议重新分析",
            "mvp_dimensions": {},
            "v2_dimensions": {},
            "confidence": 0.3,
            "fallback": True,
        }

    def _update_batch_status(self, result: BatchResult):
        """更新批次状态"""
        done = result.completed_items + result.failed_items + result.cached_items + result.skipped_items
        if done >= result.total_items:
            if result.failed_items > 0 and result.completed_items > 0:
                result.status = BatchStatus.PARTIAL
            elif result.failed_items == result.total_items:
                result.status = BatchStatus.FAILED
            else:
                result.status = BatchStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc).isoformat()
        else:
            result.status = BatchStatus.PROCESSING

    def _notify_progress(self, batch_id: str, result: BatchResult):
        """通知进度回调"""
        callbacks = self._progress_callbacks.get(batch_id, [])
        for cb in callbacks:
            try:
                cb(result.to_dict())
            except Exception as e:
                logger.error("BatchAnalyzer: 进度回调异常: %s", e)

        # 完成后清理回调
        if result.status in (BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.PARTIAL):
            self._progress_callbacks.pop(batch_id, None)
