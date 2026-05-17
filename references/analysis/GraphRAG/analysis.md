# GraphRAG 深度技术分析

> 基于源码分析 | https://github.com/microsoft/graphrag

---

## 1. 项目概述

- **GitHub地址**: https://github.com/microsoft/graphrag
- **Star数**: ~25k+
- **主要语言**: Python (88.4%), Jupyter Notebook (11.6%)
- **License**: MIT
- **一句话描述**: 微软研究院出品的基于知识图谱的RAG系统，通过LLM从非结构化文本中提取实体和关系构建知识图谱，利用社区检测和层次化摘要实现全局和局部查询

### 1.1 研究背景

传统RAG（检索增强生成）通过向量相似度检索相关文本片段，但有两个根本局限：
1. **局部性**: 只能检索与查询在语义上直接相关的片段，无法回答需要综合多个文档的"全局"问题
2. **缺乏结构**: 纯向量检索忽略了文本中实体间的关系结构

GraphRAG通过构建知识图谱来解决这些问题，将RAG从"检索相关片段"升级为"推理相关知识"。

### 1.2 核心创新

1. **知识图谱构建**: 自动从非结构化文本中提取实体和关系
2. **社区检测**: Leiden算法发现知识图谱中的社区结构
3. **层次化摘要**: 为每个社区生成摘要，支持多层次查询
4. **三种查询模式**: Local（实体级）、Global（社区级）、Drift（混合）

---

## 2. 核心架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        GraphRAG System                                │
│                                                                        │
│  ┌──────────────── Indexing Pipeline ──────────────────────────────┐  │
│  │                                                                  │  │
│  │  原始文档                                                         │  │
│  │     │                                                             │  │
│  │     ▼                                                             │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Text Chunking (文本分块)                              │       │  │
│  │  │ - token_size: 可配置                                  │       │  │
│  │  │ - overlap: 可配置                                     │       │  │
│  │  └──────────────────────┬───────────────────────────────┘       │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Entity & Relationship Extraction (实体/关系提取)     │       │  │
│  │  │ - LLM从每个chunk中提取实体和关系                     │       │  │
│  │  │ - Gleaning: 多轮补充提取                             │       │  │
│  │  │ - 实体合并: 去重+类型投票                            │       │  │
│  │  │ - 关系合并: 权重累加+描述合并                        │       │  │
│  │  └──────────────────────┬───────────────────────────────┘       │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Knowledge Graph Construction (知识图谱构建)           │       │  │
│  │  │ - 节点: 实体 (名称+类型+描述+来源)                   │       │  │
│  │  │ - 边: 关系 (源+目标+描述+权重+来源)                  │       │  │
│  │  │ - 存储: 可配置 (默认Parquet)                         │       │  │
│  │  └──────────────────────┬───────────────────────────────┘       │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Community Detection (社区检测)                        │       │  │
│  │  │ - Leiden算法                                         │       │  │
│  │  │ - 层次化社区结构                                     │       │  │
│  │  │ - 每个社区包含一组相关实体和关系                      │       │  │
│  │  └──────────────────────┬───────────────────────────────┘       │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Community Report Generation (社区报告生成)            │       │  │
│  │  │ - 为每个社区生成结构化摘要报告                        │       │  │
│  │  │ - 层次化: 子社区摘要→父社区摘要                      │       │  │
│  │  └──────────────────────┬───────────────────────────────┘       │  │
│  │                          │                                        │  │
│  │                          ▼                                        │  │
│  │  ┌──────────────────────────────────────────────────────┐       │  │
│  │  │ Embedding & Storage (嵌入和存储)                      │       │  │
│  │  │ - 文本单元嵌入 (chunk content)                        │       │  │
│  │  │ - 实体嵌入 (entity name + description)               │       │  │
│  │  │ - 社区报告嵌入                                       │       │  │
│  │  └──────────────────────────────────────────────────────┘       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────── Query Pipeline ─────────────────────────────────┐  │
│  │                                                                    │  │
│  │  用户查询                                                          │  │
│  │     │                                                             │  │
│  │     ├──────────────────┬──────────────────┐                     │  │
│  │     ▼                  ▼                  ▼                     │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐          │  │
│  │  │ Local    │    │ Global   │    │ Drift            │          │  │
│  │  │ Search   │    │ Search   │    │ Search           │          │  │
│  │  │          │    │          │    │                  │          │  │
│  │  │ 实体匹配 │    │ 社区报告 │    │ 实体+社区上下文  │          │  │
│  │  │ →相关    │    │ Map→     │    │ →迭代扩展        │          │  │
│  │  │ chunks   │    │ Reduce→  │    │ →LLM推理         │          │  │
│  │  │ +关系    │    │ LLM      │    │                  │          │  │
│  │  │ →LLM     │    │          │    │                  │          │  │
│  │  └──────────┘    └──────────┘    └──────────────────┘          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块划分

