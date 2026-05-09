# VibeUtopia 蓝图修正 —— 回归核心目标

## 0. 使用说明（先读）

> 本文件是 `docs/` 目录重构的总指挥文档。
> 你后续修改 `docs` 里的 PRD、架构、路线图、分层设计时，以本文件为唯一执行依据。

### 0.1 本文件输出什么
- 给出目标：发前风控优先、准确率优先、仿真为增强。
- 给出动作：每个 `docs/*.md` 是保留、改写、融合还是后置。
- 给出顺序：先改哪些文档，后改哪些文档。
- 给出验收：怎么判断某个文档“改完且合格”。

### 0.2 执行规则（强约束）
- 规则1：任何新增内容必须回答“是否提升风控准确率”。
- 规则2：仿真只能作为增强模块，不能变成独立产品主线。
- 规则3：阶段1-3不新增与主线弱相关的用户入口。
- 规则4：若某项能力难以量化准确率收益，降级为“后置能力”。

## 一、问题诊断：偏离度分析

### 原始目标（来自 docs/原始需求.md）
> 博主发布视频/文案前，模拟多平台用户反应，预测舆论风险，避免翻车。

### 当前偏离
| 维度 | 原始需求 | 当前实现 | 偏离度 |
|------|---------|---------|--------|
| 用户入口 | 1个：上传视频/粘贴文案 | 7个Tab + 7个Vue页面 | 严重 |
| 核心流程 | 内容→风险报告 | 多入口多流程混合 | 严重 |
| 基础设施 | LLM API即可 | Neo4j+MySQL+Redis+Milvus+PaddlePaddle | 过度 |
| 后端服务 | ~5个核心服务 | 38+服务模块 | 过度 |
| 平台覆盖 | 全平台 | 仅5个(B站/抖音/小红书/知乎/微博)且微博人格未补全 | 严重不足 |
| 博主服务 | 明确标注"以后再说" | 已实现(V2.R6) | 偏离 |
| 视觉模型 | API即可 | 混合本地PaddlePaddle+API | 可简化 |

## 二、修正方案：单入口 + 灵活输入 + 全平台覆盖

### 2.1 唯一用户入口
**"内容预审"** —— 一个页面，一个流程：

```
┌─────────────────────────────────────────────────────┐
│                   内容预审工作台                       │
├─────────────────────────────────────────────────────┤
│  输入区（三种模式，用户自由选择）：                      │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ 📹 视频文件（拖拽/选择，支持多个）              │  │
│  │    本地视频上传，后台自动：                      │  │
│  │    → 关键帧提取 → 画面理解 → OCR → 音频转写    │  │
│  │    → 提取文案/脚本（从视频内容自动生成）         │  │
│  ├───────────────────────────────────────────────┤  │
│  │ 📝 文案/脚本（文本框输入，支持多个）             │  │
│  │    直接粘贴文案、脚本、标题、描述等              │  │
│  ├───────────────────────────────────────────────┤  │
│  │ 📎 混合输入（视频+文案+脚本同时上传）           │  │
│  │    综合分析：视频画面 × 文案语义 × 脚本意图     │  │
│  │    跨模态交叉验证风险点                         │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  [开始预审]                                          │
├─────────────────────────────────────────────────────┤
│  分析过程（实时展示）：                                │
│  ┌─ Step1: 视频理解（如上传了视频）───────────────┐  │
│  │ 关键帧提取 → 画面内容识别 → 文字OCR → 音频转写 │  │
│  │ → 从视频自动提取/生成文案脚本                   │  │
│  └────────────────────────────────────────────────┘  │
│  ┌─ Step2: 文案理解（如输入了文案或从视频提取）────┐  │
│  │ 语义分析 → 情感倾向 → 敏感词/隐喻/双关识别      │  │
│  └────────────────────────────────────────────────┘  │
│  ┌─ Step3: 舆论推演（全平台）─────────────────────┐  │
│  │ 每个平台模拟多种典型人格 → 推演反应和传播路径   │  │
│  │ → 标记高风险平台和高风险人群                    │  │
│  └────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│  输出：风险预审报告                                   │
│  ┌─ 总体风险评级 ─────────────────────────────────┐ │
│  │ 🔴 高风险 / 🟡 中风险 / 🟢 低风险              │ │
│  ├─ 各平台反应预测 ───────────────────────────────┤ │
│  │ B站: xxx  微博: xxx  小红书: xxx  知乎: xxx     │ │
│  │ 抖音: xxx 贴吧: xxx  NGA: xxx  虎扑: xxx       │ │
│  │ 豆瓣: xxx 快手: xxx  公众号: xxx ...           │ │
│  ├─ 风险点清单（按时间线/段落标记）──────────────┤ │
│  │ #1 00:12-00:18 某画面可能引发xxx争议            │ │
│  │ #2 第3段文案"xxx"可能被解读为xxx                │ │
│  │ #3 视频画面与文案表述不一致，可能引发xxx质疑    │ │
│  ├─ 传播推演 ───────────────────────────────────┤ │
│  │ 预计首发平台: xxx → 扩散路径: xxx → xxx        │ │
│  │ 可能的舆论转折点: xxx                           │ │
│  └─ 修改建议 ───────────────────────────────────┘ │
│    建议修改xxx画面/文案为xxx                         │
└─────────────────────────────────────────────────────┘
```

### 2.2 输入模式详细设计

| 模式 | 输入 | 后台处理 | 输出 |
|------|------|---------|------|
| **仅视频** | 1个或多个本地视频文件 | 关键帧提取→画面理解(多模态API)→OCR(API)→音频转写(API)→自动生成文案描述 | 视频风险报告 |
| **仅文案** | 文案/脚本/标题/描述 文本 | 文案语义分析→敏感检测→隐喻识别 | 文案风险报告 |
| **混合输入** | 视频+文案+脚本等 | 视频理解+文案理解+**跨模态交叉验证**(画面与文案是否矛盾、互补、冲突) | 综合风险报告 |

关键点：即使只上传视频，后台也会自动从视频提取/生成文案，然后用文案+画面双通道分析。

### 2.3 全平台覆盖

#### 平台清单（按优先级分层）

**P0 - 核心平台（必须覆盖，舆论影响力最大）**
| 平台 | 代号 | 用户规模 | 核心特征 | 典型风险 |
|------|------|---------|---------|---------|
| 微博 | weibo | 5.88亿月活 | 热搜驱动公共广场，情绪化，饭圈文化 | 性别对立、明星丑闻、政治敏感 |
| 哔哩哔哩 | bilibili | 3.68亿月活 | 弹幕文化，反商业，ACG核心，年轻用户 | 游戏争议、性别辩论、AI恐惧 |
| 抖音 | douyin | 10亿月活 | 算法驱动，情绪化，民粹倾向 | 消费维权、炫富、食品安全 |
| 小红书 | xiaohongshu | 3亿月活 | 种草文化，女性主导，消费决策 | 性别歧视、虚假种草、消费欺诈 |
| 知乎 | zhihu | 1亿月活 | 理性长文，专业人群，逻辑批判 | 伪科学揭穿、精英视角争议 |
| 百度贴吧 | tieba | 6亿月活 | 匿名论坛，亚文化，游戏社区 | 网暴、游戏争议、群体对立 |

**P1 - 重要平台（覆盖主要垂直领域）**
| 平台 | 代号 | 用户规模 | 核心特征 | 典型风险 |
|------|------|---------|---------|---------|
| 快手 | kuaishou | 7.31亿月活 | 老铁文化，下沉市场，草根内容 | 乡村低俗、直播骗局、短剧监管 |
| 微信公众号 | wechat_official | 触达12亿+ | 深度阅读，私域传播，中年用户 | 政治敏感、付费争议、KOL发声 |
| 豆瓣 | douban | 2亿月活 | 文艺青年，女性主导，社会议题 | 性别议题、MeToo、社会运动 |
| 虎扑 | hupu | 3-5千万月活 | 直男社区，体育+游戏，男性视角 | 性别对立(与小红书对立)、评分争议 |
| 今日头条 | toutiao | 4-5亿月活 | 算法新闻，下沉市场，民族主义 | 假新闻传播、情绪升级 |
| NGA玩家社区 | nga | 2-3千万月活 | 硬核游戏，数据驱动，部落主义 | 游戏公司公关危机、原神争议 |
| 视频号 | wechat_channels | 5.3亿月活 | 社交分享驱动，中老年用户 | 养生谣言、中老年诈骗 |

**P2 - 补充平台（垂直领域/特殊场景）**
| 平台 | 代号 | 用户规模 | 核心特征 | 典型风险 |
|------|------|---------|---------|---------|
| 小黑盒 | xiaoheihe | 1-1.5千万月活 | Steam玩家，游戏社区 | 游戏评价、CDKey争议 |
| TapTap | taptap | 4-4.5千万月活 | 手游评分，品质导向 | 评分操纵、游戏质量争议 |
| 米游社 | miyoushe | 3-5千万月活 | 米哈游粉丝，情感依恋 | 福利争议、角色设计争议 |
| 游民星空 | gamersky | 5-10百万月活 | 游戏新闻，攻略社区 | 版权争议、游戏新闻传播 |
| 澎湃新闻 | thepaper | 3-5千万月活 | 深度新闻，调查报道 | 调查报道引发的社会反应 |
| 观察者网 | guancha | 2-3千万月活 | 民族主义，工业党 | 民族主义情绪升级 |
| 虎嗅 | huxiu | 1-2千万月活 | 商业科技，企业高管 | 企业声誉、科技行业争议 |
| 36氪 | 36kr | 1-2千万月活 | 创投科技，投资者 | 公司治理、IPO丑闻 |
| Lofter | lofter | 3-5千万月活 | 同人创作，CP文化，女性主导 | 版权争议、AI艺术抵制 |
| 西瓜视频 | xigua | 1.2亿月活 | 中长视频，信息消费 | 内容分发但社区讨论少 |
| 即刻 | jike | 数百万 | 科技圈，产品经理 | 科技圈小众舆论 |
| 什么值得买 | smzdm | 3-5千万月活 | 消费决策，测评 | 消费欺诈、虚假测评 |

