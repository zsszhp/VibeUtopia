"""ChromaDB 模型预热机制

解决首次检索延迟高的问题，通过应用启动时预加载 ONNX 模型。
"""

import logging
import time
import os
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ChromaModelWarmup:
    """ChromaDB 模型预热器"""
    
    def __init__(self, persist_dir: str = "./data/chroma_memories"):
        self.persist_dir = persist_dir
        self._warmed_up = False
        self._warmup_time: Optional[float] = None
        self._client = None
        self._collection = None
    
    def warmup(self) -> bool:
        """执行模型预热"""
        if self._warmed_up:
            logger.info("ChromaDB 模型已预热完成，跳过")
            return True
        
        start_time = time.time()
        
        try:
            try:
                import chromadb
            except ImportError:
                logger.warning("ChromaDB 未安装，跳过模型预热")
                return False
            
            logger.info("开始预热 ChromaDB 模型...")
            
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            
            self._collection = self._client.get_or_create_collection(
                name="memory_stream",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB 集合已加载")
            
            try:
                results = self._collection.query(
                    query_texts=["warmup query"],
                    n_results=1,
                )
                logger.info("ChromaDB 虚拟检索完成，模型已激活")
            except Exception as query_error:
                logger.debug("虚拟检索返回空结果 (集合为空): %s", query_error)
            
            self._warmed_up = True
            self._warmup_time = time.time() - start_time
            
            logger.info("ChromaDB 模型预热完成，耗时 %.2f 秒", self._warmup_time)
            return True
            
        except Exception as e:
            logger.error("ChromaDB 模型预热失败：%s", e)
            self._warmed_up = False
            self._warmup_time = None
            return False
    
    @property
    def is_warmed_up(self) -> bool:
        return self._warmed_up
    
    @property
    def warmup_time(self) -> Optional[float]:
        return self._warmup_time
    
    def get_status(self) -> dict:
        return {
            "warmed_up": self._warmed_up,
            "warmup_time_seconds": self._warmup_time,
            "persist_dir": self.persist_dir,
            "chroma_available": self._client is not None,
        }


_warmup_instance: Optional[ChromaModelWarmup] = None


def warmup_chroma_model(persist_dir: str = "./data/chroma_memories") -> bool:
    global _warmup_instance
    if _warmup_instance is None:
        _warmup_instance = ChromaModelWarmup(persist_dir=persist_dir)
    return _warmup_instance.warmup()


def get_warmup_status() -> dict:
    global _warmup_instance
    if _warmup_instance is None:
        return {"warmed_up": False, "warmup_time_seconds": None, "status": "未初始化"}
    return _warmup_instance.get_status()


def initialize_on_startup():
    """应用启动时自动触发预热"""
    logger.info("应用启动，触发 ChromaDB 模型预热...")
    
    persist_dir = Path("./data/chroma_memories")
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    success = warmup_chroma_model(str(persist_dir))
    
    if success:
        logger.info("ChromaDB 模型预热成功，首次检索延迟将降至<100ms")
    else:
        logger.warning("ChromaDB 模型预热失败，首次检索将包含模型加载延迟")
    
    return success