| 模块 | 职责 |
|------|------|
| Index | 索引管线（分块→提取→图谱→社区→报告） |
| Query | 查询管线（Local/Global/Drift三种模式） |
| LanguageModel | LLM抽象层，支持多种模型 |
| Storage | 存储层（Parquet/LanceDB等） |
| Prompt | Prompt模板管理 |

---

## 3. Indexing管线详解

### 3.1 文本分块

```python
# 默认分块策略
chunk_strategy = {
    "type": "token",
    "size": 1200,      # 每个chunk的token数
    "overlap": 100,    # 重叠token数
    "encoding_model": "cl100k_base"
}
```

分块策略直接影响后续实体提取的质量：
- **太大**: 单个chunk包含太多实体，提取不精确
- **太小**: 上下文不足，实体关系不完整
- **重叠**: 确保跨边界的实体关系不被截断

### 3.2 实体和关系提取

GraphRAG使用精心设计的Prompt模板进行实体提取：

```python
# 实体提取Prompt（简化版）
ENTITY_EXTRACTION_PROMPT = """
Given a text document and a list of entity types, identify all entities 
of those types and all relationships among them.

Steps:
1. Identify all entities with: name, type, description
2. Identify all relationships with: source, target, description, strength
3. Output in structured format

Entity types: {entity_types}
Text: {input_text}
"""
```

**Gleaning机制**: 支持多轮补充提取
```python
# 第一轮提取后，询问是否还有遗漏
CONTINUE_EXTRACTION_PROMPT = "MANY entities were missed in the last extraction. Add them below using the same format:"

# 询问是否继续
IF_LOOP_PROMPT = "It appears some entities may have still be missed. Answer YES | NO"
```

### 3.3 实体合并

```python
def merge_entities(entity_name, new_entities, existing_entity):
    """合并同一名称的多个实体"""
    
    # 类型投票：选择出现频率最高的类型
    all_types = [e['type'] for e in new_entities] + [existing_entity['type']]
    merged_type = Counter(all_types).most_common(1)[0][0]
    
    # 描述合并：拼接所有描述，用分隔符分隔
    all_descriptions = [e['description'] for e in new_entities] + [existing_entity['description']]
    merged_description = GRAPH_FIELD_SEP.join(sorted(set(all_descriptions)))
    
    # 来源合并
    all_sources = [e['source_id'] for e in new_entities] + [existing_entity['source_id']]
    merged_sources = GRAPH_FIELD_SEP.join(set(all_sources))
    
    return {
        'entity_type': merged_type,
        'description': merged_description,
        'source_id': merged_sources
    }
```

### 3.4 社区检测

使用Leiden算法进行层次化社区检测：

```python
import leidenalg
import igraph as ig

# 从知识图谱构建igraph
graph = ig.Graph.from_networkx(knowledge_graph)

# Leiden社区检测
partition = leidenalg.find_partition(
    graph,
    leidenalg.ModularityVertexPartition,
    n_iterations=10
)

# 结果：每个节点被分配到一个社区
communities = {}
for idx, community in enumerate(partition):
    for node_idx in community:
        node_name = graph.vs[node_idx]['name']
        communities[node_name] = idx
```

### 3.5 社区报告生成

为每个社区生成结构化摘要：

```python
COMMUNITY_REPORT_PROMPT = """
You are a helpful assistant generating a report for a community in a knowledge graph.

The community contains the following entities:
{entities}

And the following relationships:
{relationships}

Generate a comprehensive report describing:
1. The main topics and themes
2. Key entities and their roles
3. Important relationships
4. Overall significance

Report:
"""
```

---

## 4. Query管线详解

### 4.1 Local Search

```
查询 → 实体匹配 → 相关文本单元+关系 → LLM生成
```

```python
async def local_search(query, entities_vdb, text_chunks, knowledge_graph):
    # 1. 实体匹配
    entities = await entities_vdb.query(query, top_k=10)
    
    # 2. 获取相关文本单元
    related_chunks = []
    for entity in entities:
        node = await knowledge_graph.get_entity(entity.name)
        chunk_ids = node.source_id.split(GRAPH_FIELD_SEP)
        chunks = await text_chunks.get_by_ids(chunk_ids)
        related_chunks.extend(chunks)
    
    # 3. 获取相关关系
    related_edges = []
    for entity in entities:
        edges = await knowledge_graph.get_entity_edges(entity.name)
        related_edges.extend(edges)
    
    # 4. LLM生成
    context = format_context(related_chunks, related_edges)
    response = await llm.generate(query, context=context)
    
    return response
```

