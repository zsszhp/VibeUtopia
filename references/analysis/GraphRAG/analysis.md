# GraphRAG 深度技术分析

## 项目概述
- GitHub地址：https://github.com/microsoft/graphrag
- Star数：~25k+
- 主要语言：Python (88.4%), Jupyter Notebook (11.6%)
- License：MIT
- 一句话描述：微软研究院出品的基于知识图谱的RAG系统，通过LLM从非结构化文本中提取实体和关系构建知识图谱，利用社区检测和层次化摘要实现全局和局部查询

## 核心架构
- 整体架构图（文字描述）：
  ```
  ┌─────────────────────── Indexing Pipeline ───────────────────────┐
  │                                                                  │
  │  原始文档 → 文本分块 → 实体/关系提取(LLM) → 知识图谱构建       │
  │                              ↓                                   │
  │                    社区检测(Leiden算法)                           │
  │                              ↓                                   │
  │                    社区报告生成(LLM)                              │
  │                              ↓                                   │
  │                    文本单元→实体→关系→社区→报告 嵌入化           │
  └──────────────────────────────────────────────────────────────────┘
  
  ┌─────────────────────── Query Pipeline ───────────────────────────┐
  │                                                                  │
  │  Local Search:  查询 → 实体匹配 → 相关文本单元+关系 → LLM生成  │
  │  Global Search: 查询 → 社区报告Map → 中间摘要Reduce → LLM生成  │
  │  Drift Search:  查询 → 实体匹配+社区上下文 → 迭代扩展 → LLM   │
  └──────────────────────────────────────────────────────────────────┘
  ```

- 核心模块划分和职责：
  - `packages/graphrag/graphrag/config/`：配置系统，定义indexing和query的所有参数
  - `packages/graphrag/graphrag/data_model/`：数据模型（Entity/Relationship/Community/CommunityReport/TextUnit/Covariate）
  - `packages/graphrag/graphrag/graphs/`：图算法（Leiden社区检测、模块度计算、连通分量、度计算）
  - `packages/graphrag/graphrag/query/`：查询引擎
    - `local_search/`：局部搜索，基于实体匹配检索相关上下文
    - `global_search/`：全局搜索，Map-Reduce模式遍历社区报告
    - `drift_search/`：DRIFT搜索，结合局部和全局的迭代搜索
    - `context_builder/`：上下文构建器，组装检索结果
  - `packages/graphrag-vectors/`：向量存储抽象层，支持LanceDB/Azure AI Search/CosmosDB
  - `packages/graphrag-storage/`：表存储抽象层，支持Parquet/CSV/CosmosDB/Azure Blob

- 数据流和控制流：
  1. **Indexing**：文档输入 → 分块(tiktoken) → LLM提取实体和关系 → 构建图 → Leiden社区检测 → LLM生成社区报告 → 嵌入所有数据 → 存储到Parquet/向量库
  2. **Local Search**：查询 → 提取查询中的实体 → 匹配知识图谱中的实体 → 获取关联的文本单元、关系、协变量 → 组装上下文 → LLM生成答案
  3. **Global Search**：查询 → 遍历所有社区报告 → Map阶段：每个社区生成中间答案 → Reduce阶段：汇总中间答案 → LLM生成最终答案

## 关键技术实现

### 知识图谱构建与实体关系提取
- 实现原理：
  - 文本分块后，每个chunk通过LLM提取实体和关系
  - 实体提取Prompt要求LLM输出标准化的(entity_name, entity_type, description)三元组
  - 关系提取输出(source, target, relationship, description)四元组
  - 支持多轮提取（gleaning）：第一轮提取后，LLM追问"是否还有遗漏的实体"，最多gleaning N轮
  - 实体和关系的描述通过map-reduce方式摘要合并（同一实体在不同chunk中的描述）
- 核心代码逻辑：
  ```
  # 伪代码：实体关系提取
  for chunk in text_chunks:
      extraction_result = llm.extract_entities(chunk, prompt=ENTITY_EXTRACTION_PROMPT)
      for record in extraction_result:
          if record.type == "entity":
              graph.add_node(record.name, type=record.type, description=record.description)
          elif record.type == "relationship":
              graph.add_edge(record.source, record.target, relation=record.relation, description=record.description)
      # Gleaning: 追问是否遗漏
      for i in range(max_gleaning):
          additional = llm.ask("Any more entities? Previous: {extraction_result}")
          if no_additional: break
  ```

