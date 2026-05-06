# 🛡 VibeUtopia - 发布前内容风控评估平台

在发布文案、视频脚本前，模拟多平台真实用户反应，预测舆论风险，避免翻车。

## ✨ 功能特性

- **七维风险评估**：从政治敏感、性别议题、民族宗教、道德伦理、法律合规、群体冒犯、时事踩雷七个维度评估内容风险
- **句子级定位**：精确标注哪个句子存在风险、属于哪类风险及其严重程度
- **多平台人格模拟**：模拟 B站、小红书、知乎、抖音 四大平台用户的真实反应与情绪分布
- **安全改写建议**：对高风险句子提供至少2种保留原意的安全改写版本
- **历史记录**：追踪每次评估的风险分与建议，便于对比改进

## 🚀 快速启动

### 前置条件

- Python 3.10+（推荐通过 [conda](https://docs.conda.io/) 管理环境）
- 有效的 LLM API Key（支持 DeepSeek / 阿里云百炼 等兼容 OpenAI 格式的接口）

### 1. 配置环境变量

```bash
# 复制配置模板
copy .env.example .env

# 编辑 .env，填入你的 API Key
```

### 2. 安装依赖

```bash
conda activate py310   # 激活你的 Python 环境
pip install -r requirements.txt
```

### 3. 一键启动

```bash
start.bat
```

启动后访问：
- 前端界面：http://localhost:8501
- 后端 API 文档：http://localhost:8000/docs

## 📁 项目结构

```
VibeUtopia/
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据库连接
│   ├── models.py           # 数据模型
│   ├── routes.py           # API 路由
│   ├── prompts/            # LLM 提示词模板
│   └── services/           # 业务逻辑层
│       ├── analyzer.py     # 核心分析编排
│       ├── llm_client.py   # LLM 调用封装
│       ├── persona_simulator.py  # 平台人格模拟
│       ├── risk_assessor.py      # 七维风险评估
│       ├── rewriter.py     # 安全改写生成
│       └── text_splitter.py      # 文本分句处理
├── frontend/
│   └── app.py              # Streamlit 前端
├── data/                   # 本地数据库（运行时生成，不上传）
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
└── start.bat               # Windows 一键启动脚本
```

## 🔧 环境变量说明

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | LLM API Key | `sk-xxx` |
| `DEEPSEEK_BASE_URL` | API 接口地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 使用的模型名称 | `deepseek-chat` |
| `DATABASE_URL` | 数据库连接（默认本地SQLite） | `sqlite:///./data/vibeutopia.db` |