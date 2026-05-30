---
description: VibeUtopia 项目根规则（6段式）
globs:
alwaysApply: true
---

## 1. Project Overview

- **VibeUtopia** — 社媒内容风控与趋势预测平台
- **核心能力**：28+平台信号采集 → 多模态分析 → 舆情仿真 → 风险评估 → 决策建议
- **技术栈**：
  - 后端：Python 3.11 + FastAPI + SQLAlchemy + MySQL + Neo4j + ChromaDB
  - 前端：Vue 3 + TypeScript + Vite + Naive UI + TailwindCSS
  - AI：LiteLLM 多模型路由（DeepSeek/Qwen/Claude/GPT）
  - 多模态：OpenCV + SceneDetect + 帧抽取 + 音频转写
- **详见** `CLAUDE.md`

## 2. Commands

### 后端命令
- **安装依赖**：`pip install -r requirements.txt`
- **启动服务**：`cd src/backend && uvicorn main:app --reload --port 8000`
- **Docker部署**：`docker-compose -f scripts/docker-compose.yml up -d`

### 前端命令
- **安装依赖**：`cd src/frontend && pnpm install`
- **开发模式**：`cd src/frontend && pnpm dev`
- **构建生产**：`cd src/frontend && pnpm build`

### 测试命令
- **后端测试**：`pytest tests/ -v`
- **前端类型检查**：`cd src/frontend && vue-tsc -b`
- **前端构建**：`cd src/frontend && pnpm build`

## 3. Architecture

### 项目结构
- `src/backend/` — FastAPI 后端服务
  - `services/` — 核心业务逻辑（signal/analyzer/simulation/persona）
  - `routes*.py` — API 路由
  - `models.py` — Pydantic 模型
  - `database.py` — SQLAlchemy 配置
- `src/frontend/` — Vue 3 前端应用
  - `views/` — 页面组件
  - `components/` — 通用组件
  - `stores/` — Pinia 状态管理
  - `api/` — Axios API 调用
- `data/config/` — 配置文件（YAML）
- `tests/` — 测试脚本

### 架构模式
- **API 层**：FastAPI 路由 → Service 层 → 数据库/外部 API
- **前端层**：Vue 3 组件 → Pinia Store → Axios API
- **仿真层**：Signal → Simulation Engine → Decision Engine

## 4. Conventions

### 代码规范
- **Python**：snake_case，async/await 模式，Pydantic 模型验证
- **TypeScript**：camelCase，泛型+接口，Vue 3 Composition API
- **Vue 组件**：PascalCase，`<script setup>` 语法
- **配置文件**：YAML 格式，路径通过环境变量或 config 管理

### API 设计
- RESTful 风格，版本前缀 `/api/v1/`
- 请求/响应使用 Pydantic 模型验证
- 错误返回标准 HTTP 状态码 + 错误信息

### 数据流
- Signal → Analyzer → Simulator → Decision Engine → API Response
- 前端 WebSocket 实时接收仿真进度

## 5. Hard Constraints

- **数据库连接**必须用 SQLAlchemy Session 管理，请求结束必须关闭
- **异步操作**用 `async/await`，禁止混用同步阻塞
- **外部 API 调用**必须加超时和重试机制
- **敏感信息**禁止硬编码，必须通过 `.env` 环境变量
- **文件上传**必须校验文件类型和大小
- **用户输入**必须校验和 sanitize，防 XSS/注入

## 6. Gotchas

- **LiteLLM** 多模型路由配置在 `data/config/model_config.yaml`
- **Neo4j** 图数据库用于实体关系存储，启动前确保服务运行
- **ChromaDB** 向量数据库用于博主记忆，启动前确保服务运行
- **信号采集**调度配置在 `data/config/signal_config.yaml`
- **前端 API 地址**配置在 `src/frontend/src/api/index.ts`

## 7. 日志必须记录的操作

- 信号采集：开始/完成/失败
- 分析任务：启动/完成/失败
- 仿真运行：开始/阶段完成/结束
- 风险评估：高分预警
- API 调用：外部模型调用失败
- 数据库：连接失败/迁移执行
- 用户操作：登录/登出/关键操作
