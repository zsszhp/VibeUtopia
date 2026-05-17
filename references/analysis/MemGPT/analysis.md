# MemGPT/Letta 深度技术分析

> 基于源码分析 | https://github.com/letta-ai/letta

---

## 1. 项目概述

- **GitHub地址**: https://github.com/letta-ai/letta
- **Star数**: ~15k+
- **主要语言**: Python (99.5%)
- **License**: MIT (原MemGPT)
- **一句话描述**: 构建具有高级记忆和自我改进能力的AI智能体，通过分层记忆架构（核心记忆+归档记忆+召回记忆）突破LLM上下文窗口限制

### 1.1 核心问题

LLM的上下文窗口是有限的（如GPT-4的8K-128K token），但AI Agent需要：
- 记住数周或数月的交互历史
- 维护持久化的个性和知识
- 在长时间运行中保持一致性

MemGPT的解决方案是**分层记忆架构**，模拟人类大脑的工作方式。

### 1.2 项目名称演变

- **MemGPT** (2023): 原始论文和原型
- **Letta** (2024): 正式产品化，增加了服务端、客户端SDK等

---

## 2. 分层记忆架构

### 2.1 三层记忆系统

```
┌──────────────────────────────────────────────────────────────────┐
│                    MemGPT Memory Architecture                     │
│                                                                    │
│  ┌──────────────── Context Window (发送给LLM) ─────────────────┐  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ System Prompt + Core Memory (核心记忆)                   │ │  │
│  │  │ - 持久化的Agent个性和知识                                │ │  │
│  │  │ - Agent可以通过工具主动编辑                              │ │  │
│  │  │ - 始终在上下文中                                        │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ External Memory Summary (外部记忆摘要)                   │ │  │
│  │  │ - 归档记忆和召回记忆的统计信息                           │ │  │
│  │  │ - 让LLM知道有哪些外部记忆可用                            │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ Conversation Messages (对话消息)                         │ │  │
│  │  │ - 最近的对话历史                                        │ │  │
│  │  │ - 超出窗口的旧消息被截断                                │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────── External Memory (外部存储) ───────────────────┐  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ Archival Memory (归档记忆)                                │ │  │
│  │  │ - 无限容量的长期记忆                                      │ │  │
│  │  │ - 向量数据库存储                                          │ │  │
│  │  │ - 语义搜索检索                                            │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐ │  │
│  │  │ Recall Memory (召回记忆)                                  │ │  │
│  │  │ - 对话历史的完整记录                                      │ │  │
│  │  │ - 支持时间范围和关键词搜索                                │ │  │
│  │  └──────────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Memory（核心记忆）

核心记忆是Agent的"人格和知识基础"，始终存在于上下文中：

```python
class CoreMemory:
    """核心记忆 - 始终在上下文中"""
    
    def __init__(self, memory_blocks):
        self.blocks = memory_blocks  # 多个内存块
    
    def edit(self, block_name, new_content):
        """Agent可以主动编辑核心记忆"""
        self.blocks[block_name] = new_content
    
    def get_context(self):
        """获取上下文中显示的核心记忆"""
        return "\n".join([
            f"## {name}\n{content}" 
            for name, content in self.blocks.items()
        ])
```

**核心记忆的局限性**: 受上下文窗口限制，核心记忆通常只有几百到几千token。

### 2.3 Archival Memory（归档记忆）

归档记忆是无限容量的长期存储：

```python
class ArchivalMemory:
    """归档记忆 - 无限容量的向量存储"""
    
    def __init__(self, vector_store):
        self.vector_store = vector_store
    
    async def insert(self, content):
        """插入记忆"""
        embedding = await self.embed(content)
        await self.vector_store.upsert({
            'content': content,
            'embedding': embedding,
            'timestamp': datetime.now()
        })
    
    async def search(self, query, top_k=10):
        """语义搜索"""
        query_embedding = await self.embed(query)
        results = await self.vector_store.search(
            query_embedding, top_k=top_k
        )
        return results
