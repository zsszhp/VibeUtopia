# VibeUtopia 生产环境部署指南

## 目录

- [系统要求](#系统要求)
- [Docker 部署](#docker-部署)
- [环境变量配置](#环境变量配置)
- [数据库初始化](#数据库初始化)
- [前端构建和部署](#前端构建和部署)
- [Nginx 反向代理配置](#nginx-反向代理配置)
- [SSL 证书配置](#ssl-证书配置)
- [性能调优建议](#性能调优建议)
- [常见问题排查](#常见问题排查)

---

## 系统要求

### 硬件要求

| 层级 | CPU | 内存 | GPU | 适用场景 |
|------|-----|------|-----|----------|
| Lite | 4核+ | 8GB+ | 无 | 纯API模式，所有模型走云端 |
| Standard | 8核+ | 16GB+ | 4-6GB VRAM | 本地OCR+小模型推理 |
| Pro | 16核+ | 32GB+ | 8-12GB VRAM | 本地视觉模型+中等推理 |
| Ultra | 32核+ | 64GB+ | 16GB+ VRAM | 全本地模型部署 |

### 软件要求

| 组件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.10+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| Docker | 24+ | 25+ |
| Docker Compose | 2.20+ | 2.30+ |
| MySQL | 8.0+ | 8.0 |
| Neo4j | 5.x | 5.x Community |
| Nginx | 1.24+ | 1.26+ |

### 操作系统

- **推荐**：Ubuntu 22.04 LTS / Debian 12
- **支持**：CentOS 8+ / Windows Server 2022+ / macOS 13+

---

## Docker 部署

### 1. 使用 docker-compose.yml

项目根目录已包含 `docker-compose.yml`，可一键启动 Neo4j 和 MySQL：

```bash
# 启动基础设施服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f neo4j
docker compose logs -f mysql
```

**docker-compose.yml 包含的服务：**

| 服务 | 端口 | 说明 |
|------|------|------|
| `neo4j` | 7474(HTTP), 7687(Bolt) | 图数据库 |
| `mysql` | 3306 | 关系型数据库 |

### 2. 完整 Docker 部署（含后端）

如需将后端也容器化，可扩展 `docker-compose.yml`：

```yaml
services:
  backend:
    build: .
    container_name: vibeutopia-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+pymysql://vibe_user:vibe_password@mysql:3306/vibeutopia
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      mysql:
        condition: service_healthy
      neo4j:
        condition: service_started
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    restart: unless-stopped
```

### 3. 手动部署（非 Docker）

```bash
# 克隆项目
git clone <repository-url>
cd VibeUtopia

# 安装 Python 依赖
pip install -r requirements.txt

# 复制并编辑环境配置
cp .env.example .env
# 编辑 .env 填入真实配置

# 启动后端
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## 环境变量配置

### 完整 .env 配置清单

复制 `.env.example` 为 `.env`，根据实际情况修改：

```bash
cp .env.example .env
```

#### LLM 厂商配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LONGCAT_API_KEY` | LongCat API Key | 空 |
| `LONGCAT_BASE_URL` | LongCat API 地址 | `https://api.longcat.chat/openai/v1` |
| `LONGCAT_MODEL` | LongCat 模型名 | `LongCat-Flash-Thinking-2601` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 空 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | DeepSeek 模型名 | `deepseek-chat` |
| `ALIYUN_API_KEY` | 阿里云 API Key | 空 |
| `ALIYUN_BASE_URL` | 阿里云 API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `ALIYUN_MODEL` | 阿里云模型名 | `qwen-max` |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key | 空 |
| `SILICONFLOW_BASE_URL` | 硅基流动 API 地址 | `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_MODEL` | 硅基流动模型名 | `deepseek-ai/DeepSeek-V3` |
| `ZHIPU_API_KEY` | 智谱 API Key | 空 |
| `ZHIPU_BASE_URL` | 智谱 API 地址 | `https://open.bigmodel.cn/api/paas/v4` |
| `ZHIPU_MODEL` | 智谱模型名 | `glm-4` |
| `ZHIPU_VL_MODEL` | 智谱视觉模型名 | `glm-4v` |

> **多 Key 支持**：每个厂商支持配置多个 Key，用逗号分隔。系统自动按顺序使用，配额耗尽时切换下一个。

#### 模型路由控制

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEFAULT_PROVIDER` | 默认厂商 | `longcat` |
| `DEFAULT_MODEL` | 强制使用的模型（留空自动选择） | 空 |

#### 数据库配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接URL | `sqlite:///./data/vibeutopia.db` |
| `MYSQL_HOST` | MySQL 主机 | 空 |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户 | `vibe_user` |
| `MYSQL_PASSWORD` | MySQL 密码 | `vibe_password` |
| `MYSQL_DATABASE` | MySQL 数据库名 | `vibeutopia` |
| `CHROMA_DB_PATH` | ChromaDB 存储路径 | `./data/chroma` |

#### Neo4j 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | `vibeutopia2024` |

#### 仿真引擎配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AGENTS_PER_PLATFORM` | 每平台 Agent 数 | `10` |
| `MEMORY_RETRIEVAL_LIMIT` | 记忆检索限制 | `5` |
| `LLM_TIMEOUT` | LLM 调用超时(秒) | `30` |
| `LLM_MAX_RETRIES` | LLM 最大重试次数 | `3` |
| `MODEL_COOLDOWN_SECONDS` | 模型冷却时间(秒) | `300` |

#### 多模态配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `KEYFRAME_MAX_FRAMES` | 最大关键帧数 | `50` |
| `KEYFRAME_INTERVAL_SECONDS` | 关键帧间隔(秒) | `5.0` |
| `OCR_MIN_CONFIDENCE` | OCR 最低置信度 | `0.5` |
| `WHISPER_MODEL` | Whisper 模型 | `base` |
| `WHISPER_DEVICE` | Whisper 设备 | `cpu` |

#### 硬件检测配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HARDWARE_DETECTION_ENABLED` | 是否启用硬件检测 | `true` |
| `VRAM_THRESHOLD_LITE` | Lite 层级 VRAM 阈值(GB) | `8` |
| `VRAM_THRESHOLD_STANDARD` | Standard 层级 VRAM 阈值(GB) | `16` |

#### 本地模型配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `VLLM_BASE_URL` | vLLM 服务地址 | `http://localhost:8000` |

---

## 数据库初始化

### MySQL

```bash
# 使用 Docker 启动的 MySQL 已自动创建数据库
# 如需手动初始化：
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS vibeutopia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'vibe_user'@'%' IDENTIFIED BY 'vibe_password';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON vibeutopia.* TO 'vibe_user'@'%';"
mysql -u root -p -e "FLUSH PRIVILEGES;"
```

应用启动时 SQLAlchemy 会自动创建所有表（`Base.metadata.create_all`）。

### SQLite

无需手动初始化，应用启动时自动创建 `data/vibeutopia.db`。

### ChromaDB

ChromaDB 数据存储在 `CHROMA_DB_PATH` 指定的目录下，首次使用时自动初始化。

```bash
# 确保 data 目录存在
mkdir -p ./data/chroma
```

### Neo4j

```bash
# 使用 Docker 启动
docker compose up -d neo4j

# 验证连接
# 浏览器访问 http://localhost:7474
# 用户名: neo4j  密码: vibeutopia2024
```

> **注意**：Neo4j 不可用时系统会自动降级到关系型数据库模式，不影响核心功能使用。

---

## 前端构建和部署

### 开发模式

```bash
cd frontend-vue

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 生产构建

```bash
cd frontend-vue

# 安装依赖
npm install

# 构建
npm run build

# 构建产物在 dist/ 目录
```

### 部署静态文件

将 `dist/` 目录下的文件部署到 Nginx 或其他 Web 服务器：

```bash
# 复制到 Nginx 目录
cp -r dist/* /var/www/vibeutopia/
```

---

## Nginx 反向代理配置

```nginx
server {
    listen 80;
    server_name vibeutopia.example.com;

    # 前端静态文件
    root /var/www/vibeutopia;
    index index.html;

    # 前端路由 - SPA 回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（深度分析可能耗时较长）
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
    }

    # 上传文件大小限制
    client_max_body_size 100M;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1024;
}
```

---

## SSL 证书配置

### 使用 Let's Encrypt（推荐）

```bash
# 安装 certbot
apt install certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d vibeutopia.example.com

# 自动续期（certbot 已自动配置定时任务）
certbot renew --dry-run
```

### 手动配置 SSL

```nginx
server {
    listen 443 ssl http2;
    server_name vibeutopia.example.com;

    ssl_certificate /etc/ssl/certs/vibeutopia.crt;
    ssl_certificate_key /etc/ssl/private/vibeutopia.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # ... 其余配置同上
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name vibeutopia.example.com;
    return 301 https://$server_name$request_uri;
}
```

---

## 性能调优建议

### 后端

1. **Uvicorn Worker 数量**

```bash
# 根据 CPU 核心数设置
uvicorn backend.main:app --workers 4 --host 0.0.0.0 --port 8000
```

2. **MySQL 连接池**

在 `.env` 中已配置：
- `pool_size=10`
- `max_overflow=20`
- `pool_recycle=3600`
- `pool_pre_ping=True`

3. **LLM 调用优化**
- 设置合理的 `LLM_TIMEOUT`（默认30秒）
- 配置 `LLM_MAX_RETRIES`（默认3次）
- 启用多 Key 轮换避免单 Key 限流

4. **ChromaDB 预热**

应用启动时已自动预热 ChromaDB 模型，优化首次检索延迟。

### 前端

1. **启用 Gzip/Brotli 压缩**
2. **配置 CDN 加速静态资源**
3. **开启 HTTP/2**

### 数据库

1. **MySQL**
   - `innodb_buffer_pool_size` 设为物理内存的 50-70%
   - `max_connections` 根据并发需求调整
   - 定期执行 `ANALYZE TABLE` 更新统计信息

2. **Neo4j**
   - `dbms.memory.heap.max_size` 设为物理内存的 50%
   - `dbms.memory.pagecache.size` 设为物理内存的 25%

---

## 常见问题排查

### 1. 后端启动失败

**症状**：`ModuleNotFoundError` 或 `ImportError`

**解决**：
```bash
pip install -r requirements.txt
```

### 2. MySQL 连接失败

**症状**：`Can't connect to MySQL server`

**解决**：
- 检查 MySQL 服务是否运行：`docker compose ps mysql`
- 检查 `.env` 中 `MYSQL_HOST`、`MYSQL_PASSWORD` 配置
- 系统会自动降级到 SQLite，不影响使用

### 3. Neo4j 连接失败

**症状**：日志显示 `Neo4j 连接失败`

**解决**：
- 检查 Neo4j 服务：`docker compose ps neo4j`
- 浏览器访问 `http://localhost:7474` 验证
- 系统会自动降级到关系型数据库模式

### 4. LLM API 调用失败

**症状**：分析任务一直处于 processing 状态

**解决**：
- 检查 API Key 是否正确配置
- 使用 `/api/v3/llm-test` 端点测试连通性
- 检查网络是否能访问 API 服务
- 配置多个厂商 Key 作为备份

### 5. ChromaDB 初始化失败

**症状**：Memory Stream 功能不可用

**解决**：
- 确保 `CHROMA_DB_PATH` 目录可写
- 检查磁盘空间是否充足
- 删除损坏的 ChromaDB 数据后重启

### 6. 前端无法连接后端

**症状**：前端页面空白或 API 请求失败

**解决**：
- 检查后端是否运行：`curl http://localhost:8000/api/v1/models`
- 检查 Nginx 代理配置
- 检查 CORS 配置（开发环境已允许所有来源）

### 7. 视频上传失败

**症状**：上传返回 400 错误

**解决**：
- 检查文件格式是否为 mp4/mov/avi/webm
- 检查文件大小是否超过 100MB
- 检查 Nginx `client_max_body_size` 配置
