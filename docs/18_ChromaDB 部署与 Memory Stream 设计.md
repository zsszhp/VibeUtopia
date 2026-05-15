# ChromaDB 部署与 Memory Stream 设计

**创建日期**: 2026-05-15  
**阶段**: 阶段 3 - 模型优化 + 人生故事生成  
**状态**: ✅ 设计完成

---

## 1. 部署架构

### 1.1 ChromaDB 内嵌式部署

ChromaDB 采用内嵌式（Embedded）部署模式，零运维负担，与 FastAPI 后端同进程运行。

```
┌────────────────────────────────────────────────┐
│           FastAPI Backend Process              │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │      ChromaDB PersistentClient          │   │
│  │  ┌───────────────────────────────────┐  │   │
│  │  │  HNSW Index (Cosine Similarity)   │  │   │
│  │  │  - memory_stream collection       │  │   │
│  │  │  - agent_profiles collection      │  │   │
│  │  └───────────────────────────────────┘  │   │
│  └──────────────────┬──────────────────────┘   │
│                     │                           │
│            Persist to:                          │
│         ./data/chroma_memories/                 │
└────────────────────────────────────────────────┘
```

**优势**:
- 零部署：无需 Docker 容器，Python 库直接集成
- 低延迟：进程内调用，无网络开销
- 自动持久化：数据自动保存到磁盘
- 免运维：无独立服务需要监控

### 1.2 目录结构

```
/workspace/
├── data/
│   ├── chroma_memories/        # ChromaDB 持久化目录
│   │   ├── Chroma.sqlite3      # 元数据数据库
│   │   └── chroma/             # 向量索引文件
│   ├── vibeutopia.db           # SQLite 数据库（降级用）
│   └── agents/
│       └── {agent_id}/
│           └── story.md        # 完整人生故事
```

---

## 2. Memory Stream 存储架构

### 2.1 双层存储设计

| 存储层 | 工具 | 用途 | 优势 |
|--------|------|------|------|
| **向量层** | ChromaDB | 语义检索（Relevance 因子） | 余弦相似度、HNSW 索引 |
| **元数据层** | MySQL/SQLite | 完整元数据、Recency/Importance 排序 | 关系型查询、事务支持 |

**工作流程**:
```
1. ChromaDB向量检索 → 获取候选记忆（多取 3 倍）
2. MySQL加载完整元数据 → 获取created_at, importance等
3. 三因子评分 → Recency(0.5) + Importance(0.3) + Relevance(0.2)
4. 重排 → 返回Top-K
5. 更新last_accessed → Recency衰减依赖此字段
```

### 2.2 记忆条目结构

```python
class MemoryEntry:
    memory_id: str              # UUID
    agent_id: str               # 所属 Agent
    content: str                # 记忆内容
    memory_type: str            # observation/reflection/plan
    importance: float           # 重要性 0.0-1.0
    timestamp: datetime         # 创建时间
    embedding: List[float]      # 向量（ChromaDB 存储）
    tags: List[str]             # 标签
    access_count: int           # 访问次数
    last_accessed: datetime     # 最后访问时间（Recency 计算用）
```

### 2.3 记忆类型定义

| 类型 | 说明 | 来源 | 重要性范围 | 示例 |
|------|------|------|-----------|------|
| **observation** | 对外部事件的观察 | 仿真中感知到的事件 | 0.1-0.8 | "看到大 VXX 发表了关于 YY 的帖子" |
| **reflection** | 对过往记忆的反思总结 | Reflection 机制触发时生成 | 0.5-1.0 | "我发现自己对政策问题越来越敏感" |
| **plan** | 行为计划 | Agent 自主规划或响应事件 | 0.2-0.6 | "明天要发一篇关于 XX 的深度分析" |

---

## 3. 三因子检索算法

### 3.1 综合评分公式

```
score = 0.5×Recency + 0.3×Importance + 0.2×Relevance
```

### 3.2 Recency（近期性）— 权重 0.5

**指数衰减模型**:
```python
score = e^(-0.05 × hours_since_creation)
```

