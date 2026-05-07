from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routes import router
from backend.services.signal.scheduler import SignalScheduler
from backend.services.graph.graph_store import GraphStore
from backend.config import settings

# 全局调度器实例
signal_scheduler = SignalScheduler()

# 全局图谱存储实例
graph_store = GraphStore(
    uri=settings.NEO4J_URI,
    user=settings.NEO4J_USER,
    password=settings.NEO4J_PASSWORD,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 尝试连接 Neo4j
    graph_store.connect()
    yield
    # 关闭时停止调度器
    if signal_scheduler.is_running:
        signal_scheduler.stop()
    graph_store.close()


app = FastAPI(title="VibeUtopia", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
