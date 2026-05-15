# VibeUtopia 全项目实施计划

## 项目现状评估

### 已完成 (MVP阶段)
- ✅ Phase 1: FastAPI后端 + Vue3前端 + LLM连通
- ✅ Phase 3: 七维风险评估 + 平台人格模拟 + 改写建议 + 文本切分 + 结果聚合
- ✅ Phase 4: 报告展示组件 + 主工作台界面 + 前后端联调 + 启动脚本
- ✅ Phase 5: 视频文案提取 + 视频分析API + 前端视频链接标签页

### 已有代码骨架(需完善/集成)
- `backend/services/signal/` — 信号采集层(fetcher/rss_fetcher/event_detector/keyword_extractor/deep_crawler/scheduler)
- `backend/services/graph/` — 知识图谱(graph_store/graph_updater/entity_extractor/ontology_generator)
- `backend/services/persona/` — 人格工厂(graph_injector/memory/quality_validator/social_network)
- `backend/services/simulation/` — 仿真引擎(engine/decision_engine/rule_engine/time_model/message_bus/recorder + platforms/propagation/replay/monitors)
- `backend/services/` — 分析器(analyzer/enhanced_analyzer/risk_assessor/signal_matcher/dynamic_weights/entity_risk_chain/cross_modal_risk等)
- `backend/models.py` — 完整数据模型(Task/RiskItem/PlatformReaction/SignalRecord/SeedEventRecord/AgentRecord/SocialRelation/AgentMemory/SimulationRecord/V2AnalysisResult/BacktestRecord等)
- `frontend-vue/` — Vue3 + Naive UI暗色主题前端(Workbench/LeftPanel/RightPanel/AnalysisPipeline/RiskGauge/DimensionRadar/PlatformReactions)

### 核心差距 — ✅ 全部已解决
1. ~~5核心API端点未收敛~~ → ✅ 已实现`/api/review`统一入口
2. ~~信号采集层未接入主流程~~ → ✅ 已集成到风险评估流程
3. ~~人格工厂未完成Life Story~~ → ✅ A/B/C三级生成器完整实现
4. ~~仿真引擎未集成~~ → ✅ 已与review流程对接+GA-S3 GroupAgent
5. ~~多模态风控未完善~~ → ✅ Paraformer+OCR+跨模态冲突检测
6. ~~ChromaDB未接入~~ → ✅ Memory Stream+三因子检索+模型预热
7. ~~前端三面板布局未完成~~ → ✅ 完整三面板+6个新组件

> **项目状态**: ✅ 全部6个阶段已完成，详见 `docs/PROJECT_COMPLETION_REPORT.md`

---

## 实施计划: 6阶段路线图

### 阶段1: 回归核心 — 单入口串联 ✅ 已完成

**目标**: 5核心API端点端到端跑通,输出可读风险报告,建立准确率基线

**Go/No-Go**: 核心流程端到端跑通,输出可读报告 → 继续;否则继续修核心流程

#### 1.1 后端核心API收敛
- [ ] 实现`POST /api/review`统一入口,支持video/text/mixed三种模式
- [ ] 实现`GET /api/review/{task_id}`获取预审结果(含7维+证据链+置信度)
- [ ] 实现`GET /api/review/{task_id}/progress`分析进度(5步骤推送)
- [ ] 实现`GET /api/history`历史记录
- [ ] 实现`GET /api/models`可用模型列表(硬件自适应)
- [ ] 重构`routes.py`,将76个旧路由标记deprecated,5核心端点为主
- [ ] 更新`ReviewTask`数据模型,增加mode/depth/platforms/result字段
- [ ] 实现ReviewOrchestrator编排器:内容理解→风险评估→报告输出

