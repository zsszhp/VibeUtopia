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

### 阶段 2 完成进度（2026-05-15）
- Date: 2026-05-15
- Context: 阶段 2 验收测试全部通过
- Category: 代码结构|测试方法
- Instructions:
  - 阶段 2 验收测试通过率 100%（4/4 测试通过）
  - 验收标准 1：5 大核心平台人格原型覆盖率 - 100 个原型（每平台 20 个）✅
  - 验收标准 2：回测命中率 85.0%（要求≥60%）✅
  - 验收标准 3：平台情绪差异测试 - 标准差 0.195/0.120（要求>0.01）✅
  - 验收标准 4：P0 平台影响占比 82.8%~100%（要求≥70%）✅
  - 回测案例库：40 个案例（36 个 paperwork + 4 个 video_transcript）
  - 阶段 2.1~2.4 已完成，阶段 2.5（Prompt 版本管理）待执行
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

- Date: [2026-05-15]
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