**当前实现 vs 目标**
| 层级 | 已实现 | 需新增 | 需补全 |
|------|--------|--------|--------|
| P0 | bilibili, douyin, xiaohongshu, zhihu(4/6) | weibo, tieba | weibo缺人格模板和prompt |
| P1 | 0/7 | 全部7个 | - |
| P2 | 0/12 | 全部12个 | - |
| **总计** | **4个(含weibo半成品)** | **需增至25+平台** | |

## 三、技术架构修正

### 3.1 多模态模型方案：API为主、本地为辅

#### API vs 本地：客观对比（不考虑隐私/安全/成本）

| 维度 | API | 本地部署 | 胜者 |
|------|-----|---------|------|
| **模型质量** | 可用235B+ MoE顶级模型 | 单卡最多32B，但新代际模型8B≈旧32B | API仍领先，但差距缩小 |
| **OCR能力** | 通用大模型OCR ~89，专用OCR模型可达94+ | 专用OCR模型0.9B参数本地轻松跑 | **本地专用OCR更强** |
| **速率限制** | 视觉API 5-10RPM，30帧视频要等3-6分钟 | 无限制，连续处理 | **本地碾压** |
| **批处理效率** | 受限速和队列影响 | GPU连续推理，无等待 | **本地碾压** |
| **运维成本** | 零运维 | CUDA/显存/量化/vLLM/驱动 | **API碾压** |
| **持续升级** | 厂商自动升级 | 需手动下载切换 | **API碾压** |
| **可微调** | 仅prompt engineering | 可LoRA微调（针对"中国舆论风险"垂直领域） | **本地碾压** |
| **离线可用** | 需网络 | 完全离线 | **本地碾压** |

**关键发现**：
1. **专用OCR模型（1B参数）在OCR上碾压所有通用大模型**：GLM-OCR(94.62) > PaddleOCR-VL-1.5(94.50) > Qwen3-VL-235B(89.15) > GPT-5.4(85.8)
2. **新代际模型效率暴增**：Qwen3-VL-8B已超越Qwen2.5-VL-32B，本地8B模型即可获得不错效果
3. **Kimi K2.6多模态能力平庸**，不适合视觉任务，它是代码/Agent模型
4. **本地部署的专用OCR模型极具性价比**：0.9B参数，1-2GB显存即可，OmniDocBench 94+

**结论：API在通用视觉理解上仍领先，但本地在OCR和速率限制上有明确优势。最佳策略是混合使用。**

#### 推荐策略：API视觉理解 + 本地专用OCR + 本地音频转写

```
视觉理解（画面内容识别、风险判断）：
  主力 → API（Qwen3-VL-Plus / Qwen3-VL-235B API，质量最强）
  降级 → 本地（Qwen3-VL-8B-Instruct，API限速时自动切换）

OCR（视频中文字识别）：
  主力 → 本地（GLM-OCR 或 PaddleOCR-VL-1.5，0.9B参数，精度94+，碾压所有大模型）
  备选 → API（Qwen3-VL-Plus内置OCR，需精度不如专用模型时）

音频转写：
  主力 → 本地GPU（faster-whisper large-v3，免费快速无限制）
  降级 → API（阿里Paraformer，无GPU时使用）

文本理解/人格模拟/风险评估：
  主力 → API（DeepSeek-V4-Flash / Qwen3.6-Plus，质量最强）
  降级 → 本地（Qwen3-32B / DeepSeek-V4-Flash量化，限速时降级）
```

---

#### 视觉理解（画面内容识别+风险判断）

**API模型（主力）**

| 优先级 | 模型 | 提供商 | 发布时间 | 核心能力 | 定价 | 推荐理由 |
|--------|------|--------|---------|---------|------|---------|
| ★★★ | **Qwen3-VL-Plus** | 阿里云百炼 | 2026.4 | 中文VL顶级，视频理解强 | ~$0.60/MTok+0.002/图 | 中文VL API性价比之王 |
| ★★★ | **GLM-5V-Turbo** | 智谱AI | 2026.4 | 原生多模态Agent，CogViT编码器 | 中等 | 视觉Agent能力最强，GUI理解顶级 |
| ★★☆ | **Qwen3-VL (qwen-vl-max)** | 阿里云百炼 | 2025.9 | 235B MoE，OCRBench强 | ~0.02元/千token | 成熟稳定，中文原生 |
| ★★☆ | **Gemini 3.1 Pro** | Google | 2026 | 1M上下文，原生多模态 | $2.00/$4.40每MTok | 视频理解卓越，国内需代理 |
| ★☆☆ | **GPT-5.4 Vision** | OpenAI | 2026.3 | 推理强，1.05M上下文 | $2.50/$15每MTok | 中文不如国产，国内需代理 |

**本地模型（降级通道/微调基座）**

| 优先级 | 模型 | 参数 | 发布时间 | 显存需求(INT4/AWQ) | 许可证 | 推荐理由 |
|--------|------|------|---------|-------------------|--------|---------|
| ★★★ | **Qwen3-VL-8B-Instruct** | 8B Dense | 2025.9 | ~8GB(INT4) | Apache 2.0 | **已超越Qwen2.5-VL-32B**，6GB显存可跑 |
| ★★★ | **Qwen3-VL-30B-A3B** | 30B MoE/3B激活 | 2025.9 | ~8GB(AWQ) | Apache 2.0 | MoE高效，3B激活参数，质量≈32B |
| ★★☆ | **Qwen3-VL-32B** | 32B Dense | 2025.9 | ~18GB(AWQ) | Apache 2.0 | 单卡4090最高配，质量接近API |
| ★★☆ | **GLM-4.1V-9B-Thinking** | 9B | 2025.8 | ~9GB(INT4) | Apache 2.0 | 超72B级Qwen2.5-VL，思维链推理 |
| ★★☆ | **InternVL3.5-8B** | 8B | 2025.8 | ~8GB(INT4) | MIT | 原生多模态，V2PE长上下文 |
| ★☆☆ | **Kimi-VL-A3B-Thinking** | 16B MoE/3B激活 | 2025.6 | ~8GB | MIT | OCR能力强，但综合不如Qwen3-VL |

**重要：Qwen2.5-VL系列已完全被Qwen3-VL超越，不应再作为首选。**

---

#### OCR（视频中文字识别）— 专用模型碾压通用大模型

2025末-2026初，专用OCR模型爆发，1B参数在OmniDocBench上达94+，全面超越百亿级通用大模型。

| 优先级 | 模型 | 参数 | OmniDocBench | 显存需求 | 许可证 | 推荐理由 |
|--------|------|------|-------------|---------|--------|---------|
| ★★★ | **GLM-OCR** | 0.9B | **94.62** | ~2GB | Apache 2.0 | 精度最高+速度最快，1-2GB显存 |
| ★★★ | **PaddleOCR-VL-1.5** | 0.9B | **94.50** | ~2GB | Apache 2.0 | 乱码/倾斜/多语言最鲁棒 |
| ★★☆ | **DeepSeek-OCR-2** | 3B | 91.09 | ~6GB | Apache 2.0 | 高压缩比，批量处理快 |
| ★★☆ | **HunyuanOCR** | ~1B | ~92 | ~2GB | Apache 2.0 | 腾讯出品，端到端架构，API封装简单 |
| ★☆☆ | **MinerU 2.5** | ~1B | 90.67 | ~2GB | AGPL-3.0 | 解耦分治架构，版面分析好 |

**关键结论：OCR应使用本地专用模型，不用API通用大模型。0.9B参数模型2GB显存即可运行，精度94+，比Qwen3-VL-235B的89.15高出5+点。**

---

#### 音频转写（语音→文字）

| 优先级 | 方案 | 类型 | 能力 | 速率限制 | 显存需求 | 推荐理由 |
|--------|------|------|------|---------|---------|---------|
| ★★★ | **faster-whisper large-v3** | 本地GPU | 中文ASR极强 | 无限制 | ~10GB | 免费快速无限制，实际比API更优 |
| ★★☆ | **阿里Paraformer API** | API | 中文ASR最强 | 有QPS限制 | 无 | 无GPU时的首选 |
| ★★☆ | **讯飞语音转写API** | API | 中文专精 | 有QPS限制 | 无 | 备选 |

**音频转写特殊：本地GPU反而是更优解**——faster-whisper large-v3在GPU上速度极快（10分钟视频1-2分钟转完），无速率限制，免费，中文质量接近API。

---

#### 文本理解/人格模拟/风险评估

**API（主力）**

| 优先级 | 模型 | 提供商 | 发布时间 | 定价 | 用途 |
|--------|------|--------|---------|------|------|
| ★★★ | **DeepSeek-V4-Pro** | DeepSeek | 2026.4 | 中等 | 深度推理（风险评估），1M上下文 |
| ★★★ | **DeepSeek-V4-Flash** | DeepSeek | 2026.4 | 低价 | 快速分析、批量人格模拟，284B/13B激活 |
| ★★★ | **Qwen3.6-Plus** | 阿里云 | 2026.4 | 中等 | 最新文本模型，综合最强 |
| ★★☆ | **GLM-5** | 智谱AI | 2026.1 | 中等 | Agent能力突出 |
| ★☆☆ | **MiniMax M2.7** | MiniMax | 2026.3 | 中等 | Agent协作能力强 |

**本地（降级/微调基座）**

| 优先级 | 模型 | 显存需求(AWQ/INT4) | 用途 |
|--------|------|-------------------|------|
| ★★★ | **Qwen3-32B** | ~18GB(AWQ) | API限速降级首选 |
| ★★☆ | **Qwen3.6-35B-A3B** | ~8GB(AWQ) | 低显存方案，MoE高效 |
| ★★☆ | **DeepSeek-V4-Flash量化** | ~80GB(FP8)/~40GB(INT4) | 需要多GPU |
| ★☆☆ | **MiniMax-M2.5量化** | ~80GB | 多Agent协作微调 |

---

#### 模型路由策略

