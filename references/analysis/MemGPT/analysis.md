# MemGPT/Letta 深度技术分析

## 项目概述
- GitHub地址：https://github.com/letta-ai/letta
- Star数：~15k+
- 主要语言：Python (99.5%)
- License：MIT (原MemGPT)
- 一句话描述：构建具有高级记忆和自我改进能力的AI智能体，通过分层记忆架构（核心记忆+归档记忆+召回记忆）突破LLM上下文窗口限制

## 核心架构
- 整体架构图（文字描述）：
  ```
  用户消息 → Agent.step() → 内部步骤循环
                ↓
         [上下文窗口管理]
         ┌─────────────────────────────────┐
         │ System Prompt + Core Memory     │ ← 可编辑的内存块(Blocks)
         │ External Memory Summary         │ ← 归档/召回记忆统计
         │ Summary Memory (可选)           │ ← 对话摘要
         │ Conversation Messages           │ ← 近期对话
         └─────────────────────────────────┘
                ↓
         LLM决策 → 工具调用
         ┌─────────────────────────────────┐
         │ core_memory_append/replace      │ ← 编辑核心记忆
         │ archival_memory_insert/search   │ ← 归档记忆(向量检索)
         │ conversation_search             │ ← 召回记忆(消息搜索)
         │ send_message                    │ ← 回复用户
         └─────────────────────────────────┘
  ```

- 核心模块划分和职责：
  - `letta/agent.py`：Agent核心类，实现step循环、LLM调用、工具执行、上下文管理
  - `letta/schemas/memory.py`：Memory模型，由多个Block组成（persona/human等），支持只读块
  - `letta/services/block_manager.py`：Block管理器，处理核心记忆块的CRUD
  - `letta/services/passage_manager.py`：Passage管理器，管理归档记忆（向量存储的文本段落）
  - `letta/services/message_manager.py`：消息管理器，管理召回记忆（对话历史）
  - `letta/services/agent_manager.py`：智能体状态管理，包括消息列表、系统提示重建
  - `letta/memory/`：消息摘要模块，当上下文溢出时压缩历史消息
  - `letta/orm/`：SQLAlchemy ORM模型，持久化到PostgreSQL

- 数据流和控制流：
  1. **消息处理循环**：用户消息 → inner_step → LLM推理 → 工具调用 → 状态更新 → 判断是否继续(heartbeat/function_failed/memory_warning)
  2. **上下文窗口管理**：当token使用超过阈值 → 触发summarize_messages_inplace → 旧消息被摘要替换
  3. **核心记忆编辑**：LLM通过core_memory_append/replace工具 → 修改Memory Block → 重建系统提示
  4. **归档记忆**：archival_memory_insert → 文本分块+嵌入 → 存入pgvector；archival_memory_search → 向量检索

## 关键技术实现

### 分层记忆架构
- 实现原理：三层记忆设计突破上下文窗口限制
  - **Core Memory（核心记忆）**：始终在上下文窗口中，LLM可直接读写，由多个Block组成（persona块描述智能体身份，human块描述用户信息），有字符数限制
  - **Archival Memory（归档记忆）**：无限容量的外部存储，通过archival_memory_search工具按需检索，基于向量数据库(pgvector)
  - **Recall Memory（召回记忆）**：完整的对话历史，通过conversation_search工具检索，支持关键词和日期搜索
- 核心代码逻辑：
  ```python
  class Agent(BaseAgent):
      def step(self, input_messages, chaining=True, max_chaining_steps=None):
          while True:
              step_response = self.inner_step(messages=next_input_messages)
              # 链式调用判断
              if token_warning: continue  # 内存压力警告
              elif function_failed: continue  # 工具调用失败重试
              elif heartbeat_request: continue  # 智能体请求继续
              else: break  # 正常结束

      def inner_step(self, messages, ...):
          # Step 0: 更新核心记忆（从DB读取最新Block数据）
          current_memory = Memory(blocks=[block_manager.get_block_by_id(b.id) ...])
          self.update_memory_if_changed(current_memory)
          # Step 1: 构建输入消息序列
          in_context_messages = agent_manager.get_in_context_messages(...)
          input_sequence = in_context_messages + messages
          # Step 2: 调用LLM
          response = self._get_ai_reply(message_sequence=input_sequence)
          # Step 3: 处理LLM响应（工具调用或普通回复）
          all_messages, heartbeat, failed = self._handle_ai_response(response_message)
          # Step 4: 持久化消息
          agent_state = agent_manager.append_to_in_context_messages(all_messages)
          # Step 5: 检查内存压力
          if total_tokens > threshold * context_window:
              active_memory_warning = True
  ```

