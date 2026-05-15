"""数据库迁移脚本 - 阶段 3: ChromaDB + Memory Stream

创建 Agent 记忆和人格相关表
"""

import logging
from sqlalchemy import create_engine, text
from backend.config import settings

logger = logging.getLogger(__name__)


def create_agent_memories_table(engine):
    """创建 Agent 记忆表
    
    SQLite 兼容版本（不使用 ENUM 和 MySQL 特定语法）
    注意：weight 字段用于向后兼容现有代码
    """
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS agent_memories (
        memory_id VARCHAR(36) PRIMARY KEY,
        agent_id VARCHAR(36) NOT NULL,
        memory_type VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        importance REAL DEFAULT 0.5,
        weight REAL DEFAULT 0.5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        access_count INTEGER DEFAULT 0,
        tags TEXT
    )
    """
    
    create_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_agent_id ON agent_memories(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memories(memory_type)",
        "CREATE INDEX IF NOT EXISTS idx_created_at ON agent_memories(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_agent_type ON agent_memories(agent_id, memory_type)",
    ]
    
    with engine.connect() as conn:
        try:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            
            # 创建索引
            for index_sql in create_indexes:
                conn.execute(text(index_sql))
                conn.commit()
            
            logger.info("✅ agent_memories 表创建成功")
        except Exception as e:
            logger.error("❌ 创建 agent_memories 表失败：%s", e)
            raise


def create_agent_profiles_table(engine):
    """创建 Agent 人格表
    
    SQLite 兼容版本
    """
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS agent_profiles (
        agent_id VARCHAR(36) PRIMARY KEY,
        platform VARCHAR(50) NOT NULL,
        archetype_base VARCHAR(100),
        tier VARCHAR(1) DEFAULT 'B',
        layer1_basic TEXT,
        layer2_values TEXT,
        layer3_knowledge TEXT,
        layer4_behavior TEXT,
        layer5_constraints TEXT,
        layer6_relations TEXT,
        layer7_state TEXT,
        life_story_path VARCHAR(255),
        quality_score REAL,
        status VARCHAR(20) DEFAULT 'active',
        version INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    create_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_platform ON agent_profiles(platform)",
        "CREATE INDEX IF NOT EXISTS idx_tier ON agent_profiles(tier)",
        "CREATE INDEX IF NOT EXISTS idx_status ON agent_profiles(status)",
    ]
    
    with engine.connect() as conn:
        try:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            
            # 创建索引
            for index_sql in create_indexes:
                conn.execute(text(index_sql))
                conn.commit()
            
            logger.info("✅ agent_profiles 表创建成功")
        except Exception as e:
            logger.error("❌ 创建 agent_profiles 表失败：%s", e)
            raise


def create_social_relations_table(engine):
    """创建社交关系表
    
    SQLite 兼容版本
    """
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS social_relations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id_a VARCHAR(36) NOT NULL,
        agent_id_b VARCHAR(36) NOT NULL,
        relation_type VARCHAR(20) NOT NULL,
        weight REAL DEFAULT 1.0,
        platform VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    create_indexes = [
        "CREATE UNIQUE INDEX IF NOT EXISTS unique_relation ON social_relations(agent_id_a, agent_id_b, relation_type)",
        "CREATE INDEX IF NOT EXISTS idx_agent_a ON social_relations(agent_id_a)",
        "CREATE INDEX IF NOT EXISTS idx_agent_b ON social_relations(agent_id_b)",
        "CREATE INDEX IF NOT EXISTS idx_relation_type ON social_relations(relation_type)",
    ]
    
    with engine.connect() as conn:
        try:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            
            # 创建索引
            for index_sql in create_indexes:
                conn.execute(text(index_sql))
                conn.commit()
            
            logger.info("✅ social_relations 表创建成功")
        except Exception as e:
            logger.error("❌ 创建 social_relations 表失败：%s", e)
            raise


def run_migration():
    """执行数据库迁移"""
    
    logger.info("🚀 开始数据库迁移 - 阶段 3: ChromaDB + Memory Stream")
    
    # 创建数据库引擎
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # 创建表
        create_agent_memories_table(engine)
        create_agent_profiles_table(engine)
        create_social_relations_table(engine)
        
        logger.info("✅ 数据库迁移完成！")
        logger.info("创建的表:")
        logger.info("  - agent_memories (Agent 记忆)")
        logger.info("  - agent_profiles (Agent 人格)")
        logger.info("  - social_relations (社交关系)")
        
    except Exception as e:
        logger.error("❌ 迁移失败：%s", e)
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_migration()
