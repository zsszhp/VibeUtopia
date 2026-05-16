# 参与贡献指南 / Contributing Guide

感谢你对 VibeUtopia 项目的关注！我们欢迎任何形式的贡献。

Thank you for your interest in VibeUtopia! We welcome contributions of all kinds.

---

## 如何贡献 / How to Contribute

### 报告问题 / Reporting Issues

如果你发现了 Bug 或有功能建议：

1. 在 [GitHub Issues](https://github.com/zsszhp/VibeUtopia/issues) 中搜索是否已有相关问题
2. 如果没有，创建新的 Issue，包含：
   - **Bug 报告**：复现步骤、预期行为、实际行为、环境信息（Python 版本、操作系统等）
   - **功能建议**：使用场景、期望效果、可能的实现思路

If you find a bug or have a feature suggestion:

1. Search [GitHub Issues](https://github.com/zsszhp/VibeUtopia/issues) for existing reports
2. If none exists, create a new Issue with:
   - **Bug report**: Steps to reproduce, expected behavior, actual behavior, environment info
   - **Feature request**: Use case, expected outcome, possible implementation ideas

### 提交代码 / Submitting Code

1. **Fork 仓库** — 点击 GitHub 页面右上角的 Fork 按钮

2. **克隆到本地**
   ```bash
   git clone https://github.com/your-username/VibeUtopia.git
   cd VibeUtopia
   ```

3. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或修复分支
   git checkout -b fix/your-fix-name
   ```

4. **开发与测试**
   - 确保代码风格与现有代码一致
   - 新功能需要包含对应的测试
   - 运行现有测试确保没有破坏

5. **提交代码**
   ```bash
   git add .
   git commit -m "feat: 简短描述你的改动"
   ```

   提交信息格式（Conventional Commits）：
   - `feat:` 新功能
   - `fix:` 修复 Bug
   - `docs:` 文档更新
   - `style:` 代码格式调整（不影响功能）
   - `refactor:` 重构
   - `test:` 测试相关
   - `chore:` 构建/工具链相关

6. **推送到你的 Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   - 在 GitHub 上创建 PR，目标分支为 `main`
   - 描述你的改动内容和原因
   - 关联相关的 Issue（如有）

---

## 开发环境搭建 / Development Setup

### 后端 / Backend

```bash
# 创建 Python 虚拟环境
conda create -n vibeutopia python=3.10
conda activate vibeutopia

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 启动后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端 / Frontend

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

---

## 代码规范 / Code Style

### Python 后端
- 遵循 [PEP 8](https://peps.python.org/pep-0008/) 代码风格
- 使用类型注解（Type Hints）
- 函数和类添加中文文档字符串

### Vue 前端
- 遵循 [Vue 官方风格指南](https://vuejs.org/style-guide/)
- 使用 TypeScript
- 组件命名使用 PascalCase

### 通用规范
- 每次提交只做一件事，保持提交粒度合理
- 提交信息清晰描述改动内容
- 不提交调试代码、个人配置等无关文件

---

## 许可证 / License

通过向 VibeUtopia 贡献代码，你同意你的贡献将在 [AGPL-3.0](LICENSE) 许可证下授权。

By contributing code to VibeUtopia, you agree that your contributions will be licensed under the [AGPL-3.0](LICENSE) license.
