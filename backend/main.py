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

# WebSocket连接管理
ws_connections: dict[str, list] = {}  # sim_id -> [websocket]


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


app = FastAPI(title="VibeUtopia", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


# ─── WebSocket端点 ────────────────────────────────────────────────

@app.websocket("/ws/simulation/{sim_id}")
async def ws_simulation(websocket, sim_id: str):
    """仿真状态实时推送WebSocket"""
    await websocket.accept()

    if sim_id not in ws_connections:
        ws_connections[sim_id] = []
    ws_connections[sim_id].append(websocket)

    try:
        while True:
            # 保持连接，接收客户端消息（如控制指令）
            data = await websocket.receive_text()
            # 可以处理客户端发来的控制指令
            import json
            try:
                msg = json.loads(data)
                if msg.get("action") == "pause":
                    # 暂停仿真逻辑（待实现）
                    await websocket.send_json({"type": "ack", "action": "paused"})
                elif msg.get("action") == "resume":
                    await websocket.send_json({"type": "ack", "action": "resumed"})
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        if sim_id in ws_connections:
            ws_connections[sim_id].remove(websocket)
            if not ws_connections[sim_id]:
                del ws_connections[sim_id]


async def broadcast_simulation_update(sim_id: str, data: dict):
    """向所有监听某仿真的WebSocket客户端广播更新"""
    if sim_id in ws_connections:
        import json
        message = json.dumps(data, ensure_ascii=False)
        for ws in ws_connections[sim_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass
