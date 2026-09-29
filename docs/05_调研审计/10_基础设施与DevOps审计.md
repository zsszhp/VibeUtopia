# 基础设施与DevOps审计

> **文档定位**：调研审计｜启动脚本、容器、CI 与环境一致性审计
> **所属目录**：`docs/05_调研审计/`


> 审计范围：docs/03_使用与运维/16、24、25，docker 相关文件，setup.sh / setup.ps1 / start.sh / start.ps1，requirements.txt，.env.example，scripts/，系统对 Docker / MySQL / Neo4j / ChromaDB 的依赖与降级路径。
> 审计视角：本地开发体验、一键启动真实可用性、环境配置复杂度、依赖版本健康、Windows/Linux 跨平台、密钥管理、日志/监控/告警、备份、升级迁移、资源占用，以及与现代 Python/Node 工程化、LLM 应用成本可观测、容器化最佳实践的差距。

---

## 1. 执行摘要

VibeUtopia 的**功能实现层相当完整**（多模态风控、仿真、模型路由、降级 fallback 遍布 355 处），但**基础设施与开发体验层严重欠账**：文档宣称的一键启动、自动降级、备份/健康检查脚本，绝大多数与代码事实不符或根本不存在。

核心结论：

1. **一键启动不可用（P0）**。所有入口（README、setup.sh、start.sh、start.ps1、doc16/24/15）给出的后端启动命令 `uvicorn backend.main:app` 均无法直接运行——包结构在 `src/backend`，项目无 `pyproject.toml`/可安装包，`PYTHONPATH` 未指向 `src`。`start.sh` 甚至 `cd backend`（目录不存在）。README 提到的 `start.bat` 文件不存在，`bash setup.sh` 在根目录也找不到脚本。
2. **Docker 编排文件位置与文档全部错位**。唯一的 `scripts/docker-compose.yml` 被 README、doc16、doc24、setup.sh/setup.ps1 一致假定在项目根目录；setup 脚本里 `[ -f "docker-compose.yml" ]` / `Test-Path "docker-compose.yml"` 检查静默失败 → **Docker 数据库从未被一键脚本拉起**。
3. **宣称的降级能力名不副实**。"MySQL 失败自动降级 SQLite"在代码上几乎不可能触发（SQLAlchemy `create_engine` 惰性连接，不抛连接错误）；`CHROMA_DB_PATH` 配置项存在但被硬编码路径绕过；Neo4j 降级写路径有损。
4. **运维层大量"文档有、仓库无"**：备份脚本（4 个）、健康检查脚本、Dockerfile（doc24 让用户 `build: .`）、迁移 runner（`python -m backend.migrations.xxx` 占位符）全部缺失。
5. **密钥管理仅停留在"不提交 .env"**：数据库/Neo4j 密码以明文硬编码在被 git 跟踪的 `docker-compose.yml` 与 `scripts/setup_mysql.py` 中，无密钥注入机制、无轮换工具、无 .env 校验。
6. **可观测性缺口大**：无 `/health` 端点、无集中日志配置/轮转、无 Prometheus 指标、**无 LLM token/费用归集**（只有 Key 调用计数），与"LLM 应用成本可观测"的行业基线差距明显。

一句话评价：**这是一个"应用代码跑得通、工程底盘跑不通"的项目**。新开发者按文档操作，大概率在 30 分钟内卡死在启动环节。

---

## 2. 环境与依赖现状

### 2.1 运行时与工具链（三套并存，互不一致）

| 来源 | Python | 包管理 | 前端包管理 | 数据库启动方式 |
|------|--------|--------|------------|----------------|
| README.md | 3.10 + conda | pip | npm | `docker compose up -d neo4j`（根目录） |
| docs/03_使用与运维/16 | 3.11 + uv | uv pip | pnpm | `docker compose up -d`（根目录） |
| scripts/setup.sh/ps1 | 3.10+（提示装 3.12） | venv + pip | npm（start 脚本） | `docker-compose` / `docker compose`（根目录） |
| docs/03_使用与运维/24 | 3.10+（推荐 3.12） | pip | npm | 根目录 compose |

