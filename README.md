# VibeUtopia - 平行数字世界：发布前风控与舆论仿真平台

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)

[English](README_EN.md) | 中文

> 在发布文案、视频脚本前，模拟多平台真实用户反应，预测舆论风险，避免"翻车"。
> V2 阶段将构建高保真平行数字世界，让千级 Agent 自由交互与社会演化，实现预测未来走向、辅助决策。

---

## ✨ 核心亮点

- 🛡️ **十一维风险评估** — 政治敏感、法律合规、民族宗教、事实错误、平台禁区、性别议题、群体冒犯、道德伦理、时事踩雷、情绪极化、价值观倾向
- 🎯 **句子级精准定位** — 标注哪个句子有风险、属于哪类风险、严重程度如何
- 👥 **多平台人格模拟** — B站/小红书/知乎/抖音四大平台真实用户反应与情绪分布
- ✍️ **安全改写建议** — 对高风险句子提供至少 2 种保留原意的安全改写版本
- 🎬 **多模态视频风控** — 关键帧提取 + OCR + 语音转录 + 跨模态风险检测
- 🌐 **千级 Agent 社交仿真** — 知识图谱 + 7层人格工厂 + 社会关系网络 + 传播动力学

---

## 📋 功能特性

### MVP（已实现）

| 功能 | 说明 |
|------|------|
| 十一维风险评估 | 11个维度独立打分 + 综合评分，对应"可发/建议修改/不建议发" |
| 句子级定位 | 精确标注风险句子、风险维度、判定依据 |
| 多平台人格模拟 | 模拟 B站/小红书/知乎/抖音 用户的正面/中性/负面反应及原因 |
| 安全改写建议 | 高风险句子的 2+ 种安全改写版本 |
| 视频文案提取 | 粘贴 B站/抖音链接，自动提取字幕/简介/标题进行分析 |
| 历史记录 | 追踪每次评估的风险分与建议，便于对比改进 |
| REST API | 完整的 API 接口，支持程序化调用 |

### V2（已实现）

| 模块 | 版本 | 核心功能 |
|------|------|----------|
| 增强风险分析 | R1 | 快速/深度双模式、风险上下文感知、实体风险链追踪 |
| 回测与一致性 | R2 | 历史案例回测、分析一致性校验、基准确立 |
| 趋势预测与报告 | R3 | 舆论趋势预测、模式分类、4类风控报告生成 |
| 多模态视频风控 | R4 | 关键帧提取+OCR、语音转录+情感分析、跨模态风险检测 |
| 信号采集+世界构建 | R5 | 热搜聚合、知识图谱、7层人格工厂、社交仿真引擎、传播动力学 |
| 博主服务 | R6 | 博主风格画像、选题推荐、竞品对标分析 |

### V2+（已实现）

- ✅ 1000+ Agent 大规模社交仿真（GA-S3 GroupAgent，等效10万+个体）
- ✅ 反事实仿真（删除/替换/软化/改写4种策略，前后对比）
- ✅ 长期记忆与社会演化（Memory Stream + Reflection + 人生故事驱动）
- ✅ 决策辅助（4级建议 + 修改优先级 + 风险预估）
- ✅ 博主服务（风格画像 + 选题推荐 + 竞品对标）
- ✅ 信号采集面板（热榜 + 事件检测 + 调度器控制）
- ✅ 知识图谱可视化（D3.js力导向图 + 实体查询 + 路径搜索）

### V3（部分完成）

| 子版本 | 内容 | 状态 |
|--------|------|------|
| V3.1 | 扩展平台覆盖至 28 个 | ✅ 已完成 |
| V3.2 | 本地模型部署（Ollama / vLLM 架构） | ✅ 已完成 |
| V3.3 | 多语言内容风控 | ⏸ 暂缓 |

---

## 🏗️ 系统架构

VibeUtopia 采用五层架构设计：