```python
MODEL_ROUTING = {
    # 视觉理解 - API优先，本地降级
    "frame_understanding": {
        "primary": "qwen3-vl-plus",           # API: 中文VL性价比之王
        "fallback": "glm-5v-turbo",           # API: 视觉Agent最强
        "local_fallback": "qwen3-vl-8b",      # 本地: 已超Qwen2.5-VL-32B
    },
    # OCR - 本地专用模型优先（精度碾压通用大模型）
    "ocr": {
        "primary": "glm-ocr",                 # 本地: 94.62精度，0.9B参数
        "fallback": "paddleocr-vl-1.5",       # 本地: 94.50精度，乱码/多语言更鲁棒
        "api_fallback": "qwen3-vl-plus",      # API降级（精度仅89，远不如专用模型）
    },
    # 音频转写 - 本地优先（实际比API更优）
    "audio_transcription": {
        "primary": "faster-whisper-large-v3",  # 本地GPU（免费快速无限制）
        "fallback": "aliyun-paraformer",       # API（无GPU时）
    },
    # 风险评估 - API深度推理
    "risk_assessment": {
        "primary": "deepseek-v4-pro",          # API: 1.6T/49B激活，1M上下文
        "fallback": "qwen3.6-plus",           # API: 最新Qwen文本模型
        "local_fallback": "qwen3-32b",        # 本地降级
    },
    # 人格模拟
    "persona_simulation": {
        "primary": "deepseek-v4-flash",        # API: 284B/13B激活，快+便宜
        "fallback": "qwen3.6-plus",           # API备选
        "local_fallback": "qwen3-32b",        # 本地降级
    },
    # 文案分析
    "text_analysis": {
        "primary": "deepseek-v4-flash",        # API（快+便宜）
        "fallback": "qwen3-plus",             # API中档
    },
}
```

#### 本地部署的硬件需求

| 方案 | GPU | 可运行 | 显存 | 适用场景 |
|------|-----|--------|------|---------|
| 入门 | RTX 3060 12GB | GLM-OCR(0.9B) + Qwen3-VL-8B(INT4) + faster-whisper medium | 12GB | OCR+基础视觉+音频转写 |
| 推荐 | RTX 4090 24GB | GLM-OCR + Qwen3-VL-32B(AWQ) + faster-whisper large + Qwen3-32B(AWQ) | 24GB | 完整本地降级+微调 |
| 旗舰 | 2×A100 80GB | DeepSeek-V4-Flash(FP8) + 全部模型并行 | 160GB | 接近API质量的全本地方案 |

**操作系统**：纯API模式Windows完全够用；启用本地模型推理建议Ubuntu（vLLM仅支持Linux，但transformers/Ollama支持Windows）

### 3.3 后端架构修正

**保留的核心服务**
1. `analyzer.py` — 分析编排核心（需重构：串联为单流程）
2. `risk_assessor.py` — 风险评估
3. `persona_simulator.py` — 人格模拟（需扩展到25+平台）
4. `rewriter.py` — 安全改写建议
5. `keyframe_extractor.py` — 关键帧提取
6. `frame_risk.py` — 画面风险分析（改为API调用，移除本地PaddlePaddle依赖）
7. `frame_ocr.py` — 画面OCR（改为API调用，移除本地PaddleOCR依赖）
8. `audio_analyzer.py` — 音频转写（改为API优先）
9. `cross_modal_risk.py` — 跨模态风险
10. `llm_client.py` — LLM调用（需扩展：多模态API支持）
11. `simulation/engine.py` — 仿真引擎（简化为内部调用）
12. `simulation/platforms/` — 平台模拟器（需从5个扩展到25+个）
13. `simulation/propagation/` — 传播推演

**降级为内部/后台的功能**
| 当前模块 | 修正方案 |
|----------|---------|
| 信号采集(signal/) | 移除用户入口，保留为可配置的背景数据源 |
| 知识图谱(graph/) | 移除用户入口，保留为内部实体关联能力 |
| 人格工厂管理UI | 移除管理界面，预置人格模板，自动生成 |
| 仿真控制面板UI | 移除控制面板，分析时自动运行仿真 |
| 博主服务(V2.R6) | 移除，回归"以后再说" |
| PaddleOCR/PaddlePaddle | 移除本地依赖，改用API多模态模型的OCR能力 |

**移除的依赖**
| 依赖 | 原用途 | 修正 |
|------|--------|------|
| `paddleocr` | 本地OCR | 改用API（Qwen3-VL / GLM-OCR内置OCR） |
| `paddlepaddle` | PaddleOCR后端 | 不再需要 |
| `easyocr` | OCR备选 | 不再需要 |
| `neo4j` | 知识图谱 | 评估是否保留（可能简化为LLM内部推理） |
| `pymysql` | MySQL | 评估是否可退回SQLite |
| `yt-dlp` | 在线视频下载 | 移除，只支持本地视频 |

**保留的依赖**
| 依赖 | 用途 |
|------|------|
| `opencv-python` | 关键帧提取、视频处理 |
| `scenedetect` | 场景检测 |
| `ffmpeg-python` | 视频处理 |
| `faster-whisper` | 音频转写（备选，有GPU时使用） |
| `fastapi` | 后端框架 |
| `sqlalchemy` | ORM |
| `openai` | LLM API调用 |

### 3.4 前端架构修正

**Vue前端只保留1个页面**：`/workbench`（内容预审工作台）

移除的页面：`/video-review`（合并入workbench）、`/signals`、`/simulation`、`/reports`（合并入workbench）、`/settings`（系统管理）、`/blogger`

### 3.5 后端API修正

只暴露用户流程所需的端点：
- `POST /api/review` — 提交内容（视频/文案/混合）进行预审
- `GET /api/review/{task_id}` — 获取预审结果
- `GET /api/review/{task_id}/progress` — 获取分析进度（WebSocket推送）
- `GET /api/history` — 历史记录
- `GET /api/models` — 可用模型列表

## 四、硬件/环境需求 — 硬件自适应架构

### 4.1 设计原则：一套代码，三级适配

核心思想：系统启动时自动检测硬件能力，选择最优模型策略。用户无需手动配置，开源用户也不会被门槛挡住。

```
┌─────────────────────────────────────────────────┐
│              VibeUtopia 启动                      │
│                                                   │
│  1. 硬件探测：GPU型号、显存大小、CUDA版本         │
│  2. 自动分级：Lite / Standard / Pro               │
│  3. 模型路由：按分级选择最优模型方案               │
│  4. 用户可覆盖：设置中可手动切换分级/模型          │
│                                                   │
├─────────────────────────────────────────────────┤
│  TIER Lite (无GPU / 集显)         ← 无GPU笔记本  │
│  ├─ 视觉理解: Qwen3-VL-Plus API                  │
│  ├─ OCR: Qwen3-VL-Plus API (内置OCR)             │
│  ├─ 音频转写: 阿里Paraformer API                  │
│  ├─ 文本/推理: DeepSeek-V4-Flash API              │
│  └─ 成本: ~2-3元/次，零硬件门槛                   │
│                                                   │
│  TIER Standard (12GB GPU)         ← 5070Ti笔记本 │
│  ├─ 视觉理解: Qwen3-VL-Plus API                  │
│  ├─ OCR: GLM-OCR 本地 (94.62精度)                │
│  ├─ 音频转写: faster-whisper large-v3 本地        │
│  ├─ 文本/推理: DeepSeek-V4-Flash API              │
│  ├─ 视觉降级: Qwen3-VL-8B 本地 (API限速时)       │
│  └─ 成本: ~1-2元/次 (OCR+音频省了)               │
│                                                   │
│  TIER Pro (24GB GPU)              ← 4090台式     │
│  ├─ 视觉理解: Qwen3-VL-Plus API                  │
│  ├─ OCR: GLM-OCR 本地 (94.62精度)                │
│  ├─ 音频转写: faster-whisper large-v3 本地        │
│  ├─ 文本/推理: DeepSeek-V4-Flash API              │
│  ├─ 视觉降级: Qwen3-VL-32B(AWQ) 本地             │
│  ├─ 文本降级: Qwen3-32B(AWQ) 本地                │
│  └─ 成本: ~0.5-1元/次 (大部分本地完成)            │
│                                                   │
│  TIER Ultra (多GPU/服务器)                        │
│  ├─ 全部本地：Qwen3-VL-235B + GLM-OCR            │
│  ├─ 全部本地：DeepSeek-V4-Flash量化               │
│  └─ 成本: ~0元/次 (全本地)                        │
└─────────────────────────────────────────────────┘
```

### 4.2 硬件探测与自动分级

```python
# backend/services/hardware_detector.py

import torch
import logging

logger = logging.getLogger(__name__)

def detect_tier():
    """启动时自动检测硬件并返回运行级别"""
    
    if not torch.cuda.is_available():
        logger.info("未检测到GPU，使用 TIER Lite (纯API模式)")
        return "lite"
    
    gpu_name = torch.cuda.get_device_name(0)
    vram_mb = torch.cuda.get_device_properties(0).total_mem // (1024 * 1024)
    vram_gb = vram_mb / 1024
    
    if vram_gb >= 80:
        tier = "ultra"
    elif vram_gb >= 20:
        tier = "pro"
    elif vram_gb >= 10:
        tier = "standard"
    else:
        tier = "lite"
    
    logger.info(f"检测到GPU: {gpu_name}, 显存: {vram_gb:.1f}GB, 运行级别: TIER {tier.upper()}")
    return tier


def get_model_config(tier: str) -> dict:
    """根据运行级别返回模型配置"""
    configs = {
        "lite": {
            "frame_understanding": {"provider": "api", "model": "qwen3-vl-plus"},
            "ocr": {"provider": "api", "model": "qwen3-vl-plus"},
            "audio_transcription": {"provider": "api", "model": "aliyun-paraformer"},
            "risk_assessment": {"provider": "api", "model": "deepseek-v4-pro"},
            "persona_simulation": {"provider": "api", "model": "deepseek-v4-flash"},
            "text_analysis": {"provider": "api", "model": "deepseek-v4-flash"},
        },
        "standard": {
            "frame_understanding": {
                "provider": "api", "model": "qwen3-vl-plus",
                "fallback": {"provider": "local", "model": "qwen3-vl-8b-int4"}
            },
            "ocr": {"provider": "local", "model": "glm-ocr"},
            "audio_transcription": {"provider": "local", "model": "faster-whisper-large-v3"},
            "risk_assessment": {"provider": "api", "model": "deepseek-v4-pro"},
            "persona_simulation": {"provider": "api", "model": "deepseek-v4-flash"},
            "text_analysis": {"provider": "api", "model": "deepseek-v4-flash"},
        },
        "pro": {
            "frame_understanding": {
                "provider": "api", "model": "qwen3-vl-plus",
                "fallback": {"provider": "local", "model": "qwen3-vl-32b-awq"}
            },
            "ocr": {"provider": "local", "model": "glm-ocr"},
            "audio_transcription": {"provider": "local", "model": "faster-whisper-large-v3"},
            "risk_assessment": {
                "provider": "api", "model": "deepseek-v4-pro",
                "fallback": {"provider": "local", "model": "qwen3-32b-awq"}
            },
            "persona_simulation": {
                "provider": "api", "model": "deepseek-v4-flash",
                "fallback": {"provider": "local", "model": "qwen3-32b-awq"}
            },
            "text_analysis": {"provider": "api", "model": "deepseek-v4-flash"},
        },
        "ultra": {
            "frame_understanding": {"provider": "local", "model": "qwen3-vl-235b-fp8"},
            "ocr": {"provider": "local", "model": "glm-ocr"},
            "audio_transcription": {"provider": "local", "model": "faster-whisper-large-v3"},
            "risk_assessment": {"provider": "local", "model": "deepseek-v4-flash-fp8"},
            "persona_simulation": {"provider": "local", "model": "deepseek-v4-flash-fp8"},
            "text_analysis": {"provider": "local", "model": "deepseek-v4-flash-fp8"},
        },
    }
    return configs[tier]
```

