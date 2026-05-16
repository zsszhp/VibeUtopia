# 致谢与参考项目 / Acknowledgments & References

VibeUtopia 的架构设计受到了以下优秀开源项目的启发。我们衷心感谢这些项目的作者和贡献者。

The architecture design of VibeUtopia was inspired by the following excellent open-source projects. We sincerely thank the authors and contributors of these projects.

---

## 参考项目 / Reference Projects

### 1. MiroFish

- **仓库 / Repository**: https://github.com/666ghj/MiroFish
- **许可证 / License**: AGPL-3.0
- **简介 / Description**: 基于 OASIS 框架（CAMEL-AI）的多Agent社交仿真引擎，使用 Zep Cloud 构建知识图谱，模拟 Twitter/Reddit 上的用户互动

**借鉴内容 / What We Learned**:
- 知识图谱驱动的世界构建理念
- LLM 增强的人格生成方法
- 双平台社交仿真的架构设计

---

### 2. BettaFish

- **仓库 / Repository**: https://github.com/666ghj/BettaFish
- **许可证 / License**: GPL-2.0 + Non-Commercial Learning License 1.1 + Apache-2.0 + MIT（多许可证）
- **简介 / Description**: 4-Agent 协作式舆情分析系统，具备 ForumEngine 协作机制和 MindSpider 两阶段爬取能力

**借鉴内容 / What We Learned**:
- ForumEngine 协作概念 — 专业Agent角色分工协作
- 两阶段爬取策略的设计思路
- 专业Agent角色分工的架构理念

---

### 3. TrendRadar

- **仓库 / Repository**: https://github.com/sansan0/TrendRadar
- **许可证 / License**: GPL-3.0
- **简介 / Description**: AI 驱动的舆情监控系统，使用 NewsNow API 聚合 11+ 平台热搜，支持 LiteLLM 多模型路由

**借鉴内容 / What We Learned**:
- NewsNow API 多平台热搜聚合方案
- 增量检测机制
- LiteLLM 多模型统一接口
- 3阶段 JSON 解析策略

---

### 4. DeepSearchAgent-Demo

- **仓库 / Repository**: https://github.com/666ghj/DeepSearchAgent-Demo
- **许可证 / License**: MIT
- **简介 / Description**: 无框架深度搜索 Agent，采用迭代搜索策略，支持自适应工具选择

**借鉴内容 / What We Learned**:
- 迭代搜索策略 — 多轮搜索逐步逼近答案
- 自适应工具选择机制

---

### 5. ex-skill

- **仓库 / Repository**: https://github.com/perkfly/ex-skill
- **许可证 / License**: MIT
- **简介 / Description**: 基于聊天记录的人格构建工具，采用5层人格结构

**借鉴内容 / What We Learned**:
- 5层人格结构设计（VibeUtopia 在此基础上扩展为7层人格工厂）

---

## 重要声明 / Important Notice

> **VibeUtopia 仅借鉴上述项目的架构思想和设计理念，未直接复制任何源代码。**
>
> 所有借鉴内容均属于思想层面的参考（著作权法中的"思想-表达二分法"——思想不受著作权保护，只有表达才受保护），不构成衍生作品。各参考项目的代码和知识产权归其原作者所有。
>
> VibeUtopia only borrowed architectural concepts and design ideas from the above projects, and did not directly copy any source code. All referenced content falls under the idea-expression dichotomy in copyright law — ideas are not protected by copyright, only expressions are. No derivative works were created. The code and intellectual property of each reference project belong to their respective original authors.

---

## 依赖库致谢 / Dependency Acknowledgments

VibeUtopia 还依赖了以下优秀的开源项目（通过 pip/npm 安装使用）：

### Python 后端
| 库 | 许可证 |
|----|--------|
| FastAPI | MIT |
| Uvicorn | BSD-3-Clause |
| SQLAlchemy | MIT |
| Pydantic | MIT |
| httpx | BSD-3-Clause |
| Naive UI | MIT |
| Vue.js | MIT |
| ECharts | Apache-2.0 |
| faster-whisper | MIT |
| Neo4j Python Driver | Apache-2.0 |
| pyvis | BSD-3-Clause |
| ECharts (via pyecharts) | MIT |

### Vue3 前端
| 库 | 许可证 |
|----|--------|
| Vue 3 | MIT |
| Element Plus | MIT |
| ECharts | Apache-2.0 |
| D3.js | ISC |
| Pinia | MIT |
| Vue Router | MIT |
| Tailwind CSS | MIT |
| Vite | MIT |
| TypeScript | Apache-2.0 |