同一项目四份文档给出四种环境画像；`requirements.txt` 未钉 Python 版本，无 `pyproject.toml`、无 `uv.lock`、无 `requirements.lock`、无 `.nvmrc`/`engines`。

### 2.2 依赖清单健康度（requirements.txt）

- **全部下界约束、无上界、无哈希锁**：`fastapi>=0.110.0`、`chromadb>=0.5.0` 等，任意一次 `pip install` 都可能拉到不兼容大版本，无法复现环境。
- **死依赖**：`litellm>=1.35.0` 声明在"AI 与模型路由"，但全代码库 `import litellm` **零命中**——模型路由实际是自研 `src/backend/services/llm_client.py`。docs/15 还写着"模型路由 LiteLLM 最终决定"，属文档-代码脱节。
- **重依赖未拆分**：`opencv-python`（含 GUI 依赖，服务器场景应 `opencv-python-headless`）、`chromadb`（嵌入式向量库，自带嵌入模型下载）与业务依赖混装；`pytest`/`pytest-asyncio` 放在主 requirements 而非 dev 依赖。
- **系统级依赖未声明**：FFmpeg 必装（doc16 有，但 setup.sh/requirements 均不检查）、ChromaDB 的 sqlite3 版本问题（doc16 FAQ 靠手动 `pysqlite3` hack）无自动化兜底。
- **前端双锁文件**：`package-lock.json`（111KB）与 `pnpm-lock.yaml`（70KB）同时入库，`node_modules` 状态不可预期；doc16 用 pnpm、start 脚本用 npm。

### 2.3 基础设施依赖与降级路径实测评估

| 组件 | 依赖方式 | 文档宣称降级 | 代码实际 | 评估 |
|------|----------|--------------|----------|------|
| MySQL | `DATABASE_URL` 或 `MYSQL_HOST` | 失败自动降级 SQLite（doc24 FAQ2） | `database.py:_create_engine` 的 try/except 包住 `create_engine`，但 SQLAlchemy 惰性连接，MySQL 不可达时此处不抛错；真正失败发生在 `init_db()`/首次查询并向上抛出 | **降级失效（P1）** |
| Neo4j | `NEO4J_*` | 不可用自动降级关系库（doc24/25） | `graph_store.connect()` 真实 try/except + `verify_connectivity()`，失败转内存 dict + 尝试写 `AgentRecord` | **降级真实但有损**：实体属性压缩进 `persona_json`、关系语义简化，"核心功能不受影响"表述夸大 |
| ChromaDB | `CHROMA_DB_PATH`（.env.example=`./data/chroma`） | 配置路径 | `memory_stream.py` / `chroma_model_warmup.py` **硬编码** `./data/chroma_memories`，配置项被完全绕过 | **配置失效（P1）** |
| Docker | scripts/docker-compose.yml | 一键启动 | compose 无 app 服务、无 Dockerfile、无 healthcheck（Neo4j）、无资源 limits、`version: '3.8'` 已废弃 | **半成品** |

### 2.4 数据层现状

- `data/` 目录混放：SQLite 库（`vibeutopia.db`）、运行日志（`signal_collection.log`、`t7_enhancement.log`）、`chroma_memories/`、backtest、reports。gitignore 已覆盖运行时产物，但**路径命名双轨**（`data/chroma` vs `data/chroma_memories` vs `src/data/chroma_memories`）加剧混乱。
- 迁移体系残缺：`src/backend/migrations/` 仅有 `003_chromadb_memorystream.py`、`004_risk_score_column.py`，**001/002 缺失**，无 Alembic、无迁移版本表、无执行入口（doc25 升级步骤写 `python -m backend.migrations.xxx` 纯占位）。
- 表结构靠 `Base.metadata.create_all` 自动建表，**无 schema 变更/数据迁移路径**，升级改列只能手工 SQL。

---

## 3. 开发者体验（DX）走查

按"新机器、新克隆、照文档做"的真实路径逐步验证：

