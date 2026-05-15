"""ChromaDB 初始化脚本

测试 ChromaDB 连接和 Memory Stream 功能
"""

import logging
from pathlib import Path
from backend.services.persona.memory_stream import MemoryStreamStore

logger = logging.getLogger(__name__)


def test_chromadb_connection():
    """测试 ChromaDB 连接"""
    
    persist_dir = "./data/chroma_memories"
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        store = MemoryStreamStore(persist_dir=persist_dir)
        
        if store.is_chroma_available:
            logger.info("✅ ChromaDB 连接成功")
            logger.info(f"📁 持久化目录：{persist_dir}")
            return True
        else:
            logger.warning("⚠️  ChromaDB 不可用，降级为数据库检索")
            return False
            
    except Exception as e:
        logger.error(f"❌ ChromaDB 连接失败：{e}")
        return False


def test_memory_store():
    """测试 Memory Stream 存储和检索"""
    
    logger.info("🧪 开始 Memory Stream 功能测试")
    
    store = MemoryStreamStore(persist_dir="./data/chroma_memories")
    
    # 测试 1: 单条存储
    logger.info("\n测试 1: 单条存储")
    memory_id = store.store(
        agent_id="test_agent_001",
        content="测试记忆内容：今天天气不错",
        memory_type="observation",
        importance=0.6,
        tags=["测试", "日常"],
    )
    logger.info(f"✅ 存储成功，memory_id: {memory_id}")
    
    # 测试 2: 批量存储
    logger.info("\n测试 2: 批量存储")
    memories = [
        {"content": "童年经历：在北京长大", "type": "observation", "importance": 0.8},
        {"content": "价值观：重视公平和正义", "type": "reflection", "importance": 0.9},
        {"content": "计划：明天要读一本书", "type": "plan", "importance": 0.4},
        {"content": "观察：看到 AI 发展的新闻", "type": "observation", "importance": 0.7},
        {"content": "反思：技术应该服务于人类", "type": "reflection", "importance": 0.85},
    ]
    memory_ids = store.store_batch(agent_id="test_agent_001", memories=memories)
    logger.info(f"✅ 批量存储成功，数量：{len(memory_ids)}")
    
    # 测试 3: 三因子检索
    logger.info("\n测试 3: 三因子检索")
    results = store.retrieve(
        agent_id="test_agent_001",
        query="对技术和 AI 的看法",
        top_k=5,
    )
    logger.info(f"✅ 检索成功，返回：{len(results)} 条")
    for i, mem in enumerate(results, 1):
        logger.info(f"{i}. [{mem['memory_type']}] {mem['content'][:50]}...")
        logger.info(f"   综合得分：{mem['composite_score']:.3f}")
        logger.info(f"   - Recency: {mem.get('recency_score', 'N/A')}")
        logger.info(f"   - Importance: {mem['importance']:.2f}")
        logger.info(f"   - Relevance: {mem.get('relevance_score', 'N/A')}")
    
    # 测试 4: 获取最近记忆
    logger.info("\n测试 4: 获取最近记忆")
    recent = store.get_recent(agent_id="test_agent_001", limit=10)
    logger.info(f"✅ 获取成功，数量：{len(recent)}")
    for mem in recent:
        logger.info(f"- [{mem['memory_type']}] {mem['content'][:50]}...")
    
    # 测试 5: Reflection 触发检查
    logger.info("\n测试 5: Reflection 触发检查")
    # 添加更多 observation 记忆以触发 Reflection
    for i in range(5):
        store.store(
            agent_id="test_agent_002",
            content=f"观察记忆{i}: 看到关于{i*10}的话题讨论",
            memory_type="observation",
            importance=0.6,
        )
    
    triggered = store.check_and_trigger_reflection(agent_id="test_agent_002")
    if triggered:
        logger.info("✅ Reflection 机制已触发")
    else:
        logger.info("ℹ️  未达到 Reflection 触发阈值")
    
    logger.info("\n✅ Memory Stream 功能测试完成")


def cleanup_test_data():
    """清理测试数据"""
    
    logger.info("🧹 清理测试数据...")
    
    from sqlalchemy import create_engine, text
    from backend.config import settings
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            conn.execute(text("DELETE FROM agent_memories WHERE agent_id LIKE 'test_agent_%'"))
            conn.execute(text("DELETE FROM agent_profiles WHERE agent_id LIKE 'test_agent_%'"))
            conn.commit()
            logger.info("✅ 测试数据清理完成")
        except Exception as e:
            logger.error(f"❌ 清理失败：{e}")
        finally:
            engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # 测试 ChromaDB 连接
    chroma_ok = test_chromadb_connection()
    
    if chroma_ok:
        # 运行 Memory Stream 测试
        test_memory_store()
        
        # 清理测试数据
        cleanup_test_data()
    else:
        logger.warning("⚠️  ChromaDB 不可用，跳过功能测试")
