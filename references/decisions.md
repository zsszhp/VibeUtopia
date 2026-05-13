# 落地决策总表

| 参考项目 | Feature/Pattern | 决策 | 理由 | 目标阶段 |
|----------|----------------|------|------|---------|
| **TrendRadar** | NewsNow API统一聚合 | 采纳 | 一个API覆盖11+平台，零维护成本，已验证可行 | 1-2 |
| **TrendRadar** | 增量检测+排名时间线 | 采纳 | 精确追踪热点生命周期，减少重复处理 | 1-2 |
| **TrendRadar** | LiteLLM多模型接口 | 采纳 | 100+模型统一调用+fallback，降低单模型风险 | 1 |
| **TrendRadar** | 时间线调度系统 | 采纳(改进) | 灵活调度，改用asyncio.Queue替代Celery | 1-2 |
| **TrendRadar** | 3阶段JSON解析降级 | 采纳 | 健壮的LLM输出处理，json.loads→json_repair→LLM重试 | 1 |
| **TrendRadar** | 通知推送系统 | 不采纳 | VibeUtopia不需要多渠道推送，信号仅内部消费 | - |
| **TrendRadar** | 事件关联(跨平台合并) | 采纳(改进) | 新增LLM事件聚类，原项目无此能力 | 2 |
| **TrendRadar** | 因果链推理 | 采纳(改进) | 新增因果推理模块，原项目仅描述不分析 | 2 |
| **BettaFish** | ForumEngine协作思想 | 采纳(改进) | 保留Host主持概念，改用asyncio.Queue | 4-5 |
| **BettaFish** | 专职Agent分工 | 采纳(改进) | 改为A/B/C/Group四层Agent架构 | 3-5 |
| **BettaFish** | 两阶段爬取策略 | 采纳 | 广度关键词+API优先深度爬取 | 1-2 |
| **BettaFish** | 反思-总结循环 | 采纳(改进) | Agent基于反馈调整行为 | 4 |
| **BettaFish** | 多模型情感分析 | 采纳 | BERT-LoRA+LLM辅助 | 2-3 |
| **BettaFish** | 日志文件通信 | 不采纳 | 文件I/O不适合实时仿真 | - |
| **BettaFish** | Playwright为主 | 不采纳 | 维护成本高，改用API优先+Playwright降级 | - |
| **BettaFish** | 串行报告生成 | 不采纳 | 改为流式输出 | - |
| **MiroFish** | GraphRAG知识图谱 | 采纳 | Neo4j自建图谱，去掉Zep Cloud依赖，用于世界构建+社会关系 | 4 |
| **MiroFish** | LLM增强人格生成 | 采纳(改进) | 扩展为7层人格，增加社会关系+动态演化 | 3 |
| **MiroFish** | LLM驱动仿真配置 | 采纳 | 自动生成时间/事件/活动配置 | 3-4 |
| **MiroFish** | 中国时区时间模型 | 采纳 | 细化为8时段+Agent个性化 | 3-4 |
| **MiroFish** | OASIS多体仿真框架 | 后置 | 重型框架，当前聚焦风控核心；待主线稳定后再评估自研引擎 | 6+ |
| **MiroFish** | 双平台仿真 | 采纳(改进) | 扩展为5个中国平台 | 2-5 |
| **MiroFish** | Zep Cloud | 不采纳 | SaaS付费依赖，成本不可控 | - |
| **MiroFish** | 5层人格固定维度 | 不采纳 | 扩展为7层 | - |
| **MiroFish** | 配置驱动行为 | 不采纳 | 改为决策驱动 | - |
| **DeepSearchAgent** | 迭代搜索策略 | 采纳 | 初搜→分析→深搜，用于深度信号采集 | 1-2 |
| **DeepSearchAgent** | 工具自适应选择 | 采纳 | LLM根据上下文选工具 | 3-4 |
| **DeepSearchAgent** | 无框架纯LLM驱动 | 不采纳 | 需要Agent分层架构和持久化状态 | - |
| **DeepSearchAgent** | 无持久化状态 | 不采纳 | 需要Memory Stream | - |
| **DeepSearchAgent** | 串行搜索 | 不采纳 | 需要并行搜索 | - |
| **ex-skill** | 5层人格分层 | 采纳(改进) | 扩展为7层，增加社会关系+动态演化 | 3 |
| **ex-skill** | 真实数据提取人格 | 采纳(改进) | 扩展为多数据源 | 3 |
| **ex-skill** | 人格量化与存储 | 采纳 | 7层结构化存储+版本管理 | 3 |
| **ex-skill** | 单一数据源 | 不采纳 | 扩展为多数据源 | - |
| **ex-skill** | 固定权重 | 不采纳 | 改为动态权重 | - |
| **ex-skill** | 无演化机制 | 不采纳 | 新增动态演化层 | - |
| **Stanford GA** | Memory Stream | 采纳 | ChromaDB向量检索+MySQL持久化 | 3-4 |
| **Stanford GA** | 三因子检索 | 采纳 | Recency+Importance+Relevance加权 | 3-4 |
| **Stanford GA** | Reflection反思机制 | 采纳 | 定期从记忆流生成高层反思 | 4 |

---

## 技术选型对比矩阵

| 技术领域 | TrendRadar | BettaFish | MiroFish | DeepSearchAgent | ex-skill | **VibeUtopia选型** |
|----------|-----------|-----------|----------|----------------|----------|-------------------|
| LLM接口 | LiteLLM | OpenAI SDK | OpenAI SDK | OpenAI SDK | OpenAI SDK | **LiteLLM**（统一多模型+fallback） |
| Agent框架 | 无 | 自研节点流水线 | OASIS(CAMEL-AI) | 无 | 无 | **自研四层架构**（A/B/C/Group） |
| 知识图谱 | 无 | 无 | Zep Cloud | 无 | 无 | **Neo4j**（自托管，完全可控） |
| 向量检索 | 无 | 无 | 无 | 无 | 无 | **ChromaDB**（内嵌式，零部署） |
| 情感分析 | LLM分析 | BERT-LoRA等 | LLM分析 | 无 | 无 | **BERT-LoRA + LLM辅助** |
| 爬虫 | NewsNow API | Playwright | 无 | 无 | 无 | **API优先 + Playwright降级** |
| 通信机制 | 无 | 文件日志 | 无 | 无 | 无 | **asyncio.Queue**（零外部依赖） |
| 任务调度 | timeline.yaml | 无 | 无 | 无 | 无 | **asyncio.Queue + 自研调度器** |
| 数据库 | SQLite | PostgreSQL | 无 | 无 | 无 | **MySQL + SQLite降级 + Neo4j + ChromaDB** |
| 前端 | 无 | Flask | 无 | 无 | 无 | **Vue3 + Vite + Naive UI + ECharts + D3.js** |
| 记忆系统 | 无 | 无 | 无 | 无 | 无 | **Memory Stream(ChromaDB)** |
| 仿真引擎 | 无 | 无 | OASIS | 无 | 无 | **后置**（待风控主线稳定后评估自研） |