| 时间 | 分数 |
|------|------|
| 刚创建 | 1.0 |
| 1 小时前 | 0.95 |
| 24 小时前 | 0.30 |
| 7 天前 | 0.0002 |

### 3.3 Importance（重要性）— 权重 0.3

**来源**: LLM 评估或手动指定

| 记忆类型 | 重要性范围 | 示例 |
|---------|-----------|------|
| 日常琐事 | 0.1-0.3 | "早餐吃了面包" |
| 社交互动 | 0.4-0.6 | "和某用户争论了 XX 话题" |
| 重大事件 | 0.7-1.0 | "目睹了 XX 政策的发布" |

### 3.4 Relevance（相关性）— 权重 0.2

**计算**: 查询向量与记忆向量的余弦相似度

```python
relevance = cosine_similarity(query_embedding, memory_embedding)
```

---

## 4. 数据库表设计

### 4.1 MySQL 表结构

```sql
-- Agent 记忆表
CREATE TABLE agent_memories (
    memory_id VARCHAR(36) PRIMARY KEY,
    agent_id VARCHAR(36) NOT NULL,
    memory_type ENUM('observation', 'reflection', 'plan') NOT NULL,
    content TEXT NOT NULL,
    importance DECIMAL(3,2) DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INT DEFAULT 0,
    tags JSON,
    INDEX idx_agent_id (agent_id),
    INDEX idx_memory_type (memory_type),
    INDEX idx_created_at (created_at),
    INDEX idx_agent_type (agent_id, memory_type)
);

-- Agent 人格表（7 层人格元数据）
CREATE TABLE agent_profiles (
    agent_id VARCHAR(36) PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    archetype_base VARCHAR(100),
    tier ENUM('A', 'B', 'C') DEFAULT 'B',
    layer1_basic JSON,
    layer2_values JSON,
    layer3_knowledge JSON,
    layer4_behavior JSON,
    layer5_constraints JSON,
    layer6_relations JSON,
    layer7_state JSON,
    life_story_path VARCHAR(255),
    quality_score DECIMAL(3,2),
    status ENUM('active', 'archived', 'evolved') DEFAULT 'active',
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_platform (platform),
    INDEX idx_tier (tier),
    INDEX idx_status (status)
);
```

### 4.2 ChromaDB Collection 设计

```python
# Collection: memory_stream
{
    "name": "memory_stream",
    "metadata": {
        "hnsw:space": "cosine",  # 余弦相似度
        "hnsw:construction_ef": 128,  # 索引构建参数
        "hnsw:search_ef": 64,  # 检索参数
    },
    "fields": {
        "id": "memory_id",
        "embedding": "embedding (768 维)",
        "document": "content",
        "metadata": {
            "agent_id": str,
            "memory_type": str,
            "importance": float,
            "created_at": ISO8601,
            "tags": JSON,
            "access_count": int,
        }
    }
}
```

---

## 5. 实现代码

### 5.1 MemoryStreamStore 核心类

已有实现位于：`backend/services/persona/memory_stream.py`

**关键方法**:
- `store()`: 单条存储
- `store_batch()`: 批量存储
- `retrieve()`: 三因子检索
- `get_recent()`: 获取最近记忆
- `check_and_trigger_reflection()`: Reflection 触发检查

### 5.2 使用示例

```python
from backend.services.persona.memory_stream import MemoryStreamStore

# 初始化
memory_store = MemoryStreamStore(persist_dir="./data/chroma_memories")

# 存储记忆
memory_id = memory_store.store(
    agent_id="agent_123",
    content="看到微博上关于 AI 监管的讨论，感觉有点担忧",
    memory_type="observation",
    importance=0.7,
    tags=["AI", "监管", "微博"],
)

# 批量存储（从 Life Story 转换）
memories = [
    {"content": "童年经历...", "type": "observation", "importance": 0.8},
    {"content": "价值观反思...", "type": "reflection", "importance": 0.9},
]
memory_ids = memory_store.store_batch(agent_id="agent_123", memories=memories)

# 三因子检索
query = "对 AI 监管的态度"
results = memory_store.retrieve(
    agent_id="agent_123",
    query=query,
    top_k=10,
)

# 获取最近记忆
recent = memory_store.get_recent(agent_id="agent_123", limit=20)
```

