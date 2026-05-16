# nano-graphrag 深度技术分析

## 项目概述
- GitHub地址：https://github.com/gusye1234/nano-graphrag
- Star数：~2k+
- 主要语言：Python (100%)
- License：MIT
- 一句话描述：微软GraphRAG的轻量级重新实现，约1100行核心代码，保留核心功能的同时大幅简化代码，支持增量插入和多种存储后端

## 核心架构
- 整体架构图（文字描述）：
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

- 核心模块划分和职责：
  - `nano_graphrag/graphrag.py`：GraphRAG主类，dataclass风格配置，协调insert/query流程
  - `nano_graphrag/_op.py`：核心操作函数（chunking、entity_extraction、community_report、query）
  - `nano_graphrag/_llm.py`：LLM调用封装（OpenAI/Azure/Bedrock）
  - `nano_graphrag/_utils.py`：工具函数（EmbeddingFunc、MD5哈希、异步限制器、TokenizerWrapper）
  - `nano_graphrag/_splitter.py`：文本分割器（按分隔符分块）
  - `nano_graphrag/base.py`：存储抽象基类（BaseKVStorage/BaseVectorStorage/BaseGraphStorage/QueryParam）
  - `nano_graphrag/prompt.py`：所有Prompt模板（实体提取、社区报告、查询响应）
  - `nano_graphrag/_storage/`：存储实现
    - `kv_json.py`：JSON文件KV存储
    - `vdb_nanovectordb.py`：NanoVectorDB向量存储
    - `vdb_hnswlib.py`：HNSWLib向量存储
    - `gdb_networkx.py`：NetworkX图存储
    - `gdb_neo4j.py`：Neo4j图存储
  - `nano_graphrag/entity_extraction/`：可选的DSPy实体提取模块

- 数据流和控制流：
  1. **Insert**：文本 → MD5去重 → token分块 → LLM提取实体/关系 → 合并到知识图谱 → Leiden社区检测 → LLM生成社区报告 → 嵌入存储
  2. **Query (local)**：查询 → 嵌入 → 向量检索相关实体 → 获取关联chunks和关系 → 组装上下文 → LLM生成
  3. **Query (global)**：查询 → 按重要性排序社区报告 → 取Top-K → LLM生成
  4. **Query (naive)**：查询 → 嵌入 → 向量检索chunks → LLM生成

## 关键技术实现

### 增量插入
- 实现原理：
  - 使用MD5哈希作为chunk的唯一标识，避免重复计算
  - 新文档插入时，只处理新的chunk，已有chunk跳过
  - 但每次插入后，社区检测和社区报告需要重新计算（这是主要开销）
- 核心代码逻辑：
  ```python
  async def ainsert(self, string_or_strings):
      # 1. 去重：MD5哈希检查已有文档
      new_docs = {k: v for k, v in docs.items() if k not in existing_doc_keys}
      if not new_docs: return
      
      # 2. 分块
      chunks = get_chunks(new_docs, chunk_func, tokenizer_wrapper, ...)
      inserting_chunks = {k: v for k, v in chunks.items() if k not in existing_chunks}
      
      # 3. 实体提取（只处理新chunk）
      maybe_nodes, maybe_edges = await extract_entities(chunks, ...)
      
      # 4. 合并到知识图谱
      await _merge_nodes_edges(knowledge_graph_inst, maybe_nodes, maybe_edges, ...)
      
      # 5. 重新社区检测（全量）
      communities = await _communities(knowledge_graph_inst)
      
      # 6. 重新生成社区报告（全量）
      community_reports = await _report_communities(communities, ...)
  ```

### 实体提取与图谱构建
- 实现原理：
  - 使用LLM从文本chunk中提取实体和关系
  - 提取结果格式：`("entity", entity_name, entity_type, description)` 和 `("relationship", source, target, relation, description)`
  - 支持gleaning：第一轮提取后追问是否遗漏，最多N轮
  - 实体描述合并：同一实体在不同chunk中的描述通过LLM摘要合并
