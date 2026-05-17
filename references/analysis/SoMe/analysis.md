# SoMe 深度技术分析

> 基于源码分析 + AAAI 2026论文

---

## 1. 项目概述

- **GitHub**: https://github.com/LivXue/SoMe
- **Star数**: ~50+
- **主要语言**: Python
- **License**: Apache-2.0
- **论文**: AAAI 2026收录 — "SoMe: A Comprehensive Benchmark for Social Media Agent"
- **一句话描述**: 面向LLM社交媒体Agent的综合评测基准，涵盖8大任务、900万+帖子、6591用户画像

### 1.1 研究背景

SoMe填补了社交媒体Agent评测领域的空白。现有的Agent评测基准（如AgentBench、ToolBench）主要关注通用能力，缺乏对社交媒体场景的针对性评估。SoMe首次系统性地定义了社交媒体Agent的8大核心能力维度。

---

## 2. 核心架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────┐
│                     SoMe Benchmark                             │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              8 Social Media Agent Tasks                 │  │
│  │                                                         │  │
│  │  Post-centered (内容中心):                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐           │  │
│  │  │ RED: 实时事件    │  │ SES: 流式事件    │           │  │
│  │  │ 检测             │  │ 摘要             │           │  │
│  │  ├──────────────────┤  ├──────────────────┤           │  │
│  │  │ MID: 虚假信息   │  │                  │           │  │
│  │  │ 检测             │  │                  │           │  │
│  │  └──────────────────┘  └──────────────────┘           │  │
│  │                                                         │  │
│  │  User-centered (用户中心):                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐           │  │
│  │  │ UBP: 用户行为   │  │ UEA: 用户情感    │           │  │
│  │  │ 预测             │  │ 分析             │           │  │
│  │  ├──────────────────┤  ├──────────────────┤           │  │
│  │  │ UCS: 用户评论   │  │                  │           │  │
│  │  │ 模拟             │  │                  │           │  │
│  │  └──────────────────┘  └──────────────────┘           │  │
│  │                                                         │  │
│  │  Comprehensive (综合):                                  │  │
│  │  ┌──────────────────┐  ┌──────────────────┐           │  │
│  │  │ MCR: 媒体内容    │  │ SMQ: 社交媒体    │           │  │
│  │  │ 推荐             │  │ 问答             │           │  │
│  │  └──────────────────┘  └──────────────────┘           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ SocialMedia  │  │  Qwen-Agent  │  │  Evaluation      │   │
│  │ Agent        │  │  Framework   │  │  Scripts         │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Tools        │  │  Datasets    │  │  Knowledge Base  │   │
│  │ (搜索/分析)  │  │  (9M+ posts) │  │  (Embedding)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 八大评测任务详解

#### Post-centered（以内容为中心）

**RED - Realtime Event Detection（实时事件检测）**:
- 从实时社交媒体流中检测正在发生的事件
- 需要理解事件的时效性和重要性
- 评估指标：事件检测准确率、时效性

**SES - Streaming Event Summary（流式事件摘要）**:
- 对持续演化的事件生成增量摘要
- 需要跟踪事件的发展脉络
- 评估指标：摘要完整性、时效性

**MID - Misinformation Detection（虚假信息检测）**:
- 识别和标记潜在的虚假或误导性信息
- 结合知识库检索和LLM推理
- **对VibeUtopia最直接相关**
- 评估指标：检测准确率、误报率

#### User-centered（以用户为中心）

**UBP - User Behavior Prediction（用户行为预测）**:
- 预测用户在社交媒体上的下一步行为
- 需要理解用户的行为模式
- 评估指标：行为预测准确率

**UEA - User Emotion Analysis（用户情感分析）**:
- 分析用户在社交媒体上的情感状态
- 需要理解隐含情感和讽刺
- 评估指标：情感分类准确率

**UCS - User Comment Simulation（用户评论模拟）**:
- 模拟真实用户对内容的评论回复
- 需要理解用户画像和社交语境
- **可用于生成风控测试数据**
- 评估指标：评论真实性、多样性

#### Comprehensive（综合）

**MCR - Media Content Recommend（媒体内容推荐）**:
- 为用户推荐相关内容
- 需要理解用户兴趣和内容特征
- 评估指标：推荐准确率、多样性

**SMQ - Social Media QA（社交媒体问答）**:
- 回答关于社交媒体内容的复杂问题
- 需要多跳推理和信息整合
- 评估指标：回答准确率

### 2.3 SocialMediaAgent设计

```python
class SocialMediaAgent(Agent):
    def __init__(self, llm, function_list, system_message, name, description, files):
        super().__init__(function_list=function_list, llm=llm,
                         system_message=system_message, name=name,
                         description=description)
        self.mem = Memory(llm=llm, files=files)

    def _run(self, messages, lang='zh'):
        num_llm_calls_available = MAX_LLM_CALL_PER_RUN  # 默认20
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

### 2.4 数据集规模

| 数据集 | 规模 | 用途 |
|--------|------|------|
| 社交媒体帖子 | 900万+ | 训练和评测 |
| 用户画像 | 6591个 | 用户中心任务 |
| 外部报告 | 25686份 | 知识库（虚假信息检测） |
| 评估样本 | 每个任务数百个 | 标准化评测 |

---

## 3. 关键技术实现

### 3.1 虚假信息检测（MID）任务设计

**实现原理**: MID任务是SoMe中最接近VibeUtopia需求的设计：

```
内容输入
  → Agent调用知识库检索工具（搜索相关事实）
  → Agent调用内容分析工具（分析内容特征）
  → LLM综合判断是否为虚假信息
  → 输出：标签（虚假/真实/不确定）+ 理由 + 证据
