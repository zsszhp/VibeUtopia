import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.auth import check_ws_api_key, is_auth_enabled, require_api_key
from backend.database import init_db
from backend.routes import router
from backend.services.signal.scheduler import SignalScheduler
from backend.services.graph.graph_store import GraphStore
from backend.services.analyzer import set_broadcast_func
from backend.config import settings
from backend.services.chroma_model_warmup import initialize_on_startup

logger = logging.getLogger(__name__)

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
review_ws_connections: dict[str, list] = {}  # task_id -> [websocket]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 尝试连接 Neo4j
    graph_store.connect()
    # 注入 WebSocket 广播函数到 analyzer
    set_broadcast_func(broadcast_review_update)
    # 预热 ChromaDB 模型 (优化首次检索延迟)
    initialize_on_startup()
    yield
    # 关闭时停止调度器
    if signal_scheduler.is_running:
        signal_scheduler.stop()
    graph_store.close()


app = FastAPI(
    title="VibeUtopia",
    version="0.5.0",
    lifespan=lifespan,
    description=(
        "内容预审风控平台 API。\n\n"
        "## 鉴权\n"
        "生产环境必须配置环境变量 `API_KEY`，所有 `/api/**` 与 `/ws/**` 请求须携带 "
        "`X-API-Key: <key>` 或 `Authorization: Bearer <key>`。\n"
        "未配置 `API_KEY` 时仅限本地开发放行（响应头 `X-API-Auth: disabled`），禁止裸奔上生产。"
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_mode_headers(request: Request, call_next):
    """响应头标注鉴权模式：未启用时明确提示生产必须配置 API_KEY"""
    response = await call_next(request)
    if is_auth_enabled():
        response.headers["X-API-Auth"] = "api-key"
    else:
        response.headers["X-API-Auth"] = "disabled"
        response.headers["X-API-Auth-Warning"] = (
            "API_KEY not configured; authentication is DISABLED. "
            "Production deployments MUST set API_KEY."
        )
    return response


# 路由统一挂鉴权依赖：配置了 API_KEY 则校验 X-API-Key / Authorization: Bearer，未配置放行
# （危险端点 delete / resume delete / set-model-override / upload 均被覆盖）
_AUTH_DEPS = [Depends(require_api_key)]


# ─── 统一错误响应（前端固定解析 response.data.detail） ──────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """4xx/5xx 统一为 {"detail": "<可读消息>"}，保证前端可解析。"""
    detail = exc.detail
    if not isinstance(detail, str):
        detail = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验失败 422，detail 收敛为可展示字符串而非对象数组。"""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        msg = str(err.get("msg", "参数无效"))
        parts.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=422, content={"detail": "请求参数校验失败: " + "; ".join(parts)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底 5xx：服务端记完整堆栈，客户端只拿到通用消息，避免内部信息外泄。"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


@app.get("/health", tags=["ops"])
async def health():
    """存活探活端点：供 Docker/K8s/SLB 与一键启动脚本探测服务状态"""
    return {"status": "ok", "service": "vibeutopia", "version": app.version}


@app.get("/healthz", tags=["ops"], include_in_schema=False)
async def healthz():
    return {"status": "ok"}


@app.get("/api/v1/health", tags=["ops"], dependencies=_AUTH_DEPS)
async def health_v1():
    """文档与运维脚本约定的健康检查路径（与 /health 等价，受 API Key 保护）。

    免鉴权探活请使用 /health、/healthz、/ready。
    """
    return {"status": "ok", "service": "vibeutopia", "version": app.version}


@app.get("/ready", tags=["ops"])
async def ready():
    """就绪探针（readiness）：检查数据库连接是否可用。"""
    from sqlalchemy import text

    from backend.database import engine

    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.warning("就绪检查失败: database 不可用: %s", e)
        checks["database"] = "unavailable"
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ok", "checks": checks}


# 路由统一挂鉴权依赖（_AUTH_DEPS 已在上方定义）

app.include_router(router, prefix="/api/v1", dependencies=_AUTH_DEPS)

# 注册阶段 3 新增路由（装饰器为相对路径，前缀在此统一挂载，避免双重前缀）
from backend.routes_v3 import router as router_v3
app.include_router(router_v3, prefix="/api/v3", dependencies=_AUTH_DEPS)

# 注册博主多视频知识引擎路由
from backend.routes_blogger import router as router_blogger
app.include_router(router_blogger, prefix="/api/v1", dependencies=_AUTH_DEPS)

# 注册本地模型部署管理路由 (V3.2)
from backend.routes_local_models import router as router_local_models
app.include_router(router_local_models, dependencies=_AUTH_DEPS)

# 注册断点续传路由
from backend.routes_resume import router as router_resume
app.include_router(router_resume, prefix="/api/v1", dependencies=_AUTH_DEPS)

# 注册人生故事生成路由（路由自身携带 prefix=/api/v1/story，此处不叠加前缀）
from backend.routes_story import router as router_story
app.include_router(router_story, dependencies=_AUTH_DEPS)


# ─── WebSocket端点 ────────────────────────────────────────────────

@app.websocket("/ws/simulation/{sim_id}")
async def ws_simulation(websocket: WebSocket, sim_id: str):
    """仿真状态实时推送WebSocket"""
    if not await check_ws_api_key(websocket):
        await websocket.close(code=1008, reason="missing or invalid API key")
        return
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


@app.websocket("/ws/review/{task_id}")
async def ws_review_progress(websocket: WebSocket, task_id: str):
    """预审分析进度实时推送WebSocket — 5步骤进度格式

    推送消息类型:
    - step_update: 步骤变更 (understanding→assessment→signal→simulation→report)
    - risk_alert: 风险预警弹窗
    - review_complete: 分析完成，完整报告已可查询
    """
    if not await check_ws_api_key(websocket):
        await websocket.close(code=1008, reason="missing or invalid API key")
        return
    await websocket.accept()

    if task_id not in review_ws_connections:
        review_ws_connections[task_id] = []
    review_ws_connections[task_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            import json
            try:
                msg = json.loads(data)
                # 客户端可请求当前进度
                if msg.get("action") == "get_progress":
                    await websocket.send_json({
                        "type": "step_update",
                        "task_id": task_id,
                        "step": "assessment",
                        "progress": 0.0,
                        "detail": "查询中...",
                    })
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        if task_id in review_ws_connections:
            review_ws_connections[task_id].remove(websocket)
            if not review_ws_connections[task_id]:
                del review_ws_connections[task_id]


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


async def broadcast_review_update(task_id: str, data: dict):
    """向所有监听某预审任务的WebSocket客户端广播进度更新

    消息格式对齐设计文档5步骤:
    - step_update: {type, task_id, step, progress, detail, completed_dimensions, remaining_dimensions}
      step取值: understanding / assessment / signal / simulation / report
    - risk_alert: {type, task_id, dimension, score, severity, evidence}
    - review_complete: {type, task_id, risk_level, overall_risk, dimensions_count}
    """
    if task_id in review_ws_connections:
        import json
        message = json.dumps(data, ensure_ascii=False)
        for ws in review_ws_connections[task_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass
