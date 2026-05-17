# AgentSociety 深度技术分析

> 基于源码分析 | https://github.com/tsinghua-fib-lab/AgentSociety

---

## 1. 项目概述

- **GitHub地址**: https://github.com/tsinghua-fib-lab/AgentSociety
- **Star数**: ~2.5k+
- **主要语言**: Python
- **License**: Apache-2.0
- **一句话描述**: 清华FIB实验室出品的大规模社会仿真平台，基于LLM驱动的"类人心智"智能体在真实城市环境中模拟复杂社会行为

### 1.1 研究背景

AgentSociety是"生成式智能体"（Generative Agents）研究浪潮中的重要作品。继Stanford的Smallville（25个Agent）之后，AgentSociety将规模扩展到**数万个Agent**，并在真实城市环境（OpenStreetway）中进行仿真。

### 1.2 核心创新

1. **大规模**: 支持数万个Agent并发仿真
2. **真实环境**: 基于OpenStreetMap的真实城市空间
3. **多模态空间**: 城市空间 + 社交空间 + 经济空间
4. **Ray分布式**: 基于Ray框架的高效分布式计算
5. **干预实验**: 支持在仿真中注入干预措施，观察社会响应

---

## 2. 核心架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AgentSociety Platform                              │
│                                                                        │
│  ┌──────────────── Agent Layer ───────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ┌─────────────────────┐   ┌──────────────────────────────┐   │  │
│  │  │ Social Agent        │   │ Custom Agent                 │   │  │
│  │  │ (LLM驱动的社会Agent)│   │ (自定义行为Agent)            │   │  │
│  │  │                     │   │                              │   │  │
│  │  │ ┌─────────────────┐ │   │ ┌──────────────────────────┐ │   │  │
│  │  │ │ Personality     │ │   │ │ Behavior Module          │ │   │  │
│  │  │ │ System          │ │   │ │                          │ │   │  │
│  │  │ │ - 问卷数据生成  │ │   │ │ - 自定义决策逻辑        │ │   │  │
│  │  │ │ - 程序化人格    │ │   │ │ - 自定义工具集          │ │   │  │
│  │  │ └─────────────────┘ │   │ └──────────────────────────┘ │   │  │
│  │  └─────────────────────┘   └──────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────── Space Layer ────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │  │
│  │  │ Urban Space     │  │ Social Space    │  │ Economic Space │  │  │
│  │  │ (城市空间)      │  │ (社交空间)      │  │ (经济空间)     │  │  │
│  │  │                 │  │                 │  │                │  │  │
│  │  │ - OSM地图数据   │  │ - 消息传递     │  │ - 职业市场    │  │  │
│  │  │ - 位置/移动    │  │ - 社交网络     │  │ - 消费行为    │  │  │
│  │  │ - POI兴趣点    │  │ - 群组形成     │  │ - 经济决策    │  │  │
│  │  └─────────────────┘  └─────────────────┘  └────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────── Simulation Engine ──────────────────────────────┐  │
│  │                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ Ray Distributed Computing Engine                          │   │  │
│  │  │ - Async Simulation: 异步事件驱动                          │   │  │
│  │  │ - Group Management: 分组管理大规模Agent                   │   │  │
│  │  │ - Client Pool: 连接池管理LLM调用                          │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │ Research Toolkit                                          │   │  │
│  │  │ - Intervention: 干预实验框架                               │   │  │
│  │  │ - Data Collection: 仿真数据收集                            │   │  │
│  │  │ - Visualization: 可视化工具                               │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块划分

| 模块 | 职责 |
|------|------|
| Agent Layer | Agent定义、人格系统、行为逻辑 |
| Space Layer | 城市/社交/经济三层空间建模 |
| Simulation Engine | Ray分布式仿真引擎 |
| Research Toolkit | 干预实验和数据分析工具 |

---

## 3. Agent人格系统

### 3.1 人格生成方式

AgentSociety支持两种人格生成方式：

**方式1: 问卷数据生成**（AgentSociety 1.0）
```python
# 基于真实问卷数据生成Agent人格
class SurveyPersonalityGenerator:
    def generate(self, survey_data):
        """
        survey_data: 包含年龄、性别、教育、收入、政治倾向等
        """
        prompt = f"""
        基于以下问卷数据，生成一个详细的人物画像:
        年龄: {survey_data['age']}
        性别: {survey_data['gender']}
        教育: {survey_data['education']}
        收入: {survey_data['income']}
        政治倾向: {survey_data['political_leaning']}
        
        生成包括: 日常习惯、社交偏好、消费行为、政治观点等
        """
        return self.llm.generate(prompt)
```

