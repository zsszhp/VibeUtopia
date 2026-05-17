# MiroFish 深度技术分析

> 基于源码分析

---

## 1. 项目概述

- **Star数**: 少量
- **主要语言**: Python
- **License**: 未明确
- **一句话描述**: 基于知识图谱的社交Agent系统，使用Zep Cloud构建知识图谱，通过LLM生成Agent人格，实现知识驱动的社交仿真

### 1.1 核心思想

MiroFish的核心是将**知识图谱**与**Agent人格**结合起来：
1. 用知识图谱存储和组织领域知识
2. 用LLM从知识图谱中生成Agent人格
3. Agent基于人格和知识进行社交互动

---

## 2. 核心架构

### 2.1 知识图谱构建管线

```
┌──────────────────────────────────────────────────────────────┐
│                  MiroFish Knowledge Pipeline                  │
│                                                                │
│  原始文档                                                       │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────────────────────────────────────┐                 │
│  │ Zep Cloud 知识图谱                        │                 │
│  │ 1. 创建独立知识图谱                       │                 │
│  │ 2. 本体生成器分析文档                     │                 │
│  │ 3. 设置图谱本体                           │                 │
│  │ 4. 文档分块 → episodes                    │                 │
│  │ 5. Zep自动抽取实体和关系                  │                 │
│  └──────────────────────┬───────────────────┘                 │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────┐                 │
│  │ Agent人格生成                             │                 │
│  │ - 从知识图谱中提取实体特征                │                 │
│  │ - LLM生成Agent Profile                    │                 │
│  │ - user_id, name, bio, personality         │                 │
│  └──────────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 GraphBuilder核心实现

```python
class GraphBuilder:
    def __init__(self, zep_api_key, zep_base_url):
        self.zep_client = ZepClient(api_key=zep_api_key, base_url=zep_base_url)
    
    async def build_graph(self, documents: List[str], graph_id: str) -> Dict:
        # Step 1: 创建知识图谱
        graph = await self.zep_client.graph.create(graph_id=graph_id)
        
        # Step 2: 生成本体
        ontology = await self.ontology_generator.generate(documents)
        
        # Step 3: 设置本体
        await self.zep_client.graph.set_ontology(graph_id, ontology)
        
        # Step 4: 添加文档
        for doc in documents:
            chunks = self.chunk_document(doc)
            for chunk in chunks:
                await self.zep_client.graph.add_episode(
                    graph_id=graph_id,
                    content=chunk
                )
        
        # Step 5: 等待处理完成
        await self.wait_for_processing(graph_id)
        
        return await self.zep_client.graph.get(graph_id)
```

### 2.3 本体生成器

```python
class OntologyGenerator:
    async def generate(self, documents: List[str]) -> Dict:
        """LLM分析文档，生成实体类型和关系类型定义"""
        
        prompt = f"""
        分析以下文档，定义知识图谱的本体（Ontology）：
        
        文档内容:
        {documents}
        
        请输出:
        1. 实体类型列表（精确10个）
        2. 关系类型列表（精确10个）
        3. 每种类型的描述
        
        以JSON格式输出。
        """
        
        response = await self.llm.generate(prompt)
        ontology = json.loads(response)
        
        return {
            "entity_types": ontology["entity_types"],  # 精确10个
            "edge_types": ontology["edge_types"]        # 精确10个
        }
```

---

## 3. Agent人格系统

### 3.1 OasisAgentProfile数据类

```python
@dataclass
class OasisAgentProfile:
    user_id: str      # 唯一标识
    user_name: str    # 用户名
    name: str         # 显示名称
    bio: str          # 个人简介
    personality: str  # 性格描述
    interests: List[str]  # 兴趣列表
    knowledge_areas: List[str]  # 知识领域