| 步骤 | 文档指引 | 实际结果 | 判定 |
|------|----------|----------|------|
| 1. 一键配置 | README：`bash setup.sh` | 根目录无 `setup.sh`（在 `scripts/`） | ❌ P0 |
| 2. 配置数据库 | README/doc16/doc24：根目录 `docker compose up -d` | 根目录无 `docker-compose.yml`（在 `scripts/`） | ❌ P0 |
| 3. setup 内部启动 DB | setup.sh:61-91 `if [ -f "docker-compose.yml" ]` | 文件不存在 → 静默跳过，打印"配置完成" | ❌ P0 |
| 4. 安装依赖 | `pip install -r requirements.txt` | 可行，但无锁文件；litellm 等多余包；耗时长（opencv/chromadb） | ⚠️ |
| 5. 启动后端 | `uvicorn backend.main:app --reload` | `ModuleNotFoundError: backend`（包在 `src/backend`，无安装入口，PYTHONPATH 未设） | ❌ P0 |
| 6. start.sh 一键启动 | `bash scripts/start.sh` | 第 33 行 `cd backend` 失败（无此目录） | ❌ P0 |
| 7. start.ps1 一键启动 | `powershell -File scripts\start.ps1` | `PYTHONPATH=$ProjectRoot`（缺 `\src`）+ `uvicorn backend.main:app` → 同样导入失败；前端目录 `src\frontend` 正确 | ❌ P0 |
| 8. start.bat | README"双击 start.bat" | 文件不存在 | ❌ P0 |
| 9. 启动前端 | README/doc16：`cd frontend` | 实际 `src/frontend` | ❌ P0 |
| 10. 访问前端 | 端口 3000 / 5173 / 8080 三种说法 | `vite.config.ts` 与 start.ps1 为 **3000**；start.sh 与 doc16 为 5173；doc16 QuickStart 为 8080 | ⚠️ 文档自相矛盾 |
| 11. 验证 checklist | doc16 的 13 项检查 | 检查命令本身多处路径/端口错误；`curl /api/models` 无对应路由确认 | ⚠️ |

**DX 结论：一键启动真实可用性 ≈ 0**。10 个必经步骤中 8 个直接失败，且多数失败是**静默的**（setup 跳过 DB 不报错、start 脚本继续跑前端），开发者会误以为环境已就绪，再在运行期撞上数据库/图谱问题。

其他 DX 问题：
- 无 `Makefile` / `justfile` / `task` 等统一任务入口；命令散落在 5 份文档里。
- 无 pre-commit、无 lint 配置入库（`.ruff_cache` 存在说明有人本地跑 ruff，但 `pyproject.toml`/`ruff.toml` 未提交），格式化/静态检查不可复现。
- 无 `.vscode/launch.json` 有效调试配置说明（有 `.vscode/` 但未审计其可用性）。
- 根目录残留 20+ 个 `docker_*.txt` 调试文件（已被 gitignore，但污染本地工作区）。
- Windows 侧 PowerShell 脚本质量较好（有 venv 激活、进程守护），Linux 侧 `start.sh` 是裸 `&` + `kill PID`，无信号处理、无优雅退出。

---

## 4. 部署与运行风险

### 4.1 一键启动与进程管理
- 无 systemd unit、无进程守护（doc16 提到 systemd 是 Ubuntu 优势但仓库无 unit 文件）。后端崩溃无自动拉起。
- `start.sh`/`start.ps1` 固定 `sleep 10` 等待启动，慢机器会误报；健康探测仅 curl `/docs`。
- 生产启动建议 `uvicorn --workers 4`（doc24），但 WebSocket 连接管理在**进程内存**（`ws_connections` dict），多 worker 下广播必然丢消息——扩容章节自己也提示需要 sticky session，但无实现方案。