---

## 6. Reflection 机制

### 6.1 触发条件

当 Agent 累积的 observation 记忆的重要性之和超过阈值时触发：

```python
IMPORTANCE_THRESHOLD = 10  # 累积重要性阈值

def should_reflect(agent_id: str) -> bool:
    recent_obs = get_recent_unreflected(agent_id)
    cumulative_importance = sum(obs.importance for obs in recent_obs)
    return cumulative_importance >= IMPORTANCE_THRESHOLD
```

### 6.2 Reflection 流程

```
1. 获取触发 Reflection 的记忆集合
2. LLM 生成反思问题（如："这些经历反映了你什么样的价值观？"）
3. 对每个问题，检索相关记忆（Top-5）
4. LLM 生成反思内容
5. 将反思保存为 reflection 类型记忆
6. 重要性自动评估为 0.7-1.0（高层洞察）
```

### 6.3 示例输出

```
输入记忆:
- "看到 AI 公司裁员新闻，感到不安" (importance=0.6)
- "朋友讨论 AI 取代工作，产生共鸣" (importance=0.5)
- "读了一篇 AI 伦理文章，深受启发" (importance=0.7)

Reflection 输出:
"我发现自己对技术发展的态度是谨慎乐观的。虽然担心 AI 可能带来的失业
问题，但也相信它能创造新的机会。这种矛盾心理让我更加注重学习和适
应能力。" (importance=0.9)
```

---

## 7. 性能优化

### 7.1 ChromaDB 配置优化

```python
chromadb.PersistentClient(
    path="./data/chroma_memories",
    settings=chromadb.Settings(
        anonymized_telemetry=False,
        allow_reset=True,
        hnsw:space="cosine",
        hnsw:construction_ef=128,  # 更高精度，更多内存
        hnsw:search_ef=64,         # 检索时的邻域大小
    )
)
```

### 7.2 批量操作

```python
# 批量存储（推荐）
memory_store.store_batch(agent_id, memories)

# 避免逐条存储（性能差 10x）
for memory in memories:
    memory_store.store(agent_id, memory)  # 不推荐
```

### 7.3 定期清理

```sql
-- 删除 90 天前的低重要性记忆（importance < 0.3）
DELETE FROM agent_memories
WHERE created_at < NOW() - INTERVAL 90 DAY
  AND importance < 0.3;
```

---

## 8. 验收标准

### 8.1 功能验收

- [x] ChromaDB 内嵌式部署成功
- [ ] Memory Stream 三因子检索准确率>85%
- [ ] Reflection 机制正常触发
- [ ] 批量存储性能：1000 条记忆<5 秒
- [ ] 检索延迟：Top-10 检索<100ms

### 8.2 测试用例

```python
def test_memory_stream():
    store = MemoryStreamStore()
    
    # 测试 1: 单条存储
    mid = store.store("agent_1", "测试内容", importance=0.8)
    assert mid is not None
    
    # 测试 2: 批量存储
    memories = [{"content": f"内容{i}", "importance": 0.5} for i in range(100)]
    mids = store.store_batch("agent_1", memories)
    assert len(mids) == 100
    
    # 测试 3: 三因子检索
    results = store.retrieve("agent_1", "测试", top_k=10)
    assert len(results) <= 10
    assert "composite_score" in results[0]
    
    # 测试 4: Recency 衰减
    time.sleep(3600)  # 1 小时后
    results2 = store.retrieve("agent_1", "测试", top_k=10)
    assert results2[0]["recency_score"] < results[0]["recency_score"]
```

---

## 9. 下一步

1. ✅ ChromaDB 内嵌式部署设计完成
2. ✅ Memory Stream 存储架构设计完成
3. [ ] 创建数据库迁移脚本
4. [ ] 运行 Memory Stream 完整测试
5. [ ] 集成到 Life Story 生成流程

---

**相关文档**:
- `docs/07_世界构建层设计.md` - 人格工厂与记忆系统详细设计
- `backend/services/persona/memory_stream.py` - Memory Stream 实现
- `backend/services/persona/reflection_engine.py` - Reflection 引擎