**方式2: 程序化人格生成**（AgentSociety 2.0）
```python
# 程序化生成多样化人格
class ProceduralPersonalityGenerator:
    def generate(self, config):
        personality = {
            'big_five': self.generate_big_five(config),
            'values': self.generate_values(config),
            'interests': self.generate_interests(config),
            'social_style': self.generate_social_style(config)
        }
        return personality
    
    def generate_big_five(self, config):
        """大五人格模型"""
        return {
            'openness': random.gauss(config['openness_mean'], 0.1),
            'conscientiousness': random.gauss(config['conscientiousness_mean'], 0.1),
            'extraversion': random.gauss(config['extraversion_mean'], 0.1),
            'agreeableness': random.gauss(config['agreeableness_mean'], 0.1),
            'neuroticism': random.gauss(config['neuroticism_mean'], 0.1)
        }
```

### 3.2 Agent行为决策

```python
class SocialAgent:
    def __init__(self, personality, memory, tools):
        self.personality = personality
        self.memory = memory
        self.tools = tools
    
    async def step(self, observation):
        """每步决策"""
        # 1. 感知环境
        perceived = self.perceive(observation)
        
        # 2. 更新记忆
        self.memory.update(perceived)
        
        # 3. 决策（LLM驱动）
        action = await self.decide(perceived)
        
        # 4. 执行
        result = await self.execute(action)
        
        return result
    
    async def decide(self, observation):
        """LLM决策"""
        prompt = f"""
        你是 {self.personality['name']}，一个 {self.personality['age']} 岁的 {self.personality['occupation']}。
        你的性格: {self.personality['big_five']}
        
        当前观察到: {observation}
        你的记忆: {self.memory.recent()}
        
        你现在应该做什么？选择一个行动。
        """
        return await self.llm.generate(prompt)
```

---

## 4. 三层空间架构

### 4.1 Urban Space（城市空间）

```python
class UrbanSpace:
    """基于OSM的城市空间"""
    
    def __init__(self, osm_file):
        self.graph = self.load_osm(osm_file)
        self.pois = self.extract_pois()
    
    def get_location(self, agent):
        """获取Agent当前位置"""
        return agent.current_location
    
    def move(self, agent, destination):
        """移动Agent到目标位置"""
        path = self.find_path(agent.current_location, destination)
        travel_time = self.calculate_travel_time(path)
        agent.current_location = destination
        return travel_time
    
    def get_nearby_pois(self, location, radius=500):
        """获取附近POI"""
        return [poi for poi in self.pois 
                if self.distance(location, poi.location) <= radius]
```

### 4.2 Social Space（社交空间）

```python
class SocialSpace:
    """Agent间的社交关系网络"""
    
    def __init__(self):
        self.social_graph = nx.Graph()
    
    def add_agent(self, agent):
        self.social_graph.add_node(agent.id, agent=agent)
    
    def form_relationship(self, agent1, agent2, relation_type):
        self.social_graph.add_edge(
            agent1.id, agent2.id, 
            type=relation_type,
            strength=0.1  # 初始关系强度
        )
    
    def interact(self, agent1, agent2, interaction):
        """处理Agent间互动"""
        edge = self.social_graph[agent1.id][agent2.id]
        
        # 根据互动类型更新关系强度
        if interaction.type == 'conversation':
            edge['strength'] += interaction.quality * 0.01
        elif interaction.type == 'conflict':
            edge['strength'] -= 0.05
        
        edge['strength'] = max(0, min(1, edge['strength']))
```

### 4.3 Economic Space（经济空间）

```python
class EconomicSpace:
    """Agent的经济行为空间"""
    
    def __init__(self):
        self.job_market = JobMarket()
        self.goods_market = GoodsMarket()
    
    def work(self, agent):
        """Agent工作"""
        job = self.job_market.find_job(agent)
        if job:
            income = job.calculate_income(agent)
            agent.wealth += income
            return income
        return 0
    
    def consume(self, agent, good):
        """Agent消费"""
        price = self.goods_market.get_price(good)
        if agent.wealth >= price:
            agent.wealth -= price
            agent.inventory.append(good)
            return True
        return False
```

