# nano-graphrag 深度技术分析

> 基于源码分析（v1.0+）

---

## 1. 项目概述

- **GitHub**: https://github.com/gusye1234/nano-graphrag
- **Star数**: ~2k+
- **主要语言**: Python（100%）
- **License**: MIT
- **一句话描述**: 微软GraphRAG的轻量级重新实现，约1100行核心代码，保留核心功能的同时大幅简化

### 1.1 与微软GraphRAG的对比

| 特性 | 微软GraphRAG | nano-graphrag |
|------|-------------|---------------|
| 代码量 | ~10万行 | **~1100行** |
| 增量插入 | 不支持 | **支持** |
| 社区检测 | Leiden多层 | Leiden单层 |
| 全局搜索 | Map-Reduce | Top-K社区 |
| 双模型 | 不支持 | **支持** |
| 协变量 | 支持 | 不支持 |
| 存储 | 固定 | **可插拔（5种）** |

---

## 2. 核心架构

### 2.1 整体架构

```
┌─────────────────── GraphRAG(dataclass) ──────────────────────┐
│                                                               │
│  insert(text) → chunking → entity_extraction(LLM) → 图构建  │
│                              ↓                                │
│                    community_detection(Leiden)                │
│                              ↓                                │
│                    community_report(LLM)                      │
│                              ↓                                │
│              ┌───────────────┼───────────────┐                │
│          KVStorage     VectorStorage    GraphStorage          │
│         (JSON文件)    (NanoVectorDB)     (NetworkX)           │
│                                                               │
│  query(text, mode) →                                          │
│    local:  实体匹配 → 相关chunks+关系 → LLM生成              │
│    global: Top-K社区报告 → LLM生成                            │
│    naive:  向量检索chunks → LLM生成                           │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| GraphRAG主类 | `graphrag.py` | dataclass风格配置，协调insert/query |
| 核心操作 | `_op.py` | chunking、实体提取、社区报告、查询 |
| LLM封装 | `_llm.py` | OpenAI/Azure/Bedrock |
| 存储抽象 | `base.py` | BaseKVStorage/BaseVectorStorage/BaseGraphStorage |
| 存储实现 | `_storage/` | JSON/NanoVectorDB/HNSW/NetworkX/Neo4j |
| Prompt | `prompt.py` | 所有Prompt模板 |
| 工具函数 | `_utils.py` | MD5哈希、异步限制器、TokenizerWrapper |
| 文本分割 | `_splitter.py` | 按分隔符分块 |

---

## 3. 关键技术实现

### 3.1 增量插入 — 核心优势

```python
async def ainsert(self, string_or_strings):
    # 1. MD5去重
    new_docs = {k: v for k, v in docs.items() if k not in existing_doc_keys}
    if not new_docs: return

    # 2. 分块
    chunks = get_chunks(new_docs, chunk_func, tokenizer_wrapper)
    inserting_chunks = {k: v for k, v in chunks.items() if k not in existing_chunks}

    # 3. 实体提取（只处理新chunk）
    maybe_nodes, maybe_edges = await extract_entities(chunks)

    # 4. 合并到知识图谱
    await _merge_nodes_edges(knowledge_graph_inst, maybe_nodes, maybe_edges)

    # 5. 重新社区检测（全量）
    communities = await _communities(knowledge_graph_inst)

    # 6. 重新生成社区报告（全量）
    community_reports = await _report_communities(communities)
```

### 3.2 实体提取与图谱构建

```python
async def _handle_single_entity_extraction(record, chunk_key):
    if record[0] != '"entity"': return None
    entity_name = clean_str(record[1].upper())
    entity_type = clean_str(record[2].upper())
    entity_description = clean_str(record[3])
    return {
        "entity_name": entity_name,
        "entity_type": entity_type,
        "description": entity_description,
        "source_id": chunk_key
    }
```

**Gleaning机制**: 第一轮提取后追问是否遗漏，最多N轮

### 3.3 双模型策略

| 模型 | 默认 | 用途 |
|------|------|------|
| best_model | gpt-4o | 实体提取、查询响应 |
| cheap_model | gpt-4o-mini | 实体描述摘要、社区报告 |

两个模型都有独立的并发控制（max_async）和token限制。

### 3.4 存储可插拔

```python
# 默认配置
graph = GraphRAG(working_dir="./data")

# 替换向量存储为HNSWLib
from nano_graphrag._storage.vdb_hnswlib import HNSWLibStorage
graph = GraphRAG(working_dir="./data", vector_db_storage_cls=HNSWLibStorage)

# 替换图存储为Neo4j
from nano_graphrag._storage.gdb_neo4j import Neo4jStorage
graph = GraphRAG(working_dir="./data", graph_storage_cls=Neo4jStorage)
```

---

## 4. 与VibeUtopia的关联

### 4.1 可借鉴的技术路线

1. **轻量级GraphRAG** ⭐⭐⭐⭐⭐: 1100行代码，最易理解和定制的起点
2. **增量插入** ⭐⭐⭐⭐⭐: MD5去重+增量chunk处理
3. **存储抽象层** ⭐⭐⭐⭐⭐: 三层抽象，可直接复用
4. **双模型策略** ⭐⭐⭐⭐: 高质量+低成本模型分工
5. **only_need_context** ⭐⭐⭐⭐: 只返回上下文，便于集成

### 4.2 需要避免的坑

| 问题 | 应对方案 |
|------|----------|
| 社区重建开销 | 批量插入而非逐条插入 |
| NetworkX内存限制 | 大规模使用Neo4j后端 |
| 无并发安全 | 使用PostgreSQL/Neo4j |
| 全局搜索简化 | 适合Top-K场景 |
| 缺少协变量 | 如需声明性声明需自研 |

---

## 5. 精华与糟粕

### 精华
1. 极简代码（1100行核心代码）
2. 增量插入（MD5去重）
3. 存储可插拔（5种后端）
4. 双模型策略（效果+成本平衡）
5. only_need_context模式

### 糟粕
1. 社区重建开销（每次insert都重建）
2. 无并发安全（文件存储）
3. 全局搜索简化（只取Top-K）
4. 缺少协变量

---

## 6. 总结

nano-graphrag是**最实用的轻量级GraphRAG实现**，其1100行代码保留了GraphRAG的核心功能。对于VibeUtopia，其增量插入和双模型策略最具参考价值。
