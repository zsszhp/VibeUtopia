---
description: Git 开发工作流
globs:
alwaysApply: true
---

## 分支策略

- **只在 main 分支开发**：单人/多人协作模式，不强制 feature 分支
- **动手前必须 pull**：先拉取两个远端最新代码
- **AI 可执行 pull/merge/fetch**：但不执行 commit/push（由用户手动操作）

## 双远端管理

必须同步推送到两个平台：
- **Gitee**: `https://gitee.com/zzsszhp/VibeUtopia.git`
- **GitHub**: `https://github.com/zsszhp/VibeUtopia.git`

## Commit 规范

- **格式**：`feat: 新增XXX功能` / `fix: 修复XXX问题` / `refactor: 重构XXX`
- **语言**：必须使用中文
- **描述**：说明修改内容、原因、影响范围
- **一个 commit 只做一件事**：完成小目标就提交，大目标完成再总结提交
- **每个 commit 必须可工作**：禁止提交半成品/编译不通过的代码

## 工作流程

### 动手前
1. `git pull gitee main && git pull github main` — 拉取两个远端
2. 若有本地未提交改动：
   - `git add -A`
   - `git commit -m "详细中文描述"`
   - `git push gitee && git push github`

### 完成后
1. `git add -A`
2. `git commit -m "详细中文描述"`
3. `git push gitee && git push github`

## 冲突处理

- 合并冲突逐文件选最优方案，不要盲目覆盖
- 合并后必须编译+测试
- 无法判断时询问用户

## 不可删除的文件

- `tests/video/` — 测试音视频文件（Git LFS 跟踪）
- `references/projects/` — 25+ 开源项目源码
- `references/papers/` — 25+ PDF 论文

## MEMORY.md 规范

- `.monkeycode/MEMORY.md` 每次更新后必须同步 push
- 多人协作共享规范在此维护