### 4.3 你的三台设备配置表

| 设备 | GPU | 显存 | 自动分级 | 本地可运行 | API依赖 |
|------|-----|------|---------|-----------|---------|
| 无GPU笔记本 | Intel集显 | 共享 | **Lite** | 无 | 全部API |
| 5070Ti笔记本 | RTX 5070 Ti Laptop | 12GB GDDR7 | **Standard** | GLM-OCR + faster-whisper-large-v3 + Qwen3-VL-8B(INT4) | 视觉+文本API |
| 4090台式 | RTX 4090 Desktop | 24GB GDDR6X | **Pro** | GLM-OCR + faster-whisper-large-v3 + Qwen3-VL-32B(AWQ) + Qwen3-32B(AWQ) | 视觉+文本API(限速降级到本地) |

#### 每台设备的具体能力

**无GPU笔记本 (TIER Lite)**
```
OCR:        Qwen3-VL-Plus API     精度~89       速度: 受API限速
视觉理解:   Qwen3-VL-Plus API     顶级          速度: 受API限速
音频转写:   阿里Paraformer API    中文最强       速度: 受QPS限制
文本推理:   DeepSeek-V4-Flash API 顶级          速度: 快
单次成本:   ~2-3元
适用:       开发调试、API测试、随时可用
```

**5070Ti笔记本 (TIER Standard)**
```
OCR:        GLM-OCR 本地           精度94.62     速度: 极快(0.9B)
视觉理解:   Qwen3-VL-Plus API     顶级          速度: 受API限速
            降级→ Qwen3-VL-8B本地  良好          速度: ~3-5秒/帧
音频转写:   faster-whisper本地     中文极强       速度: 实时倍速
文本推理:   DeepSeek-V4-Flash API 顶级          速度: 快
显存分配:   GLM-OCR(~2GB) + faster-whisper(~4GB) + Qwen3-VL-8B预留(~6GB) = 12GB
单次成本:   ~1-2元 (OCR+音频免费)
适用:       日常使用、移动办公
```

**4090台式 (TIER Pro)**
```
OCR:        GLM-OCR 本地           精度94.62     速度: 极快
视觉理解:   Qwen3-VL-Plus API     顶级          速度: 受API限速
            降级→ Qwen3-VL-32B本地 接近API       速度: ~5-8秒/帧
音频转写:   faster-whisper本地     中文极强       速度: 实时倍速
文本推理:   DeepSeek-V4-Flash API 顶级          速度: 快
            降级→ Qwen3-32B本地    良好          速度: 可接受
显存分配:   需按需加载(不同时跑)
            模式1: GLM-OCR(2GB) + faster-whisper(4GB) + Qwen3-VL-32B(18GB) ≈ 24GB
            模式2: GLM-OCR(2GB) + Qwen3-32B(18GB) + faster-whisper(4GB) ≈ 24GB
单次成本:   ~0.5-1元 (大部分本地)
适用:       深度分析、微调训练、主力开发
```

### 4.4 显存管理策略

不同模型不能同时占满显存，需要按需加载：

```python
# backend/services/model_manager.py

class ModelManager:
    """GPU显存管理：按需加载/卸载模型"""
    
    def __init__(self, tier: str):
        self.tier = tier
        self.loaded_models = {}  # model_name -> model_instance
        self.vram_budget = self._get_vram_budget()
    
    def _get_vram_budget(self) -> int:
        """获取可用显存(MB)，预留2GB给系统"""
        if not torch.cuda.is_available():
            return 0
        total = torch.cuda.get_device_properties(0).total_mem // (1024 * 1024)
        return total - 2048  # 预留2GB
    
    def load_model(self, model_name: str):
        """按需加载模型，显存不足时先卸载低优先级模型"""
        if model_name in self.loaded_models:
            return self.loaded_models[model_name]
        
        required_vram = MODEL_VRAM_REQUIREMENTS[model_name]
        current_usage = sum(MODEL_VRAM_REQUIREMENTS[m] for m in self.loaded_models)
        
        if current_usage + required_vram > self.vram_budget:
            # 卸载最低优先级的已加载模型
            self._evict_lowest_priority(required_vram)
        
        model = self._load_from_disk(model_name)
        self.loaded_models[model_name] = model
        return model
    
    def _evict_lowest_priority(self, needed_vram: int):
        """卸载低优先级模型释放显存"""
        # 优先级: OCR > 音频转写 > 视觉降级 > 文本降级
        priority_order = ["text_fallback", "frame_fallback", "audio", "ocr"]
        for category in reversed(priority_order):
            # 释放该类别的模型直到有足够空间
            ...

# 模型显存需求表
MODEL_VRAM_REQUIREMENTS = {
    "glm-ocr":              2048,   # 2GB
    "paddleocr-vl-1.5":    2048,   # 2GB
    "faster-whisper-medium":2560,   # 2.5GB
    "faster-whisper-large":4096,   # 4GB (large-v3)
    "qwen3-vl-8b-int4":    6144,   # 6GB
    "qwen3-vl-30b-a3b":    8192,   # 8GB
    "qwen3-vl-32b-awq":   18432,   # 18GB
    "qwen3-32b-awq":      18432,   # 18GB
}
```

### 4.5 开源用户的分级体验

开源后不同条件用户的体验：

| 用户类型 | 硬件 | 分级 | 能力 | 门槛 |
|----------|------|------|------|------|
| 普通用户 | 任意电脑 | Lite | 全API，功能完整 | 只需API Key |
| 游戏本用户 | RTX 3060-5070 | Standard | OCR+音频本地加速，更省钱 | GPU+CUDA |
| AI爱好者 | RTX 4090 | Pro | 大部分本地，质量最高 | GPU+CUDA+模型下载 |
| 研究机构 | A100集群 | Ultra | 全本地，可微调 | 多GPU+Linux |

**安装包设计**：
```bash
# 最小安装 (Lite用户)
pip install vibeutopia

# GPU加速 (Standard/Pro用户)
pip install vibeutopia[gpu]        # faster-whisper + CUDA支持
pip install vibeutopia[ocr]        # GLM-OCR 本地
pip install vibeutopia[vl-local]   # Qwen3-VL 本地推理
pip install vibeutopia[all]        # 全部本地能力
```

### 4.6 操作系统兼容性

| 功能 | Windows 11 | Ubuntu 22.04 | macOS |
|------|-----------|-------------|-------|
| 纯API模式 | 完全支持 | 完全支持 | 完全支持 |
| FFmpeg | 需手动安装 | apt install | brew install |
| faster-whisper GPU | CUDA配置 | 原生支持 | 不支持(需MPS) |
| GLM-OCR | CUDA | CUDA | 不支持 |
| vLLM推理 | 不支持 | **仅Linux** | 不支持 |
| Ollama推理 | 支持 | 支持 | 支持(MPS) |
| Docker | WSL2 | 原生 | Docker Desktop |

**推荐**：开发阶段Windows即可（API模式），后续微调/高性能需求切Linux。

### 4.7 API Key配置（Lite模式只需这一步）

```yaml
# config/api_keys.yaml (用户只需填这个)
qwen:
  api_key: "sk-xxx"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"

deepseek:
  api_key: "sk-xxx" 
  base_url: "https://api.deepseek.com/v1"

zhipu:
  api_key: "xxx.xxx"
  base_url: "https://open.bigmodel.cn/api/paas/v4"

aliyun_asr:
  api_key: "xxx"
  # Paraformer语音转写
```

系统启动时自动检测：有GPU→加载本地模型，无GPU→纯API。用户零配置。

## 五、Agent系统设计

### 5.1 参考项目对比

| 项目 | Agent数量 | 人格结构 | 记忆系统 | 交互模式 | 结果质量 |
|------|----------|---------|---------|---------|---------|
| **Stanford Generative Agents** | 25(原始)/1,052(扩展) | 自然语言描述+生活日常 | Memory Stream(观察+反思+规划) | 自由交互 | 85%调查准确率 |
| **AgentSociety(清华)** | 10,000+ | 三层心智(情感+需求+认知) | 流式记忆+态度值(0-10) | MQTT分布式+Ray | 多项社会实验验证 |
| **OASIS(CAMEL-AI)** | 1,000,000 | 人格+兴趣+行为模式 | 持久化Profile | 异步图结构 | 信息扩散+极化验证 |
| **MiroFish(58K star)** | 数千(可配) | 人格+背景+初始立场+社交关系 | Zep Cloud/Neo4j | 双平台并行仿真 | 舆论趋势预测 |
| **S3/GA-S3(清华)** | 百~十亿(群组Agent) | 人口统计推断+兴趣+行为 | 态度更新 | 社交网络传播 | 流量预测 |
| **当前VibeUtopia** | 24原型/100仿真Agent | **7层人格(最细致)** | L7动态层(弱) | 3层Agent(A/B/C) | 未充分验证 |

**关键发现**：
1. VibeUtopia的7层人格结构是所有项目中最细致的，这是优势
2. 但每平台6个原型太少（参考项目8-15个），且只覆盖4个平台
3. 当前记忆系统太弱（只有L7动态层），需要参考Stanford的Memory Stream
4. 100个仿真Agent的配置合理，但原型多样性不足
5. MiroFish用Neo4j做GraphRAG辅助Agent记忆，这个架构值得借鉴

