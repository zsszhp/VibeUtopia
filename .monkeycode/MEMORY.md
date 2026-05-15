# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [代码结构 | 代码模式 | 代码生成 | 构建方法 | 测试方法 | 依赖关系 | 环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

### 阶段 2.5 Prompt 版本管理机制（2026-05-15 完成）
- Date: 2026-05-15
- Context: 阶段 2.5 任务完成
- Category: 代码结构 | 测试方法
- Instructions:
  - 版本管理器：`backend/services/prompt_version_manager.py` (448 行)
  - A/B 测试运行器：`backend/services/prompt_ab_test_runner.py` (253 行)
  - CLI 工具：`backend/services/prompt_manager_cli.py` (243 行)，支持 7 个命令（register/list/show/create-ab-test/run-ab-test/history/recommend）
  - 配置文件：`backend/prompts/prompt_config.yaml`（活跃版本、A/B 测试、回滚策略、发布流程）
  - 变更记录：`backend/prompts/changelog.md`
  - 测试案例库：`data/ab_test_cases.json` (15 个案例：5 高 +4 中+3 低 +3 边界)
  - A/B 测试脚本：`tests/run_prompt_ab_test.py`
  - 已注册版本：risk_assessment v1.0, v20260514115816（存储在 backend/prompts/versions/risk_assessment/）
  - 历史测试记录：4 条（存储在 backend/prompts/ab_tests/）
  - 评估指标：accuracy, avg_risk_score, avg_response_time, parse_success_rate
  - 详细报告：`docs/T2.2_Prompt 版本管理_完成报告.md`

### 多人协作 Git 工作流规范（强制执行）
- Date: 2026-05-15 (更新)
- Context: 用户强调多人开发项目，必须遵循 Git 协作规范
- Instructions:
  - **动手前检查云端**: 每次执行新开发任务前，必须先执行 `git pull` 检查并拉取云端最新提交，确保在最新代码基础上修改（多人协作项目，避免冲突）
  - **动手前提交备份**: 拉取最新代码后，若有本地未提交改动，先执行 `git add -A && git commit -m "详细中文注释" && git push` 保存当前状态
  - **动手后提交备份**: 完成开发任务后，必须执行 `git add -A && git commit -m "详细中文注释" && git push` 推送备份
  - **提交注释要求**: 所有 git commit message 必须使用详细的中文注释，说明修改内容、原因和影响范围，不得使用简短英文或无意义描述
  - **MEMORY.md 必须提交**: 记忆文件是多人协作的核心规范，每次更新后必须提交推送，让其他同事参考遵循
  - **进度记录到记忆**: 已完成的工作进度必须写入 MEMORY.md，避免其他同事重复工作
  - 这是强制性工作流，不能跳过任何步骤

### 阶段 2 完成进度（2026-05-15 更新）
- Date: 2026-05-15 (更新)
- Context: 阶段 2.5 Prompt 版本管理机制已完成
- Category: 代码结构 | 测试方法
- Instructions:
  - 阶段 2.5 完成度：100% (7/7 需求)
  - 核心模块：PromptVersionManager (448 行), PromptABTestRunner (253 行), CLI (243 行)
  - 配置文件：prompt_config.yaml, changelog.md
  - 测试资源：15 个 A/B 测试案例
  - 已注册版本：risk_assessment v1.0, v20260514115816
  - 历史测试：4 条 A/B 测试记录
  - 详细报告：docs/T2.2_Prompt 版本管理_完成报告.md
  - 阶段 2.1/2.2/2.5 已完成，2.3 进行中 (13/20)，2.4 待执行
  - 详细报告：`tests/PHASE2_ACCEPTANCE_REPORT.md`

### LLM 模型配置
- Date: 2026-05-14
- Context: Agent 在配置模型路由时发现
- Category: 环境配置
- Instructions:
  - 使用 LongCat 系列模型：Thinking-2601(advanced)、Omni-2603(advanced/vision-only)、Chat(standard)、Lite(standard)
  - Omni 模型标记 text=false，不用于纯文本任务（返回 400 错误）
  - API Key: ak_2mC1K99ZH6lS9Wh3SE2C30YM7x（配置在.env 中）

