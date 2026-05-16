# VibeUtopia 项目指令

> 本文件控制 Claude Code 在本项目中的**默认行为**。每次会话自动加载。

---

## 🔒 强制 Git 工作流（最高优先级）

**多人协作项目，以下步骤绝对不能跳过：**

1. **动手前** — `git pull` 拉取两个远端最新代码
2. **动手前** — 若有本地未提交改动，先 `git add -A && git commit -m "详细中文" && git push gitee && git push github`
3. **动手后** — 完成后必须 `git add -A && git commit -m "详细中文" && git push gitee && git push github`
4. **提交注释** — 所有 commit message 用中文，说明修改内容、原因、影响范围
5. **MEMORY.md 必须提交** — `.monkeycode/MEMORY.md` 每次更新后必须 push

两个远端：
- Gitee: `https://gitee.com/zzsszhp/VibeUtopia.git`
- GitHub: `https://github.com/zsszhp/VibeUtopia`

---

## 🎯 默认 Skill 调用规则

### 每次会话开始时
- 调用 `using-superpowers` — 确认当前适用的 skill，检查是否匹配任务

### 创建功能 / 修改行为前
- 调用 `brainstorming` — 先设计再实现，"简单"功能也要过设计流程
- 设计完成后调用 `writing-plans` — 生成详细实施计划

### 代码搜索 / 定位 / 小修改
- 默认使用 `cavecrew` 子代理（而非 vanilla Explore），节省 ~60% token
- 模式：`cavecrew-investigator`（定位）→ `cavecrew-builder`（修改）→ `cavecrew-reviewer`（审查）

### 遇到 Bug / 测试失败
- 调用 `systematic-debugging` — 先查根因再修，禁止猜测式修复

### 完成任何任务前
- 调用 `verification-before-completion` — 必须有验证证据才能声称完成
- 未运行验证命令 = 不能说"完成"

### 修改代码后
- 调用 `simplify` — 审查变更代码的质量和效率

---

## 📁 项目不可删除的文件

- `tests/video/` — 4 个测试案例的音视频文件（Git LFS 跟踪）
- `references/projects/` — 25+ 开源项目源码（本地保留，不上传 git）
- `references/papers/` — 25+ 篇 PDF 论文（本地保留，不上传 git）

---

## 🧠 记忆文件

- **项目规范记忆**: `.monkeycode/MEMORY.md` — 多人协作共享规范
- **Claude 记忆**: `~/.claude/projects/E--z-project-my-VibeUtopia/memory/` — Claude 持久化记忆

两者都要保持同步更新。

---

## 📊 项目进度速查

| 阶段 | 状态 |
|------|------|
| MVP（基础风控） | ✅ 完成 |
| V2.R1-R6（增强→多模态→世界构建→博主） | ✅ 完成 |
| V2+（大规模仿真+决策辅助） | ✅ 完成 |
| V3（25+平台+本地模型+多语言） | 🔜 规划中 |

详细进度见 `.monkeycode/MEMORY.md` 和 `docs/15_环境与待办事项.md`。

---

## ⚠️ 红线

- 不得跳过 Git 工作流步骤
- 不得在未验证的情况下声称任务完成
- 不得删除 `tests/video/`、`references/projects/`、`references/papers/`
- 不得在未调用 `brainstorming` 的情况下直接实现新功能
- commit message 必须用中文，不得用英文或无意义描述