### 5.2 Agent数量设计

**核心原则：原型多样性 > Agent总数**

参考研究表明：
- Stanford: 25个独特Agent即可涌现可信社会行为
- AgentSociety: 10,000+Agent，但核心是数百种不同人格
- MiroFish: 数千Agent，但重点在人格多样性
- OASIS: 100万Agent，但研究表明100-500就能复现核心现象

**结论：最终目标是万级Agent大规模仿真，分阶段递进。**

#### 原型(Archetype)设计 — 每平台15-20个原型

每平台6个原型远不够。参考AgentSociety每个Agent有独立的8+维度人格，MiroFish使用数千独立人格。每个平台用户群体高度分化，需要覆盖主流群体、争议群体、极端群体、边缘群体。

| 层级 | 平台数 | 原型数/平台 | 总原型数 | 设计原则 |
|------|--------|-----------|---------|---------|
| **P0** | 6 (微博、B站、抖音、小红书、知乎、贴吧) | **20** | 120 | 完整覆盖：主流5+争议5+极端3+边缘3+跨界4 |
| **P1** | 7 (快手、公众号、豆瓣、虎扑、头条、NGA、视频号) | **15** | 105 | 核心覆盖：主流4+争议4+极端2+边缘2+跨界3 |
| **P2** | 12 (小黑盒、TapTap、米游社、游民星空、澎湃、观察者网、虎嗅、36氪、Lofter、西瓜视频、即刻、什么值得买) | **10** | 120 | 代表性覆盖：主流3+争议3+极端2+边缘2 |
| **总计** | 25平台 | 10-20/平台 | **~345原型** | |

**原型分类标准（每平台）**：
- **主流群体**(3-5个)：平台最大用户群，如B站的"ACG核心用户"、微博的"追星粉丝"
- **争议群体**(3-5个)：最容易制造或卷入舆论的群体，如微博的"性别对立参与者"、虎扑的"直男评论员"
- **极端群体**(2-3个)：持极端立场的少数派，他们的反应是风险预警的关键
- **边缘群体**(2-3个)：平台非主流用户，如小红书的"男性美妆博主"、B站的"中老年用户"
- **跨界群体**(2-4个)：活跃于多个平台的用户，是跨平台传播的桥梁

#### Agent规模目标 — 分阶段递进至万级

参考项目证明：Agent数量直接影响仿真真实度。MiroFish用数千Agent才能预测舆论趋势，AgentSociety用1万+Agent才能复现社会现象。

| 阶段 | Agent数/分析 | 原型覆盖 | LLM调用 | 预估时间 | 预估成本 | 参考对标 |
|------|------------|---------|---------|---------|---------|---------|
| **MVP** | ~100 | P0平台，每原型1-2变体 | ~300 | 1-2分钟 | ~0.5元 | Stanford 25Agent级 |
| **标准** | ~500 | P0+P1平台，每原型2-3变体 | ~1,500 | 3-5分钟 | ~2元 | MiroFish标准级 |
| **深度** | ~2,000 | 全部25平台，每原型3-5变体 | ~5,000 | 10-15分钟 | ~5元 | MiroFish深度级 |
| **大规模** | ~5,000-10,000 | 全平台，Group Agent(GA-S3)扩展 | ~10,000-20,000 | 20-40分钟 | ~10-20元 | AgentSociety级 |

**关键优化：参考GA-S3的Group Agent机制**
- 当Agent数>1000时，将相似Agent归为"群组Agent"
- 一个群组Agent代表10-100个相似个体，用统计分布代替逐一模拟
- 这样5000个独立Agent的效果可扩展到等效10万+个体
- 这是OASIS达到100万Agent的核心技术

```
Agent层级架构：

  A-tier (意见领袖, ~1%)
  ├─ 每个独立LLM推理
  ├─ 影响力大，决定传播方向
  └─ 例：微博大V、B站百大UP主

  B-tier (活跃用户, ~9%)
  ├─ 采样LLM推理（每tick部分调用）
  ├─ 活跃互动，推动讨论
  └─ 例：评论区活跃分子

  C-tier (普通用户, ~40%)
  ├─ 规则引擎决策（不调LLM）
  ├─ 被动消费，偶尔回复
  └─ 例：浏览不评论的用户

  Group-tier (群组Agent, ~50%)
  ├─ 统计模型（基于人口统计+态度分布）
  ├─ 代表大量相似个体的集体行为
  └─ 例："2万点赞"背后的群体态度分布
```

#### 每次分析的Agent配置

```
┌─────────────────────────────────────────────────────┐
│  分析请求 → 内容类型识别 → 自动选择相关平台            │
│                                                       │
│  例：一篇关于"游戏女性角色设计"的视频                    │
│  → 自动识别：游戏相关 + 性别相关                       │
│  → 激活平台：B站(20) + 微博(20) + 小红书(20)          │
│  + 知乎(20) + NGA(15) + 虎扑(15) + 贴吧(20)          │
│  + 抖音(20) + 米游社(10) + TapTap(10)                │
│  = 170个原型                                          │
│                                                       │
│  MVP: 每原型1变体 = ~170 Agent                        │
│  标准: 每原型3变体 = ~510 Agent                        │
│  深度: 每原型5变体 + Group Agent = ~2000+等效Agent     │
└─────────────────────────────────────────────────────┘
```

### 5.3 Agent人格结构升级

当前7层结构保留并增强：

| 层 | 名称 | 当前 | 升级 |
|----|------|------|------|
| L1 | 基础属性 | age, gender, occupation, region, income, education | +marital_status, housing, platform_account_age, follower_tier |
| L2 | 价值观 | 5维度(0-10) | +gender_awareness, nationalism, consumer_consciousness(8维度) |
| L3 | 知识背景 | 专业领域, 信息来源, 认知水平, 媒介素养 | +platform_literacy(平台使用熟练度), content_discernment |
| L4 | 行为模式 | 表达风格, 互动偏好, 内容偏好, 活跃时段 | +engagement_triggers(什么内容会让他互动), share_threshold |
| L5 | 校正层 | 文化禁忌, 敏感触发, 回避话题, 自我审查 | +platform_norms(平台特有规范), moderation_awareness |
| L6 | 社交关系 | 社交圈, 影响力, 关注领域, 社交活跃度 | +social_graph_seed(社交网络种子), trust_network |
| L7 | 动态状态 | 近期经历, 情绪基线, 态度变化, 记忆锚点 | **+Memory Stream(Stanford式记忆流)** |

#### L7 Memory Stream 升级（参考Stanford Generative Agents）

```python
class MemoryStream:
    """Stanford式记忆流 - Agent的核心记忆系统"""
    
    def __init__(self):
        self.memories = []  # List[MemoryEntry]
    
    def add(self, observation: str, importance: int):
        """添加新记忆"""
        self.memories.append(MemoryEntry(
            content=observation,
            timestamp=datetime.now(),
            importance=importance,  # LLM评分1-10
            access_count=0,
            last_access=datetime.now()
        ))
    
    def retrieve(self, query: str, top_k: int = 10) -> list:
        """检索最相关的记忆，三因子评分"""
        scored = []
        for mem in self.memories:
            recency = math.exp(-hours_since(mem.last_access) / 24)  # 近期衰减
            importance = mem.importance / 10  # 重要度
            relevance = cosine_similarity(embed(query), embed(mem.content))  # 相关性
            score = 0.5 * recency + 0.3 * importance + 0.2 * relevance
            scored.append((mem, score))
        return sorted(scored, key=lambda x: -x[1])[:top_k]
    
    def reflect(self) -> list:
        """反思：从低层记忆合成高层洞察"""
        # 定期触发，如每10条新记忆后
        # 例：多次看到性别相关讨论 → 合成"我对性别议题很敏感"
        recent = self.memories[-10:]
        insights = llm.reflect(recent)  # LLM合成
        for insight in insights:
            self.add(insight, importance=8)  # 反思结果重要性高
        return insights
```

### 5.5 Agent人生故事驱动人格（Life Story Driven Persona）

**核心洞察：经历定义人，不是属性定义人。**

Stanford 2024年1000人实验证明：用AI访谈获取的数万字人生故事作为Agent记忆，调查准确率达85%，**显著优于**仅靠人口统计属性或短段描述的Agent。这直接验证了"人生故事驱动"路线的正确性。

#### 5.5.1 人生故事生成策略

| 策略 | 方法 | 单AgentToken | 单Agent成本 | 适用Agent层级 | Reference |
|------|------|-------------|-----------|-------------|-----------|
| **AI访谈生成** | AI扮演访谈者，结构化6轮访谈（童年→求学→工作→感情→价值观→社会议题） | ~30K输出 | ~¥0.5 | A-tier(KOL)、B-tier种子Agent | Stanford 1000人 |
| **人口统计采样+LLM丰富** | 从CGSS等人口统计数据采样基础属性，LLM据此生成"完整人生档案" | ~10K输出 | ~¥0.2 | B-tier批量Agent、C-tier模板 | AgentSociety |
| **模板变体+递增扩展** | 按时代/地区/阶层创建基础人生模板，每个Agent基于模板+变体种子递增展开 | ~3K输出 | ~¥0.05 | C-tier群体Agent | MiroFish |

**AI访谈生成流程（A-tier专用）**：
```python
INTERVIEW_ROUNDS = [
    {"topic": "童年与家庭", "prompt": "请聊聊你的童年，你在哪里长大？家庭氛围如何？有没有影响深远的童年经历？"},
    {"topic": "求学经历", "prompt": "你的学生时代是怎样的？最喜欢的科目？有没有校园霸凌或特别好的老师？"},
    {"topic": "职业与经济", "prompt": "你是怎么进入现在这个行业的？工作中最自豪和最挫败的经历？"},
    {"topic": "情感与社交", "prompt": "你最重要的关系是什么？有没有改变你人生轨迹的人？"},
    {"topic": "价值观形成", "prompt": "哪些经历塑造了你的价值观？你对社会公平、消费、家庭责任怎么看？"},
    {"topic": "平台与网络", "prompt": "你平时在哪些平台活跃？什么内容会让你想评论/转发？最近关注什么话题？"},
]

async def generate_life_story(archetype: PersonaArchetype) -> str:
    """通过AI访谈生成完整人生故事"""
    context = archetype_to_dict(archetype)  # L1-L6属性作为访谈引导
    story_parts = []
    for round_spec in INTERVIEW_ROUNDS:
        prompt = f"你是一个{context['L1_basic']['age_range']}岁的{context['L1_basic']['occupation']}，"
                 f"来自{context['L1_basic']['region']}。{round_spec['prompt']}"
        response = await call_llm(prompt, max_tokens=5000)
        story_parts.append(f"## {round_spec['topic']}\n{response}")
    return "\n\n".join(story_parts)
```

