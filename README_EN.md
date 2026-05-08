# VibeUtopia - Parallel Digital World: Pre-publication Risk Control & Public Opinion Simulation Platform

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)

English | [中文](README.md)

> Simulate real user reactions across multiple Chinese social media platforms before publishing content, predict public opinion risks, and avoid "cancel culture" incidents. V2 builds a high-fidelity parallel digital world where thousands of Agents interact freely and evolve socially, enabling future trend prediction and decision support.

---

## ✨ Key Highlights

- 🛡️ **7-Dimension Risk Assessment** — Political sensitivity, gender issues, ethnic/religious, moral/ethical, legal compliance, group offense, current events
- 🎯 **Sentence-Level Precision** — Pinpoint exactly which sentence carries risk, its category, and severity
- 👥 **Multi-Platform Persona Simulation** — Realistic user reactions and sentiment distribution on Bilibili/Xiaohongshu/Zhihu/Douyin
- ✍️ **Safe Rewrite Suggestions** — At least 2 safe rewrite alternatives preserving original meaning
- 🎬 **Multi-Modal Video Risk Control** — Keyframe extraction + OCR + audio transcription + cross-modal risk detection
- 🌐 **1000+ Agent Social Simulation** — Knowledge graph + 7-layer persona factory + social network + propagation dynamics

---

## 📋 Features

### MVP (Implemented)

| Feature | Description |
|---------|-------------|
| 7-Dimension Risk Assessment | Independent scoring across 7 dimensions + overall score with "Safe / Revise / Don't Publish" verdict |
| Sentence-Level Localization | Precise identification of risky sentences, risk category, and reasoning |
| Multi-Platform Persona Simulation | Simulated positive/neutral/negative reactions from Bilibili/Xiaohongshu/Zhihu/Douyin users |
| Safe Rewrite Suggestions | 2+ safe rewrite alternatives for high-risk sentences |
| Video Transcript Extraction | Paste Bilibili/Douyin links to auto-extract subtitles/descriptions/titles for analysis |
| History Tracking | Track risk scores and suggestions across evaluations for comparison |
| REST API | Complete API endpoints for programmatic access |

### V2 (Implemented)

| Module | Version | Core Features |
|--------|---------|---------------|
| Enhanced Risk Analysis | R1 | Quick/deep dual mode, risk context awareness, entity risk chain tracing |
| Backtest & Consistency | R2 | Historical case backtesting, analysis consistency verification, baseline establishment |
| Trend Prediction & Reports | R3 | Public opinion trend prediction, pattern classification, 4 types of risk control reports |
| Multi-Modal Video Risk Control | R4 | Keyframe extraction + OCR, audio transcription + sentiment analysis, cross-modal risk detection |
| Signal Acquisition + World Building | R5 | Hot search aggregation, knowledge graph, 7-layer persona factory, social simulation engine, propagation dynamics |
| Blogger Services | R6 | Blogger style profiling, topic recommendation, competitor benchmarking |

### V2+ (Planned)

- 1000+ Agent large-scale social simulation
- Counterfactual simulation ("what if" analysis)
- Long-term memory and social evolution
- Additional platform support (Weibo, Twitter, etc.)

---

## 🏗️ System Architecture

VibeUtopia employs a five-layer architecture:

