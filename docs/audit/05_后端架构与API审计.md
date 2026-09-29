# 后端架构与 API 审计报告

> 审计范围：`src/backend/`（main.py、routes*.py、models.py、database.py、config.py、services/ 131 个模块约 1.7MB 源码）
> 审计基准：REST 规范、服务边界、LLM 可靠性、并发、安全、可观测性、数据迁移、测试门禁
> 证据标注格式：`file:line`，均为本仓库实际行号
> 结论可信度：静态通读 + `py_compile` / AST 校验（本地 venv 缺 sqlalchemy，未做运行时压测）

---

## 1. 执行摘要

VibeUtopia 后端是单进程 FastAPI 单体，承载约 90 个 HTTP 端点、2 个 WebSocket 端点与 131 个服务模块。功能覆盖面（多模态风控、信号采集、社会仿真、断点续传、细粒度视频理解）远超同类原型项目，但**工程质量与功能完成度严重不对称**：大量"已实现"能力在运行时不可达或不可靠。

**总体评级：C+（功能丰富 / 工程就绪度低）**

| 维度 | 评级 | 一句话结论 |
|------|------|-----------|
| API 一致性 | D | 路由双前缀导致近半 v3 端点 404；错误格式不统一；无版本弃用策略 |
| 数据层 | C- | 26 张表靠 `create_all` 建表；无 Alembic；JSON 全塞 Text；外键缺索引 |
| LLM 编排 | C+ | 多 Key 轮换/冷却/降级思路正确，但无 token 成本核算、重试无退避 |
| 性能与并发 | D+ | 全同步 SQLAlchemy 跑在 async 路由里；视频预处理阻塞请求线程 |
| 安全 | F | 零鉴权、CORS 全开、路径遍历、密钥入库入 Git |
| 可观测性 | F | 无 metrics、无 trace_id、无健康检查、无集中日志配置 |
| 测试 | F | 8 个脚本式测试，无 API 层测试、无 CI 门禁、核心模块不可导入 |

**必须立即处理的 4 个 P0：**

1. **`engine.py` 语法错误**：`try` 块（`engine.py:150`）的 `finally` 被错误缩进到 `_supplement_agents` 末尾（`engine.py:227-228`），`py_compile` 直接报 `SyntaxError: expected 'except' or 'finally' block`。**仿真引擎当前不可导入、不可运行。**
2. **路由双前缀**：`routes_v3.py` 的路由路径已含 `/api/v3/`，又被 `main.py:59` 以 `prefix="/api/v3"` 挂载 → 实际注册为 `/api/v3/api/v3/...`。前端 `api/index.ts:219` 请求 `/api/v3/signals/hotlist` 将 404。信号面板、图谱、批量、多模态等约 40 个端点全部不可达。
3. **全链路零鉴权**：90 个端点无任何 `Depends` 鉴权、API Key 校验或中间件。任何人可提交分析、启动/停止信号调度器、拉取 Ollama 模型、删除博主索引。
4. **任意本地文件读取/处理**：`routes.py:177-180` 与 `routes_v3.py:1225` 直接接受客户端传入的服务器文件路径（仅 `os.path.exists` 校验），配合上传文件名未消毒（`routes.py:676`），构成路径遍历与本地文件处理面。

**MEMORY.md 三项待办核验结论（详见 §11）：数据库异步化 ❌ 未做；routes.py 视频预处理移入后台 ❌ 未做；engine.py 缩进修复 ❌ 未做（批量持久化仅部分完成）。**

---

## 2. 架构现状与模块依赖

### 2.1 分层拓扑

```
main.py（应用装配 + WebSocket + 全局单例）
  ├── routes.py            /api/v1   预审主流程 (902 行)
  ├── routes_v3.py         /api/v3   多模态/信号/图谱/仿真/批量 (1392 行)
  ├── routes_blogger.py    /api/v1/blogger
  ├── routes_resume.py     /api/v1/resume
  ├── routes_local_models.py  自带 prefix=/api/v3/local-models
  └── routes_story.py      ⚠ 从未 include_router（死代码）
        ↓
services/（131 模块，无明确分层）
  ├── 编排层: analyzer.py (647) / enhanced_analyzer.py / resumable_analyzer.py (508) / batch_analyzer.py (538)
  ├── 领域层: risk_assessor / signal_matcher / entity_risk_chain / 30+ 风控模块
  ├── 仿真层: simulation/engine.py (578) + monitors/ + platforms/ + propagation/
  ├── 基础设施: llm_client.py (1009) / checkpoint_manager / hardware_detector
  └── 数据: 直接 import SessionLocal（无仓储层 / 无 DI）
        ↓
database.py (同步 SQLAlchemy) + Neo4j GraphStore + ChromaDB
```

### 2.2 依赖健康度

| 问题 | 证据 | 影响 |
|------|------|------|
| **服务层直连基础设施** | `analyzer.py:8`、`engine.py:146,470`、`engine.py:473` 直接 `from backend.database import SessionLocal` | 无法单元测试（必须起库）、无法替换存储、会话泄漏面广 |
| **全局可变单例** | `main.py:15` `signal_scheduler`、`main.py:18` `graph_store`、`llm_client.py:438-443` 模块级 `registry/router/_llm_semaphore`、`routes.py:710` `_persona_factory` | 多 worker 部署即状态分裂；测试间互相污染 |
| **全局函数指针注入** | `analyzer.py:23-29` `_broadcast_func`，由 `main.py:35` 注入 | 隐式依赖，方向反了（应由编排层持有回调） |
| **巨型编排函数** | `analyzer.py:206-647` 单函数 440 行（切分→并行评估→仿真→持久化）；`enhanced_analyzer.py` 8 个 Phase 全在一个模块 | God Service 苗头；任一 Phase 失败的影响面不可控 |
| **循环/双向依赖风险** | `engine.py:470-471` 在方法内延迟 import models；`routes_v3.py:1207` 端点内延迟 import fine_grained | 掩盖了真实的模块边界问题，运行期才发现导入错误 |