- 核心代码逻辑：
  ```python
  async def _handle_single_entity_extraction(record, chunk_key):
      if record[0] != '"entity"': return None
      entity_name = clean_str(record[1].upper())
      entity_type = clean_str(record[2].upper())
      entity_description = clean_str(record[3])
      return {"entity_name": entity_name, "entity_type": entity_type, 
              "description": entity_description, "source_id": chunk_key}
  
  async def _handle_entity_relation_summary(name, description, config, tokenizer):
      tokens = tokenizer.encode(description)
      if len(tokens) < summary_max_tokens: return description  # 不需要摘要
      prompt = PROMPTS["summarize_entity_descriptions"].format(entity_name=name, ...)
      summary = await cheap_model_func(prompt, max_tokens=summary_max_tokens)
      return summary
  ```

### 存储抽象与可插拔后端
- 实现原理：三类存储抽象，全部可替换
  - `BaseKVStorage`：键值存储，默认JSON文件，用于LLM缓存和社区报告
  - `BaseVectorStorage`：向量存储，默认NanoVectorDB，用于实体/chunk嵌入检索
  - `BaseGraphStorage`：图存储，默认NetworkX，用于知识图谱操作
- 配置方式：
  ```python
  # 替换向量存储为HNSWLib
  from nano_graphrag._storage.vdb_hnswlib import HNSWLibStorage
  graph = GraphRAG(working_dir="./data", vector_db_storage_cls=HNSWLibStorage)
  
  # 替换图存储为Neo4j
  from nano_graphrag._storage.gdb_neo4j import Neo4jStorage
  graph = GraphRAG(working_dir="./data", graph_storage_cls=Neo4jStorage)
  
  # 自定义LLM
  graph = GraphRAG(working_dir="./data", best_model_func=my_llm_func, cheap_model_func=my_llm_func)
  ```

### 双模型策略
- 实现原理：使用两个LLM模型分工
  - **best_model**（默认gpt-4o）：用于实体提取、查询响应等需要高质量的任务
  - **cheap_model**（默认gpt-4o-mini）：用于实体描述摘要、社区报告生成等可容忍较低质量的任务
  - 两个模型都有独立的并发控制（max_async）和token限制（max_token_size）

## 对VibeUtopia的参考价值

### 可借鉴的技术路线
- **轻量级GraphRAG实现**：如果VibeUtopia需要知识图谱增强的RAG能力，nano-graphrag的1100行代码是最容易理解和定制的起点
- **增量插入设计**：MD5去重+增量chunk处理，适合风控场景中持续新增内容的需求
- **存储抽象层**：BaseKVStorage/BaseVectorStorage/BaseGraphStorage三层抽象，VibeUtopia可直接复用此设计模式，将ChromaDB接入VectorStorage
- **双模型策略**：风控场景中实体提取用高质量模型，摘要生成用低成本模型，平衡效果和成本
- **only_need_context模式**：`QueryParam(only_need_context=True)`只返回检索上下文不生成答案，适合VibeUtopia将检索结果喂给风控智能体而非直接返回用户
- **Naive RAG回退**：支持naive模式作为GraphRAG的降级方案，当图谱构建失败时仍可提供基本检索能力

### 需要避免的坑
- **社区重建开销**：每次insert都需要重新计算社区和报告，频繁插入时性能差
- **NetworkX内存限制**：默认图存储使用NetworkX（内存中），大规模图谱会占用大量内存
- **无并发安全**：文件存储（JSON/NanoVectorDB）不支持多进程并发写入
- **全局搜索简化**：与微软GraphRAG的Map-Reduce不同，nano-graphrag只取Top-K社区报告，可能遗漏重要信息
- **缺少协变量(Covariate)**：未实现微软GraphRAG的协变量功能，无法提取实体的声明性声明

## 精华与糟粕
| 类别 | 内容 | 说明 |
|------|------|------|
| 精华 | 极简代码 | 1100行核心代码，易于理解和定制 |
| 精华 | 增量插入 | MD5去重+增量chunk处理，避免重复计算 |
| 精华 | 存储可插拔 | 三类存储全部可替换，适配不同后端 |
| 精华 | 双模型策略 | 高质量模型+低成本模型分工，平衡效果和成本 |
| 精华 | only_need_context | 只返回检索上下文，便于集成到其他系统 |
| 糟粕 | 社区重建开销 | 每次insert都重建社区，频繁更新场景性能差 |
| 糟粕 | 无并发安全 | 文件存储不支持多进程并发 |
| 糟粕 | 全局搜索简化 | 只取Top-K社区，可能遗漏信息 |
| 糟粕 | 缺少协变量 | 未实现Covariate功能 |