```

**评估方法**:
- LLM-as-Judge：使用LLM评估检测结果的合理性
- 精确匹配：与标注数据对比

### 3.2 基于嵌入的知识库

```python
# 知识库配置
embedding_model_path = "Qwen/Qwen3-Embedding-4B"
knowledge_path = "./database/knowledge_data/knowledge_base.json"
knowledge_emb_path = "./database/emb_data/knowledge_base.npy"

# 知识库检索
def search_knowledge(query, top_k=5):
    query_emb = embed(query)
    similarities = cosine_similarity(query_emb, knowledge_embeddings)
    top_indices = np.argsort(similarities)[-top_k:]
    return [knowledge_base[i] for i in top_indices]
```

### 3.3 LLM-as-Judge评估范式

SoMe广泛使用LLM-as-Judge进行评估，适用于难以精确匹配的主观评测：

```python
judge_prompt = f"""
请评估以下Agent回答的质量：

问题：{question}
Agent回答：{agent_answer}
参考答案：{reference_answer}

评分维度（1-5分）：
1. 准确性：回答是否正确
2. 完整性：是否覆盖了所有要点
3. 相关性：是否切题
4. 可解释性：是否提供了合理的解释

请输出JSON格式的评分。
"""
```

---

## 4. 技术路线分析

### 4.1 与VibeUtopia项目的详细关联

**1. MID虚假信息检测** ⭐⭐⭐⭐⭐:
- SoMe的MID任务设计可直接参考用于VibeUtopia的风控Agent评测
- 知识库检索 + LLM推理的检测流程与VibeUtopia一致
- 评估指标（准确率、误报率）可直接采用

**2. 用户评论模拟（UCS）** ⭐⭐⭐⭐:
- 模拟真实用户评论的能力可用于生成风控测试数据
- 基于用户画像的评论生成，增加测试数据的多样性

**3. Agent工具调用循环** ⭐⭐⭐⭐:
- LLM→工具调用→结果整合循环是风控Agent的典型工作流
- VibeUtopia可直接采用此模式

**4. 知识库+RAG方案** ⭐⭐⭐⭐:
- 基于嵌入的知识库检索方案
- 可用于VibeUtopia的法规知识库和风险案例库

**5. LLM-as-Judge评估** ⭐⭐⭐⭐:
- 适用于风控场景中难以精确匹配的评估需求
- 可评估Agent审核决策的合理性

**6. 八大任务评测体系** ⭐⭐⭐:
- 任务分类思想（内容/用户/综合）可用于设计VibeUtopia的风控Agent评测基准
- 但VibeUtopia需要更聚焦于风控相关任务

---

## 5. 需要避免的坑

| 问题 | 具体表现 | 应对方案 |
|------|----------|----------|
| 非仿真框架 | 专注评测，不包含仿真运行环境 | 与OASIS/AgentSociety组合使用 |
| 依赖Qwen-Agent | Agent实现深度绑定Qwen-Agent | 迁移到自研Agent框架 |
| 无社交网络动态 | 静态评测，不模拟演化 | 需要动态仿真补充 |
| 数据集偏微博 | 主要针对微博格式 | 适配其他平台格式 |
| 单Agent评测 | 不支持多Agent交互仿真 | 仅用于评测，不用于仿真 |

---

## 6. 精华与糟粕

### 6.1 精华

| 序号 | 内容 | 说明 |
|------|------|------|
| 1 | **八大任务评测体系** | 最全面的社交媒体Agent评测基准 |
| 2 | **MID虚假信息检测** | 直接可用于风控场景 |
| 3 | **Agent工具调用循环** | 标准的LLM Agent工作流 |
| 4 | **基于嵌入的知识库** | RAG方案可直接参考 |
| 5 | **900万+帖子数据集** | 大规模真实社交媒体数据 |
| 6 | **AAAI 2026论文** | 学术认可度高 |
| 7 | **LLM-as-Judge评估** | 适用于主观性强的评测 |
| 8 | **UCS评论模拟** | 可生成风控测试数据 |

### 6.2 糟粕

| 序号 | 内容 | 说明 |
|------|------|------|
| 1 | 非仿真框架 | 无法运行动态仿真 |
| 2 | 深度绑定Qwen-Agent | 迁移成本高 |
| 3 | 无社交网络动态 | 静态评测，不模拟演化 |
| 4 | 数据集偏微博 | 平台覆盖面有限 |
| 5 | 单Agent评测 | 不支持多Agent交互 |

---

## 7. 总结

SoMe是**首个系统性的社交媒体Agent评测基准**，填补了行业空白。对于VibeUtopia，SoMe的最大价值在于：

1. **MID任务设计**（风控Agent评测的参考标准）
2. **LLM-as-Judge评估**（主观评测的最佳实践）
3. **知识库+RAG方案**（法规知识库的设计参考）
4. **UCS评论模拟**（测试数据生成）

但SoMe是评测基准而非仿真框架，VibeUtopia需要将其与仿真框架（如AgentSociety/OASIS）组合使用。
