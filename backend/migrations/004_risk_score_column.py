"""数据库迁移脚本 - 004: risk_items 表添加 risk_score 列

为 risk_items 表添加 risk_score 数值化风险分数列 (0-100)
"""

import logging
from sqlalchemy import create_engine, text, inspect
from backend.config import settings

logger = logging.getLogger(__name__)


def add_risk_score_column(engine):
    """为 risk_items 表添加 risk_score 列"""

    with engine.connect() as conn:
        try:
            inspector = inspect(engine)
            columns = [col["name"] for col in inspector.get_columns("risk_items")]

            if "risk_score" in columns:
                logger.info("risk_score 列已存在，跳过添加")
                return

            conn.execute(text(
                "ALTER TABLE risk_items ADD COLUMN risk_score FLOAT"
            ))
            conn.commit()

            logger.info("✅ risk_items.risk_score 列添加成功")
        except Exception as e:
            logger.error("❌ 添加 risk_score 列失败：%s", e)
            raise


def run_migration():
    """执行数据库迁移"""

    logger.info("🚀 开始数据库迁移 - 004: risk_items 添加 risk_score 列")

    engine = create_engine(settings.DATABASE_URL)

    try:
        add_risk_score_column(engine)
        logger.info("✅ 数据库迁移完成！")
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