```
┌─────────────────────────────────────────────┐
│            分析决策层 (R3/R6/V2+)             │
│  趋势预测 · 报告生成 · 博主画像 · 竞品对标  │
│  决策辅助 · 反事实仿真 · 博主历史分析         │
├─────────────────────────────────────────────┤
│            仿真运行层 (R5/V2+)                 │
│  社交仿真引擎 · 传播动力学 · 极化分析         │
│  GA-S3 GroupAgent · 规模递进 · 批量分析        │
├─────────────────────────────────────────────┤
│            世界构建层 (R5/V2+)                 │
│  知识图谱 · 7层人格工厂 · 社会关系网络        │
│  人生故事A/B/C三级 · Memory Stream · Reflection│
├─────────────────────────────────────────────┤
│            信号采集层 (R5)                   │
│  热搜聚合 · 定向爬取 · 事件检测 · 定时调度  │
├─────────────────────────────────────────────┤
│            基础风控层 (MVP/R1/R2/R4)          │
│  十一维评估 · 人格模拟 · 回测 · 多模态视频    │
│  Paraformer音频转写 · 跨模态冲突检测           │
└─────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI + Uvicorn | 高性能异步 API |
| **数据验证** | Pydantic v2 | 请求/响应模型校验 |
| **ORM** | SQLAlchemy 2.0 | 数据库操作 |
| **数据库** | SQLite (MVP) / MySQL (V2) | 关系型存储 |
| **图数据库** | Neo4j 5 | 知识图谱 + 社会关系网络 |
| **向量数据库** | ChromaDB | Agent 记忆存储 (Memory Stream) |
| **LLM 接入** | httpx + LiteLLM | 支持 DeepSeek / 阿里云百炼 / 智谱 / 硅基流动 / LongCat / Ollama / vLLM 等多模型路由 |
| **前端框架** | Vue 3 + TypeScript | 组合式 API |
| **UI 组件** | Naive UI | 暗色主题组件库 |
| **可视化** | ECharts + D3.js | 图表 + 知识图谱可视化 |
| **CSS 方案** | Tailwind CSS 4 | 原子化样式 |
| **构建工具** | Vite 8 | 极速开发与构建 |
| **视频处理** | OpenCV + PySceneDetect + FFmpeg | 关键帧提取 + 场景检测 |
| **OCR** | Qwen3-VL-Plus / GLM-OCR API | 视频帧文字识别(API模式) |
| **语音转录** | faster-whisper / Paraformer API | 高效语音转文字（本地+云端双模式） |
| **容器化** | Docker Compose | Neo4j 等基础设施 |

---

## 🚀 快速启动

### 环境要求

- Python 3.10+（推荐通过 conda 管理环境）
- Node.js 18+（前端开发需要）
- 有效的 LLM API Key（支持 DeepSeek / 阿里云百炼 / 任意 OpenAI 兼容接口）

### 1. 克隆项目

```bash
git clone https://github.com/zsszhp/VibeUtopia.git
cd VibeUtopia
```

### 1.5 一键环境配置（推荐新机器使用）

```bash
bash setup.sh
```

脚本将自动完成：检查 Python、创建虚拟环境、安装依赖、检查 Docker、启动数据库、配置 .env。

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的 API Key 和接口地址
```

`.env` 文件内容示例：

```ini
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./data/vibeutopia.db
```

### 3. 安装后端依赖

```bash
conda create -n vibeutopia python=3.10
conda activate vibeutopia
pip install -r requirements.txt
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 5. 启动基础设施（可选，V2 知识图谱功能需要）

```bash
docker compose up -d neo4j
```

### 6. 启动应用

**方式一：分别启动（推荐开发时使用）**

```bash
# 终端1 - 启动后端
conda activate vibeutopia
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2 - 启动 Vue3 前端
cd frontend
npm run dev
```

**方式二：一键启动**

双击 `start.bat`，自动启动后端和前端。

### 7. 访问应用

| 入口 | 地址 |
|------|------|
| Vue3 前端 | http://localhost:3000 |
| 后端 API 文档 | http://localhost:8000/docs |
| Neo4j 浏览器 | http://localhost:7474 |

---

## 📡 API 文档

启动后端后访问 http://localhost:8000/docs 查看完整的交互式 API 文档。

### 核心端点一览

<details>
<summary><b>基础风控层 (MVP / R1 / R2)</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/analyze` | 文案风险分析 |
| `GET` | `/api/v1/analyze/{task_id}` | 获取分析结果 |
| `POST` | `/api/v1/analyze-video` | 视频文案提取+分析 |
| `POST` | `/api/v1/extract-video` | 仅提取视频文案 |
| `POST` | `/api/v1/analyze/v2` | V2 增强分析（快速/深度模式） |
| `GET` | `/api/v1/analyze/v2/{task_id}` | 获取 V2 分析结果 |
| `GET` | `/api/v1/risk/context` | 获取当前风险上下文（72h） |
| `GET` | `/api/v1/entities/{name}/risk-chain` | 实体风险链追踪 |
| `POST` | `/api/v1/backtest/run` | 运行回测 |
| `GET` | `/api/v1/backtest/results` | 获取回测结果 |
| `POST` | `/api/v1/consistency/check` | 一致性校验 |
| `GET` | `/api/v1/consistency/results` | 获取一致性结果 |

