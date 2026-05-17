import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

logger = logging.getLogger(__name__)


def _build_database_url() -> str:
    """构建数据库URL：MySQL优先，SQLite降级"""
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


def init_db():
    # 确保 SQLite 数据库所在目录存在
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.split("///")[-1]
        db_dir = Path(db_path).parent
        if db_dir and db_dir.name:
            db_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_type() -> str:
    """返回当前数据库类型"""
    return "mysql" if DATABASE_URL.startswith("mysql") else "sqlite"