### 2.3 启动期耦合

`main.py:29-42` lifespan 内同步执行 `init_db()` → `graph_store.connect()` → `initialize_on_startup()`（ChromaDB 模型预热）。Neo4j 不可用时仅 `connect()` 失败（`graph_store.connect()` 未 try），但后续图谱端点返回 503（`routes_v3.py:682`）——降级路径存在但启动日志会抛异常。ChromaDB 预热在启动路径上同步执行，拖慢冷启动。

---

## 3. API 层评估

### 3.1 端点分类（共 90 个 HTTP + 2 个 WS）

| 类别 | 数量 | 前缀 | 代表端点 | 一致性 |
|------|------|------|----------|--------|
| 预审主流程 | 6 | `/api/v1` | `POST /review`、`GET /review/{id}`、`GET /history` | 好（有 response_model） |
| 文件上传 | 1 | `/api/v1` | `POST /upload` | 中（文件名未消毒） |
| 人格/记忆 | 5 | `/api/v1` | `POST /persona/generate` | 中 |
| 断点续传 | 6 | `/api/v1/resume` | `POST /resume/submit` | 好（有 response_model） |
| 博主知识引擎 | 9 | `/api/v1/blogger` | `POST /index`、`POST /ask` | 中 |
| 多模态/音频 | 3 | `/api/v3`（双前缀） | `POST /analyze-multimodal` | **坏** |
| 模型路由/硬件 | 6 | `/api/v3`（双前缀） | `GET /available-models` | **坏** |
| 信号采集 | 5 | `/api/v3`（双前缀） | `GET /signals/hotlist` | **坏** |
| 知识图谱 | 4 | `/api/v3`（双前缀） | `GET /graph/overview` | **坏** |
| 博主历史/竞品/反事实/决策 | 5 | `/api/v3`（双前缀） | `POST /competitor/compare` | **坏** |
| 仿真/批量/回测/极化 | 12 | `/api/v3`（双前缀） | `POST /batch/submit` | **坏** |
| 细粒度视频 | 2 | `/api/v3`（相对路径） | `GET /fine-grained/status` | 好（唯一正确的 v3 写法） |
| 帧缩略图 | 1 | `/api/v3`（相对路径） | `GET /analysis/{id}/frames/{p}` | 中（防遍历不严） |
| 图像生成 | 2 | `/api/v3`（双前缀） | `POST /image/generate` | **坏** |
| 本地模型部署 | 10 | `/api/v3/local-models` | `GET /status` | 好（自带 prefix） |
| 人生故事 | 6 | `/api/v1/story` | `POST /generate` | **死代码（未挂载）** |

### 3.2 P0 缺陷：路由双前缀

```
routes_v3.py:45   router = APIRouter()                     # 无 prefix
routes_v3.py:66   @router.post("/api/v3/analyze-multimodal")  # 路径已含 /api/v3
main.py:59        app.include_router(router_v3, prefix="/api/v3")  # 再加一层
                  → 实际注册: /api/v3/api/v3/analyze-multimodal
```

对照前端契约 `api/index.ts:4` `const V3_BASE = '/api/v3'`、`api/index.ts:219` 请求 `${V3_BASE}/signals/hotlist` = `/api/v3/signals/hotlist` → **404**。

同一文件内两种写法并存：`routes_v3.py:1204` `@router.get("/fine-grained/status")` 是正确的相对路径写法（实测 MEMORY 记录该端点可用），而 `routes_v3.py:539` `/api/v3/signals/hotlist` 是错误写法。**约 40 个 v3 端点当前不可达**（信号面板、图谱可视化、批量分析、仿真规模、回测对比、图像生成、多模态分析、模型路由全部命中）。

修复方案二选一（推荐 A）：
- **A**：把 `routes_v3.py` 中所有路径的 `/api/v3` 前缀去掉，保留 `main.py` 的 `prefix="/api/v3"`（与 fine-grained 写法对齐）
- **B**：`main.py:59` 改为 `include_router(router_v3)` 不加 prefix，保留路由自带前缀（但 fine-grained 会失去前缀，需一并改）

### 3.3 REST 一致性缺陷

| 问题 | 证据 | 规范要求 |
|------|------|----------|
| 错误体格式不统一 | 大多 `HTTPException(detail=...)` → `{"detail": "..."}`；`routes_v3.py:1284,1311` 直接 `return {"error": "非法路径"}`（HTTP 200） | 统一 `{code, message, request_id}` 信封 |
| 错误信息泄漏内部实现 | `routes_v3.py:104` `detail=f"分析失败：{str(e)}"`、`routes.py:703` 同类 | 对外摘要 + 对内 detail，禁止拼接异常原文 |
| 裸 `except Exception: pass` | `main.py:100-101,141-142,158-159`；`routes.py:333-334` | 至少记日志；WS 广播失败需可观测 |
| `response_model` 覆盖率低 | 有 model：routes.py 6/11、routes_resume 5/6、routes_story 3/6；routes_v3 仅靠返回值注解，`/fine-grained`、`/graph/*`、`/batch/*` 无模型 | 全端点声明 response_model |
| 版本管理混乱 | `/api/v1` 与 `/api/v3` 并存；`routes_v3.py:212` 用 `deprecated=True` 但指向的 `/api/v1/persona/generate` 同样无鉴权；`routes_story.py:28` 内嵌完整 `/api/v1/story` 前缀而挂载方式不明 | 单一版本策略 + Sunset 头 |
| 路径风格不统一 | snake_case `/analyze-multimodal` vs hyphen `/fine-grained` vs noun `/review` | 统一 kebab-case 资源风格 |
| 查询参数无边界校验 | `routes.py:517-518` `page=1, per_page=20` 无 `ge/le` 约束，`per_page=10**6` 可打爆内存 | `per_page: int = Query(20, ge=1, le=100)` |
| N+1 查询 | `routes.py:551` 每个 task 单独 `query(AnalysisSummary)` | JOIN 或 `selectinload` |

