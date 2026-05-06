from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    # 确保 SQLite 数据库所在目录存在
    if settings.DATABASE_URL.startswith("sqlite"):
        db_path = settings.DATABASE_URL.split("///")[-1]
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