**人口统计采样+LLM丰富流程（B-tier批量）**：
```python
# 基于CGSS 2018数据分布采样
POPULATION_DISTRIBUTIONS = {
    "age": [(0.18, "18-24"), (0.25, "25-34"), (0.28, "35-44"), (0.18, "45-54"), (0.11, "55+")],
    "education": [(0.35, "高中及以下"), (0.30, "大专"), (0.25, "本科"), (0.10, "研究生")],
    "income": [(0.20, "低收入"), (0.45, "中等"), (0.25, "中高"), (0.10, "高收入")],
    # ...
}

async def generate_life_archive(demographics: dict) -> str:
    """基于人口统计生成完整人生档案"""
    prompt = f"""请为一个具有以下背景的人生成详细人生档案：
{json.dumps(demographics, ensure_ascii=False)}

请按年龄段描述：0-6岁、7-12岁、13-18岁、19-22岁、23岁至今。
每段包含：关键事件、重要人物、心理状态、价值观变化。"""
    return await call_llm(prompt, max_tokens=10000)
```

**批量生成成本估算**：

| 阶段 | Agent数 | 生成方式 | 总Token | 总成本 | 备注 |
|------|--------|---------|--------|-------|------|
| MVP | ~100 | AI访谈30% + LLM丰富70% | ~2M | ~¥30 | 一次性 |
| 标准 | ~500 | AI访谈10% + LLM丰富50% + 模板40% | ~5M | ~¥80 | 一次性 |
| 深度 | ~2,000 | AI访谈5% + LLM丰富30% + 模板65% | ~10M | ~¥150 | 一次性 |
| 大规模 | ~10,000 | AI访谈2% + LLM丰富20% + 模板78% | ~20M | ~¥300 | 一次性 |

**人生故事是一次性投资**：生成后持久化存储，反复使用，成本摊薄到每次分析中可忽略。

#### 5.5.2 人生故事→人格记忆的转化

生成的人生故事需要转化为Memory Stream可检索的记忆条目：

```python
async def story_to_memories(life_story: str, agent_id: str) -> list[MemoryEntry]:
    """将人生故事拆解为记忆条目"""
    # Step1: LLM提取关键人生事件
    prompt = f"""从以下人生故事中，提取所有重要人生事件。
每个事件用一句话描述，并评分重要度(1-10)。
格式：事件描述 | 重要度

{life_story}"""
    events_text = await call_llm(prompt, max_tokens=3000)

    # Step2: 解析为MemoryEntry
    memories = []
    for line in events_text.strip().split("\n"):
        if "|" in line:
            content, importance = line.rsplit("|", 1)
            memories.append(MemoryEntry(
                agent_id=agent_id,
                content=content.strip(),
                timestamp=None,  # 历史记忆无精确时间
                importance=int(importance.strip()),
                memory_type="life_event",  # 区分人生事件和仿真中产生的新记忆
                access_count=0,
            ))

    # Step3: 生成embedding（用于Relevance检索）
    for mem in memories:
        mem.embedding = await embed(mem.content)

    return memories
```

#### 5.5.3 平台信息浸泡（Persona Immersion）

Agent初始化后，进入"浸泡期"模拟刷平台，形成近期态度：

```python
IMMERSION_CONFIG = {
    "lite": {"days": 3, "posts_per_day": 20},     # 快速浸泡
    "standard": {"days": 7, "posts_per_day": 30},  # 标准浸泡
    "deep": {"days": 14, "posts_per_day": 50},     # 深度浸泡
}

async def immerse_agent(agent: Agent, platform: str, config: dict):
    """让Agent在平台上浸泡，吸收信息形成态度"""
    for day in range(config["days"]):
        # 获取该平台的模拟热门帖子
        posts = await get_platform_trending(platform, limit=config["posts_per_day"])

        for post in posts:
            # 检索相关记忆 → 决定是否互动
            relevant_memories = agent.memory_stream.retrieve(post["content"], top_k=5)
            reaction = await agent.react(post, relevant_memories)

            if reaction["engaged"]:  # Agent选择互动
                # 记录到Memory Stream
                agent.memory_stream.add(
                    observation=f"在{platform}看到关于{post['topic']}的帖子，我的反应是{reaction['attitude']}",
                    importance=reaction["importance"],
                )

        # 每天结束后，检查是否触发反思
        if agent.memory_stream.should_reflect():
            insights = agent.memory_stream.reflect()
            # 反思结果写回记忆，重要度高
```

**浸泡的效果**：
- 没有浸泡：Agent只有"静态属性"，对热点话题反应生硬
- 经过浸泡：Agent有"近期体验"，能引用"前几天看到过类似讨论"，反应更自然
- 深度浸泡：Agent形成稳定的"态度立场"，对争议话题有明确倾向

#### 5.5.4 存储架构 — 混合存储方案

```
┌──────────────────────────────────────────────────────────┐
│                  Agent人格数据存储架构                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐  结构化数据(L1-L6属性、评分、状态)       │
│  │  MySQL /    │  表：agents(元数据)                      │
│  │  SQLite     │  表：agent_memories(记忆条目+索引)       │
│  │             │  表：social_relations(社交关系)           │
│  └─────────────┘  查询：按平台/属性/状态筛选Agent         │
│                                                          │
│  ┌─────────────┐  向量检索(Memory Stream的Relevance因子)  │
│  │  ChromaDB   │  存储：记忆条目的embedding               │
│  │  (内嵌式)   │  查询：语义相似度检索Top-K记忆            │
│  │             │  特点：Python内嵌，零部署，无需独立服务   │
│  └─────────────┘  规模：10K Agent × 1000条 ≈ 10M条 可胜任 │
│                                                          │
│  ┌─────────────┐  社交图谱 + 知识图谱                     │
│  │   Neo4j     │  存储：Agent间关注/信任/影响关系          │
│  │             │  存储：实体(人名/机构/事件)关系           │
│  │             │  查询：传播路径、影响力分析                │
│  └─────────────┘  Reference：MiroFish GraphRAG           │
│                                                          │
│  ┌─────────────┐  原始文档(完整人生故事)                   │
│  │  文件系统    │  路径：agents/{agent_id}/story.md       │
│  │             │  大小：50-500KB/Agent                    │
│  │             │  特点：太大不适合DB字段，文件IO更高效      │
│  └─────────────┘  10K Agent ≈ 1-5GB磁盘空间              │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**关键决策：为什么不用Milvus？**

| 对比维度 | ChromaDB | Milvus |
|---------|----------|--------|
| 部署方式 | Python内嵌，pip install | 独立服务，需Docker |
| 运维成本 | 零 | 高（配置、监控、备份） |
| 10M条向量性能 | <100ms | <10ms |
| 适用规模 | <10M条 | >10M条 |
| 当前项目需求 | 10K Agent × 1000条 = 10M条 | 过度 |
| 结论 | **推荐** | 过重 |

当Agent数>100K（远期目标）时，可迁移到Milvus。当前阶段ChromaDB足够。

#### 5.5.5 人格完善性验证

| 验证维度 | 方法 | 通过标准 | Reference |
|---------|------|---------|-----------|
| **7层覆盖完整性** | 检查L1-L7每层是否都有有效值 | 无空缺字段 | VibeUtopia |
| **Big Five一致性** | 用标准Big Five问卷(60题)测试Agent，同Agent两次测试相关性 | r > 0.7 | Stanford 1000人 |
| **行为一致性** | 相似刺激→相似反应；不同刺激→不同反应 | 内部一致性Cronbach's α > 0.6 | Stanford |
| **跨场景稳定性** | 不同平台/话题下，L2核心价值观不矛盾 | 价值观波动 < 2分(10分制) | AgentSociety |
| **与人口统计符合度** | Agent群体态度分布 vs CGSS同类人群真实数据 | 分布相似度 > 0.7 | AgentSociety |
| **反思质量** | Agent能否从记忆中合理归纳出自身特质 | LLM评判反思合理性 > 7/10 | Stanford |
| **群体多样性** | 整体Agent群体态度呈多峰分布，非全部趋同 | 态度分布标准差 > 1.5 | OASIS |

**自动验证流水线**：
```python
async def validate_persona(agent: Agent) -> dict:
    """自动验证Agent人格完善度"""
    scores = {}

    # 1. 结构完整性检查
    scores["structure"] = check_7layer_completeness(agent)

    # 2. Big Five一致性测试
    big_five_1 = await agent.answer_big_five_questionnaire()
    big_five_2 = await agent.answer_big_five_questionnaire()  # 重复测试
    scores["big5_consistency"] = pearson_correlation(big_five_1, big_five_2)

    # 3. 行为一致性：给5对相似刺激+5对不同刺激
    similar_reactions = [await agent.react(s) for s in SIMILAR_STIMULI_PAIRS]
    different_reactions = [await agent.react(d) for d in DIFFERENT_STIMULI_PAIRS]
    scores["behavioral_consistency"] = compute_consistency(similar_reactions, different_reactions)

    # 4. 反思质量
    reflection = agent.memory_stream.reflect()
    scores["reflection_quality"] = await llm_judge(reflection, rubric="是否合理归纳自身特质")

    # 5. 总分
    scores["overall"] = weighted_average(scores)
    scores["passed"] = scores["overall"] >= 0.7

    return scores