### 3.4 未挂载路由（死代码）

`routes_story.py:28` 定义 `APIRouter(prefix="/api/v1/story")` 并含 6 个端点，但 `main.py` 五处 `include_router`（`main.py:55,59,63,67,71`）**均未注册它**。人生故事查询/演化 API 全部不可用，而 MEMORY.md 与 T1 文档仍宣称"API 端点位于 /api/v1/persona/*"。需确认是漏挂载还是废弃未删。

---

## 4. 数据层评估

### 4.1 模型盘点（models.py，26 个实体）

核心链路：`Task` → `RiskItem` / `PlatformReaction` / `AnalysisSummary`（1:1）→ `V2AnalysisResult`（1:1）。
信号链：`SignalRecord` / `SeedEventRecord`。
仿真链：`AgentRecord` / `AgentMemory` / `SocialRelation` / `SimulationRecord` / `SimulationStatus` / `PropagationSnapshot` / `PropagationEdge`。
扩展：`VideoAnalysisRecord` / `FrameRecord` / `BloggerProfileRecord` / `BacktestRecord` / `ConsistencyRecord` / `TrendPredictionRecord` / `ReportRecord` 等。

### 4.2 设计问题

| 问题 | 证据 | 说明 |
|------|------|------|
| **JSON 全部落 Text** | `models.py:16` `MySQLText = Text().with_variant(LONGTEXT,'mysql')`；`dimensions_json`/`agents_json`/`platform_simulation_json` 等 30+ 列 | 无法 SQL 过滤/索引 JSON 字段；MySQL 上是 LONGTEXT 全表扫描温床；应改 `JSON` 类型 + 生成列索引 |
| **外键无索引** | `models.py:41` `RiskItem.task_id = Column(String(36), ForeignKey("tasks.id"))` 无 `index=True`；`models.py:55` `PlatformReaction.task_id` 同 | `GET /review/{id}` 每次全表扫 risk_items/platform_reactions；数据量上来必慢 |
| **唯一约束不完整** | `models.py:231` `V2AnalysisResult.task_id` 有 unique；`SimulationRecord`/`PropagationEdge` 无 (sim_id,tick) 联合索引 | 仿真写入是热点路径（`engine.py:475-488` 每 tick 逐行 insert） |
| **字符串枚举无约束** | `status`/`severity`/`dimension` 均为 `String(20-50)` 自由文本 | `routes.py:281` 已出现 `low/medium/high → green/yellow/orange/red` 的双套枚举映射，靠运行时兼容 |
| **时间戳无时区保证** | `models.py:29` `DateTime`（无 timezone=True），`utcnow()` 返回 aware datetime | SQLite 接受，MySQL/跨时区比较会出错 |
| **无软删除/审计字段** | 除 `created_at/updated_at` 外无 `deleted_at`、`version`、`updated_by` | 多租户与合规审计无法落地 |
| **多租户零准备** | `Task`（`models.py:19-34`）无 `user_id`/`tenant_id`/`org_id` | `GET /history`（`routes.py:525`）返回全局所有任务，接多租户必须改表+全查询 |

### 4.3 迁移机制

- **无 Alembic**（全局 grep 无 `import alembic`），只有两个手写脚本：`migrations/003_chromadb_memorystream.py`、`migrations/004_risk_score_column.py`（001/002 缺失）。
- `database.py:61` `init_db()` 仅 `Base.metadata.create_all()` —— **只建新表，不改旧表**。`004` 那种 `ALTER TABLE` 必须人工执行，且脚本不在启动路径上。
- 无 `schema_version` 表，无法知道当前库结构对应哪个代码版本。
- `migrations/004:41` 自建 `create_engine(settings.DATABASE_URL)` 而非 `database.engine`，绕过 `_build_database_url()` 的 MySQL/SQLite 降级逻辑，生产 MySQL 场景下迁移脚本可能打到错误的库。

### 4.4 一致性与事务

- `analyzer.py:608,636` 在长流程末尾两次 `db.commit()`，中途失败会留下 `status=processing` 的僵尸任务（`routes.py:251` 查询时只认 `completed`）。
- `engine.py:502-504` 持久化失败 `rollback` 后仅打日志，仿真继续跑 → 内存态与库态分叉，回放数据缺失。
- 会话生命周期：`get_db`（`database.py:64-69`）依赖 FastAPI 依赖注入正确关闭；但 `analyzer.py:208`、`engine.py:473` 手工 `SessionLocal()`，异常路径靠 `try/finally`，而 `engine.py` 的 `finally` 已被写坏（见 P0）。

---

## 5. LLM 编排与可靠性

### 5.1 现有能力（做得对的部分）

`llm_client.py` 是后端最成熟的服务模块（1009 行），已具备：