### 4.2 容器化缺口
- **无 Dockerfile**：doc24"完整 Docker 部署（含后端）"给出 `build: .` 的 compose 片段，仓库无任何可构建的 Dockerfile（仅 `references/` 参考项目里有）。
- `scripts/docker-compose.yml` 缺陷清单：
  - `version: '3.8'` 已被 Compose V2 废弃（会有警告）；
  - Neo4j 无 `healthcheck`（MySQL 有），`depends_on: condition: service_started` 形同虚设；
  - 无 `deploy.resources.limits` / `mem_limit`，MySQL+Neo4j 默认可吃满开发机内存；
  - 无日志驱动配置（json-file 无 max-size，磁盘会被撑爆）；
  - 端口 `3306:3306`、`7474/7687` 全量暴露宿主机，无 `127.0.0.1:` 绑定，笔记本连公网 WiFi 即暴露数据库；
  - 无自定义 network，凭据以明文 environment 注入。
- 镜像版本：`neo4j:5-community`、`mysql:8.0` 为浮动 tag，无 digest 钉扎，不可复现构建。

### 4.3 数据安全与迁移
- 备份：doc25 写了 4 个完整备份脚本（mysql/sqlite/chroma/neo4j/config）+ crontab，**`scripts/` 下一个都没有**；升级章节第一步 `bash scripts/backup_mysql.sh` 直接失败。无恢复演练记录。
- 迁移：见 2.4，schema 演进无工具支撑，多人协作下极易出现"我这儿能跑你那儿缺列"。
- ChromaDB 嵌入式单机文件存储，多 worker/多实例部署会**并发写损坏**（doc25 提到可分片/Server 模式，无落地）。

### 4.4 资源占用（视频处理 / 向量库）
- 视频链路：关键帧抽取（`KEYFRAME_MAX_FRAMES=50`）+ OpenCV 场景检测 + OCR + 可选 Whisper，单任务 CPU/内存峰值高；无任务队列限流（仅 LLM 侧有并发控制）、无磁盘配额、上传 100MB 限制只在 Nginx 文档里，应用层未见统一校验。
- 仿真引擎：`AGENTS_PER_PLATFORM=10` × 28 平台规模，`scale_manager` 有资源校验但默认配置下内存随 Agent 数线性增长。
- LLM_TIMEOUT=30s、深度分析 Nginx 超时 300s，长任务阻塞 worker；无 Celery/RQ/队列，重任务与 API 共进程。

---

## 5. 可观测性缺口

| 能力 | 现状 | 基线要求 | 差距 |
|------|------|----------|------|
| 健康探活 | **无 `/health`/`/healthz` 端点**（grep 零命中）；doc25 用业务端点冒充健康检查 | liveness/readiness 分离，供 Docker/K8s/SLB 使用 | P1 |
| 健康检查脚本 | doc25 内嵌 `health_check.sh` 片段，**无落地文件** | scripts/health_check.sh + cron/监控接入 | P1 |
| 日志 | 113 处 `logging.getLogger`，但 **main.py 无 logging.basicConfig/无 handler 配置**；无文件输出、无轮转、无 JSON 结构化；doc25 自述"控制台输出（建议重定向）" | 集中配置、级别可配（LOG_LEVEL）、RotatingFileHandler 或 stdout JSON，可接 Loki/ELK | P1 |
| 日志关键字 | doc25 定义了 9 个关键字表 | 代码中部分存在，无断言/告警规则绑定 | P2 |
| 指标 | 无 Prometheus/StatsD；doc25 说"可选扩展 pip install prometheus-fastapi-instrumentator" | RED/USE 指标默认暴露 | P2 |
| 告警 | 无任何告警通道（邮件/Webhook/企微） | 阈值告警（doc25 有阈值表但无执行方） | P2 |
| 分布式追踪 | 无 request_id / trace_id 贯穿 | 至少 request_id 中间件 + 日志关联 | P2 |
| **LLM 成本可观测** | `llm_client.py` 仅 `_key_usage_stats`（calls/errors/last_used）；**无 token 用量、无单价、无费用估算、无按任务/模型/厂商归集**；max_tokens 硬编码 4096 | 每次调用记录 prompt/completion tokens，落库或导出；成本面板/日报；预算告警 | **P1（LLM 应用核心缺失）** |
| 任务可观测 | 分析任务状态有 WS 推送，但无任务耗时分布、成功率指标（doc25 阈值表无数据源） | 任务级 metrics + 慢任务追踪 | P2 |