```

### 3.2 人格生成流程

```python
class OasisProfileGenerator:
    async def generate_profile(self, graph_id: str, entity_name: str) -> OasisAgentProfile:
        """从知识图谱中的实体生成Agent人格"""
        
        # 获取实体信息
        entity = await self.zep_client.graph.get_entity(graph_id, entity_name)
        
        # 获取相关关系
        edges = await self.zep_client.graph.get_entity_edges(graph_id, entity_name)
        
        # LLM生成人格
        prompt = f"""
        基于以下知识图谱中的实体信息，生成一个社交Agent的人格档案:
        
        实体: {entity.name}
        描述: {entity.description}
        关系: {edges}
        
        生成:
        1. 用户名
        2. 个人简介(bio)
        3. 性格描述
        4. 兴趣列表
        5. 知识领域
        """
        
        response = await self.llm.generate(prompt)
        profile_data = json.loads(response)
        
        return OasisAgentProfile(
            user_id=entity_name,
            user_name=profile_data["user_name"],
            name=entity.name,
            bio=profile_data["bio"],
            personality=profile_data["personality"],
            interests=profile_data["interests"],
            knowledge_areas=profile_data["knowledge_areas"]
        )
```

---

## 4. Zep Cloud集成

### 4.1 Zep核心功能

Zep是一个专门为AI应用设计的知识图谱服务：

| 功能 | 说明 |
|------|------|
| 实体抽取 | 自动从文本中抽取命名实体 |
| 关系抽取 | 自动识别实体间的关系 |
| 知识图谱 | 以图结构存储实体和关系 |
| Episode管理 | 管理知识来源（文档片段） |
| 语义搜索 | 基于图谱的语义检索 |

### 4.2 与自建图谱的对比

| 特性 | Zep Cloud | 自建（NetworkX/Neo4j） |
|------|-----------|----------------------|
| 部署 | SaaS，零运维 | 需要自行部署维护 |
| 扩展性 | 自动扩展 | 需要手动扩展 |
| 实体抽取 | 内置 | 需要自行实现 |
| 关系抽取 | 内置 | 需要自行实现 |
| 成本 | 按量付费 | 固定成本 |
| 数据控制 | 数据在云端 | 完全自控 |

---

## 5. 与VibeUtopia项目的关联与借鉴

### 5.1 知识图谱驱动的Agent

MiroFish的核心理念——**从知识图谱生成Agent人格**——可以直接应用于VibeUtopia：

```
VibeUtopia Agent生成管线:
  领域文档 → 知识图谱构建 → 实体/关系抽取 → 
  LLM人格生成 → Agent Profile → Agent行为
```

### 5.2 本体驱动的人格设计

MiroFish使用LLM生成本体的设计很有创意：
- 不需要预先定义固定的实体类型
- LLM根据文档内容自动发现合适的分类
- 精确10个类型的约束保证图谱的结构化程度

### 5.3 知识图谱作为Agent记忆

Zep的知识图谱可以作为Agent的长期记忆：
- 实体 = 记忆中的人物/地点/事件
- 关系 = 记忆中的关联
- 图谱搜索 = 记忆检索

### 5.4 人格与知识的关联

MiroFish将人格与知识领域关联的设计值得借鉴：
- Agent的知识领域决定其能参与的话题
- Agent的兴趣决定其主动发起的话题
- Agent的关系网络决定其社交圈

---

## 6. 精华与糟粕

### 6.1 精华

1. **知识图谱+人格**: 将知识与人格有机结合
2. **LLM本体生成**: 自动发现实体和关系类型
3. **Zep集成**: 利用成熟的知识图谱服务
4. **结构化人格**: 从知识图谱中推导出结构化的人格特征

### 6.2 糟粕

1. **依赖Zep Cloud**: SaaS依赖，有成本和可用性问题
2. **固定10类型**: 精确10个实体/边类型的约束可能不够灵活
3. **人格生成质量**: LLM生成的Profile可能不够真实
4. **缺乏演化**: 人格一旦生成，缺乏动态演化机制

---

## 7. 总结

MiroFish是一个将知识图谱与Agent人格结合的创新项目。其核心贡献在于：
1. 证明了知识图谱可以驱动Agent人格生成
2. 提供了从文档到Agent的完整管线
3. 展示了LLM在本体发现中的应用

对于VibeUtopia，MiroFish的最大价值在于其**知识驱动的Agent设计方法论**。
