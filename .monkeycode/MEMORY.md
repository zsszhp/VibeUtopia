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
- Category: [代码结构|代码模式|代码生成|构建方法|测试方法|依赖关系|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

### 多人协作Git工作流规范
- Date: 2026-05-14
- Context: 用户在阶段1开发完成后明确指令（更新合并原有"每次动手前先提交推送到git"条目）
- Instructions:
  - **动手前检查云端**: 每次执行新开发任务前，必须先执行 `git pull` 检查并拉取云端最新提交，确保在最新代码基础上修改（多人协作项目，避免冲突）
  - **动手前提交备份**: 拉取最新代码后，若有本地未提交改动，先执行 `git add -A && git commit -m "详细中文注释" && git push` 保存当前状态
  - **动手后提交备份**: 完成开发任务后，必须执行 `git add -A && git commit -m "详细中文注释" && git push` 推送备份
  - **提交注释要求**: 所有git commit message必须使用详细的中文注释，说明修改内容、原因和影响范围，不得使用简短英文或无意义描述
  - 这是强制性工作流，不能跳过任何步骤

### LLM模型配置
- Date: 2026-05-14
- Context: Agent 在配置模型路由时发现
- Category: 环境配置
- Instructions:
  - 使用LongCat系列模型：Thinking-2601(advanced)、Omni-2603(advanced/vision-only)、Chat(standard)、Lite(standard)
  - Omni模型标记text=false，不用于纯文本任务（返回400错误）
  - API Key: ak_2mC1K99ZH6lS9Wh3SE2C30YM7x（配置在.env中）

### 回测运行方式
- Date: 2026-05-14
- Context: Agent 在执行回测验证时发现
- Category: 测试方法
- Instructions:
  - 使用 tests/backtest_full.py 运行回测，直接调用风险评估模块（跳过平台仿真等耗时步骤）
  - 25个案例约耗时5分钟
  - 报告输出到 data/backtest/report_*.json

### 回测基线与T4/T5优化进度
- Date: 2026-05-14
- Context: Agent 在执行T4/T5优化任务时发现
- Category: 测试方法
- Instructions:
  - 回测基线（优化前）：综合准确率69%，red类29%，green类100%
  - T4优化（Prompt从7维扩展到11维）：综合准确率提升至77%（+8%），red类提升至57%（+28%）
  - T5集成（信号关联+实体风险链+动态权重）：已集成到回测流程，完整验证待API配额恢复
  - 新增4个维度：事实错误、平台禁区、情绪极化、价值观倾向
  - 红线维度评分标准：触碰即HIGH 76+（政治敏感、法律合规、民族宗教、事实错误、平台禁区）
  - 多维度叠加机制：3个及以上维度触发时总分必须≥76

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
- Category: 代码结构|代码生成|构建方法
- Instructions:
  - T1 系统已完成集成，包含 A/B/C 三级人格生成器和 Memory Stream 向量记忆存储
  - 使用 PersonaFactory 统一生成人格，通过 tier 参数选择策略 (A/B/C)
  - API 端点位于 /api/v1/persona/* 和 /api/v1/memory/*
  - C-tier 适用于快速测试 (<1s, 质量 0.91+)，B-tier 适用于批量生成 (~30s, 质量 0.92+)
  - Memory Stream 使用 ChromaDB 优先，自动降级到数据库检索
  - 三因子检索权重：Recency(0.5) + Importance(0.3) + Relevance(0.2)
  - 生成的人格包含 7 层结构 (L1-L7) 和 Big Five 人格特质
  - 质量校验通过 QualityValidator 自动进行