```
┌─────────────────────────────────────────────────┐
│         Analysis & Decision Layer (R3/R6)       │
│  Trend Prediction · Report Gen · Blogger · Comp │
├─────────────────────────────────────────────────┤
│           Simulation Layer (R5)                  │
│  Social Sim Engine · Propagation · Polarization │
├─────────────────────────────────────────────────┤
│           World Building Layer (R5)              │
│  Knowledge Graph · Persona Factory · Social Net │
├─────────────────────────────────────────────────┤
│           Signal Collection Layer (R5)           │
│  Hot Aggregation · Crawling · Event Detection   │
├─────────────────────────────────────────────────┤
│         Basic Risk Control Layer (MVP/R1/R2/R4) │
│  7-Dim Assessment · Persona Sim · Backtest · MM │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Description |
|-------|-----------|-------------|
| **Backend Framework** | FastAPI + Uvicorn | High-performance async API |
| **Data Validation** | Pydantic v2 | Request/response model validation |
| **ORM** | SQLAlchemy 2.0 | Database operations |
| **Database** | SQLite (MVP) / MySQL (V2) | Relational storage |
| **Graph Database** | Neo4j 5 | Knowledge graph + social network |
| **LLM Integration** | httpx + OpenAI-compatible protocol | Supports DeepSeek / Alibaba Cloud / any compatible API |
| **Frontend Framework** | Vue 3 + TypeScript | Composition API |
| **UI Components** | Element Plus | Enterprise component library |
| **Visualization** | ECharts + D3.js | Charts + knowledge graph visualization |
| **CSS** | Tailwind CSS 4 | Atomic styling |
| **Build Tool** | Vite 8 | Fast dev & build |
| **Video Processing** | OpenCV + PySceneDetect + FFmpeg | Keyframe extraction + scene detection |
| **OCR** | PaddleOCR + EasyOCR | Text recognition in video frames |
| **Audio Transcription** | faster-whisper | Efficient speech-to-text |
| **Containerization** | Docker Compose | Neo4j and other infrastructure |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ (conda recommended)
- Node.js 18+ (for frontend development)
- A valid LLM API Key (DeepSeek / Alibaba Cloud / any OpenAI-compatible API)

### 1. Clone the Repository

```bash
git clone https://github.com/zsszhp/VibeUtopia.git
cd VibeUtopia
```

### 2. Configure Environment Variables

```bash
# Copy the config template
cp .env.example .env

# Edit .env with your API Key and endpoint
```

Example `.env` file:

```ini
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DATABASE_URL=sqlite:///./data/vibeutopia.db
```

### 3. Install Backend Dependencies

```bash
conda create -n vibeutopia python=3.10
conda activate vibeutopia
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend-vue
npm install
cd ..
```

### 5. Start Infrastructure (Optional, needed for V2 knowledge graph features)

```bash
docker compose up -d neo4j
```

### 6. Start the Application

**Option A: Separate startup (recommended for development)**

```bash
# Terminal 1 - Backend
conda activate vibeutopia
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Vue3 Frontend
cd frontend-vue
npm run dev
```

**Option B: One-click startup (MVP with Streamlit frontend)**

Double-click `start.bat`, or start manually:

```bash
# Terminal 1 - Backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Streamlit Frontend (MVP)
streamlit run frontend/app.py --server.port 8501
```

### 7. Access the Application

| Entry Point | URL |
|-------------|-----|
| Vue3 Frontend | http://localhost:5173 |
| Streamlit Frontend (MVP) | http://localhost:8501 |
| Backend API Docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

---

## 📡 API Documentation

After starting the backend, visit http://localhost:8000/docs for the full interactive API documentation.

### Core Endpoints Overview

<details>
<summary><b>Basic Risk Control Layer (MVP / R1 / R2)</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyze` | Text risk analysis |
| `GET` | `/api/v1/analyze/{task_id}` | Get analysis result |
| `POST` | `/api/v1/analyze-video` | Video extraction + analysis |
| `POST` | `/api/v1/extract-video` | Extract video transcript only |
| `POST` | `/api/v1/analyze/v2` | V2 enhanced analysis (quick/deep mode) |
| `GET` | `/api/v1/analyze/v2/{task_id}` | Get V2 analysis result |
| `GET` | `/api/v1/risk/context` | Get current risk context (72h) |
| `GET` | `/api/v1/entities/{name}/risk-chain` | Entity risk chain tracing |
| `POST` | `/api/v1/backtest/run` | Run backtest |
| `GET` | `/api/v1/backtest/results` | Get backtest results |
| `POST` | `/api/v1/consistency/check` | Consistency check |
| `GET` | `/api/v1/consistency/results` | Get consistency results |

</details>