### 回测运行方式
- Date: 2026-05-14
- Context: Agent 在执行回测验证时发现
- Category: 测试方法
- Instructions:
  - 使用 tests/backtest_full.py 运行回测，直接调用风险评估模块（跳过平台仿真等耗时步骤）
  - 25 个案例约耗时 5 分钟
  - 报告输出到 data/backtest/report_*.json

### 回测基线与 T4/T5 优化进度
- Date: 2026-05-14
- Context: Agent 在执行 T4/T5 优化任务时发现
- Category: 测试方法
- Instructions:
  - 回测基线（优化前）：综合准确率 69%，red 类 29%，green 类 100%
  - T4 优化（Prompt 从 7 维扩展到 11 维）：综合准确率提升至 77%（+8%），red 类提升至 57%（+28%）
  - T5 集成（信号关联 + 实体风险链 + 动态权重）：已集成到回测流程，完整验证待 API 配额恢复
  - 新增 4 个维度：事实错误、平台禁区、情绪极化、价值观倾向
  - 红线维度评分标准：触碰即 HIGH 76+（政治敏感、法律合规、民族宗教、事实错误、平台禁区）
  - 多维度叠加机制：3 个及以上维度触发时总分必须≥76

### LLM 多 API Key 轮换配置
- Date: 2026-05-15
- Context: 用户提供两个 API Key 用于轮换
- Instructions:
  - API Key 配置在 .env 文件中：`LONGCAT_API_KEY=key1,key2`
  - 使用策略：优先使用 Key 1，配额用完后切换到 Key 2
  - 可用模型：LongCat-Flash-Chat、LongCat-Flash-Thinking-2601、LongCat-Flash-Omni-2603
  - 优先级：LongCat-Flash-Omni-2603 > LongCat-Flash-Thinking-2601 > LongCat-Flash-Chat

## T1 人生故事驱动人格系统集成