---

## 6. 安全与密钥管理

### 6.1 明文密钥与默认口令（P1）
| 位置 | 内容 | 风险 |
|------|------|------|
| `scripts/docker-compose.yml`（git 跟踪） | `MYSQL_ROOT_PASSWORD: root_password`、`vibe_password`、`NEO4J_AUTH: neo4j/vibeutopia2024` | 默认口令入库，任何克隆者/镜像同步均可见 |
| `scripts/setup_mysql.py`（git 跟踪） | 硬编码 `root/123456` | 与 compose 口令还不一致，双重误导；典型凭据泄漏 |
| `src/backend/config.py` | `NEO4J_PASSWORD` 默认 `vibeutopia2024`、`MYSQL_PASSWORD` 默认 `vibe_password` | 代码内嵌默认口令，忘配 .env 即用弱口令连库 |
| `.env.example` | 同上默认密码示例 | 可接受，但应改为占位符 `${MYSQL_PASSWORD}` 形式 |
| 本地 `.env` | 未入 git（✅），但含真实多厂商 API Key | 无加密（如 sops/age）、无提交前 secret 扫描（gitleaks/pre-commit） |

### 6.2 网络与应用安全
- CORS：`main.py` `allow_origins=["*"]`（doc25 自己写"生产环境应限制"，代码未做环境区分）。
- 后端 `--host 0.0.0.0` 直接监听所有网卡；Nginx 反代/防火墙规则只在文档里。
- 数据库端口映射全量暴露（见 4.2）。
- 无速率限制、无 API 鉴权（FastAPI 无 security 依赖）、内网管理端点（`/api/v3/model-status` 等暴露 Key 池状态）无访问控制。
- 日志脱敏要求（doc25）无代码级约束，`llm_client` 异常路径可能带出请求细节。

### 6.3 供应链
- requirements 无哈希锁、无 `pip-audit`/`safety` 流程；前端 lock 双轨；无 SBOM；镜像浮动 tag。参考项目 `references/` 本地保留不入库（正确），但无依赖准入清单。

---

## 7. 问题清单 P0-P3

### P0 — 阻断性（一键启动 / 部署主路径不可用）
| # | 问题 | 证据位置 |
|---|------|----------|
| P0-1 | 后端模块路径错误：所有文档/脚本用 `backend.main:app`，实际包在 `src/backend` 且无可安装入口；start.ps1 `PYTHONPATH=$ProjectRoot` 缺 `\src` | README.md:193、docs/03_使用与运维/16:222、docs/03_使用与运维/24:112、scripts/start.ps1:67-70、src/backend/main.py:6 |
| P0-2 | `start.sh` 第 33 行 `cd backend`、第 67 行 `cd frontend` 目录不存在（实为 `src/`） | scripts/start.sh:33,67 |
| P0-3 | `docker-compose.yml` 在 `scripts/`，README/doc16/doc24/setup.sh/setup.ps1 全部假定根目录；setup 静默跳过 DB 启动 | scripts/docker-compose.yml、scripts/setup.sh:81、scripts/setup.ps1:84 |
| P0-4 | README 引用不存在的 `setup.sh`（根目录）与 `start.bat` | README.md:141,202 |
| P0-5 | 无 Dockerfile，doc24"完整 Docker 部署" `build: .` 无法构建 | docs/03_使用与运维/24:76-95 |
| P0-6 | 前端目录/端口文档错位：`cd frontend` vs `src/frontend`；端口 3000/5173/8080 三说并存 | README.md:177、vite.config.ts:8、scripts/start.sh:74、docs/03_使用与运维/16:208 |