### Leiden社区检测与层次化摘要
- 实现原理：
  - 使用Leiden算法对知识图谱进行社区检测，发现层次化的社区结构
  - 每个社区生成一份摘要报告（Community Report），由LLM基于社区内所有实体和关系生成
  - 社区报告包含：标题、摘要、影响力、关键实体等结构化信息
  - 层次化：社区可以嵌套，从局部小社区到全局大社区
- 配置方式：
  ```yaml
  # settings.yaml
  entity_extraction:
    max_gleanings: 1  # 追问轮数
  community_reports:
    max_length: 2000  # 报告最大长度
    max_input_length: 8000  # 输入最大长度
  clustering:
    max_cluster_size: 10  # 最大社区大小
  ```

### 多种搜索模式
- **Local Search**：查询 → 提取查询实体 → 匹配图谱实体 → 获取关联文本单元+关系+协变量 → 组装上下文 → LLM生成
  - 适合：具体事实查询，如"某用户发布了什么违规内容"
- **Global Search**：查询 → 遍历社区报告 → Map-Reduce → 生成答案
  - 适合：宏观趋势查询，如"最近一周违规内容的整体趋势"
  - Map阶段：每个社区报告独立生成中间答案和重要性评分
  - Reduce阶段：按重要性排序，汇总中间答案生成最终答案
- **DRIFT Search**：结合Local和Global的迭代搜索
  - 先用查询实体匹配局部上下文
  - 再通过社区报告扩展到全局上下文
  - 迭代多轮直到收敛

### 向量存储与嵌入
- 实现原理：
  - 所有数据（文本单元、实体、关系、社区报告）都进行嵌入
  - 支持多种向量存储后端：LanceDB（默认）、Azure AI Search、CosmosDB
  - 查询时通过向量相似度检索相关实体/文本单元
  - 嵌入模型默认使用text-embedding-3-small

## 对VibeUtopia的参考价值

### 可借鉴的技术路线
- **知识图谱构建**：社交媒体内容中的用户关系、话题传播、内容引用等天然适合图谱建模，可参考GraphRAG的实体关系提取流程构建风控知识图谱
- **社区检测**：通过Leiden算法发现用户社群/话题社区，识别潜在的协同违规行为和风险传播路径
- **多粒度查询**：Local Search适合查具体违规事件，Global Search适合分析违规趋势，DRIFT适合复杂风控推理
- **层次化摘要**：社区报告的层次化结构可用于风控报告的自动生成（从具体事件到整体趋势）
- **Map-Reduce全局查询**：风控场景中需要全局视角（如"本周最活跃的违规类型"），Global Search的Map-Reduce模式非常适合

### 需要避免的坑
- **Indexing成本极高**：GraphRAG的索引过程需要大量LLM调用（实体提取+社区报告），微软官方也警告"start small"，VibeUtopia需要评估增量更新的成本
- **增量更新困难**：GraphRAG的索引是全量批处理，不支持真正的增量更新——新增文档需要重新运行整个pipeline或至少重新计算社区
- **延迟高**：Global Search需要遍历所有社区报告，在社区数量多时延迟很高，不适合实时风控
- **存储格式限制**：默认使用Parquet文件存储，不适合在线查询场景，需要迁移到数据库
- **LLM依赖重**：实体提取和社区报告都依赖LLM，LLM质量直接影响图谱质量

## 精华与糟粕
| 类别 | 内容 | 说明 |
|------|------|------|
| 精华 | 知识图谱+RAG融合 | 图结构增强检索，支持多跳推理 |
| 精华 | Leiden社区检测 | 自动发现层次化社区结构，无需人工定义 |
| 精华 | Map-Reduce全局查询 | 优雅解决全局性问题回答，避免上下文窗口限制 |
| 精华 | DRIFT搜索 | 结合局部和全局的迭代搜索，兼顾精度和广度 |
| 精华 | 多种存储后端 | LanceDB/Azure AI Search/CosmosDB可插拔 |
| 糟粕 | Indexing成本极高 | 大量LLM调用，不适合频繁更新的场景 |
| 糟粕 | 增量更新缺失 | 全量批处理模式，新增内容需要重建索引 |
| 糟粕 | 实时性差 | Global Search延迟高，不适合实时风控 |
| 糟粕 | 代码架构复杂 | 多包结构(graphrag/graphrag-vectors/graphrag-storage)，理解和修改成本高 |