### 上下文窗口自动管理
- 实现原理：当上下文窗口接近溢出时，自动触发消息摘要压缩
  - 监控token使用量，超过`memory_warning_threshold`（默认0.85）时发出警告
  - 调用`summarize_messages_inplace`：计算截断点 → LLM摘要旧消息 → 删除旧消息 → 插入摘要消息
  - 支持多次重试（max_summarizer_retries），如果摘要后仍然溢出则继续压缩
- 核心代码逻辑：
  ```python
  def summarize_messages_inplace(self):
      in_context_messages = agent_manager.get_in_context_messages(...)
      cutoff = calculate_summarizer_cutoff(in_context_messages, token_counts)
      message_sequence_to_summarize = in_context_messages[1:cutoff]
      summary = summarize_messages(agent_state, message_sequence_to_summarize)
      # 删除旧消息，插入摘要
      agent_state = agent_manager.trim_older_in_context_messages(num=cutoff)
      agent_state = agent_manager.prepend_to_in_context_messages([summary_message])
  ```

### 工具执行与状态持久化
- 实现原理：LLM通过function calling调用工具，不同类型工具有不同的执行环境
  - LETTA_CORE工具：直接在Agent进程中执行，可访问self对象
  - LETTA_MEMORY_CORE工具：在Agent状态副本上执行，支持只读块保护
  - EXTERNAL工具：在沙箱中执行（ToolExecutionSandbox）
  - MCP工具：通过AsyncBaseMCPClient远程调用
- 状态持久化：每次step结束后调用save_agent，将AgentState写入PostgreSQL

### Block系统（核心记忆的组成单元）
- 实现原理：核心记忆由多个Block组成，每个Block有label、value、read_only属性
  - persona Block：描述智能体身份和行为，可编辑
  - human Block：描述用户信息，可编辑
  - 支持自定义Block和只读Block
  - Block可以在多个智能体间共享（通过block_id引用）

## 对VibeUtopia的参考价值

### 可借鉴的技术路线
- **分层记忆架构**：VibeUtopia的Memory Stream可参考Letta的三层记忆设计——核心记忆（当前风控状态）始终在上下文中，归档记忆（历史风控记录）按需检索，召回记忆（审核对话历史）支持搜索
- **上下文窗口自动管理**：风控智能体在长时间运行中上下文会膨胀，Letta的自动摘要压缩机制可直接参考
- **Block系统**：将风控智能体的核心状态（当前风险等级、关注用户列表、敏感词库等）组织为Block，支持动态更新和只读保护
- **Heartbeat机制**：智能体可以通过request_heartbeat参数请求继续执行，适合风控场景中的多步骤推理（先检索→再分析→最后决策）
- **工具沙箱执行**：外部工具在沙箱中执行，保护主进程安全，适合风控场景中调用第三方API

### 需要避免的坑
- **PostgreSQL强依赖**：Letta深度绑定PostgreSQL + pgvector，VibeUtopia如果使用ChromaDB则需要自行适配归档记忆的向量检索
- **单工具调用限制**：当前只支持单工具调用（>1 tool call not supported），限制了并行工具执行能力
- **摘要信息损失**：自动摘要会丢失对话细节，风控场景中可能需要保留完整的审核记录
- **配置复杂**：LettaConfig包含大量配置项（archival_storage_type/recall_storage_type/metadata_storage_type等），部署配置繁琐
- **核心记忆容量有限**：Core Memory有字符数限制（persona默认2000字符，human默认2000字符），不适合存储大量风控规则

## 精华与糟粕
| 类别 | 内容 | 说明 |
|------|------|------|
| 精华 | 三层记忆架构 | 核心记忆+归档记忆+召回记忆，优雅解决上下文窗口限制 |
| 精华 | 自动上下文管理 | 智能摘要压缩，无需人工干预 |
| 精华 | Block系统 | 模块化的核心记忆组织，支持共享和只读保护 |
| 精华 | Heartbeat链式推理 | 智能体自主决定是否继续推理，支持复杂多步骤任务 |
| 糟粕 | PostgreSQL强绑定 | 归档记忆依赖pgvector，迁移成本高 |
| 糟粕 | 单工具调用限制 | 不支持并行工具调用，效率受限 |
| 糟粕 | 核心记忆容量小 | 字符数限制严格，不适合存储大量规则 |
| 糟粕 | 代码耦合度高 | Agent类1700+行，职责过多（LLM调用+工具执行+状态管理+上下文管理） |