- **模型注册表**：`ModelRegistry`（`llm_client.py:53-145`）从 `model_config.yaml` 加载 provider/model/tier，支持 `.env` 覆盖 base_url/model，支持**多 Key 逗号分隔**（`llm_client.py:117`）。
- **能力标记**：`ModelEndpoint`（`llm_client.py:33-47`）区分 `vision/text/image_gen/image_mode`，避免 Omni 模型接纯文本（历史 400 错误的根因已修）。
- **配额冷却**：`_is_quota_error`（`llm_client.py:491`）把 429/402/403 判为配额耗尽 → `mark_unavailable` 进入冷却（`settings.MODEL_COOLDOWN_SECONDS` 默认 300s）。
- **降级链**：`_call_with_routing`（`llm_client.py:642-684`）同 tier 优先、低 tier 兜底、多 Key 轮换、配额耗尽跳下一端点。
- **全局并发闸**：`_llm_semaphore=10 / _vlm_semaphore=5 / _image_gen_semaphore=3`（`llm_client.py:441-443`）。
- **JSON 降级解析**：`parse_llm_json`（`llm_client.py:456-484`）直解 → markdown 块 → 最外层 `{}` → fallback。

### 5.2 关键缺口

| 缺口 | 证据 | 后果 |
|------|------|------|
| **重试无退避/抖动** | `llm_client.py:666-678` 内层 `for attempt in range(LLM_MAX_RETRIES)` 立即重试，无 `await asyncio.sleep`；只有 `risk_assessor.py:66` 有 `min(2**attempt,8)` | 对 429 是"重试风暴"，加剧限流；与 `risk_assessor` 的两层重试叠乘（3×2=6 次调用） |
| **零 token/成本核算** | `llm_client.py:726` 只取 `data["choices"][0]["message"]["content"]`，**丢弃 `usage`**；`_key_usage_stats`（`llm_client.py:269`）只记 calls/errors | 无法回答"这次分析花了多少钱"；`scale_manager.py:303-323` 的成本是拍脑袋估算（0.01/次） |
| **无语义/结果缓存** | `batch_analyzer.py:62` 仅 md5 精确哈希缓存，进程内存态 | 相同内容跨批次/跨 worker 重复付费 |
| **超时一刀切** | `settings.LLM_TIMEOUT=30`（`config.py:37`），长上下文/图像生成同 30s | 图像生成、长视频帧分析易超时误判为失败并触发重试 |
| **无熔断** | 仅冷却单 Key；provider 级故障无熔断器 | 整个 provider 5xx 时仍按端点粒度逐个试探 |
| **prompt 注入面** | `risk_assessor.py:20` `prompt = prompt_template + text` 直接拼接用户内容；`transcript_detector` 同类 | 用户内容可劫持评估 prompt（"请输出全绿"），风控产品属高危 |
| **固定 max_tokens=4096** | `llm_client.py:618,633,701,770` | 长报告截断，JSON 解析失败率升高 |

### 5.3 断点续传（业界对标亮点，但未接入主流程）

`resumable_analyzer.py:44-53` 定义 8 阶段管道（text_extraction → … → report_compilation），`CheckpointManager` 原子写入 `data/checkpoints/`，限流感知 `quota_retry_wait=60` + `max_quota_retries=5`。**设计质量高**，但：

- 主流程 `routes.py:231` 的 `background_tasks.add_task(run_analysis, ...)` 走的是 `analyzer.run_analysis`，**未走 ResumableAnalyzer**。
- `routes_resume.py` 是独立入口，用户必须显式调 `/resume/submit` 才享受断点续传。
- FastAPI `BackgroundTasks` 进程内执行，**重启即丢**（对比 Celery/ARQ 的持久化队列）。

---

## 6. 性能与并发瓶颈

### 6.1 事件循环阻塞（最严重）

- **同步 ORM 在 async 路由**：`database.py:28-49` `create_engine` + `sessionmaker`（同步）；所有 `async def` 路由里 `db.query(...)` 是阻塞调用。单请求阻塞期间**整个 worker 的所有请求排队**。
- **视频预处理在请求线程内**：`routes.py:174-204` 在返回响应前同步执行 `extract_video_text(video_path)`（OCR+抽帧）与 Paraformer 转写——**这才是 MEMORY 待办"视频预处理移入后台"的现场**，目前完全未做，10 分钟视频可让请求挂数分钟。
- **httpx 新建连接**：`llm_client.py:712` 每次调用 `async with httpx.AsyncClient(...)` 新建客户端，无连接池复用，TLS 握手开销 × 调用量。
- **`_urllib_call` 降级路径**：`llm_client.py:735` `run_in_executor` 占用默认线程池，与 ORM 阻塞争抢线程。

### 6.2 数据库热点

- 仿真每 tick 逐行 `db.add(record)`（`engine.py:475-488`），1000 Agent × 100 tick = 10 万行 insert；虽单次 commit，但无 `bulk_save_objects`/`executemany`。
- `GET /history`（`routes.py:543-551`）`count()` + `offset/limit` 深分页 + N+1 summary 查询。
- `SimulationRecord` 无 (sim_id, tick) 索引，回放查询全表扫。

### 6.3 并发模型缺陷

| 问题 | 证据 |
|------|------|
| WebSocket 连接表无锁 | `main.py:25-26` 普通 dict，`broadcast_*` 遍历时 `remove` 并发修改 |
| 广播失败静默吞掉 | `main.py:158-159` `except Exception: pass` |
| 无请求级限流 | 全局 grep 无 slowapi/limiter；`POST /review` 可被刷爆 LLM 配额 |
| 无队列背压 | `batch_analyzer` 用进程内 `asyncio.Queue`，无限堆积直到 OOM |
| 仿真可并发多实例但共享 Neo4j/SQLite | `graph_store` 单例、SQLite `check_same_thread=False`（`database.py:31`）写锁竞争 |

---

## 7. 安全与合规风险

> 评级：**F — 上线前必须整改**。以下每条单独都足以阻断生产发布。