### P1 — 严重（降级失效 / 数据与密钥风险 / 可观测性断裂）
| # | 问题 | 证据位置 |
|---|------|----------|
| P1-1 | "MySQL 失败自动降级 SQLite"基本不会触发（`create_engine` 惰性连接），文档虚假承诺 | src/backend/database.py:28-44、docs/03_使用与运维/24:459 |
| P1-2 | `CHROMA_DB_PATH` 配置无效，代码硬编码 `./data/chroma_memories`，与 .env.example 的 `./data/chroma` 冲突 | src/backend/config.py:35、src/backend/services/persona/memory_stream.py:34、chroma_model_warmup.py:18 |
| P1-3 | 数据库/Neo4j 弱口令硬编码入库；setup_mysql.py 硬编码 root/123456 | scripts/docker-compose.yml:10,23-26、scripts/setup_mysql.py:3 |
| P1-4 | 备份脚本 4 个全部不存在，升级流程第一步即失败 | docs/03_使用与运维/25:137-263,485-488 vs scripts/ 目录清单 |
| P1-5 | 无 `/health` 端点、健康检查脚本未落地，容器/SLB 无法探活 | 全库 grep 无 health 路由、docs/03_使用与运维/25:31-70 |
| P1-6 | 无 LLM token/费用归集，成本不可观测（LLM 应用基线缺失） | src/backend/services/llm_client.py:269,359-375 |
| P1-7 | 迁移体系残缺：001/002 缺失、无 runner/Alembic，`python -m backend.migrations.xxx` 是占位符 | src/backend/migrations/、docs/03_使用与运维/25:515 |
| P1-8 | 依赖无上界无锁文件，环境不可复现；litellm 死依赖 | requirements.txt 全文 |
| P1-9 | 日志无集中配置/轮转/落盘，故障后无事后分析材料 | src/backend/main.py（无 logging 配置）、docs/03_使用与运维/25:74-89 |

### P2 — 重要（工程化与一致性）
| # | 问题 |
|---|------|
| P2-1 | 工具链四说并存（conda/py3.10、uv/py3.11、venv/py3.12、pnpm vs npm），前端双 lock 文件 |
| P2-2 | CORS `allow_origins=["*"]` 未按环境区分；后端 0.0.0.0 监听；DB 端口全暴露 |
| P2-3 | 无 CI（无 .github/workflows）、无 pre-commit、lint/pytest 配置未入库 |
| P2-4 | WebSocket 会话在进程内存，多 worker/扩容方案与实现矛盾 |
| P2-5 | docker-compose：废弃 version 字段、Neo4j 无 healthcheck、无资源 limits、无日志轮转、镜像 tag 浮动 |
| P2-6 | Neo4j 降级写路径有损（属性压缩/关系简化），"核心功能不受影响"表述夸大 |
| P2-7 | 无 systemd unit / 进程守护 / 优雅停机；start.sh 裸 & + kill |
| P2-8 | 重任务（视频/仿真）与 API 同进程，无队列限流、无磁盘配额 |
| P2-9 | 测试仅 8 个文件、无 conftest.py/pytest.ini，基础设施脚本零测试 |
| P2-10 | 无 request_id/追踪；管理端点无鉴权 |

### P3 — 改进项
| # | 问题 |
|---|------|
| P3-1 | 根目录 20+ 个 `docker_*.txt` 调试残留污染工作区 |
| P3-2 | doc16 QuickStart（5 分钟/8080 端口/compose 全栈）与现实差距过大，建议删除或重写 |
| P3-3 | doc16 FAQ 的 pysqlite3 兼容 hack 应固化为安装期自动处理 |
| P3-4 | requirements 应区分 `opencv-python-headless`（服务器）；pytest 拆 dev 依赖 |
| P3-5 | 备份无恢复演练文档；容量规划数字无实测支撑 |
| P3-6 | 无 .nvmrc/engines；Node 版本未钉扎 |
| P3-7 | `AGENTS_PER_PLATFORM` 等业务参数在 .env，建议集中到 config/yaml 并校验 schema |
| P3-8 | docs/15 等历史文档与当前实现（LiteLLM→自研路由）脱节，需清理 |

---

## 8. 工程化改进路线

