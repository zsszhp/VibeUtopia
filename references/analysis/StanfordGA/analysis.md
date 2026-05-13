# Stanford Generative Agents 深度分析

## 核心机制

### Memory Stream

Agent的所有经历以时间线形式存储为记忆条目，每条记忆有：
- 时间戳
- 描述文本
- 重要性分数（Importance，0-10）
- 最近访问时间（Recency，指数衰减）

### 三因子检索

当Agent需要回忆时，对每条记忆计算综合得分：
```
Score = α * Recency + β * Importance + γ * Relevance
```

- **Recency**：时间越近分越高（指数衰减）
- **Importance**：LLM评估该记忆的重要性
- **Relevance**：与当前情境的语义相关性（向量相似度）

### Reflection机制

定期从记忆流中抽取重要记忆，LLM生成高层抽象反思（如"我最近对XX话题很关注"），反思条目也存入记忆流，可被后续检索。
