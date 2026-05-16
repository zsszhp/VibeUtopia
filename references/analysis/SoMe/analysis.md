# SoMe 深度技术分析

## 项目概述
- GitHub地址：https://github.com/LivXue/SoMe（原AGI-Edger/SoMe为同一项目的组织迁移）
- Star数：约50+
- 主要语言：Python
- License：Apache-2.0
- 论文：AAAI 2026收录
- 一句话描述项目核心功能：面向LLM社交媒体Agent的综合评测基准，涵盖8大任务、900万+帖子、6591用户画像，系统评估Agent在社交媒体场景中的能力

## 核心架构
- 整体架构图（用文字描述）：

```
┌──────────────────────────────────────────────────────────────┐
│                     SoMe Benchmark                            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              8 Social Media Agent Tasks                 │  │
│  │                                                         │  │
│  │  Post-centered:          User-centered:                │  │
│  │  ┌──────────────────┐    ┌──────────────────┐         │  │
│  │  │ Realtime Event   │    │ User Behavior    │         │  │
│  │  │ Detection (RED)  │    │ Prediction (UBP) │         │  │
│  │  ├──────────────────┤    ├──────────────────┤         │  │
│  │  │ Streaming Event  │    │ User Emotion     │         │  │
│  │  │ Summary (SES)    │    │ Analysis (UEA)   │         │  │
│  │  ├──────────────────┤    ├──────────────────┤         │  │
│  │  │ Misinformation   │    │ User Comment     │         │  │
│  │  │ Detection (MID)  │    │ Simulation (UCS) │         │  │
│  │  └──────────────────┘    └──────────────────┘         │  │
│  │                                                         │  │
│  │  Comprehensive:                                         │  │
│  │  ┌──────────────────┐    ┌──────────────────┐         │  │
│  │  │ Media Content    │    │ Social Media     │         │  │
│  │  │ Recommend (MCR)  │    │ QA (SMQ)         │         │  │
│  │  └──────────────────┘    └──────────────────┘         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ SocialMedia  │  │  Qwen-Agent  │  │  Evaluation      │  │
│  │ Agent        │  │  Framework   │  │  Scripts         │  │
│  │ (agent.py)   │  │  (qwen_agent)│  │  (eval_scripts/) │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Tools        │  │  Datasets    │  │  Knowledge Base  │  │
│  │ (tools/)     │  │  (9M+ posts) │  │  (Embedding)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

- 核心模块划分和职责：
  1. **SocialMediaAgent**：核心Agent实现，继承自Qwen-Agent，支持工具调用和记忆管理
  2. **Tasks模块**：8个独立任务模块，每个包含特定的提示词、工具和评估逻辑
  3. **Tools模块**：社交媒体分析工具集，供Agent调用
  4. **Qwen-Agent框架**：底层Agent框架，提供LLM调用、工具注册、记忆管理
  5. **Evaluation Scripts**：评估脚本，支持LLM-as-Judge和精确匹配两种评估方式
  6. **Datasets**：900万+帖子、6591用户画像、25686外部报告
  7. **Knowledge Base**：基于嵌入的知识库，支持RAG检索

- 数据流和控制流：
  1. 用户指定任务类型和LLM模型
  2. SocialMediaAgent初始化，加载对应任务的工具和系统提示
  3. Agent接收任务查询，通过LLM推理决定调用哪些工具
  4. 工具执行（搜索帖子、检索知识库、分析用户行为等），结果返回Agent
  5. Agent整合工具结果，生成最终回答
  6. 评估脚本对回答进行评分

## 关键技术实现

### 1. SocialMediaAgent设计
- 实现原理：基于Qwen-Agent框架的SocialMediaAgent，核心是LLM驱动的工具调用循环。Agent在每次运行中最多调用MAX_LLM_CALL_PER_RUN（默认20）次LLM
- 核心代码逻辑（来自agent.py）：

```python
class SocialMediaAgent(Agent):
    def __init__(self, llm, function_list, system_message, name, description, files):
        super().__init__(function_list=function_list, llm=llm,
                         system_message=system_message, name=name,
                         description=description)
        self.mem = Memory(llm=llm, files=files)

    def _run(self, messages, lang='zh'):
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN
        while num_llm_calls_available > 0:
            num_llm_calls_available -= 1
            output = self._call_llm(messages, functions=[...], stream=False)
            if output:
                messages.extend(output)
                for out in output:
                    for use_tool, tool_name, tool_args, _ in self._detect_tool(out):
                        if use_tool:
                            tool_result = self._call_tool(tool_name, tool_args)
                            messages.append(FunctionMessage(tool_result))
                if not used_any_tool:
                    break
