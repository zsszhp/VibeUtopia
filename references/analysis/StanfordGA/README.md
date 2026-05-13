# Stanford Generative Agents

## 项目信息

- **论文**: Generative Agents: Interactive Simulacra of Human Behavior
- **领域**: Agent记忆、行为连贯性

## 项目定位

Stanford Generative Agents论文的核心创新：Memory Stream（记忆流）+ Reflection（反思）机制，使Agent具备长期记忆、自主反思和基于记忆做决策的能力。

## 核心机制

**Memory Stream**：Agent的所有经历以时间线形式存储为记忆条目，每条记忆有：
- 时间戳
- 描述文本
- 重要性分数（Importance，0-10）
- 最近访问时间（Recency，指数衰减）

**三因子检索**：
```
Score = α * Recency + β * Importance + γ * Relevance
```

**Reflection机制**：定期从记忆流中抽取重要记忆，LLM生成高层抽象反思，反思条目也存入记忆流。

## 精华借鉴

| 精华项 | 说明 |
|--------|------|
| Memory Stream架构 | 时间线形式存储所有经历 |
| 三因子检索 | Recency+Importance+Relevance加权 |
| Reflection反思机制 | 定期生成高层抽象反思 |

## 采纳决策

| 项 | 决策 | 目标阶段 |
|----|------|---------|
| Memory Stream | 采纳 | 3-4 |
| 三因子检索 | 采纳 | 3-4 |
| Reflection反思机制 | 采纳 | 4 |

## 详细分析

见 [analysis.md](./analysis.md)
