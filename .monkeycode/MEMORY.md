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
- Context: 多人开发项目，用户明确指令规范 Git 提交流程
- Instructions:
  - **动手前拉取最新代码**: 每次执行新开发任务前，必须先执行 `git pull` 检查并拉取云端最新提交，确保在最新代码基础上修改（避免多人协作冲突）
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

### T3 Memory Stream + Reflection 机制实现
- Date: 2026-05-14
- Context: Agent 在执行 T3 任务（Memory Stream + Reflection 机制）时发现
- Category: 代码结构
- Instructions:
  - Reflection 触发机制：当 24 小时内未反射的 observation 记忆累积重要性≥10.0 时自动触发
  - Reflection 执行流程：生成 2-3 个反思问题 → 检索相关记忆 (Top-5) → LLM 生成反思文本 (200-400 字) → 评估重要性 (0.7-1.0) → 存储为 reflection 记忆
  - Memory Stream 三因子检索权重：Recency(0.5) + Importance(0.3) + Relevance(0.2)
  - Recency 衰减公式：e^(-0.05 × hours_elapsed)
  - Reflection 后台异步执行，不阻塞主流程
  - 集成方式：在 Memory Store 中调用 check_and_trigger_reflection(agent_id) 方法

### T5 信号关联 + 实体风险链 + 动态权重实现
- Date: 2026-05-14
- Context: T5 任务验证完成（现有实现已完整）
- Category: 代码结构
- Instructions:
  - 信号关联：从文案提取关键词 → 查询最近 72 小时热搜/种子事件 → LLM 评估关联度 (0-1) → 输出风险维度提升
  - 实体风险链：提取命名实体 → Neo4j 查询关联关系 → 追踪风险传导路径 (max_depth=3) → 评估链路风险分
  - 动态权重：基础权重 + 信号提升 + 实体提升 → 综合计算 total_boost = max(s,e) + min(s,e)*0.3 → 调整后权重上限 3.0
  - 集成入口：enhanced_analyzer.py 的 run_enhanced_analysis() 函数
  - 使用模式：quick(Phase1+2) / deep(Phase1+2+3)
  - 降级机制：LLM 失败→规则匹配，Neo4j 不可用→常识分析

### T0.1 回测案例库建设
- Date: 2026-05-14
- Context: Agent 在执行 T0.1 任务（建立回测案例库）时发现
- Category: 测试方法
- Instructions:
  - 回测案例库存放位置：`/workspace/cases/`
  - paperwork 目录：29 个正式测试案例（真实历史事件改编），文件命名 `{事件简述}.md`
  - video_transcript 目录：4 个视频转写测试案例，文件命名 `{BV 号}.md`
  - 案例索引：`cases/回测案例库索引.md` 包含完整清单和风险维度覆盖
  - 风险维度覆盖：17+ 维度（法律合规、道德伦理、政治敏感、群体冒犯、宗教敏感、历史虚无主义、医疗谣言、金融诈骗、色情低俗、未成年人保护、自杀自残、动物保护、食品安全、环保争议、知识产权、价值观扭曲、学术诚信、商业诚信、教育系统）
  - 风险等级分布：高风险 17 个 (58%)，中风险 12 个 (42%)
  - 案例结构：事件背景、风险触发点、舆论发酵、处理结果、专家点评
  - 使用方式：阶段 1/阶段 2 验收时选取案例验证风险等级正确率

### 单一主分支策略
- Date: 2026-05-14
- Context: 用户明确指令规范 Git 分支管理策略
- Instructions:
  - **只保留一个主分支**: 项目只允许存在 main 主分支，不允许创建或保留其他分支
  - **特性分支处理流程**: 开发任务完成后，必须立即合并到 main 分支并删除该特性分支
  - **禁止长期分支**: 不允许存在长期开发的分支，所有开发应在 main 分支上进行
  - **远程分支清理**: 本地分支合并删除后，必须同时删除远程对应的分支（git push origin --delete <branch-name>）
  - **分支合并命令**: 
    ```bash
    git checkout main
    git merge --no-ff <feature-branch> -m "merge: 合并 <分支名> 到主分支\n\n合并原因：统一代码到主分支，删除特性分支"
    git branch -D <feature-branch>
    git push origin --delete <feature-branch>
    ```
  - 这是强制性分支管理策略，不能违反

### 版本迭代测试流程
- Date: 2026-05-14
- Context: 用户明确指令版本迭代测试规范
- Instructions:
  - 每完成一个大版本工作后，必须进行详细完整的测试
  - 测试内容：与上一个版本相比，验证是否有优化和进步
  - 强制要求：全部功能测试完成后才能开始下一个大版本的开发
  - 测试范围：覆盖所有核心功能模块，确保新功能的正确性和现有功能的稳定性
  - 这是强制性工作流，不能跳过测试环节直接进入下一版本开发

### 阶段 2 验收测试规范
- Date: 2026-05-14
- Context: Agent 在执行阶段 2 验收测试时发现
- Category: 测试方法
- Instructions:
  - 阶段 2 验收使用 30+ 真实案例（多领域覆盖）进行验证
  - 验收标准 4 项：人格原型覆盖率、回测命中率、平台情绪差异、P0 平台影响占比
  - 测试脚本：`tests/phase2_acceptance_test.py`
  - 报告输出：`tests/PHASE2_ACCEPTANCE_REPORT.md` 和 `tests/phase2_acceptance_report.json`
  - 验收通过后才能进入阶段 3（模型优化 + 人生故事生成）