</details>

<details>
<summary><b>多模态视频风控 (R4)</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/analyze-video/v2` | 多模态视频风险分析 |
| `POST` | `/api/v1/analyze-frames` | 关键帧提取 + OCR + 风险评估 |
| `GET` | `/api/v1/frames/{task_id}` | 获取帧分析结果 |
| `POST` | `/api/v1/audio/transcribe` | 语音转录 + 情感分析 |
| `GET` | `/api/v1/cross-modal/{task_id}` | 跨模态风险检测结果 |

</details>

<details>
<summary><b>信号采集 + 知识图谱 (R5)</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/signals/hot` | 获取平台热搜 |
| `GET` | `/api/v1/signals/events` | 获取种子事件列表 |
| `POST` | `/api/v1/signals/crawl` | 触发深度爬取 |
| `POST` | `/api/v1/signals/scheduler` | 调度器控制 |
| `GET` | `/api/v1/graph/ontology` | 获取图本体定义 |
| `POST` | `/api/v1/graph/ontology/generate` | 动态生成本体 |
| `POST` | `/api/v1/graph/extract` | 提取实体/关系到图 |
| `POST` | `/api/v1/graph/query` | 查询子图 |
| `GET` | `/api/v1/graph/stats` | 图谱统计 |

</details>

<details>
<summary><b>人格工厂 + 仿真引擎 (R5)</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/agents/generate` | 批量生成 Agent |
| `GET` | `/api/v1/agents` | 列出 Agent |
| `GET` | `/api/v1/agents/{agent_id}` | Agent 详情 |
| `GET` | `/api/v1/agents/{agent_id}/relations` | Agent 社会关系 |
| `GET` | `/api/v1/agents/{agent_id}/memories` | Agent 记忆 |
| `POST` | `/api/v1/agents/network/generate` | 生成社会网络 |
| `POST` | `/api/v1/simulation/create` | 创建仿真任务 |
| `POST` | `/api/v1/simulation/{sim_id}/start` | 启动仿真 |
| `GET` | `/api/v1/simulation/{sim_id}/status` | 仿真状态 |
| `GET` | `/api/v1/simulation/{sim_id}/propagation` | 传播动力学 |
| `GET` | `/api/v1/simulation/{sim_id}/polarization` | 极化指数 |

</details>

<details>
<summary><b>趋势预测 + 报告 + 博主服务 (R3/R6)</b></summary>

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/prediction/trend` | 舆论趋势预测 |
| `POST` | `/api/v1/prediction/pattern` | 舆论模式分类 |
| `POST` | `/api/v1/report/risk` | 生成风控报告 |
| `POST` | `/api/v1/report/simulation` | 生成仿真报告 |
| `POST` | `/api/v1/report/trend` | 生成趋势报告 |
| `POST` | `/api/v1/report/decision` | 生成决策报告 |
| `POST` | `/api/v1/blogger/analyze` | 博主风格分析 |
| `GET` | `/api/v1/blogger/{id}/profile` | 博主画像 |
| `POST` | `/api/v1/blogger/recommend` | 选题推荐 |
| `POST` | `/api/v1/competitor/compare` | 竞品对标分析 |

</details>

### 调用示例

```bash
# 文案分析
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "你的文案内容..."}'

# V2 增强分析（深度模式）
curl -X POST http://localhost:8000/api/v1/analyze/v2 \
  -H "Content-Type: application/json" \
  -d '{"text": "你的文案内容...", "mode": "deep", "enable_simulation": true}'

# 生成 Agent
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -d '{"platforms": ["bilibili", "xiaohongshu"], "count_per_platform": 10}'
```

---

## ⚙️ 配置说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | LLM API Key | `sk-xxx` |
| `DEEPSEEK_BASE_URL` | API 接口地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 模型名称 | `deepseek-chat` |
| `DATABASE_URL` | 数据库连接 | `sqlite:///./data/vibeutopia.db` |
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | `your-password` |

---

## 📁 项目结构