| # | 风险 | 证据 | 等级 |
|---|------|------|------|
| S1 | **零鉴权/零授权**：90 端点全部匿名可达，含调度器启停、模型拉取、索引删除 | 全局无 `Depends` 鉴权；`main.py` 仅 CORS 中间件 | P0 |
| S2 | **任意本地文件处理**：客户端可传任意服务器路径，服务端读取并 OCR/转写 | `routes.py:177-180` `for video_path in req.video_files: if os.path.exists(video_path)`；`routes_v3.py:1225` `os.path.exists(req.video_path)` | P0 |
| S3 | **上传路径遍历**：`file.filename` 未消毒直接拼进路径 | `routes.py:676` `safe_filename = f"{file_id}_{file.filename}"` → `../` 可写出 upload_dir 外 | P0 |
| S4 | **API Key 明文入 Git**：MEMORY.md 记录完整 Key，且项目规范强制 push MEMORY.md | `.monkeycode/MEMORY.md:92` `API Key: ak_2mC1...` | P0 |
| S5 | **默认口令写死源码** | `config.py:57` `NEO4J_PASSWORD="vibeutopia2024"`；`config.py:63` `MYSQL_PASSWORD="vibe_password"` | P1 |
| S6 | **CORS 全开** | `main.py:49` `allow_origins=["*"]` | P1 |
| S7 | **prompt 注入可污染风控结论** | `risk_assessor.py:20` 用户文本直接拼接进 prompt | P1 |
| S8 | **敏感信息进日志** | `llm_client.py:721` 打印 400 响应原文（可能含用户内容）；异常 `str(e)` 直接返回客户端 | P1 |
| S9 | **帧缩略图防遍历不严** | `routes_v3.py:1283` 仅拦 `..` 与绝对路径；`routes_v3.py:1304` `tempfile.gettempdir() in os.path.abspath(frame_path)` 是子串判断，`/tmpfoo` 可绕过 | P1 |
| S10 | **临时文件泄漏** | `routes_v3.py:167-181` `os.unlink` 不在 `finally`，异常即泄漏 | P2 |
| S11 | **无多租户隔离** | `Task` 无 tenant_id；`GET /history` 全局可见 | P1（接 B 端即 P0） |
| S12 | **WebSocket 无鉴权** | `main.py:76,109` 任意 `sim_id`/`task_id` 可订阅进度（信息泄露） | P2 |

**密钥管理现状**：API Key 通过 `.env` → `os.getenv` 注入（方向正确，`model_config.yaml` 只存 `api_key_env` 名而非明文，`llm_client.py:89-90`）。但 `.env` 无校验是否被 gitignore；MEMORY.md 已造成一次泄漏，**该 Key 视为已泄露，必须轮换**。

---

## 8. 可观测性与运维就绪度

| 能力 | 现状 | 证据 |
|------|------|------|
| 健康检查 | **无** `/health` `/ready` | 全局 grep 无 healthz/health |
| 集中日志配置 | **无**。131 个模块各自 `getLogger(__name__)`，仅 `prompt_manager_cli.py:15` 有 `basicConfig`（CLI） | uvicorn 默认根日志，服务模块 INFO 可能被吞 |
| 结构化日志 | 无 structlog / JSON formatter | 无法接 ELK/Loki |
| 请求追踪 | 无 request_id / trace_id 中间件 | 跨 LLM 调用、WS 广播、后台任务无法串联 |
| 指标 | 无 prometheus / OpenTelemetry（grep 均无） | 无法观测 QPS、LLM 调用成功率、队列深度 |
| LLM 可观测 | 仅 `calls/errors/last_used`（`llm_client.py:269`） | 缺 p95 延迟、token、每模型成本 |
| 错误监控 | `error_monitor.py` / `error_handler.py` 存在（各 2-3KB），未接任何出口 | 只写本地日志 |
| 优雅关闭 | `main.py:39-42` 停调度器 + 关 graph_store；**不等 in-flight 分析任务** | 重启丢任务 |
| 配置校验 | `config.py` 纯 `os.getenv` 带默认值，无 pydantic-settings、无启动期校验 | 配错 key 只在第一次 LLM 调用才炸 |
| 部署就绪 | 无 Dockerfile/编排（本地仅有 requirements.txt）；SQLite 默认库 | 多 worker 即 SQLite 写锁 |

---

## 9. 测试与质量门禁

**测试资产（`tests/`，共 14 个 .py）：**

| 文件 | 性质 |
|------|------|
| `test_chromadb_init.py` / `test_chromadb_memory.py` | 模块自检脚本 |
| `test_life_story_light.py` / `test_story_generation.py` | T1 功能脚本 |
| `test_llm_models.py` / `test_platform_immersion.py` / `test_platform_weights.py` / `test_t8_t9_simple.py` | 能力冒烟脚本 |
| `scripts/backtest_full.py` 等 6 个 | 手工运行脚本，非断言测试 |

**缺口（按严重度）：**

1. **零 API 层测试**：90 个端点无一个 `TestClient` 用例。双前缀 bug（§3.2）若有契约测试可立即发现。
2. **零单元测试**：`risk_assessor`/`llm_client`/`checkpoint_manager`/评分算法（`analyzer.calculate_overall_score`）无纯函数测试。
3. **核心模块当前不可导入**：`engine.py` 语法错误 → 任何 import simulation 的测试直接失败。`py_compile` 已验证。
4. **无 CI 门禁**：无 lint/type/test 流水线配置（有 `.ruff_cache` 说明本地跑过 ruff，但无强制）。
5. **无覆盖率基线**：`.pytest_cache` 存在但无测试套件可跑。
6. **无契约测试**：前端 `api/index.ts` 手写 TS 接口与后端 Pydantic 模型双份维护，无 openapi-typescript 同步（MEMORY 里"OpenAPI 自动生成前端类型"也仍在待办）。
7. **修 Bug 不写失败用例**：与全局规范"修 Bug 必须先写复现用例"冲突（engine.py 的 finally 坏掉即典型）。