```

### 2.4 Recall Memory（召回记忆）

召回记忆保存完整的对话历史：

```python
class RecallMemory:
    """召回记忆 - 对话历史"""
    
    def __init__(self, message_store):
        self.message_store = message_store
    
    async def insert(self, message):
        """记录消息"""
        await self.message_store.insert(message)
    
    async def search(self, query=None, start_date=None, end_date=None, 
                     limit=10):
        """搜索历史消息"""
        return await self.message_store.search(
            query=query,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
```

---

## 3. Agent.step()核心循环

### 3.1 步骤流程

```python
async def step(self, user_message):
    """Agent的每一步"""
    
    # 1. 将用户消息加入召回记忆
    await self.recall_memory.insert(user_message)
    
    # 2. 构建上下文窗口
    context = self.build_context()
    
    # 3. LLM推理
    response = await self.llm.generate(context)
    
    # 4. 解析工具调用
    tool_calls = self.parse_tool_calls(response)
    
    # 5. 执行工具调用
    for tool_call in tool_calls:
        result = await self.execute_tool(tool_call)
        
        # 6. 处理工具结果
        if tool_call.name == 'core_memory_append':
            self.core_memory.append(tool_call.args['content'])
        elif tool_call.name == 'core_memory_replace':
            self.core_memory.replace(
                tool_call.args['old_content'],
                tool_call.args['new_content']
            )
        elif tool_call.name == 'archival_memory_insert':
            await self.archival_memory.insert(tool_call.args['content'])
        elif tool_call.name == 'archival_memory_search':
            results = await self.archival_memory.search(
                tool_call.args['query']
            )
            # 将搜索结果返回给LLM
        elif tool_call.name == 'conversation_search':
            results = await self.recall_memory.search(
                tool_call.args['query']
            )
        elif tool_call.name == 'send_message':
            # 回复用户
            return tool_call.args['message']
    
    # 7. 将Agent的回复加入召回记忆
    await self.recall_memory.insert(response)
    
    return response
```

### 3.2 上下文窗口管理

```python
def build_context(self):
    """构建上下文窗口"""
    
    # 系统提示 + 核心记忆（固定部分）
    system_prompt = f"""
    You are {self.name}, an AI assistant.
    
    {self.core_memory.get_context()}
    
    You have access to archival memory and conversation history.
    Use the following tools to manage your memory:
    - core_memory_append: Add to core memory
    - core_memory_replace: Edit core memory
    - archival_memory_insert: Store information in archival memory
    - archival_memory_search: Search archival memory
    - conversation_search: Search conversation history
    - send_message: Reply to the user
    """
    
    # 外部记忆摘要
    memory_summary = f"""
    External memory stats:
    - Archival memory: {self.archival_memory.count()} entries
    - Recall memory: {self.recall_memory.count()} messages
    """
    
    # 最近的对话（占用剩余空间）
    available_tokens = self.context_window_size - \
                       self.count_tokens(system_prompt) - \
                       self.count_tokens(memory_summary) - \
                       self.response_token_budget
    
    recent_messages = self.recall_memory.get_recent(
        max_tokens=available_tokens
    )
    
    return SystemMessage(system_prompt) + \
           SystemMessage(memory_summary) + \
           recent_messages
```

---

## 4. 工具系统设计

### 4.1 核心工具

```python
TOOLS = {
    "core_memory_append": {
        "description": "Append content to a core memory block",
        "parameters": {
            "section": "str - memory block name",
            "content": "str - content to append"
        }
    },
    "core_memory_replace": {
        "description": "Replace content in a core memory block",
        "parameters": {
            "section": "str - memory block name",
            "old_content": "str - content to replace",
            "new_content": "str - new content"
        }
    },
    "archival_memory_insert": {
        "description": "Insert information into archival memory",
        "parameters": {
            "content": "str - information to store"
        }
    },
    "archival_memory_search": {
        "description": "Search archival memory",
        "parameters": {
            "query": "str - search query",
            "page": "int - pagination (optional)"
        }
    },
    "conversation_search": {
        "description": "Search conversation history",
        "parameters": {
            "query": "str - search query",
            "page": "int - pagination (optional)"
        }
    },
    "send_message": {
        "description": "Send a message to the user",
        "parameters": {
            "message": "str - message content"
        }
    }
}
```

---

## 5. 持久化与服务端

### 5.1 服务端架构

```
┌──────────────────────────────────────────────────────────────┐
│                    Letta Server                               │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ FastAPI Application                                      ││
│  │ - POST /agents: 创建Agent                                ││
│  │ - POST /agents/{id}/messages: 发送消息                   ││
│  │ - GET /agents/{id}: 获取Agent状态                        ││
│  │ - GET /agents/{id}/memory: 获取记忆                      ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  ┌──────────────── Storage Layer ───────────────────────────┐│
│  │ - PostgreSQL: Agent状态、消息历史                        ││
│  │ - 向量数据库: Archival Memory                            ││
│  │ - Redis: 缓存                                           ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### 5.2 数据模型

```python
class AgentState(BaseModel):
    """Agent状态"""
    id: str
    name: str
    core_memory: Dict[str, str]  # 核心记忆块
    tools: List[str]  # 可用工具列表
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    message_ids: List[str]  # 消息ID列表
    created_at: datetime
    updated_at: datetime

class Message(BaseModel):
    """消息"""
    id: str
    agent_id: str
    role: str  # user/assistant/system/tool
    content: str
    tool_calls: Optional[List[Dict]]
    tool_results: Optional[List[Dict]]
    created_at: datetime
```

---

## 6. 与VibeUtopia项目的关联与借鉴

### 6.1 Agent记忆系统

MemGPT的分层记忆架构是VibeUtopia Agent记忆系统的最佳参考：

| MemGPT概念 | VibeUtopia对应 |
|-----------|---------------|
| Core Memory | Agent人格/知识摘要 |
| Archival Memory | Agent长期知识库 |
| Recall Memory | Agent交互历史 |
| 工具调用 | Agent能力扩展 |

### 6.2 主动记忆管理

MemGPT的核心创新——**Agent可以主动管理自己的记忆**——是VibeUtopia Agent系统的重要特性：
- Agent可以决定将什么信息存入长期记忆
- Agent可以编辑自己的人格特征
- Agent可以搜索和检索历史信息

### 6.3 持久化设计

MemGPT的持久化方案（PostgreSQL + 向量数据库 + Redis）是VibeUtopia Agent存储层的参考架构。

---

## 7. 精华与糟粕

### 7.1 精华

1. **分层记忆**: 三层架构完美平衡了容量和效率
2. **主动管理**: Agent可以自主决定记忆策略
3. **持久化**: 完整的持久化方案
4. **工具系统**: 灵活的工具调用机制
5. **开源**: 代码完全开源

### 7.2 糟粕

1. **上下文窗口管理复杂**: 需要精确计算token数
2. **LLM调用频繁**: 每次step至少1次LLM调用，工具调用可能更多
3. **记忆质量依赖**: 归档记忆的质量取决于LLM的总结能力
4. **延迟**: 多次LLM调用导致响应延迟较高

### 7.3 与Mem0对比

| 特性 | MemGPT/Letta | Mem0 |
|------|-------------|------|
| 记忆管理 | Agent主动管理 | 系统自动管理 |
| 架构复杂度 | 高 | 低 |
| 灵活性 | 高 | 中 |
| 易用性 | 低 | 高 |
| 持久化 | 完整 | 可选 |

---

## 8. 总结

MemGPT/Letta是Agent记忆系统的标杆工作。其核心价值在于**证明了分层记忆架构可以有效地突破LLM的上下文窗口限制**。

**关键指标**:
- 记忆层数: 3层（Core/Archival/Recall）
- 上下文管理: 精确的token计数
- 工具数: 6个核心工具
- 持久化: PostgreSQL + 向量DB + Redis

对于VibeUtopia，MemGPT的最大借鉴价值在于其**分层记忆架构设计**和**Agent主动记忆管理机制**。