```

```
内容输入
  │
  ├─ Step1: 内容理解
  │   ├─ 视频理解（关键帧+OCR+音频转写）
  │   ├─ 文案理解（语义+情感+敏感检测）
  │   └─ 跨模态融合
  │
  ├─ Step2: 平台匹配（自动）
  │   └─ 基于内容主题自动选择相关平台
  │      例：游戏内容 → B站+NGA+贴吧+TapTap
  │          美妆内容 → 小红书+抖音+微博
  │
  ├─ Step3: Agent生成与激活
  │   ├─ 从原型库加载相关平台的原型
  │   ├─ 每个原型生成2-5个变体Agent
  │   ├─ Agent初始化：L1-L6固定 + L7注入近期记忆
  │   └─ 构建社交网络（基于L6的social_graph_seed）
  │
  ├─ Step4: 舆论推演（多轮仿真）
  │   ├─ Round 1: 内容曝光 → Agent初次反应
  │   │   ├─ A-tier(意见领袖): LLM深度推理反应
  │   │   ├─ B-tier(活跃用户): LLM简化推理
  │   │   └─ C-tier(普通用户): 规则引擎反应
  │   │
  │   ├─ Round 2: 社交传播 → Agent看到他人反应后的二次反应
  │   │   ├─ 基于社交网络的传播（谁看到了什么）
  │   │   ├─ 态度更新（同意/反对/极化）
  │   │   └─ Memory Stream记录本轮经历
  │   │
  │   ├─ Round 3+: 传播扩散 + 极化 + 舆论转折
  │   │   ├─ 5阶段传播模型（种子→扩散→爆发→长尾→沉淀）
  │   │   ├─ 极化检测（群体态度分裂）
  │   │   └─ 反思触发（Agent从记忆中反思态度变化）
  │   │
  │   └─ 终止条件：活跃度下降或达到最大轮次
  │
  ├─ Step5: 结果汇总
  │   ├─ 各平台反应统计（正面/中性/负面比例）
  │   ├─ 高风险Agent群体识别
  │   ├─ 传播路径重建
  │   ├─ 极化程度评估
  │   └─ 关键风险点标记（哪句话/哪个画面触发了风险）
  │
  └─ Step6: 风险报告生成
      ├─ 总体风险评级
      ├─ 各平台反应预测
      ├─ 风险点清单（按严重度排序）
      ├─ 传播推演可视化
      └─ 修改建议