### 阶段 A：救活开发体验（1 周，对应 P0）
1. **统一包布局与启动入口**：落地 `pyproject.toml`（`[project]` + 可 `pip install -e .`），或最小改动方案——所有启动命令统一为 `PYTHONPATH=src uvicorn backend.main:app`；修正 start.sh/start.ps1/setup 文档中的目录与模块路径。
2. **compose 归位**：将 `docker-compose.yml` 移至仓库根（或所有文档/脚本统一 `-f scripts/docker-compose.yml`），setup 脚本改为 `docker compose -f "$ROOT/scripts/docker-compose.yml" up -d` 并在失败时显式报错而非静默跳过。
3. **补齐/删除幽灵引用**：要么提供 `start.bat`，要么从 README 删除；根目录提供 `setup.sh` 入口（转调 `scripts/`）或改文档。
4. **写一个 Dockerfile**（多阶段：node build → python runtime）并补 compose 的 `backend` 服务，使 doc24 的"完整部署"可执行。
5. **文档对齐矩阵**：一份「唯一快速开始」（根 README）+ 启动命令/端口/路径全部与脚本同源（最好脚本即文档）。
6. **验收标准**：新机器从 clone 到打开前端 ≤10 分钟，且每步失败都有明确报错。

### 阶段 B：可信的降级与数据层（2 周，对应 P1-1/2/7）
1. 修 MySQL 降级：在 `init_db()` 前做真实 `engine.connect()` 探测，失败才切 SQLite 并 WARNING；或明确**不支持**自动降级、启动时 fail-fast 报清晰错误（二选一，禁止虚假承诺）。
2. 统一 Chroma 路径：全部读 `settings.CHROMA_DB_PATH`，.env.example/备份脚本/gitignore 同步为一个路径。
3. 迁移：引入 Alembic（或补全 001/002 + 自研 runner），`create_all` 仅限开发；升级/回滚脚本化并纳入发布清单。
4. 落地 doc25 的 4 个备份脚本 + 恢复演练文档 + cron 示例，删除文档中"有脚本"的虚假引用或补实现。

### 阶段 C：可观测与安全基线（2-3 周，对应 P1-3/5/6/9、P2-2/3）
1. `/health`（存活）与 `/ready`（DB/Neo4j/Chroma/Key 池探测）+ `scripts/health_check.sh` 落地，compose 加 healthcheck 与 depends_on condition。
2. 日志：`logging.config.dictConfig` 集中配置，LOG_LEVEL 环境变量，stdout JSON + 可选 RotatingFileHandler；加 request_id 中间件。
3. **LLM 成本可观测**：调用层记录 tokens/模型/厂商/任务 ID，落 SQLite 表 + `/api/v3/cost-report`，日/月预算告警阈值。
4. 密钥：compose 改 `${MYSQL_PASSWORD}` 等 env 注入；删除 setup_mysql.py 硬编码；pre-commit 加 gitleaks；README 提供轮换指引。
5. CORS 按环境区分（dev `*` / prod 白名单）；DB 端口绑 `127.0.0.1:`；管理端点加简单 token 鉴权。
6. CI（GitHub Actions）：lint（ruff）+ pytest + 前端 build + docker build 冒烟。

### 阶段 D：生产就绪与现代化（持续，对应 P2/P3）
1. compose 资源 limits、日志驱动 max-size、镜像 digest 钉扎、自定义 network。
2. 重任务外置：分析/视频入队（ARQ/RQ + Redis），API 无状态化，WebSocket 改独立网关或 sticky session 方案落地。
3. 依赖治理：lock 文件（uv.lock / requirements.txt 哈希锁）、`pip-audit`、拆 dev 依赖、移除 litellm 或真正启用、opencv-headless、.nvmrc。
4. Prometheus 指标 + Grafana 看板（LLM 成本/任务成功率/队列积压），告警接 Webhook。
5. 测试补齐：conftest.py + 基础设施脚本测试 + 启动冒烟测试（CI 强制）。
6. 清理根目录调试残留、合并双 lock、重写 doc16 QuickStart、清理 docs/15 等过时表述。

**优先级口诀**：先让新人 10 分钟跑起来（A），再让数据与降级可信（B），然后让人看见系统状态与花费（C），最后按生产标准硬化（D）。当前最危险的不是缺功能，而是**文档与脚本共同制造了"系统已就绪"的假象**——这比没有文档更消耗协作者信任。
