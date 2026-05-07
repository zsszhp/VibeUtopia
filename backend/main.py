from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routes import router
from backend.services.signal.scheduler import SignalScheduler

# 全局调度器实例
signal_scheduler = SignalScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # 关闭时停止调度器
    if signal_scheduler.is_running:
        signal_scheduler.stop()


app = FastAPI(title="VibeUtopia", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