```

- 配置方式：通过config.py配置嵌入模型路径、知识库路径、数据解析规则、最大LLM调用次数

### 2. 八大评测任务体系
- 实现原理：将社交媒体Agent能力分为三大类八个子任务：
  - **Post-centered（以内容为中心）**：实时事件检测、流式事件摘要、虚假信息检测
  - **User-centered（以用户为中心）**：用户行为预测、用户情感分析、用户评论模拟
  - **Comprehensive（综合）**：媒体内容推荐、社交媒体问答
- 每个任务有独立的数据集、评估指标和工具集

### 3. 虚假信息检测（MID）任务
- 实现原理：Agent需要识别和标记潜在的虚假或误导性信息，结合知识库检索和LLM推理
- 对VibeUtopia的价值：MID任务的设计和评估方法可直接用于VibeUtopia的风控Agent评测

### 4. 基于嵌入的知识库
- 实现原理：使用Qwen3-Embedding-4B模型构建知识库嵌入，支持语义检索。知识库包含25686份外部网站报告
- 核心配置（来自config.py）：

```python
embedding_model_path = "Qwen/Qwen3-Embedding-4B"
knowledge_path = "./database/knowledge_data/knowledge_base.json"
knowledge_emb_path = "./database/emb_data/knowledge_base.npy"
```

### 5. 多模型支持
- 实现原理：通过OpenAI兼容API接口支持多种LLM：Qwen系列、GPT系列、DeepSeek、Claude等，也支持vLLM/Ollama本地部署

## 对VibeUtopia的参考价值

### 可借鉴的技术路线
1. **虚假信息检测任务设计**：SoMe的MID任务是目前最接近VibeUtopia需求的评测设计，其数据集构建、评估指标和Agent工具链可直接参考
2. **Agent工具调用循环**：SocialMediaAgent的LLM→工具调用→结果整合循环是风控Agent的典型工作流，VibeUtopia可直接采用
3. **基于嵌入的知识库**：知识库+嵌入检索的RAG方案，可用于VibeUtopia的法规知识库和风险案例库
4. **八大任务评测体系**：任务分类思想（内容/用户/综合）可用于设计VibeUtopia的风控Agent评测基准
5. **用户评论模拟（UCS）**：模拟真实用户评论的能力可用于生成风控测试数据
6. **LLM-as-Judge评估**：使用LLM作为评判者的评估方法，适用于风控场景中难以精确匹配的评估需求

### 需要避免的坑
1. **SoMe是评测基准而非仿真框架**：SoMe专注于评估Agent能力，不包含仿真运行环境。VibeUtopia需要的是仿真框架+评测基准的组合
2. **依赖Qwen-Agent**：Agent实现深度绑定Qwen-Agent框架，迁移成本较高
3. **缺乏社交网络动态**：SoMe是静态评测，不模拟社交网络的动态演化
4. **数据集偏中文微博**：数据解析规则（config.py中的key2entry）主要针对微博格式，需要适配其他平台
5. **单Agent评测**：每次只评估一个Agent，不支持多Agent交互仿真

## 精华与糟粕
| 类别 | 内容 | 说明 |
|------|------|------|
| 精华 | 八大任务评测体系 | 最全面的社交媒体Agent评测基准 |
| 精华 | 虚假信息检测任务 | 直接可用于风控场景 |
| 精华 | Agent工具调用循环 | 标准的LLM Agent工作流 |
| 精华 | 基于嵌入的知识库 | RAG方案可直接参考 |
| 精华 | 900万+帖子数据集 | 大规模真实社交媒体数据 |
| 精华 | AAAI 2026论文 | 学术认可度高 |
| 精华 | LLM-as-Judge评估 | 适用于主观性强的评测 |
| 糟粕 | 非仿真框架 | 无法运行动态仿真 |
| 糟粕 | 深度绑定Qwen-Agent | 迁移成本高 |
| 糟粕 | 无社交网络动态 | 静态评测，不模拟演化 |
| 糟粕 | 数据集偏微博 | 平台覆盖面有限 |
| 糟粕 | 单Agent评测 | 不支持多Agent交互 |