**建议的质量门禁（最小集）：**
`ruff check` → `mypy`（先 services 核心）→ `pytest --cov`（≥40% 起步）→ `spectral lint openapi.json` → 契约测试（schemathesis 或 Dredd）→ 核心流程集成测试（mock LLM）。

---

## 10. 行业对标

> 说明：本次审计环境外网受限，以下对标基于业界公开成熟实践（LiteLLM / LangGraph / FastAPI 生产化规范），用于校准差距方向，非引用具体版本文档。

| 领域 | 行业成熟做法 | VibeUtopia 现状 | 差距等级 |
|------|-------------|-----------------|----------|
| **LLM 网关** | LiteLLM Proxy 式统一网关：OpenAI 兼容协议、按 team/key 的 budget 与 RPM/TPM 限流、`usage` 全量落库、fallback 矩阵 + 指数退避 + jitter、缓存层 | 自研 `llm_client` 有多 Key/冷却/降级，但无预算、无 token 落库、重试无退避、无缓存 | 中（可向 LiteLLM 靠拢或直接代理化） |
| **任务编排** | LangGraph/Temporal 式**持久化状态机**：每个 step 可检查点、崩溃重放、human-in-the-loop | `resumable_analyzer` 已有 8 阶段检查点（思路正确），但主流程用 `BackgroundTasks` 未接入 | 中（把 run_analysis 换成 ResumableAnalyzer 即可闭环） |
| **后台任务** | Celery/RQ/ARQ/ dramatiq：持久化队列、重试策略、死信、worker 水平扩展 | FastAPI `BackgroundTasks`（进程内、重启丢失）+ `asyncio.Queue`（batch_analyzer） | 高 |
| **契约优先** | OpenAPI 为唯一事实源：spectral lint、breaking-change 检测、客户端 SDK 自动生成、契约测试入 CI | 无统一 response_model、前端手写 TS、双前缀说明无契约校验 | 高 |
| **成本治理** | 按 request/tenant/model 记 token 与金额、预算告警、语义缓存、prompt 版本与成本关联 | 只有调用次数；`scale_manager` 估算成本与真实消耗无关 | 高 |
| **可观测性** | OpenTelemetry traces（LLM span）、结构化日志 + trace_id、Prometheus RED 指标、`/health` `/ready` | 全无 | 高 |
| **数据迁移** | Alembic 单 head + autogenerate + 部署前 migrate；schema_version 表 | 手写 003/004 脚本 + `create_all` | 高 |
| **API 网关安全** | 鉴权（JWT/API Key/OAuth2）、限流（slowapi/nginx）、CORS 白名单、审计日志 | 全无 | 致命 |
| **多租户** | `tenant_id` 行级隔离 / Postgres RLS、配额、数据保留策略 | 零准备 | 高（商业化前置） |

**可借鉴的落地顺序**（性价比）：① 用 LiteLLM proxy 替换或包住自研路由（拿走 token 核算/限流/缓存）→ ② ARQ/Redis 队列替换 BackgroundTasks → ③ OpenAPI 生成前端类型 → ④ OpenTelemetry 三件套。

---

## 11. 问题清单 P0-P3

### P0 — 阻断发布（4 项）

| ID | 问题 | 证据 | 修复动作 | 工作量 |
|----|------|------|----------|--------|
| P0-1 | `engine.py` 语法错误，仿真引擎不可导入 | `engine.py:150` `try:` 无配对；`engine.py:227-228` `finally: db.close()` 被错误缩进进 `_supplement_agents`；`py_compile` 报 `SyntaxError: expected 'except' or 'finally' block` | 把 `finally: db.close()` 移回 `_load_agents` 的 try 块；补 `py_compile` 到 CI | 0.5h |
| P0-2 | 路由双前缀，约 40 个 v3 端点 404 | `routes_v3.py:45` 无 prefix；`routes_v3.py:66,539,650,1056...` 路径含 `/api/v3`；`main.py:59` `prefix="/api/v3"`；前端 `api/index.ts:219` 契约不符 | 统一为相对路径（推荐）或去掉 include prefix；加路由表快照测试 | 2h |
| P0-3 | 全链路零鉴权 | 全局无 auth 依赖；`main.py` 仅 CORS | 至少加 API Key/`X-Internal-Token` 中间件 + 管理端点单独鉴权；CORS 收紧白名单 | 1-2d |
| P0-4 | 任意本地文件路径处理 + 上传路径遍历 | `routes.py:177-180`、`routes_v3.py:1225`、`routes.py:676` | 路径 allowlist（uploads/ 与 temp 前缀）+ `os.path.realpath` 前缀校验 + 文件名 `Path(filename).name` 消毒 | 1d |

### P1 — 高优先（8 项）

| ID | 问题 | 证据 | 修复动作 |
|----|------|------|----------|
| P1-1 | MEMORY 待办①**数据库异步化未做**：同步 ORM 阻塞事件循环 | `database.py:28-49` sync engine；`analyzer.py:208` `SessionLocal()` | 迁 async SQLAlchemy 2.0 + `async_sessionmaker`，或短平快：`run_in_executor` 包查询 |
| P1-2 | MEMORY 待办②**视频预处理未移入后台**：请求内 OCR+转写 | `routes.py:174-204` 在 `background_tasks.add_task`（`routes.py:231`）之前 | 预处理整体挪进 `run_analysis`/ResumableAnalyzer；请求只建任务立即返回 |
| P1-3 | LLM 重试无退避/抖动，429 重试风暴 | `llm_client.py:666-678` 内层循环无 sleep | 统一 `asyncio.sleep(min(2**attempt,30) + jitter)`；与 `risk_assessor.py:66` 合并重试层 |
| P1-4 | 零 token/成本核算，`usage` 被丢弃 | `llm_client.py:726` | 解析 `usage` 落 `llm_usage_records` 表；按 task/model 聚合；预算告警 |
| P1-5 | API Key 明文泄漏入 Git | `.monkeycode/MEMORY.md:92` | **立即轮换该 Key**；从 MEMORY.md 删除；加 secret 扫描（gitleaks）pre-commit |
| P1-6 | 数据迁移体系缺失 | `database.py:61` 仅 create_all；`migrations/004:41` 另建 engine | 引入 Alembic；补 001/002 基线；迁移入启动/部署流程 |
| P1-7 | `routes_story.py` 从未挂载 | `routes_story.py:28` vs `main.py:55-71` 无 include | 确认用途后挂载或删除；加"路由未挂载"静态检查 |
| P1-8 | 错误响应格式不统一 + 异常原文泄漏 | `routes_v3.py:1284,1311` 返回 `{"error":...}` 200；`routes_v3.py:104` `str(e)` | 统一异常处理器 + 错误信封 + request_id |

