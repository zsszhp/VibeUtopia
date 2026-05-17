# RecurrentGPT 深度技术分析

> 基于源码分析 | 论文: arXiv:2305.13304

---

## 1. 项目概述

- **GitHub地址**: https://github.com/ShengdingHu/RecurrentGPT
- **Star数**: ~500+
- **主要语言**: Python (100%)
- **License**: MIT
- **一句话描述**: 基于递归生成架构的长文本写作系统，通过短期记忆（摘要）+ 长期记忆（语义向量库）双轨机制，实现数百章规模小说的连贯自动生成

### 1.1 研究背景

LLM的上下文窗口限制（如GPT-4的8K-32K token）使得直接生成长文本（如10万字以上的小说）变得不可能。现有方案要么截断上下文导致前后矛盾，要么完全遗忘早期内容。RecurrentGPT的核心创新是将人类作家的"记忆管理"模式形式化——作家不需要记住每一个写过的句子，而是维护一个不断演进的故事摘要（短期记忆）和可以随时翻阅的笔记（长期记忆）。

### 1.2 核心创新

1. **双轨记忆系统**: 短期记忆（~400词摘要）+ 长期记忆（所有历史段落，Sentence-BERT编码）
2. **记忆压缩机制**: LLM自主判断哪些信息需要保留/删除，并给出理由
3. **Human-AI协作循环**: 模拟人类作家与AI助手的协作模式
4. **指令生成**: 每次生成3条可能的后续指令，供人类选择或修改

---

## 2. 核心架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                    RecurrentGPT System                            │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   Human Simulator                            │  │
│  │  ┌───────────────┐  ┌────────────────┐  ┌───────────────┐  │  │
│  │  │ select_plan() │→ │ prepare_input()│→ │  step()       │  │  │
│  │  │ 从3条指令中选1 │  │ 扩展段落至2倍  │  │ 修订计划      │  │  │
│  │  └───────────────┘  └────────────────┘  └───────────────┘  │  │
│  └─────────────────────────┬───────────────────────────────────┘  │
│                             │ output                               │
│                             ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   RecurrentGPT Writer                        │  │
│  │                                                              │  │
│  │  ┌────────────┐   ┌──────────────┐   ┌──────────────────┐  │  │
│  │  │ Short      │   │ Long         │   │ Sentence-BERT    │  │  │
│  │  │ Memory     │   │ Memory       │   │ Encoder          │  │  │
│  │  │ (~400词    │   │ (所有历史    │   │ (multi-qa-mpnet  │  │  │
│  │  │  摘要)     │   │  段落列表)   │   │  -base-cos-v1)   │  │  │
│  │  └─────┬──────┘   └──────┬───────┘   └────────┬─────────┘  │  │
│  │        │                 │                     │             │  │
│  │        └────────┬────────┘                     │             │  │
│  │                 ▼                              │             │  │
│  │  ┌──────────────────────────────────────────────┐            │  │
│  │  │ prepare_input()                              │            │  │
│  │  │ 1. 拼接短期记忆 + 前一段落 + 指令             │            │  │
│  │  │ 2. 用指令embedding在长期记忆中top_k=2检索     │◄───────────┘  │
│  │  │ 3. 随机10%概率引入新角色提示                   │            │  │
│  │  └──────────────────┬───────────────────────────┘            │  │
│  │                     ▼                                        │  │
│  │  ┌──────────────────────────────────────────┐                │  │
│  │  │ LLM Generation (GPT-4o)                  │                │  │
│  │  │ 输出:                                     │                │  │
│  │  │ 1. Output Paragraph (~20句)              │                │  │
│  │  │ 2. Output Memory (更新摘要+理由)          │                │  │
│  │  │ 3. Output Instruction ×3 (各~5句)        │                │  │
│  │  └──────────────────┬───────────────────────┘                │  │
│  │                     ▼                                        │  │
│  │  ┌──────────────────────────────────────────┐                │  │
│  │  │ parse_output()                            │                │  │
│  │  │ 正则提取 + 更新记忆 + 重建索引            │                │  │
│  │  └──────────────────────────────────────────┘                │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块划分

| 模块 | 文件 | 职责 |
|------|------|------|
| RecurrentGPT | recurrentgpt.py | 核心Writer，管理双轨记忆、生成段落 |
| Human | human_simulator.py | 模拟人类作家，选择计划、扩展段落 |
| Utils | utils.py | API调用、文本解析、初始化生成 |
| Main | main.py | 主循环，协调Human-Writer交互 |
| Gradio | gradio_server.py | Web交互界面 |

---

## 3. 技术路线详解

### 3.1 短期记忆机制

短期记忆是一个不断演进的文本摘要（~400词），存储在 `self.short_memory` 中。每次生成新段落时，LLM需要：

1. **评估现有记忆**: 逐句分析哪些信息已经不再必要
2. **添加新信息**: 解释哪些新内容需要加入摘要
3. **输出更新后的记忆**: 保持20句以内的精简摘要

关键Prompt设计：
```
Output Memory:
Rational: <解释如何更新内存的理由>
Updated Memory: <更新后的内存>, 约10-20句话
```