#### 1.2 风险评估流程完善
- [ ] 重构`analyzer.py`输出格式,对齐PRD 5.2节评估输出格式
- [ ] 实现7维评估引擎(`RiskAssessmentEngine`),每维度独立评估
- [ ] 实现证据链机制(`EvidenceChainBuilder`),每个风险结论可追溯
- [ ] 实现置信度量化(`ConfidenceCalculator`),多源交叉验证
- [ ] 实现不确定性标注(`UncertaintyAnnotator`),列出评估边界
- [ ] 实现平台反应汇总,各平台正面/中性/负面比例+差异分析
- [ ] 实现改写建议生成,高风险项2-3个替代方案

#### 1.3 多模态风控基础
- [ ] 完善关键帧提取(`KeyframeExtractor`),FFmpeg+PySceneDetect
- [ ] 实现OCR文字识别(`FrameOCR`),GLM-OCR本地+API降级
- [ ] 实现画面理解(`VisualRiskAssessor`),Qwen3-VL-Plus API+本地fallback
- [ ] 完善音频转写(`AudioAnalyzer`),faster-whisper本地+Paraformer API
- [ ] 实现跨模态冲突检测(`CrossModalConflictDetector`),画面vs文案vs音频
- [ ] 实现VRAM管理器(`VRAMManager`),模型加载/卸载顺序控制
- [ ] 实现硬件自适应检测(`detect_tier`),Lite/Standard/Pro层级

