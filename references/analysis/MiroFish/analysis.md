# MiroFish 深度分析

## 关键实现细节

### 知识图谱构建 (services/graph_builder.py)

**流程**：
1. 使用Zep Cloud创建独立知识图谱
2. **本体生成器** (`ontology_generator.py`)：LLM分析文档文本 → 生成实体类型+关系类型定义（精确10个实体类型+边类型）
3. 设置图谱本体
4. 文档分块 → 批量发送为episodes → Zep自动抽取实体和关系
5. 等待Zep处理完成

**核心类**：
```python
class GraphBuilder:
    def __init__(self, zep_api_key, zep_base_url)
    async def build_graph(self, documents: List[str], graph_id: str) -> Dict
```

### Agent人格生成 (services/oasis_profile_generator.py)

**OasisAgentProfile 数据类**：
```python
@dataclass
class OasisAgentProfile:
    user_id: str
    user_name: str
    name: str
    bio: str
    persona: str           # 详细人格描述
    # 平台特化属性
    karma: int = 0                     # Reddit
    friend_count: int = 0              # Twitter
    follower_count: int = 0            # Twitter
    statuses_count: int = 0            # Twitter
    # 扩展属性
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
```

**OasisProfileGenerator**：
```python
class OasisProfileGenerator:
    def __init__(self, llm_client)
    async def generate_profiles(self, entities: List[Dict], num_agents: int,
                                 platform: str = "twitter") -> List[OasisAgentProfile]
    async def _generate_single_profile(self, entity: Dict, index: int) -> OasisAgentProfile
        # LLM增强生成：基于实体属性生成详细persona描述
        # 并行生成：默认3个并发请求
```

**LLM增强人格生成Prompt模式**：
- 输入：实体属性（名称、类型、描述）
- LLM推理：生成personality、bio、interests等
- 输出：完整的OasisAgentProfile

**两种输出格式**：
- CSV（Twitter，OASIS要求）
- JSON（Reddit）

### 仿真配置生成 (services/simulation_config_generator.py)

**LLM驱动的分步配置生成**：
1. **时间配置**：中国时区感知
   ```python
   dead_hours: [0, 7]       # 深夜，极低活跃
   morning_hours: [7, 9]    # 早高峰
   work_hours: [9, 18]      # 工作时间
   peak_hours: [18, 23]     # 黄金时段
   night_hours: [23, 24]    # 深夜
   # 每个时段有activity_multiplier
   ```
2. **事件配置**：仿真期间发生的外部事件
3. **Agent活动配置**：批量生成每个Agent的行为参数
4. **平台配置**

**SimulationParameters 数据类**：
```python
@dataclass
class SimulationParameters:
    time_config: TimeConfig
    event_config: EventConfig
    agent_configs: List[AgentActivityConfig]
    platform_config: PlatformConfig
```

### OASIS仿真执行

**双平台并行仿真** (`scripts/run_parallel_simulation.py`)：
- **Twitter仿真**：
  - 行为类型：`CREATE_POST`, `LIKE_POST`, `REPOST`, `FOLLOW`, `DO_NOTHING`, `QUOTE_POST`
  - Agent图：`generate_twitter_agent_graph()`
- **Reddit仿真**：
  - 行为类型：`LIKE_POST`, `DISLIKE_POST`, `CREATE_POST`, `CREATE_COMMENT`, `LIKE_COMMENT`, `DISLIKE_COMMENT`
  - Agent图：`generate_reddit_agent_graph()`

**仿真配置参数**：
```python
sign_up_probability = 0.3       # 注册概率
mimic_follow_probability = 0.3  # 模仿关注概率
mimic_post_probability = 0.2    # 模仿发帖概率
```

### AI总结与主题演化

**仿真后分析**：
- LLM分析仿真轨迹数据
- 提取关键主题和趋势
- 追踪主题随时间的演化
- 生成结构化分析报告

## 精华与糟粕

| 类别 | 内容 | 说明 |
|------|------|------|
| **精华** | 知识图谱驱动的世界构建 | 从种子文档自动构建世界模型，Agent从实体生成 |
| **精华** | LLM增强的人格生成 | 不仅是填表，而是LLM推理出有深度的人格描述 |
| **精华** | LLM驱动的仿真配置 | 自动生成时间/事件/活动配置，减少人工设计 |
| **精华** | 双平台并行仿真 | 同时模拟Twitter和Reddit，覆盖不同社交模式 |
| **精华** | 仿真后趋势分析 | AI提取仿真中的趋势和主题演化 |
| **精华** | 中国时区感知的时间模型 | 按中国用户作息分配活跃度 |
| **糟粕** | Zep Cloud付费依赖 | SaaS服务，成本不可控，数据隐私风险 |
| **糟粕** | OASIS外部框架依赖 | 更新不可控，行为模型固定，难以扩展 |
| **糟粕** | 人格维度不足 | 缺少文化背景/经济状况/社会关系/动态演化 |
| **糟粕** | 行为模型过于简化 | 缺少围观/潜水/私聊/删帖/编辑等行为 |
| **糟粕** | 仅事后分析 | 仿真中无实时监控，无法中途干预 |
| **糟粕** | 配置与行为脱节 | Agent按配置行动，非自发决策 |

## 改进项

| 改进项 | 改进方式 |
|--------|----------|
| Zep→Neo4j | 自建图谱，完全可控，支持增量更新 |
| 人格5层→7层 | 增加社会关系层+动态演化层 |
| 事后分析→实时监控 | 增加Watcher观察仿真状态 |
| 配置驱动→决策驱动 | Agent自主感知-思考-行动，非按配置执行 |
