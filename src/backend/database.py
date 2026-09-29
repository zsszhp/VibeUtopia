import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

logger = logging.getLogger(__name__)


def _build_database_url() -> str:
    """构建数据库URL：显式 sqlite/非 MySQL URL 优先，其次 MySQL，最后 settings.DATABASE_URL"""
    explicit = (settings.DATABASE_URL or "").strip()
    if explicit.startswith("sqlite") or (explicit and not explicit.startswith("mysql")):
        return explicit
    if settings.MYSQL_HOST:
        try:
            import pymysql  # noqa: F401
            url = (
                f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
                f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
                f"?charset=utf8mb4"
            )
            return url
        except ImportError:
            logger.warning("pymysql未安装，MySQL不可用，降级为SQLite")
    return settings.DATABASE_URL


def _create_engine(url: str):
    """创建数据库引擎"""
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    else:
        try:
            return create_engine(
                url,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
                pool_pre_ping=True,
            )
        except Exception:
            logger.warning("数据库引擎创建失败(%s)，降级为SQLite", url)
            sqlite_url = "sqlite:///./data/vibeutopia.db"
            return create_engine(sqlite_url, connect_args={"check_same_thread": False})


DATABASE_URL = _build_database_url()
engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _ensure_r5_task_columns():
    """R5: 已有库平滑补充 tasks 归属/工作流字段（create_all 不会改已存在的表）"""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        if "tasks" not in inspector.get_table_names():
            return
        existing = {c["name"] for c in inspector.get_columns("tasks")}
        alters: list[str] = []
        if "owner_id" not in existing:
            alters.append("ALTER TABLE tasks ADD COLUMN owner_id VARCHAR(64)")
        if "workflow_status" not in existing:
            alters.append("ALTER TABLE tasks ADD COLUMN workflow_status VARCHAR(20) DEFAULT 'draft'")
        if "workflow_history_json" not in existing:
            alters.append("ALTER TABLE tasks ADD COLUMN workflow_history_json TEXT")
        if not alters:
            return
        with engine.begin() as conn:
            for stmt in alters:
                conn.execute(text(stmt))
        logger.info("tasks 表已补充 R5 字段: %s", ", ".join(a.split("ADD COLUMN ")[-1].split(" ")[0] for a in alters))
    except Exception as e:
        logger.warning("tasks 表 R5 字段升级失败（不影响启动，新字段写入可能报错）: %s", e)


def init_db():
    # 确保 SQLite 数据库所在目录存在
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.split("///")[-1]
        db_dir = Path(db_path).parent
        if db_dir and db_dir.name:
            db_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_r5_task_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_type() -> str:
    """返回当前数据库类型"""
    return "mysql" if DATABASE_URL.startswith("mysql") else "sqlite"