这种设计使得记忆是**可解释的**——LLM不仅输出结果，还输出修改理由。这对调试和优化非常有价值。

### 3.2 长期记忆机制

长期记忆存储所有历史段落的原始文本，使用Sentence-BERT（`multi-qa-mpnet-base-cos-v1`）进行向量化：

```python
# 初始化时编码所有历史段落
if self.long_memory and not memory_index:
    self.memory_index = self.embedder.encode(
        self.long_memory, convert_to_tensor=True)

# 每次生成时，用当前指令检索相关历史
instruction_embedding = self.embedder.encode(input_instruction, convert_to_tensor=True)
memory_scores = util.cos_sim(instruction_embedding, self.memory_index)[0]
top_k_idx = torch.topk(memory_scores, k=top_k)[1]  # top_k=2
top_k_memory = [self.long_memory[idx] for idx in top_k_idx]
```

检索后，相关段落作为 "Related Paragraphs" 注入Prompt：
```
Input Related Paragraphs:
Related Paragraphs 1: <最相关的历史段落>
Related Paragraphs 2: <第二相关的历史段落>
```

**关键特性**：
- **动态索引**: 每次生成新段落后，将前一段落加入长期记忆并重建索引
- **语义检索**: 基于余弦相似度，而非关键词匹配
- **top_k=2**: 只取最相关的2段，避免上下文过长

### 3.3 记忆更新策略

记忆更新是整个系统最核心的创新。LLM在每次生成时需要输出一个结构化的记忆更新：

```python
def parse_output(self, output):
    output_paragraph = get_content_between_a_b('Output Paragraph:', 'Output Memory', output)
    output_memory_updated = get_content_between_a_b('Updated Memory:', 'Output Instruction:', output)
    self.short_memory = output_memory_updated  # 直接替换短期记忆
    # 解析3条指令...
    
    # 关键：将前一段落追加到长期记忆
    self.long_memory.append(self.input["output_paragraph"])
    self.memory_index = self.embedder.encode(self.long_memory, convert_to_tensor=True)
```

**记忆压缩的本质**：LLM从"具体描述"中提取"关键信息"。例如：
- 输入记忆: "张三走进了咖啡店，点了一杯拿铁，坐在靠窗的位置，看着窗外的雨"
- 输出记忆: "张三在咖啡店里"（保留地点和人物，丢弃细节）

### 3.4 Human-AI协作循环

系统设计了精妙的Human-in-the-loop机制：

```
迭代循环:
  1. Writer(RecurrentGPT) 生成段落P + 3条后续指令(I1,I2,I3)
  2. Human(select_plan) 从I1/I2/I3中选择最有趣的一条
  3. Human(prepare_input) 将选择的指令扩展为更详细的计划
  4. Human(step) 将段落P扩展至2倍长度（~40-50句）
  5. Human(parse_output) 输出扩展段落 + 修订后的计划
  6. 将Human的输出作为Writer的新输入，回到步骤1
```

**Human的Prompt设计**（prepare_input）：
```
1. Extended Paragraph: 将AI写的段落扩展至两倍长度
2. Selected Plan: 复制AI提出的计划
3. Revised Plan: 将选定的计划修订为下一段的提纲
```

这种设计模拟了真实的人类写作流程：AI提供创意草稿，人类进行润色和方向把控。

### 3.5 指令生成机制

RecurrentGPT每次生成3条不同的后续指令，每条约5句：

```
Output Instruction:
Instruction 1: <可能的有趣延续1>, 约5句话
Instruction 2: <可能的有趣延续2>, 约5句话
Instruction 3: <可能的有趣延续3>, 约5句话
```

Prompt中明确要求：
- "Write like a novelist and do not move too fast"
- "Think about what plot can be attractive for common readers"
- "The chapter will contain over 10 paragraphs and the novel will contain over 100 chapters"

这确保了指令既有多样性，又保持故事的连贯性和可读性。

### 3.6 新角色引入机制

系统有10%的概率在每段生成时引入新角色：

```python
if random.random() < new_character_prob:  # 0.1
    new_character_prompt = "If it is reasonable, you can introduce a new character..."
```

这是一个简单但有效的故事丰富化机制，避免角色阵容过于单调。

---

## 4. 数据流与控制流

### 4.1 初始化流程

```
1. 加载init_prompt.json（包含小说类型和主题）
2. GPT-4o生成初始内容：名称 + 大纲 + 前3段 + 摘要 + 3条指令
3. 初始化Human：使用前2段作为历史，第3段作为新段落
4. 初始化RecurrentGPT Writer：
   - short_memory = 初始摘要
   - long_memory = [段落1, 段落2]
   - memory_index = encode(long_memory)
```

### 4.2 主循环数据流