```

## 六、技术决策确认

### 6.1 已确认决策

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 视频来源 | **仅本地视频** | 用户明确要求，移除yt-dlp依赖 |
| 输入模式 | **三模式**：仅视频/仅文案/混合 | 用户明确要求 |
| 前端入口 | **单入口** | 用户明确要求 |
| 模型策略 | **API为主+本地为辅+硬件自适应** | 用户确认 |
| Agent目标 | **多Agent完整人格仿真** | 用户明确最终目标 |
| Agent人格 | **人生故事驱动(Life Story Driven)** | Stanford 1000人实验验证，访谈式远优于属性式 |
| 数据库 | **MySQL+SQLite降级** | MySQL用于多用户/仿真写入，SQLite用于Lite单用户 |
| Neo4j | **保留，降级为内部使用** | MiroFish GraphRAG + AgentSociety社交网络图，移除后传播推演质量显著下降 |
| Redis | **移除** | 当前未大量使用，用asyncio.Queue+内存LRU+令牌桶替代 |
| Milvus | **移除，用ChromaDB替代** | 10K Agent级别ChromaDB足够，无需独立向量服务 |
| 向量检索 | **ChromaDB内嵌式** | 零部署、Python内嵌、10M条向量性能足够 |
| Streamlit | **完全废弃，仅Vue前端** | Vue更高大上，Naive UI暗色主题设计感更强 |
| Agent数量 | **万级递进：100→500→2000→10000** | 参考MiroFish/AgentSociety/OASIS |
| 原型数 | **每平台15-20个，总计~345原型** | 每平台6个远不够 |

### 6.2 技术选型决策

#### Neo4j 知识图谱 — **保留，但降级为内部使用**

**保留理由**：
- MiroFish(58K star)使用Neo4j做GraphRAG，为Agent提供上下文知识
- AgentSociety使用Neo4j存储社交网络图谱
- 对本项目的实际价值：
  1. **实体关系图谱**：内容中提到的人名/机构/事件之间的关联，辅助风险评估
  2. **Agent社交网络**：Agent之间的关注/信任/影响关系，传播推演核心依赖
  3. **风险链追溯**：从单个风险点追溯到相关实体和传播路径
  4. **Agent记忆增强**：GraphRAG为Agent提供结构化知识（而非纯文本记忆）
- **移除的后果**：社交网络退化为简单邻接矩阵，传播推演质量显著下降

**降级方案**：
- 移除用户界面的图谱管理功能
- 系统自动维护，用户不可见
- Docker一键启动Neo4j（已在docker-compose.yml中）
- Lite模式可跳过Neo4j（传播推演退化为简单模型）

#### MySQL — **保留，但支持SQLite降级**

**保留理由**：
- 仿真引擎写入量大（100+Agent × 多轮交互），SQLite并发写入会锁表
- 多用户场景需要MySQL
- 但Lite/单用户模式应支持SQLite降级

**实现**：
```python
# config.py
SQLALCHEMY_DATABASE_URL = (
    os.getenv("DATABASE_URL")  # 用户可配MySQL
    or "sqlite:///./vibeutopia.db"  # 默认SQLite，零依赖
)
```

#### Redis — **移除，用SQLite/内存替代**

**分析**：
- 当前项目未大量使用Redis
- 可能用途：任务队列、缓存、限速
- 替代方案：
  - 任务队列：Python内置asyncio.Queue或Celery+SQLite broker
  - 缓存：内存LRU缓存（单进程足够）
  - 限速：内存令牌桶
- **结论**：Redis对当前项目无明确收益，增加部署门槛，移除

#### Milvus向量数据库 — **移除，用本地向量存储替代**

**分析**：
- 当前项目未使用Milvus
- 可能用途：记忆检索的向量相似度搜索
- 替代方案：Memory Stream检索用numpy/sentence-transformers计算余弦相似度即可
- Agent数<1000时不需要专业向量数据库
- **结论**：移除，降低部署复杂度

### 6.2 前端设计决策

#### 设计语言：暗色主题 + 科技感 + 数据驱动

参考Dify/Palantir/Grafana/Cursor的设计语言，打造"AI风险智能中心"的视觉印象。

#### 布局方案：三面板自适应布局（参考NotebookLM/Dify）

```
┌──────────────────────────────────────────────────────────┐
│  ◉ VibeUtopia                         [硬件: Pro ▾] [⚙] │
├────────┬─────────────────────────────┬───────────────────┤
│        │                             │                   │
│  左栏  │        主内容区              │    右栏(详情)     │
│  240px │        自适应                │    320px(可折叠)  │
│        │                             │                   │
│ ┌────┐ │  ┌───────────────────────┐  │  ┌─────────────┐  │
│ │上传│ │  │                       │  │  │ 风险详情     │  │
│ │区域│ │  │   分析流水线动画       │  │  │              │  │
│ └────┘ │  │   ●→●→●→●→●          │  │  │ 点击风险点   │  │
│        │  │   理解→推演→报告       │  │  │ 展开详情     │  │
│ 历史   │  │                       │  │  │              │  │
│ 记录   │  ├───────────────────────┤  │  │ Agent反应    │  │
│        │  │                       │  │  │ 原始回复     │  │
│ ── ──  │  │   风险仪表盘          │  │  │              │  │
│        │  │                       │  │  │ 传播路径图   │  │
│ 平台   │  │  🔴 高风险 78/100     │  │  │              │  │
│ 热力图 │  │                       │  │  │ 修改建议     │  │
│        │  │  ┌──┬──┬──┬──┬──┐    │  │  │              │  │
│        │  │  │微博│B站│抖音│...│    │  │  │              │  │
│        │  │  ├──┼──┼──┼──┼──┤    │  │  │              │  │
│        │  │  │🔴 │🟡│🟢│🟡│    │  │  │              │  │
│        │  │  └──┴──┴──┴──┴──┘    │  │  │              │  │
│        │  │                       │  │  │              │  │
│        │  │   风险时间线           │  │  │              │  │
│        │  │   ─●────●─────●──    │  │  │              │  │
│        │  │   00:12  01:35  03:22 │  │  │              │  │
│        │  │                       │  │  │              │  │
│        │  └───────────────────────┘  │  └─────────────┘  │
├────────┴─────────────────────────────┴───────────────────┤
│  状态栏: 分析中... Step 2/5 舆论推演 | Agent: 186/200活跃   │
└──────────────────────────────────────────────────────────┘
```

#### 视觉要素

| 要素 | 设计 | 参考 |
|------|------|------|
| **配色** | 深色背景(#0a0a0f) + 蓝紫渐变accent(#6366f1→#8b5cf6) + 红/黄/绿风险色 | Cursor/Grafana |
| **排版** | Inter字体，大标题700/32px，正文400/14px，代码JetBrains Mono | Vercel |
| **风险仪表** | 圆形gauge(0-100)，红/黄/绿阈值渐变，动画过渡 | Grafana |
| **分析流水线** | 节点连线动画，每步完成亮起+数据流粒子 | Dify/Flowise |
| **AI思考中** | 骨架屏shimmer + 流式文本输出 + 闪烁光标 | Vercel v0 |
| **平台热力图** | 25平台卡片网格，背景色按风险等级渐变 | Palantir |
| **传播路径** | D3.js力导向图，节点=Agent，边=传播关系，动态扩散 | AgentSociety |
| **风险时间线** | 视频进度条+风险点标记，点击跳转+展开详情 | YouTube chapters |
| **Agent对话** | 气泡式展示各Agent反应，可展开查看推理过程 | ChatGPT |

#### 技术栈

| 组件 | 选择 | 理由 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 已有代码基础 |
| UI库 | **Naive UI** (非Element Plus) | 暗色主题原生支持更好，设计感更强 |
| 图表 | **ECharts** (已有) + D3.js | ECharts做仪表盘，D3做传播图 |
| 动画 | **Lottie** + CSS transitions | 流水线动画+过渡效果 |
| 状态管理 | Pinia (已有) | |
| HTTP | Axios (已有) | |
| 样式 | **Tailwind CSS 4** (已有) | |

**关键：从Element Plus切换到Naive UI**——Element Plus偏后台管理系统风格，Naive UI设计感更现代，暗色主题更精致，组件如DataTable/Progress/Timeline更符合数据密集型界面需求。

## 七、修正后的蓝图路线

### 阶段1：回归核心 — 单入口串联（优先）
- 重构前端为单入口"内容预审工作台"（Vue + Naive UI暗色主题）
- 完全废弃Streamlit前端
- 实现三种输入模式：仅视频 / 仅文案 / 混合输入
- 串联核心流程：上传→视频理解→文案理解→舆论推演→风险报告
- 后台模块自动串联，用户无感
- 移除多余用户入口和页面
- 移除PaddleOCR/PaddlePaddle本地依赖，改用API或本地GLM-OCR
- 移除yt-dlp（仅支持本地视频）
- 移除Redis依赖

### 阶段2：全平台覆盖（核心流程跑通后）
- P0平台补全：微博人格模板、贴吧新增
- P1平台新增：快手、公众号、豆瓣、虎扑、头条、NGA、视频号（7个）
- P2平台新增：小黑盒、TapTap、米游社、游民星空、澎湃、观察者网等（12个）
- 每个平台：人格模板 + prompt模板 + 模拟器 + 传播特征
- 原型扩展：每平台从6个扩展到15-20个原型

### 阶段3：模型优化 + 人生故事生成（平台覆盖后）
- 接入最新多模态API（Qwen3-VL-Plus / GLM-5V / DeepSeek-V4）
- 接入阿里Paraformer API（音频转写主力）
- 模型路由策略：按任务类型自动选模型
- **人生故事驱动人格系统**：
  - AI访谈生成器（A-tier Agent）
  - 人口统计采样+LLM丰富（B-tier Agent）
  - 人生故事→Memory Stream记忆条目转化
  - ChromaDB向量检索接入（替代Milvus）
  - 人格完善性自动验证流水线
- 报告质量优化：更可操作的风险标注和修改建议

### 阶段4：效果提升（Agent人格就绪后）
- **平台信息浸泡系统**：Agent初始化后模拟刷平台，吸收热点形成近期态度
- Stanford Memory Stream + Reflection机制完整实现
- Agent间社交网络构建（基于Neo4j）
- 传播推演可视化（D3.js力导向图）
- 历史报告对比
- GPU加速音频转写（Pro/Ultra模式）

### 阶段5：规模化仿真（深度优化后）
- Agent规模递进：100→500→2000→10000
- GA-S3 Group Agent机制（统计模型替代相似Agent）
- 多轮仿真优化：传播5阶段模型
- 极化检测与舆论转折预测
- 批量分析优化

### 阶段6：扩展功能（以后再说，明确不现在做）
- 博主历史分析
- 竞品对比
- 信号采集面板
- 知识图谱可视化
- 本地模型部署

## 八、审批与优化补充（在保留本方案主体前提下）

> 说明：本节是对现有方案的增强，不替换前文内容。
> 定位再次确认：`docs/doc.md` 是 `docs/` 内蓝图、PRD、规划文档的修改计划与执行依据。

### 8.1 结论
- 方案总体可执行，方向与“发前风控优先、仿真增强准确率”一致。
- 建议补充执行约束，避免后续文档改造时范围膨胀。

### 8.2 必补约束（建议写入所有被改文档）
- 目标约束：所有功能必须回答“是否提升风险判断准确率”。
- 角色约束：仿真是增强模块，不是独立产品主线。
- 范围约束：阶段 1-3 不引入与主线弱相关的新功能入口。

### 8.3 文件级动作映射（供后续逐个改 docs 使用）

| 文件 | 动作 | 说明 |
|------|------|------|
| `01_产品需求文档(PRD).md` | 改写 | 收敛目标与验收指标，弱化平台化叙事 |
| `02_系统架构设计.md` | 改写 | 以“预审主链路”重排架构层次 |
| `03_MVP实施计划(Tasks).md` | 改写 | 任务顺序按准确率收益排序 |
| `04_V2深化路线图.md` | 改写 | 阶段目标改为“可验证准确率提升” |
| `05_参考项目分析与精华提炼.md` | 修订 | 增加“可落地/暂不落地”清单 |
| `06_信号采集层设计.md` | 修订 | 标注为后台能力，不做主入口 |
| `07_世界构建层设计.md` | 融合瘦身 | 保留对风控有增益部分 |
| `08_仿真运行层设计.md` | 融合瘦身 | 强化按需触发，不独立售卖 |
| `09_分析决策层设计.md` | 修订 | 增加证据链、置信度、不确定性输出 |
| `10_仿真增强风控设计.md` | 保留增强 | 作为仿真价值验证核心文档 |
| `11_仿真验证与基础迁移设计.md` | 修订 | 聚焦回测与一致性验证 |
| `12_多模态风控设计.md` | 修订 | 强化视频/音频/文案跨模态一致性校验 |
| `13_前端升级设计.md` | 改写 | 收敛为单入口工作台 |
| `14_博主附加服务设计.md` | 后置 | 暂不进入当前主线，必要能力抽取后归档 |

### 8.4 验收指标补充（准确率优先）

| 指标 | 定义 | 阶段 1-3 目标 |
|------|------|---------------|
| 风险识别准确率 | 与人工标注一致的比例 | 持续提升 |
| 漏报率 | 高风险内容未识别比例 | 持续下降 |
| 误报率 | 低风险内容被误判比例 | 持续下降 |
| 平台覆盖有效率 | 已覆盖平台中可稳定输出结果的比例 | 持续提升 |
| 单次预审时延 | 输入到报告输出耗时 | 在可用范围内受控 |

### 8.5 仿真启用与保留条件
- 启用条件：静态风险达到阈值或用户主动选择深度分析。
- 保留条件：仿真相对静态评估在回测中带来稳定准确率提升。
- 降级条件：若提升不稳定，则保留热点关联与实体风险链，减少仿真成本。

### 8.6 执行顺序补充
1. 先改 `01` 与 `04`，统一目标与路线。
2. 再改 `02`、`13`，固化单入口主流程。
3. 再改 `07/08/10/11/12`，统一仿真增强定位。
4. 最后回扫 `03/05/06/09/14`，做一致性清理。

## 九、docs 重构执行手册（按此节逐个改文件）

### 9.1 文档改造总矩阵（最终执行版）

| 文档 | 动作 | 必改点 | 完成标志 |
|------|------|--------|----------|
| `01_产品需求文档(PRD).md` | 改写 | 目标与边界、单入口流程、准确率指标 | PRD 首屏出现“发前风控优先”与指标表 |
| `02_系统架构设计.md` | 改写 | 架构按主链路重排（输入→理解→评估→报告） | 图和章节不再以平台化后台为中心 |
| `03_MVP实施计划(Tasks).md` | 改写 | 任务按准确率收益排序 | 每个任务有“预期准确率收益”字段 |
| `04_V2深化路线图.md` | 改写 | 阶段有 Go/No-Go 规则 | 每阶段都有“继续/暂停条件” |
| `05_参考项目分析与精华提炼.md` | 修订 | 增加“采纳/不采纳/后置”结论 | 每个参考项有落地结论 |
| `06_信号采集层设计.md` | 修订 | 明确后台化，不作为用户主入口 | 文档出现“后台能力”声明 |
| `07_世界构建层设计.md` | 融合瘦身 | 删除独立产品叙事，保留风控增益能力 | 与 `08` 术语一致，不抢主线 |
| `08_仿真运行层设计.md` | 融合瘦身 | 明确按需触发、成本受控 | 文档含触发条件与降级策略 |
| `09_分析决策层设计.md` | 修订 | 增加证据链、置信度、不确定性 | 报告输出结构统一 |
| `10_仿真增强风控设计.md` | 保留增强 | 明确仿真带来的准确率提升验证 | 有回测与对照实验章节 |
| `11_仿真验证与基础迁移设计.md` | 修订 | 验证优先于扩展，迁移服务于主线 | 验证指标先于基础设施叙事 |
| `12_多模态风控设计.md` | 修订 | 跨模态一致性校验必须落地 | 含视频/文案/音频冲突判定 |
| `13_前端升级设计.md` | 改写 | 单入口工作台、单流程交互 | 页面与路由收敛为主入口 |
| `14_博主附加服务设计.md` | 后置 | 仅保留主线可复用能力，其他归档 | 文档标注“后置，不纳入当前里程碑” |

### 9.2 每个文档的统一改写模板（复制即用）

> 用法：改任意 `docs/*.md` 时，先把下面结构贴到文档顶部，再填充内容。

```markdown
## 文档定位
- 本文档在主线中的角色：
- 与“发前风控优先”的关系：

## 本文档边界
- 本文档负责：
- 本文档不负责：

## 对准确率的直接贡献
- 机制1：
- 机制2：
- 验证方式：

## 关键流程/结构
- 输入：
- 处理：
- 输出：

## 依赖与降级
- 依赖：
- 失败降级策略：

## 验收标准
- 指标：
- 阈值：
- 通过条件：
```

### 9.3 统一术语表（避免各文档说法不一致）

| 术语 | 统一定义 |
|------|----------|
| 内容预审 | 用户唯一主入口，提交视频/文案进行发布前风险评估 |
| 静态评估 | 不启动仿真，仅基于内容语义与规则/模型做快速风险判断 |
| 仿真增强 | 在静态评估基础上，使用多Agent推演提升准确率 |
| 高风险内容 | 达到预设阈值，需触发仿真或人工复核 |
| 证据链 | 风险结论对应的原文/画面/音频片段及解释 |
| 置信度 | 模型对风险判断稳定性的量化表达 |

### 9.4 文档级验收清单（改完一篇就打勾）

- 是否出现“发前风控优先”明确表述。
- 是否写清“本文档负责什么/不负责什么”。
- 是否写明对准确率的直接贡献。
- 是否有输入→处理→输出闭环。
- 是否有失败降级策略。
- 是否有可量化验收指标。
- 是否与术语表一致。

### 9.5 推荐执行顺序（防返工）

1. `01`（PRD）
2. `04`（路线图）
3. `02` + `13`（架构与前端入口）
4. `10` + `11` + `12`（仿真增强与验证）
5. `07` + `08`（融合瘦身）
6. `03` + `05` + `06` + `09`（一致性收口）
7. `14`（后置归档）

### 9.6 冲突处理规则（文档间打架时用）

- 若 `PRD` 与其他文档冲突，以 `PRD` 为准。
- 若路线图与技术文档冲突，以“准确率验证优先”原则裁剪。
- 若新想法无法在当前阶段量化收益，放入后置清单，不进入主线。