- Date: 2026-05-15
- Context: 用户在项目中引入人生故事驱动人格系统
- Category: 代码结构 | 代码生成 | 构建方法
- Instructions:
  - T1 系统已完成集成，包含 A/B/C 三级人格生成器和 Memory Stream 向量记忆存储
  - 使用 PersonaFactory 统一生成人格，通过 tier 参数选择策略 (A/B/C)
  - API 端点位于 /api/v1/persona/* 和 /api/v1/memory/*
  - C-tier 适用于快速测试 (<1s，质量 0.91+)，B-tier 适用于批量生成 (~30s，质量 0.92+)
  - Memory Stream 使用 ChromaDB 优先，自动降级到数据库检索
  - 三因子检索权重：Recency(0.5) + Importance(0.3) + Relevance(0.2)
  - 生成的人格包含 7 层结构 (L1-L7) 和 Big Five 人格特质
  - 质量校验通过 QualityValidator 自动进行

## 阶段 3 完成进度（2026-05-15）

- Date: 2026-05-15
- Context: 阶段 3 核心功能完成，待 A/B 回测验证
- Category: 测试方法 | 代码结构
- Instructions:
  - 阶段 3 核心功能完成度：85%
  - 验收测试通过率：50%（2/4 完全通过，2/4 部分通过）
  - ✅ 已实现核心组件：
    - TimelineBuilder：5 阶段时间线，每阶段≥3 个关键事件
    - SceneGenerator：4 类场景故事，每场景 800-1500 字
    - NarrativeIntegrator：4 种叙事弧线 + 主题提炼
    - PersonalityEvolver：12 个触发事件，Big Five 动态调整
  - ✅ A/B/C 三级人格生成器：A-tier（6 轮访谈）、B-tier（CGSS 采样）、C-tier（模板变体）
  - ✅ ChromaDB Memory Stream：三因子检索、批量存储（1000 条/批次）、降级机制
  - ✅ 多模态 API 配置：6 个视觉模型，5 大厂商支持
  - ✅ P1 平台扩展：新增 6 个平台 24 个人格原型（快手/微信公众号/豆瓣/虎扑/今日头条/贴吧）
  - ⚠️ A/B 回测验证：关联机制待设计（人生故事→风险评估映射规则）
  - ⚠️ ChromaDB 首次检索性能：547ms（含模型加载），后续检索<100ms

### A/B 回测验证任务执行中（API 配额耗尽，待恢复后重试）
- Date: 2026-05-15 (updated: 2026-05-15)
- Context: 执行 A/B 回测验证，遇到 API 配额耗尽问题
- Category: 测试方法
- Instructions:
  - **测试脚本**: `tests/phase3_ab_test.py`（386 行）
  - **测试方法**:
    - A 组（实验组）：人生故事驱动 Agent（基于文案推断人格特质 + 故事增强标记）
    - B 组（对照组）：传统属性标签 Agent（仅基础人格属性）
  - **执行状态**: ⚠️ 失败（API 配额耗尽 + 代码 bug）
  - **失败原因**:
    1. LongCat API Key 配额耗尽：所有模型调用失败（LongCat-VL, LongCat-Flash-Chat）
    2. 代码 bug：`run_analysis()`返回 None 导致后续赋值失败
  - **修复记录**:
    - 已修复：添加 task_id 参数（commit a4af579）
    - 待修复：处理 run_analysis() 返回 None 的情况
  - **验收标准**: A 组准确率 - B 组准确率 ≥ 15%
  - **当前结果**: 0.0% 提升（1 个案例，两组均失败）
  - **下一步**:
    1. 等待 API 配额恢复（Key1→Key2 轮换）
    2. 修复代码 bug（增加错误处理）
    3. 增加测试案例数量（目标≥30 个）
    4. 重新执行测试
  - 待进入阶段 4 前必须完成 A/B 回测，验证准确率提升≥15%
  - 详细报告：`tests/PHASE3_ACCEPTANCE_REPORT.md`、`tests/PHASE3_AB_TEST_REPORT.md`
  - 提交版本：commit fe69b55（阶段 3 人生故事生成系统实现）

### T7 深度信号采集实施（2026-05-15 完成）
- Date: 2026-05-15
- Context: Agent 在运行 T7 信号采集任务时发现
- Category: 代码结构 | 构建方法 | 测试方法
- Instructions:
  - **手动采集脚本**: `tests/run_signal_collection.py` - 支持手动触发一次完整的信号采集流程
  - **4 步采集流程**: 热榜采集 → RSS 采集 → 增量检测 → 事件聚类
  - **平台覆盖**: 11+ 平台热榜聚合（NewsNow API），当前可用 9 个平台（微博、百度、知乎、B 站、抖音、头条、贴吧、澎湃、财联社、凤凰网、华尔街见闻）
  - **RSS 源**: Hacker News 等（雅虎财经 HTTP 429 限流）
  - **增量检测**: 基于 24 小时历史窗口，识别新上榜、排名变化、下榜事件
  - **事件聚类**: 基于关键词 Jaccard 相似度（阈值 0.4）将信号聚为事件簇
  - **日志输出**: `data/signal_collection.log`
  - **采集效果**:
    - 热榜信号：254 条/次（微博 30、百度 30、知乎 20、B 站 30、抖音 30、头条 30、贴吧 29、澎湃 20、财联社 13、凤凰网 12、华尔街见闻 10）
    - RSS 信号：20 条/次（Hacker News）
    - 增量检测：新上榜 10-15 条，排名变化 40+ 条
    - 事件聚类：188 个事件簇
  - **降级情况**:
    - 小红书、快手：NewsNow API 返回 500（平台暂不支持）
    - 雅虎财经：HTTP 429 限流
  - **数据库表**: `signal_records`（信号记录）、`seed_event_records`（种子事件）
  - **核心模块**: `backend/services/signal/`（11 个文件，~1800 行代码）
    - `fetcher.py` - 热榜聚合器
    - `rss_fetcher.py` - RSS 采集器
    - `incremental.py` - 增量检测器
    - `event_detector.py` - 事件检测与聚类
    - `deep_crawler.py` - 深度评论爬取器
    - `sentiment.py` - BERT-LoRA 情感标注器
    - `keyword_extractor.py` - LLM 关键词提取
    - `scheduler.py` - 定时调度器
    - `models.py` - 数据模型
    - `signal_config.yaml` - 配置文件