```
Writer.step():
  input = {previous_paragraph, instruction, short_memory}
    → prepare_input(): 检索长期记忆，构建完整Prompt
    → GPT-4o生成: {new_paragraph, updated_memory, 3 instructions}
    → parse_output(): 提取结果，更新记忆
    → 将previous_paragraph追加到长期记忆
  output = {new_paragraph, updated_memory, 3 instructions}

Human.step():
  input = {writer_output_paragraph, writer_instruction, memory}
    → select_plan(): 从3条指令中选1条
    → prepare_input(): 构建扩展Prompt
    → GPT-4o生成: {extended_paragraph, selected_plan, revised_plan}
    → parse_output(): 提取结果
  output = {extended_paragraph, revised_plan}
```

---

## 5. Prompt设计分析

### 5.1 Writer Prompt结构

Writer的Prompt是一个精心设计的结构化模板，包含：

1. **角色设定**: "I need you to help me write a novel"
2. **记忆说明**: 解释短期记忆的作用和存储要求
3. **输入部分**: Input Memory + Input Paragraph + Input Instruction + Related Paragraphs
4. **输出格式**: 严格的三段式输出（段落+记忆+指令）
5. **约束条件**: 
   - 段落约20句
   - 记忆不超过20句（500词）
   - 每条指令约5句
6. **写作指导**: "Write like a novelist", "do not move too fast"

### 5.2 关键Prompt技巧

- **元认知要求**: 要求LLM解释记忆更新的理由（"Rational"部分）
- **长度控制**: 明确的句数约束（"around 20 sentences"）
- **长期视角**: 提醒LLM这只是开始，留下未来故事空间
- **角色引入**: 条件性提示（10%概率）

---

## 6. 与VibeUtopia项目的关联与借鉴

### 6.1 记忆管理架构

RecurrentGPT的双轨记忆系统对VibeUtopia的Agent记忆设计有直接参考价值：

| RecurrentGPT概念 | VibeUtopia对应 |
|-----------------|---------------|
| 短期记忆（摘要） | Agent的当前状态/人格摘要 |
| 长期记忆（历史） | Agent的历史交互记录 |
| 语义检索 | 基于上下文的记忆召回 |
| 记忆压缩 | 定期总结/遗忘机制 |

### 6.2 人格演化

RecurrentGPT的记忆更新机制（LLM自主决定保留/丢弃哪些信息）可以借鉴到VibeUtopia的Agent人格演化中：
- Agent不应记住所有交互，而是提取关键特征
- 记忆更新应有"理由"，便于调试和审计
- 短期摘要 + 历史检索的双层架构适合长期运行的Agent

### 6.3 协作式内容生成

Human-AI协作循环的设计思路可用于VibeUtopia的多Agent协作：
- Agent生成多个候选方案
- 协调Agent（类似Human）选择最优方案
- 选中的方案被进一步细化和扩展

### 6.4 指令/计划的递归生成

每次生成3条后续指令的机制，类似于VibeUtopia中Agent的目标分解：
- 当前任务完成后，自动生成多个可能的下一步
- 根据上下文选择最合适的方向
- 保持长期目标的一致性

---

## 7. 精华与糟粕

### 7.1 精华（值得学习）

1. **记忆压缩的可解释性**: 要求LLM输出更新理由，这在AI系统中非常罕见且有价值
2. **双轨记忆设计**: 短期摘要保证效率，长期存储保证完整性
3. **结构化输出格式**: 严格的输出模板使解析稳定可靠
4. **Human-in-the-loop**: 不追求全自动化，在关键决策点引入人类判断
5. **简单而有效**: 整个系统核心代码不到200行，没有复杂的训练或微调

### 7.2 糟粕（需要改进）

1. **记忆压缩质量不稳定**: LLM的摘要质量取决于Prompt，可能丢失关键信息
2. **长期记忆线性增长**: 随着生成进行，长期记忆列表不断增长，检索效率下降
3. **无纠错机制**: 一旦LLM生成错误内容，错误会累积传播
4. **上下文窗口限制**: 即使有记忆系统，单次Prompt仍受窗口限制
5. **角色一致性**: 长时间生成后，角色性格和行为可能前后矛盾
6. **缺乏全局规划**: 系统只有局部的"下一条指令"，没有全局故事大纲的约束

### 7.3 改进方向

1. **分层记忆**: 增加"章节级"摘要，形成段落→章节→全书的三层记忆
2. **角色档案**: 为每个角色维护独立的状态档案，确保一致性
3. **回溯修正**: 允许系统在发现矛盾时回溯修改之前的记忆
4. **图结构记忆**: 用知识图谱替代线性列表，表示角色关系和事件因果

---

## 8. 总结

RecurrentGPT是一个优雅地解决了LLM长文本生成记忆限制的系统。其核心贡献——双轨记忆系统（短期摘要+长期语义检索）——不仅适用于小说生成，也适用于任何需要长期连贯性的AI任务。

对于VibeUtopia项目，RecurrentGPT的最大启示是：**记忆不是存储，而是压缩和检索的艺术**。Agent的记忆系统不应是简单的对话历史记录，而应是一个不断演进、可解释、分层的知识结构。

**关键指标**:
- 代码量: ~300行核心代码
- 记忆压缩比: ~20:1（从完整段落到摘要）
- 检索精度: top_k=2的余弦相似度
- 生成质量: 可生成100+章节的连贯小说