### 4.2 Global Search

```
查询 → 社区报告Map → 中间摘要Reduce → LLM生成
```

```python
async def global_search(query, community_reports):
    # 1. Map: 对每个社区报告生成中间摘要
    intermediate_summaries = []
    for report in community_reports:
        summary = await llm.generate(
            f"Query: {query}\n\nCommunity Report: {report.content}\n\n"
            f"Extract information relevant to the query."
        )
        intermediate_summaries.append(summary)
    
    # 2. Reduce: 合并所有中间摘要
    combined = "\n\n".join(intermediate_summaries)
    
    # 3. 最终生成
    response = await llm.generate(query, context=combined)
    
    return response
```

### 4.3 Drift Search

```
查询 → 实体匹配+社区上下文 → 迭代扩展 → LLM推理
```

Drift Search是GraphRAG的创新查询模式，结合了Local和Global的优点：
1. 先进行实体匹配（Local特性）
2. 扩展到社区上下文（Global特性）
3. 迭代扩展，逐步丰富上下文

---

## 5. Prompt设计分析

### 5.1 实体提取Prompt

GraphRAG的实体提取Prompt设计精良：
- **明确的分步指令**: 先提取实体，再提取关系
- **结构化输出格式**: 使用特殊分隔符
- **多个示例**: 提供3个完整示例
- **类型约束**: 限制实体类型为预定义集合

### 5.2 分隔符设计

```python
DEFAULT_TUPLE_DELIMITER = "<|>"     # 元组内字段分隔
DEFAULT_RECORD_DELIMITER = "##"     # 记录间分隔
DEFAULT_COMPLETION_DELIMITER = "<|COMPLETE|>"  # 完成标记
GRAPH_FIELD_SEP = "<SEP>"           # 图谱字段分隔
```

这些特殊分隔符的选择考虑了：
- 不与自然语言冲突
- 便于正则解析
- 易于理解

---

## 6. 与VibeUtopia项目的关联与借鉴

### 6.1 知识图谱构建

GraphRAG的知识图谱构建管线可以用于VibeUtopia的世界构建：
- 从文档中提取实体和关系
- 自动发现社区结构
- 生成层次化摘要

### 6.2 多模式检索

三种查询模式对应不同的信息需求：
- **Local**: "Alice是谁？" → 实体级信息
- **Global**: "这个数据集的主题是什么？" → 全局概览
- **Drift**: "Alice和Bob之间有什么关系？" → 关系推理

### 6.3 Prompt工程

GraphRAG的Prompt设计（分步指令+结构化输出+多示例）是优秀的Prompt工程实践。

---

## 7. 精华与糟粕

### 7.1 精华

1. **知识图谱增强**: 超越纯向量检索，引入结构化知识
2. **社区检测**: 自动发现知识结构
3. **三种查询模式**: 覆盖不同的信息需求
4. **层次化摘要**: 支持不同粒度的查询
5. **Gleaning机制**: 多轮补充提取提高召回率

### 7.2 糟粕

1. **构建成本高**: Indexing管线需要大量LLM调用
2. **增量更新困难**: 新增文档可能需要重建整个图谱
3. **社区质量依赖**: Leiden算法的参数影响社区质量
4. **存储开销**: 知识图谱+向量+报告，存储需求大

### 7.3 与LightRAG对比

| 特性 | GraphRAG | LightRAG |
|------|----------|----------|
| 代码量 | ~10000行 | ~1100行 |
| 社区检测 | 完整Leiden | 简化版本 |
| 查询模式 | 3种 | 5种 |
| 增量更新 | 不支持 | 支持 |
| 配置复杂度 | 高 | 低 |

---

## 8. 总结

GraphRAG是将知识图谱引入RAG的开创性工作。其核心价值在于**通过结构化知识提升RAG的推理能力**。

**关键指标**:
- 实体提取: 支持多轮Gleaning
- 社区检测: Leiden算法
- 查询模式: Local/Global/Drift三种
- 存储: Parquet + 向量数据库

对于VibeUtopia，GraphRAG的最大借鉴价值在于其**知识图谱构建管线**和**多层次检索策略**。