<details>
<summary><b>Multi-Modal Video Risk Control (R4)</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyze-video/v2` | Multi-modal video risk analysis |
| `POST` | `/api/v1/analyze-frames` | Keyframe extraction + OCR + risk assessment |
| `GET` | `/api/v1/frames/{task_id}` | Get frame analysis results |
| `POST` | `/api/v1/audio/transcribe` | Audio transcription + sentiment analysis |
| `GET` | `/api/v1/cross-modal/{task_id}` | Cross-modal risk detection results |

</details>

<details>
<summary><b>Signal Collection + Knowledge Graph (R5)</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/signals/hot` | Get platform hot search data |
| `GET` | `/api/v1/signals/events` | Get seed events list |
| `POST` | `/api/v1/signals/crawl` | Trigger deep crawl |
| `POST` | `/api/v1/signals/scheduler` | Scheduler control |
| `GET` | `/api/v1/graph/ontology` | Get graph ontology definition |
| `POST` | `/api/v1/graph/ontology/generate` | Dynamically generate ontology |
| `POST` | `/api/v1/graph/extract` | Extract entities/relations to graph |
| `POST` | `/api/v1/graph/query` | Query subgraph |
| `GET` | `/api/v1/graph/stats` | Graph statistics |

</details>

<details>
<summary><b>Persona Factory + Simulation Engine (R5)</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/agents/generate` | Batch generate Agents |
| `GET` | `/api/v1/agents` | List Agents |
| `GET` | `/api/v1/agents/{agent_id}` | Agent details |
| `GET` | `/api/v1/agents/{agent_id}/relations` | Agent social relations |
| `GET` | `/api/v1/agents/{agent_id}/memories` | Agent memories |
| `POST` | `/api/v1/agents/network/generate` | Generate social network |
| `POST` | `/api/v1/simulation/create` | Create simulation task |
| `POST` | `/api/v1/simulation/{sim_id}/start` | Start simulation |
| `GET` | `/api/v1/simulation/{sim_id}/status` | Simulation status |
| `GET` | `/api/v1/simulation/{sim_id}/propagation` | Propagation dynamics |
| `GET` | `/api/v1/simulation/{sim_id}/polarization` | Polarization index |

</details>

<details>
<summary><b>Trend Prediction + Reports + Blogger Services (R3/R6)</b></summary>

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/prediction/trend` | Opinion trend prediction |
| `POST` | `/api/v1/prediction/pattern` | Opinion pattern classification |
| `POST` | `/api/v1/report/risk` | Generate risk control report |
| `POST` | `/api/v1/report/simulation` | Generate simulation report |
| `POST` | `/api/v1/report/trend` | Generate trend report |
| `POST` | `/api/v1/report/decision` | Generate decision report |
| `POST` | `/api/v1/blogger/analyze` | Blogger style analysis |
| `GET` | `/api/v1/blogger/{id}/profile` | Blogger profile |
| `POST` | `/api/v1/blogger/recommend` | Topic recommendation |
| `POST` | `/api/v1/competitor/compare` | Competitor benchmarking |

</details>

### Usage Examples

```bash
# Text analysis
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Your content here..."}'

# V2 enhanced analysis (deep mode)
curl -X POST http://localhost:8000/api/v1/analyze/v2 \
  -H "Content-Type: application/json" \
  -d '{"text": "Your content here...", "mode": "deep", "enable_simulation": true}'

# Generate Agents
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -d '{"platforms": ["bilibili", "xiaohongshu"], "count_per_platform": 10}'
```

---

## ⚙️ Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | LLM API Key | `sk-xxx` |
| `DEEPSEEK_BASE_URL` | API endpoint URL | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | Model name | `deepseek-chat` |
| `DATABASE_URL` | Database connection | `sqlite:///./data/vibeutopia.db` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `your-password` |

---

## 📁 Project Structure