```
VibeUtopia/
├── backend/                        # FastAPI 后端
│   ├── main.py                     # 应用入口 + 生命周期 + WebSocket
│   ├── config.py                   # 配置管理（读取 .env）
│   ├── database.py                 # 数据库连接
│   ├── models.py                   # 数据模型（V1 + V2 全量模型）
│   ├── routes.py                   # API 路由（5核心端点 + 71功能端点）
│   ├── prompts/                    # LLM 提示词模板
│   │   ├── risk_assessment.txt     # 十一维风险评估
│   │   ├── rewrite.txt             # 安全改写
│   │   ├── persona_bilibili.txt    # B站人格
│   │   ├── persona_xiaohongshu.txt # 小红书人格
│   │   ├── persona_zhihu.txt       # 知乎人格
│   │   ├── persona_douyin.txt      # 抖音人格
│   │   └── ...                     # V2 新增模板
│   └── services/                   # 业务逻辑层
│       ├── analyzer.py             # 核心分析编排
│       ├── llm_client.py           # LLM 调用 + JSON 解析
│       ├── persona_simulator.py    # 人格模拟
│       ├── risk_assessor.py        # 风险评估
│       ├── rewriter.py             # 安全改写
│       ├── video_extractor.py      # 视频文案提取
│       └── ...                     # V2 新增服务
├── frontend/                       # Vue3 + Naive UI 前端
│   ├── src/
│   │   ├── views/                  # 页面组件
│   │   ├── components/             # 通用组件
│   │   ├── stores/                 # Pinia 状态管理
│   │   ├── api/                    # API 调用封装
│   │   └── router/                 # 路由配置
│   └── package.json
├── docs/                           # 设计文档
│   └── guides/                     # 开发指南
├── tests/                          # 测试脚本与用例
├── data/                           # 运行时数据（本地生成，不上传git）
├── references/                     # 参考资源
│   ├── analysis/                   # 22个参考项目深度技术分析
│   ├── projects/                   # 开源项目源码（本地保留）
│   └── papers/                     # PDF论文（本地保留）
├── docker-compose.yml              # 基础设施编排
├── setup.sh                        # 一键环境配置脚本
├── .env.example                    # 环境变量模板
├── requirements.txt                # Python 依赖
├── LICENSE                         # AGPL-3.0
├── REFERENCE.md                    # 参考项目致谢
└── CONTRIBUTING.md                 # 贡献指南
```

---

## 🗺️ 开发路线图

| 阶段 | 版本 | 状态 | 核心交付 |
|------|------|------|----------|
| 基础风控 | MVP | ✅ 已完成 | 十一维评估 + 人格模拟 + 安全改写 + 视频提取 |
| 增强分析 | V2.R1 | ✅ 已完成 | 双模式分析 + 风险上下文 + 实体风险链 |
| 质量保障 | V2.R2 | ✅ 已完成 | 回测系统 + 一致性校验 |
| 趋势与报告 | V2.R3 | ✅ 已完成 | 趋势预测 + 4类报告生成 |
| 多模态视频 | V2.R4 | ✅ 已完成 | 关键帧+OCR+语音+跨模态 |
| 世界构建+仿真 | V2.R5 | ✅ 已完成 | 知识图谱+人格工厂+仿真引擎+传播动力学 |
| 博主服务 | V2.R6 | ✅ 已完成 | 博主画像+选题推荐+竞品对标 |
| 大规模仿真+决策 | V2+ | ✅ 已完成 | 1000+Agent+反事实仿真+决策辅助+社会演化 |
| 更多平台+本地模型 | V3.1-V3.2 | ✅ 已完成 | 28平台 + Ollama/vLLM架构 |
| 多语言内容风控 | V3.3 | ⏸ 暂缓 | 多语言支持 |

---

## 🤝 参与贡献

我们欢迎任何形式的贡献！请阅读 [贡献指南](CONTRIBUTING.md) 了解如何：

- 报告 Bug 或提出功能建议
- 提交代码（Fork → 分支 → PR）
- 改进文档

---

## 🙏 致谢与参考

VibeUtopia 的架构设计受到了以下优秀开源项目的启发，详见 [致谢与参考](REFERENCE.md)：

- [MiroFish](https://github.com/666ghj/MiroFish) — 知识图谱驱动世界构建
- [BettaFish](https://github.com/666ghj/BettaFish) — 多Agent协作机制
- [TrendRadar](https://github.com/sansan0/TrendRadar) — 多平台热搜聚合
- [DeepSearchAgent-Demo](https://github.com/666ghj/DeepSearchAgent-Demo) — 迭代搜索策略
- [ex-skill](https://github.com/perkfly/ex-skill) — 多层人格结构
- [VideoRAG](https://github.com/HKUDS/VideoRAG) — 视频大模型检索增强生成
- [VideoRAG](https://github.com/HKUDS/VideoRAG) — 视频大模型检索增强生成

---

## 📄 开源许可

本项目基于 [GNU Affero General Public License v3.0](LICENSE) 许可证开源。

这意味着你可以自由使用、修改和分发本项目，但修改后的版本也必须以相同许可证开源，包括通过网络提供服务的情况（AGPL-3.0 的网络使用条款）。
