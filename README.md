# VibeUtopia - 平行数字世界：发布前风控与舆论仿真平台

在发布文案、视频脚本前，模拟多平台真实用户反应，预测舆论风险，避免翻车。V2阶段将构建高保真平行数字世界，让千级Agent自由交互与社会演化，实现预测未来走向、辅助决策。

## 功能特性

### MVP（已实现）
- **七维风险评估**：从政治敏感、性别议题、民族宗教、道德伦理、法律合规、群体冒犯、时事踩雷七个维度评估内容风险
- **句子级定位**：精确标注哪个句子存在风险、属于哪类风险及其严重程度
- **多平台人格模拟**：模拟 B站、小红书、知乎、抖音 四大平台用户的真实反应与情绪分布
- **安全改写建议**：对高风险句子提供至少2种保留原意的安全改写版本
- **视频文案提取**：粘贴B站/抖音等视频链接，自动提取字幕或简介进行分析
- **历史记录**：追踪每次评估的风险分与建议，便于对比改进

### V2（规划中，详见 [docs/04_V2深化路线图.md](docs/04_V2深化路线图.md)）
- **信号采集**：11+平台热搜聚合 + 定向评论爬取 + 事件检测
- **世界构建**：Neo4j知识图谱 + 7层人格工厂 + 社会关系网络 + 长期记忆
- **社交仿真**：1000+Agent在5个平台(微博/B站/小红书/知乎/抖音)上自由交互
- **预测决策**：趋势预测 + 反事实仿真 + 决策辅助
- **博主服务**：博主风格画像 + 选题推荐 + 竞品对标

## 快速启动

### 前置条件

- Python 3.10+（推荐通过 conda 管理环境）
- 有效的 LLM API Key（支持 DeepSeek / 阿里云百炼 / LongCat 等兼容 OpenAI 格式的接口）

### 1. 配置环境变量

```bash
# 复制配置模板
copy .env.example .env

# 编辑 .env，填入你的 API Key 和接口地址
```

`.env` 文件内容示例：
```
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

### 2. 安装依赖

```bash
conda activate py310   # 激活你的 Python 环境
pip install -r requirements.txt
```

### 3. 启动应用

打开两个终端（都先执行 `conda activate py310`），分别运行：

```bash
# 终端1 - 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2 - 启动前端
streamlit run frontend/app.py --server.port 8501
```

或者直接双击 `start.bat` 一键启动。

启动后访问：
- 前端界面：http://localhost:8501
- 后端 API 文档：http://localhost:8000/docs

## 使用方法

### 方式一：文案分析

1. 打开 http://localhost:8501
2. 在 **"文案输入"** 标签页，粘贴你的文案/脚本内容（至少10个字符）
3. 点击 **"开始评估"**
4. 等待约30-60秒，查看评估报告

### 方式二：视频分析

1. 打开 http://localhost:8501
2. 切换到 **"视频链接"** 标签页
3. 粘贴B站/抖音等视频链接（如 `https://www.bilibili.com/video/BV1xxxxxx`）
4. 先点 **"提取文案"** 查看提取到的内容（字幕 > 简介 > 标题）
5. 确认内容后，点 **"提取并评估"** 进行风控分析

### 查看评估报告

分析完成后，报告包含以下内容：

| 模块 | 说明 |
|------|------|
| 总分与建议 | 0-100分，对应"可发/建议修改/不建议发" |
| 七维风险评估 | 每个维度0-100分，红色=高风险，橙色=中风险，绿色=低风险 |
| 平台情绪预测 | B站/小红书/知乎/抖音的正面/中性/负面比例及原因 |
| 风险句子定位 | 具体哪个句子有问题、属于什么维度、判定依据 |
| 安全改写建议 | 高风险句子的2种安全改写版本 |

### 查看历史记录

左侧边栏展示最近10条评估记录，点击可查看详细报告。

### 直接调用 API

除了前端界面，也可以直接调用 REST API：

```bash
# 提交文案分析
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "你的文案内容..."}'

# 查询分析结果（返回中的 task_id）
curl http://localhost:8000/api/v1/analyze/{task_id}

# 提取视频文案
curl -X POST http://localhost:8000/api/v1/extract-video \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1xxxxxx"}'

# 提取视频文案并直接分析
curl -X POST http://localhost:8000/api/v1/analyze-video \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1xxxxxx"}'

# 查看历史记录
curl http://localhost:8000/api/v1/history
```

## 项目结构

```
VibeUtopia/
├── backend/                    # FastAPI 后端
│   ├── main.py                 # 应用入口
│   ├── config.py               # 配置管理（读取 .env）
│   ├── database.py             # 数据库连接（SQLite）
│   ├── models.py               # 数据模型
│   ├── routes.py               # API 路由
│   ├── prompts/                # LLM 提示词模板
│   │   ├── persona_bilibili.txt
│   │   ├── persona_xiaohongshu.txt
│   │   ├── persona_zhihu.txt
│   │   ├── persona_douyin.txt
│   │   ├── risk_assessment.txt
│   │   └── rewrite.txt
│   └── services/               # 业务逻辑层
│       ├── analyzer.py         # 核心分析编排
│       ├── llm_client.py       # LLM 调用封装 + JSON解析
│       ├── persona_simulator.py  # 平台人格模拟
│       ├── risk_assessor.py    # 七维风险评估
│       ├── rewriter.py         # 安全改写生成
│       ├── text_splitter.py    # 文本分句处理
│       └── video_extractor.py  # 视频文案提取（yt-dlp）
├── frontend/
│   └── app.py                  # Streamlit 前端
├── test/
│   └── paperwork/              # 测试文案与报告
├── .env.example                # 环境变量模板
├── requirements.txt            # Python 依赖
└── start.bat                   # Windows 一键启动脚本
```

## 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | LLM API Key | `sk-xxx` |
| `DEEPSEEK_BASE_URL` | API 接口地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 使用的模型名称 | `deepseek-chat` |
| `DATABASE_URL` | 数据库连接（默认本地SQLite） | `sqlite:///./data/vibeutopia.db` |

## 文档导航

| 文档 | 说明 |
|------|------|
| [docs/01_产品需求文档(PRD).md](docs/01_产品需求文档(PRD).md) | 产品愿景、用户画像、功能需求、演进策略 |
| [docs/02_系统架构设计.md](docs/02_系统架构设计.md) | 五层系统架构、技术选型、API设计、数据模型 |
| [docs/03_MVP实施计划(Tasks).md](docs/03_MVP实施计划(Tasks).md) | MVP阶段实施任务（已完成） |
| [docs/04_V2深化路线图.md](docs/04_V2深化路线图.md) | V2九阶段实施计划与验收标准 |
| [docs/05_参考项目分析与精华提炼.md](docs/05_参考项目分析与精华提炼.md) | TrendRadar/BettaFish/MiroFish等5个参考项目深度剖析 |
| [docs/06_信号采集层设计.md](docs/06_信号采集层设计.md) | 三层信号采集体系、种子事件库、定时调度 |
| [docs/07_世界构建层设计.md](docs/07_世界构建层设计.md) | Neo4j知识图谱、7层人格工厂、社会关系网络、记忆系统 |
| [docs/08_仿真运行层设计.md](docs/08_仿真运行层设计.md) | 三层Agent架构、5平台仿真、消息总线、性能优化 |
| [docs/09_分析决策层设计.md](docs/09_分析决策层设计.md) | 趋势预测、反事实仿真、报告生成引擎 |