```
VibeUtopia/
├── backend/                        # FastAPI Backend
│   ├── main.py                     # App entry + lifecycle + WebSocket
│   ├── config.py                   # Configuration (reads .env)
│   ├── database.py                 # Database connection
│   ├── models.py                   # Data models (V1 + V2)
│   ├── routes.py                   # API routes (41+ endpoints)
│   ├── prompts/                    # LLM prompt templates
│   │   ├── risk_assessment.txt     # 7-dimension risk assessment
│   │   ├── rewrite.txt             # Safe rewrite
│   │   ├── persona_bilibili.txt    # Bilibili persona
│   │   ├── persona_xiaohongshu.txt # Xiaohongshu persona
│   │   ├── persona_zhihu.txt       # Zhihu persona
│   │   ├── persona_douyin.txt      # Douyin persona
│   │   └── ...                     # V2 additional templates
│   └── services/                   # Business logic layer
│       ├── analyzer.py             # Core analysis orchestration
│       ├── llm_client.py           # LLM calls + JSON parsing
│       ├── persona_simulator.py    # Persona simulation
│       ├── risk_assessor.py        # Risk assessment
│       ├── rewriter.py             # Safe rewriting
│       ├── video_extractor.py      # Video transcript extraction
│       └── ...                     # V2 additional services
├── frontend/                       # Streamlit Frontend (MVP)
│   └── app.py
├── frontend-vue/                   # Vue3 Frontend (V2)
│   ├── src/
│   │   ├── views/                  # Page components
│   │   ├── components/             # Shared components
│   │   ├── stores/                 # Pinia state management
│   │   ├── api/                    # API call wrappers
│   │   └── router/                 # Route configuration
│   └── package.json
├── docs/                           # Design documents
├── test/                           # Test scripts & cases
├── cases/                          # Test case library
├── docker-compose.yml              # Infrastructure orchestration
├── .env.example                    # Environment variable template
├── requirements.txt                # Python dependencies
├── LICENSE                         # AGPL-3.0
├── REFERENCE.md                    # Acknowledgments & references
└── CONTRIBUTING.md                 # Contributing guide
```

---

## 🗺️ Roadmap

| Phase | Version | Status | Key Deliverables |
|-------|---------|--------|-----------------|
| Basic Risk Control | MVP | ✅ Done | 7-dim assessment + persona sim + safe rewrite + video extraction |
| Enhanced Analysis | V2.R1 | ✅ Done | Dual-mode analysis + risk context + entity risk chain |
| Quality Assurance | V2.R2 | ✅ Done | Backtest system + consistency verification |
| Trends & Reports | V2.R3 | ✅ Done | Trend prediction + 4 report types |
| Multi-Modal Video | V2.R4 | ✅ Done | Keyframe + OCR + audio + cross-modal |
| World Building + Simulation | V2.R5 | ✅ Done | Knowledge graph + persona factory + simulation engine + propagation |
| Blogger Services | V2.R6 | ✅ Done | Blogger profiling + topic recommendation + competitor analysis |
| Large-Scale Simulation | V2+ | 🔜 Planned | 1000+ Agents + counterfactual sim + social evolution |

---

## 🤝 Contributing

We welcome contributions of all kinds! Please read the [Contributing Guide](CONTRIBUTING.md) to learn how to:

- Report bugs or suggest features
- Submit code (Fork → Branch → PR)
- Improve documentation

---

## 🙏 Acknowledgments

VibeUtopia's architecture was inspired by these excellent open-source projects. See [Acknowledgments & References](REFERENCE.md) for details:

- [MiroFish](https://github.com/666ghj/MiroFish) — Knowledge graph-driven world building
- [BettaFish](https://github.com/666ghj/BettaFish) — Multi-Agent collaboration mechanism
- [TrendRadar](https://github.com/sansan0/TrendRadar) — Multi-platform hot search aggregation
- [DeepSearchAgent-Demo](https://github.com/666ghj/DeepSearchAgent-Demo) — Iterative search strategy
- [ex-skill](https://github.com/perkfly/ex-skill) — Multi-layer persona structure

---

## 📄 License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

This means you are free to use, modify, and distribute this project, but any modified versions must also be open-sourced under the same license, including when providing the software as a network service (AGPL-3.0's network use clause).
