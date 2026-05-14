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

### 每次动手前先提交推送到git
- Date: 2026-05-14
- Context: 用户在回测完成后明确指令
- Instructions:
  - 每次执行新的开发任务前，必须先执行 `git add -A && git commit -m "..." && git push` 确保当前状态已保存并推送
  - 这是强制性的第一步，不能跳过

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