#### 1.4 前端三面板布局
- [ ] 实现三面板自适应布局(左栏240px/主内容区自适应/右栏320px可折叠)
- [ ] 完善左栏:上传区域(拖拽/选择)+历史记录+平台热力图
- [ ] 完善主内容区:分析流水线动画+风险仪表盘+风险时间线
- [ ] 完善右栏:风险详情+Agent反应+传播路径图+修改建议
- [ ] 实现WebSocket进度推送,5步骤实时更新
- [ ] 实现暗色主题配色(#0a0a0f背景+#6366f1→#8b5cf6渐变accent)

#### 1.5 数据库双轨迁移
- [ ] 更新`database.py`,支持MySQL+SQLite双轨(环境变量切换)
- [ ] 新增`HotspotCorrelationRecord`热点关联表
- [ ] 新增`EntityRiskChainRecord`实体风险链表
- [ ] 新增`SimulationSummaryRecord`仿真摘要表
- [ ] 新增`BacktestComparisonRecord`回测对比表
- [ ] 所有模型定义兼容MySQL(String长度/LONGTEXT)

#### 1.6 验收标准
- 单页面完成从输入到报告的完整流程
- 三种输入模式均可用
- 报告包含7维风险评级+证据链+置信度+不确定性+改写建议
- 建立准确率基线(记录初始值)
- 5核心API端点全部可用
- Lite模式零外部依赖可运行

---

### 阶段2: 全平台覆盖 + 信号采集集成 ✅ 已完成

**目标**: 从5平台扩展到25+平台,信号采集层接入主流程

**Go/No-Go**: 平台覆盖有效率>60% → 继续;否则缩减平台范围

#### 2.1 信号采集层集成
- [ ] 完善`HotlistFetcher`,对接NewsNow API热榜聚合(11+平台)
- [ ] 完善`RssFetcher`,RSS补充源(Hacker News/华尔街见闻/澎湃等)
- [ ] 完善`IncrementalDetector`,增量检测(新上榜/排名变化/下榜)
- [ ] 完善`EventDetector`,事件聚类+信号强度评估+因果链推理
- [ ] 完善`KeywordExtractor`,LLM关键词提取+TF-IDF降级
- [ ] 完善`DeepCrawler`,深度评论爬取(API优先+Playwright降级)
- [ ] 完善`SentimentAnnotator`,情感标注(BERT-LoRA+LLM反讽检测)
- [ ] 完善`SignalScheduler`,4种调度模式(realtime/standard/economy/manual)
- [ ] 信号采集接入风险评估流程:Step2信号关联+实体风险链+动态权重
- [ ] 实现`SignalRiskCorrelator`,文案与热点事件关联
- [ ] 实现`EntityRiskChain`,Neo4j实体风险链追踪
- [ ] 实现`DynamicRiskWeighting`,基于热点热度动态调整7维权重

#### 2.2 P0核心平台补全(6平台,每平台20原型)
- [ ] 微博人格模板+仿真器(`WeiboSimulator`):热搜机制+超话社区
- [ ] B站人格模板+仿真器(`BilibiliSimulator`):分区文化+弹幕+UP主粉丝
- [ ] 小红书人格模板+仿真器(`XiaohongshuSimulator`):种草文化+女性社区+推荐流
- [ ] 知乎人格模板+仿真器(`ZhihuSimulator`):长文思辨+匿名回答+专业领域
- [ ] 抖音人格模板+仿真器(`DouyinSimulator`):算法推荐+短视频+下沉市场
- [ ] 微信视频号人格模板+仿真器(`WechatChannelsSimulator`):社交图谱分发+半私密

#### 2.3 P1扩展平台新增(7平台,每平台15原型)
- [ ] 快手:老铁文化+直播打赏
- [ ] 微信公众号:长文+封闭传播
- [ ] 豆瓣:小组文化+文艺社区
- [ ] 虎扑:男性为主+体育/数码
- [ ] 今日头条:算法推荐+下沉市场
- [ ] 贴吧:兴趣社区+签到+等级
- [ ] TapTap:游戏社区+评分文化

#### 2.4 P2长尾平台(12平台,Group-tier统计模型)
- [ ] NGA/米游社/即刻/豆瓣小组/S1/V2EX/少数派/酷安/B站动态/网易云音乐/微博超话/小红书圈子
- [ ] 仅配置平台参数,使用Group-tier统计模型估算反应

#### 2.5 验收标准
- 25+平台均有人格模板和模拟器
- 平台覆盖有效率>60%
- 信号采集接入风险评估,Step2信号关联可工作
- 每平台至少15个原型覆盖主流/争议/极端/边缘/跨界群体

---

### 阶段3: 模型优化 + 人生故事驱动人格系统 ✅ 已完成

**目标**: 接入最新多模态API,引入Life Story驱动人格,让Agent更真实

**Go/No-Go**: 人生故事Agent比属性Agent仿真准确率提升>15% → 继续;否则保留属性Agent

#### 3.1 模型路由策略
- [ ] 接入LiteLLM统一API接口
- [ ] 实现模型路由配置:按任务类型自动选模型+硬件自适应
- [ ] 画面理解:Qwen3-VL-Plus → GLM-5V-Turbo → Qwen3-VL-8B(本地)
- [ ] OCR:GLM-OCR → PaddleOCR-VL-1.5 → Qwen3-VL-Plus(API)
- [ ] 音频转写:faster-whisper-large-v3 → Paraformer(API)
- [ ] 风险评估:DeepSeek-V4-Pro → Qwen3.6-Plus → Qwen3-32B(本地)
- [ ] Agent仿真:DeepSeek-V4-Flash → Qwen3.6-Plus → Qwen3-8B(本地)

#### 3.2 Life Story驱动人格系统
- [ ] 实现A-tier AI访谈生成器(`LifeStoryInterviewer`):6轮结构化访谈→数万字人生故事
- [ ] 实现B-tier CGSS采样+LLM丰富(`CGSSSampler`):人口统计采样→LLM推理L2-L7→千字故事
- [ ] 实现C-tier模板变体(`TemplateVariator`):原型模板+随机参数变体→百字梗概
- [ ] 实现Story→7层人格映射:从Life Story中提取/推理L1-L7
- [ ] 实现Story→Memory Stream转换(`StoryToMemoryConverter`):人生故事→初始记忆条目
- [ ] 实现人格完整性校验(`PersonaValidator`):7维度+Big Five一致性
- [ ] 实现人格生成Prompt设计,对齐设计文档3.4节

#### 3.3 ChromaDB向量检索接入
- [ ] ChromaDB内嵌式部署,零运维
- [ ] Memory Stream存储:ChromaDB向量+MySQL元数据
- [ ] 三因子检索:Recency(0.5)+Importance(0.3)+Relevance(0.2)
- [ ] 记忆类型:observation/reflection/plan

#### 3.4 知识图谱注入
- [ ] 完善本体生成器(`OntologyGenerator`):LLM分析文档→实体类型+关系类型
- [ ] 完善实体关系抽取器(`EntityExtractor`):文档分块→LLM+NER→去重合并
- [ ] 完善图谱存储(`GraphStore`):Neo4j CRUD+图遍历+路径查询+社区检测
- [ ] 知识图谱注入Agent L3知识背景层

#### 3.5 验收标准
- 最新多模态API正常调用,模型路由自动切换
- A-tier生成6轮访谈,每轮2000+字
- 人格一致性校验通过率>85%
- ChromaDB向量检索延迟<100ms
- 人生故事Agent vs 属性Agent仿真准确率有提升

---

### 阶段4: 效果提升 — Memory Stream + 平台浸泡 ✅ 已完成

**目标**: Memory Stream+平台浸泡让Agent反应更真实稳定

**Go/No-Go**: Memory Stream Agent反应一致性(Big Five重复测试r)>0.7 → 继续

#### 4.1 Memory Stream + Reflection
- [ ] 实现Memory Stream存储(`MemoryStreamStore`):ChromaDB+MySQL
- [ ] 实现三因子检索:Recency+Importance+Relevance加权
- [ ] 实现Reflection触发机制(`ReflectionTrigger`):累积重要性阈值
- [ ] 实现Reflection执行:LLM生成反思问题→检索相关记忆→生成反思
- [ ] 实现记忆衰减:Recency指数衰减+访问更新

#### 4.2 平台信息浸泡系统
- [ ] 实现平台浸泡(`PlatformImmersion`):Agent初始化后模拟刷平台7-30天
- [ ] 浏览热榜→选择性吸收→形成初始态度
- [ ] 基于人格特征筛选关注内容(L3专业领域/L2价值观)
- [ ] 对核心热点生成初始态度,写入Memory Stream

#### 4.3 社交网络构建
- [ ] 实现社会关系网络生成器:属性相似度+小世界网络+幂律影响力
- [ ] 关系类型:关注/互关/同社群/价值观同盟/对立
- [ ] 影响力分配:Pareto分布,前1%大V拥有50%关注
- [ ] Neo4j存储社交图谱(Lite模式降级MySQL)

#### 4.4 仿真引擎集成
- [ ] 实现仿真编排器(`SimulationOrchestrator`):统一调度仿真全流程
- [ ] 四层Agent架构:A-tier(KOL独立LLM)/B-tier(采样LLM)/C-tier(规则引擎)/Group-tier(统计模型)
- [ ] asyncio.Queue异步通信:event_queue/action_queue/feedback_queue
- [ ] 5阶段传播模型:种子→扩散→爆发→长尾→沉淀
- [ ] 极化检测(`PolarizationDetector`):双峰性+中间派缺失
- [ ] 仿真时间模型:8时段活跃度分配+Agent个性化时间表
- [ ] 仿真终止条件:活动度<5%/最大轮次/沉淀3轮/成本超限
- [ ] 仿真启用/降级逻辑:静态评估阈值→信号关联→Agent仿真

#### 4.5 前端增强
- [ ] 传播推演可视化(D3.js力导向图)
- [ ] 极化趋势折线图(ECharts)
- [ ] 热点关联列表(Naive UI NList)
- [ ] 实体风险链时间线(Naive UI NTimeline)
- [ ] 置信度标签+不确定性Tooltip
- [ ] 历史报告对比

#### 4.6 验收标准
- 浸泡后Agent对热点话题有"近期态度"
- Big Five重复测试一致性>0.7
- 社交网络传播路径可视化可渲染1000+节点
- 仿真引擎可完成100-500 Agent仿真

---

### 阶段5: 规模化仿真 ✅ 已完成

**目标**: Agent规模递进到万级,通过Group Agent扩展到等效十万级

**Go/No-Go**: 1000+Agent仿真结果稳定性(3次一致性>60%) → 继续

#### 5.1 Agent规模递进
- [ ] 100 Agent轻量仿真(1-2分钟,~¥0.5)
- [ ] 500 Agent标准仿真(3-5分钟,~¥2)
- [ ] 2000 Agent深度仿真(10-15分钟,~¥5)
- [ ] 10000 Agent大规模仿真(20-40分钟,~¥10-20)

#### 5.2 GA-S3 Group Agent机制
- [ ] 实现GroupAgent:统计模型代表10-100个相似个体
- [ ] 蒙特卡洛采样生成群组反应
- [ ] 群组统计特征:年龄分布/立场分布/活跃度分布
- [ ] 等效覆盖>100000个体

#### 5.3 极化检测与舆论转折预测
- [ ] 极化指数计算:双峰性+中间派缺失
- [ ] 极化预警:5级(无极化→极端极化)
- [ ] 舆论转折预测:传播阶段+极化趋势+关键节点

#### 5.4 回测框架
- [ ] 回测用例整理:从cases/paperwork提取5+标准用例
- [ ] 回测运行器(`BacktestRunner`):A/B/C/D/E五组对比
- [ ] 多轮一致性检查(`ConsistencyChecker`):3轮仿真一致性
- [ ] 可信度标注系统(`CredibilityAnnotation`)
- [ ] V2 vs MVP对比报告(`ComparisonReport`)
- [ ] Go/No-Go判定:方向准确率>55%且V2比MVP提升>10%

#### 5.5 批量分析优化
- [ ] 批量提交+队列处理
- [ ] 结果缓存+增量分析
- [ ] LLM调用量优化:异步流水线+并发控制

#### 5.6 验收标准
- 10000 Agent仿真在40分钟内完成
- 3次仿真一致性>60%
- Group Agent扩展后等效个体数>10万
- 回测5+案例,V2方向准确率>55%

---

### 阶段6: 扩展功能 ✅ 已完成

- [ ] 博主历史分析
- [ ] 竞品对比
- [ ] 信号采集面板
- [ ] 知识图谱可视化
- [ ] 本地模型部署
- [ ] 趋势预测(仿真验证Go后)
- [ ] 反事实仿真(主线仿真稳定后)
- [ ] 决策辅助(报告质量稳定后)

---

## 执行原则

1. **每个阶段完成后按Go/No-Go决策**,通过后进入下一阶段
2. **收益最高的任务优先投入资源**,收益后置的任务(阶段6)仅在主线稳定后考虑
3. **降级可用**:每个依赖项不可用时系统仍可产出报告(降级标注)
4. **发前风控优先**:所有能力围绕"让风控更准"展开
5. **验证优先于扩展**:仿真可信度是后续一切预测功能的前提

## 技术债务清理(穿插在各阶段)

| 项目 | 当前状态 | 目标 | 计划阶段 |
|------|---------|------|---------|
| routes.py旧端点 | 76个路由(含5核心+71旧) | 5核心端点为主,旧端点标记deprecated | 阶段1 |
| RiskItem模型 | severity是字符串非数值 | 加risk_score数值列 | 阶段1 |
| run_analysis数据流 | analyzer写入字段与前端期望不完全对齐 | 重构analyzer输出格式 | 阶段1 |
| 视频文件上传 | 前端传文件名字符串 | 后端文件上传端点+前端FormData | 阶段1 |
| echarts chunk 1.1MB | 构建成功但包较大 | code-split或换轻量图表库 | 阶段4 |