---

## 5. 仿真引擎设计

### 5.1 时间驱动仿真

```python
class SimulationEngine:
    def __init__(self, config):
        self.ray.init()
        self.time_step = config.time_step  # 每个时间步代表的真实时间
        self.current_time = 0
        self.agents = []
    
    async def run(self, num_steps):
        for step in range(num_steps):
            self.current_time += self.time_step
            
            # 并行执行所有Agent的step
            tasks = [agent.step(self.get_observation(agent)) 
                     for agent in self.agents]
            results = await asyncio.gather(*tasks)
            
            # 处理互动
            await self.process_interactions(results)
            
            # 收集数据
            self.collect_metrics(step)
```

### 5.2 Ray分布式计算

```python
@ray.remote
class RemoteAgent:
    """Ray远程Actor，每个Agent运行在独立的Worker上"""
    
    def __init__(self, agent_config):
        self.agent = SocialAgent(agent_config)
    
    async def step(self, observation):
        return await self.agent.step(observation)


class DistributedSimulation:
    def __init__(self):
        ray.init(address="auto")
    
    def create_agents(self, num_agents):
        """创建分布式Agent池"""
        self.agent_pool = [
            RemoteAgent.remote(self.generate_config(i))
            for i in range(num_agents)
        ]
    
    async def step_all(self, observations):
        """并行执行所有Agent"""
        futures = [
            agent.step.remote(obs)
            for agent, obs in zip(self.agent_pool, observations)
        ]
        return await asyncio.gather(*[ray.get(f) for f in futures])
```

---

## 6. 干预实验框架

```python
class InterventionToolkit:
    """干预实验工具"""
    
    def inject_event(self, event, target_agents):
        """注入事件"""
        for agent in target_agents:
            agent.receive_event(event)
    
    def modify_environment(self, modification):
        """修改环境"""
        self.environment.apply(modification)
    
    def measure_effect(self, metric, time_window):
        """测量效果"""
        before = self.metrics.get(metric, self.current_time - time_window)
        after = self.metrics.get(metric, self.current_time)
        return after - before
```

---

## 7. 与VibeUtopia项目的关联与借鉴

### 7.1 大规模Agent管理

AgentSociety的Ray分布式架构是VibeUtopia大规模仿真的参考：
- 使用Ray实现Agent并行
- 分组管理降低复杂度
- 异步事件驱动提高吞吐量

### 7.2 三层空间架构

城市+社交+经济的三层空间设计可以映射到VibeUtopia：
- Urban Space → 虚拟世界地图
- Social Space → Agent社交网络
- Economic Space → 虚拟经济系统

### 7.3 人格生成系统

AgentSociety的两种人格生成方式（问卷数据和程序化）都可以用于VibeUtopia的Agent人格系统。

### 7.4 干预实验

AgentSociety的干预实验框架可以用于VibeUtopia的假设验证：
- "如果改变X，社会会如何响应？"
- "如果引入新政策，Agent行为会如何变化？"

---

## 8. 精华与糟粕

### 8.1 精华

1. **大规模**: 数万个Agent并发
2. **真实环境**: OSM真实城市数据
3. **三层空间**: 城市+社交+经济的完整建模
4. **Ray分布式**: 高效的并行计算
5. **干预实验**: 支持社会科学研究

### 8.2 糟粕

1. **依赖Ray**: 增加了部署复杂度
2. **LLM成本高**: 数万个Agent的LLM调用成本巨大
3. **人格真实性**: LLM生成的行为可能不够真实
4. **验证困难**: 大规模仿真的结果难以验证

---

## 9. 总结

AgentSociety是大规模社会仿真的代表性工作。其核心价值在于**将Stanford Smallville的概念扩展到真实城市规模和数万个Agent**。

**关键指标**:
- Agent规模: 数万个
- 空间数据: OpenStreetMap
- 计算框架: Ray
- 人格系统: 问卷数据 + 程序化生成
- 仿真模式: 时间驱动异步仿真

对于VibeUtopia，AgentSociety的最大借鉴价值在于其**大规模Agent管理架构**和**三层空间建模方法论**。