### P2 — 中优先（8 项）

| ID | 问题 | 证据 |
|----|------|------|
| P2-1 | 外键缺索引（`RiskItem.task_id`/`PlatformReaction.task_id`） | `models.py:41,55` |
| P2-2 | JSON 全 Text，无法索引过滤 | `models.py:16` 及 30+ `_json` 列 |
| P2-3 | `GET /history` N+1 + per_page 无上界 | `routes.py:543-551` |
| P2-4 | 无 `/health` `/ready`、无 metrics、无 trace_id | 全局 grep 确认 |
| P2-5 | 无 API 限流，可刷爆 LLM 配额 | 无 slowapi/limiter |
| P2-6 | prompt 注入可污染风控结论 | `risk_assessor.py:20` |
| P2-7 | WebSocket 连接表无锁 + 广播异常静默 | `main.py:25-26,158-159` |
| P2-8 | 仿真持久化失败只打日志，内存/库分叉 | `engine.py:502-504`；逐行 insert（`engine.py:475-488`）应 bulk |

### P3 — 低优先/技术债（6 项）

| ID | 问题 | 证据 |
|----|------|------|
| P3-1 | `_call_legacy` 与多 provider 路径重复 | `llm_client.py:753-784` |
| P3-2 | 每次 LLM 调用新建 httpx.AsyncClient | `llm_client.py:712` |
| P3-3 | 长流程两次 commit，僵尸 processing 任务 | `analyzer.py:608,636` |
| P3-4 | 枚举双套（severity low/high vs green/red）靠运行时映射 | `routes.py:281-285` |
| P3-5 | 帧缩略图路径校验用子串判断 | `routes_v3.py:1304` |
| P3-6 | 临时文件异常泄漏、MAX_TEXT_LENGTH=5000 截断未在 API 文档声明 | `routes_v3.py:167-181`；`analyzer.py:70` |

### MEMORY.md 待办核验（任务要求）

| 待办项 | 状态 | 证据 |
|--------|------|------|
| 数据库异步化 | ❌ **未做** | `database.py:4-49` 仍是 `create_engine` + 同步 `sessionmaker`；全仓无 async_session |
| routes.py 视频预处理移入后台 | ❌ **未做** | `routes.py:174-204` 预处理在 `background_tasks.add_task`（231 行）之前同步执行 |
| engine.py 缩进修复 + 批量持久化 | ⚠ **部分**：缩进修复 ❌ 未做（`engine.py:150`/`227` 语法错误仍可复现）；批量持久化 ◐ 传播边已有缓冲批量写（`engine.py:318-321`），但 `_persist_tick` 仍是逐行 `db.add`（`engine.py:475-488`，仅单次 commit） |

---

## 12. 架构演进路线（单体 → 模块化）

### 阶段 0：止血（1 周）——不重构，先可跑可信

1. 修 `engine.py` 语法错误 + 全仓 `py_compile` 入 CI（P0-1）。
2. 统一 `routes_v3` 路径前缀，加"路由注册表快照测试"防回归（P0-2）。
3. 路径 allowlist + 文件名消毒 + 轮换泄漏 Key（P0-4、P1-5）。
4. 最小鉴中间件（内部 API Key）+ CORS 白名单（P0-3）。
5. 统一异常处理器与错误信封（P1-8）。

### 阶段 1：可靠性（2-3 周）

1. **后台任务持久化**：`BackgroundTasks` → ARQ/Celery（Redis），分析任务入库队列表；`run_analysis` 全面切换到 `ResumableAnalyzer`（复用已有 8 阶段检查点，把 MEMORY 待办待办②③一次闭环）。
2. **LLM 网关化**：引入 LiteLLM proxy（或在 `llm_client` 补齐）：`usage` 落库、重试退避+jitter、per-tenant budget、结果缓存；超时按任务类型分层。
3. **异步数据访问**：SQLAlchemy 2.0 async（MEMORY 待办①）；热点表补索引（P2-1）；仿真写入 `bulk_save_objects`。
4. **迁移治理**：Alembic 基线 + 单 head，`create_all` 仅开发用。

### 阶段 2：契约与可观测（2 周）

1. **OpenAPI 契约优先**：全端点 `response_model`；`openapi.json` 进仓库；`openapi-typescript` 生成前端类型，删除 `api/index.ts` 手写接口；spectral lint + breaking-change 检查入 CI。
2. **可观测三件套**：`/health` `/ready`；structlog + `X-Request-Id` 中间件；OpenTelemetry（LLM span 透传 task_id）；Prometheus RED + LLM 专用指标（成功率/p95/token/成本）。
3. **质量门禁**：ruff + mypy + pytest（核心算法单测 + API 契约测试 + mock LLM 集成测试）+ gitleaks。

### 阶段 3：模块化单体 → 可扩展（4-6 周）

按领域拆包（保持单进程部署，先拆边界后拆服务）：

```
src/backend/
  api/            # v1/v3 路由，只做参数校验与响应组装
  application/    # 用例编排：ReviewWorkflow、SimulationWorkflow（ResumableAnalyzer 为基座）
  domain/         # risk / signal / persona / simulation 纯逻辑（无 I/O，可单测）
  infrastructure/ # llm_gateway、repositories、neo4j、chroma、queue
  schemas/        # Pydantic DTO（OpenAPI 唯一来源）
```

关键改造点：
- 服务层禁止 `import SessionLocal`（改为仓储注入），消灭 `engine.py:146,470` 这类延迟导入。
- 消灭模块级可变单例（`main.py:15,18`、`llm_client.py:438-443`），改 FastAPI 依赖 / lifespan 管理。
- 编排函数拆步（`analyzer.run_analysis` 440 行 → 阶段对象），与 ResumableAnalyzer 的 8 阶段对齐同一状态机。

### 阶段 4：多租户准备（商业化前置）

1. 表结构加 `tenant_id`/`created_by` + 复合索引；`GET /history` 等查询加租户过滤。
2. 鉴权升级 OAuth2/JWT + 角色（admin/analyst/viewer）；管理端点（scheduler start/stop、ollama pull、index delete）单独授权。
3. 配额与计费：接阶段 1 的 token 核算 → 按租户预算 + 超额拒绝（429 语义）。
4. 数据保留策略（`SignalRecord`/`SimulationRecord` TTL 清理任务）与审计日志表。

### 成功判据（可验收）

| 阶段 | 判据 |
|------|------|
| 0 | `py_compile` 全绿；OpenAPI 路由表与前端契约 diff 为 0；无鉴权访问 `/api/v1/review` 返回 401 |
| 1 | 杀掉进程再拉起，分析任务自动续跑；任一次分析可报出 token 成本；429 下重试间隔 ≥1s |
| 2 | CI 强制 lint+type+test+contract；任一请求可通过 trace_id 串起 LLM 调用链 |
| 3 | domain 层单测无需数据库；新增一个分析维度只改 domain+schema |
| 4 | 两个 tenant 数据互不可见；预算超限被拒绝 |

---

---

## 附录 A：审计证据索引

| 证据编号 | 结论 | 定位 |
|----------|------|------|
| E1 | engine.py 语法错误，仿真不可用 | `src/backend/services/simulation/engine.py:150`（try）、`:227-228`（orphaned finally）、`:175`（SyntaxError 报错点） |
| E2 | 路由双前缀 | `src/backend/routes_v3.py:45`（无 prefix）、`:66`（路径含 /api/v3）、`src/backend/main.py:59`（再加 prefix） |
| E3 | 前端契约不符 | `src/frontend/src/api/index.ts:4`（V3_BASE）、`:219`（请求 /api/v3/signals/hotlist） |
| E4 | 唯一正确的 v3 写法（对照） | `src/backend/routes_v3.py:1204`（/fine-grained/status 相对路径） |
| E5 | 零鉴权 | `src/backend/main.py:47-53`（仅 CORSMiddleware）；全仓无 auth Depends |
| E6 | 任意本地文件路径 | `src/backend/routes.py:177-180`、`src/backend/routes_v3.py:1225` |
| E7 | 上传路径遍历 | `src/backend/routes.py:676`（filename 未消毒拼接） |
| E8 | 视频预处理未进后台 | `src/backend/routes.py:174-204`（同步预处理）vs `:231`（才 add_task） |
| E9 | 同步 ORM | `src/backend/database.py:28-49`（create_engine/sessionmaker）、`src/backend/services/analyzer.py:208` |
| E10 | LLM usage 被丢弃 | `src/backend/services/llm_client.py:726`（只取 content） |
| E11 | 重试无退避 | `src/backend/services/llm_client.py:666-678`（内层循环无 sleep） |
| E12 | 密钥泄漏 | `.monkeycode/MEMORY.md:92`（完整 Key 明文） |
| E13 | 默认口令写死 | `src/backend/config.py:57`、`:63` |
| E14 | 迁移缺失 | `src/backend/database.py:61`（仅 create_all）、`src/backend/migrations/004_risk_score_column.py:41` |
| E15 | routes_story 未挂载 | `src/backend/routes_story.py:28` vs `src/backend/main.py:55-71` |
| E16 | 历史 N+1 / 无分页上界 | `src/backend/routes.py:543-551` |
| E17 | 外键无索引 | `src/backend/models.py:41`、`:55` |
| E18 | prompt 注入面 | `src/backend/services/risk_assessor.py:20`（模板直接拼接用户文本） |
| E19 | 广播异常静默 | `src/backend/main.py:158-159`（except pass） |
| E20 | 仿真持久化吞异常 | `src/backend/services/simulation/engine.py:502-504` |

## 附录 B：本次审计未覆盖项（后续补测）

1. **运行时压测**：本地 venv 缺 `sqlalchemy`，未能启动服务实测路由表与 404 复现（双前缀结论为静态推导 + 前端契约对照，确定性高）。
2. **LLM 实际配额行为**：未触发真实 429 验证冷却/降级链路（依据代码路径分析）。
3. **Neo4j/ChromaDB 降级路径**：仅读代码确认 503 分支，未做故障注入。
4. **依赖漏洞扫描**：未跑 `pip-audit`/`safety`，建议补入 CI。
5. **并发压测**：SQLite `check_same_thread=False` 下的写锁竞争需实测。

---

*报告生成依据：静态通读 8 个核心后端文件 + 6 个路由文件 + llm_client/analyzer/enhanced_analyzer/risk_assessor/resumable_analyzer/batch_analyzer/engine + models/database/config + 前端 api/index.ts 契约对照 + `py_compile` 语法校验。*
