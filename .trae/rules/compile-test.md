---
description: 编译与测试验证
globs:
alwaysApply: true
---

## 强制验证

- **修改 Python 代码** → 必须运行 pytest 确认无错误
- **修改前端代码** → 必须运行 vue-tsc 确认类型检查通过
- **修改核心模块** → 必须运行相关测试用例
- **发现 Bug** → 必须修复，修复后必须回归验证

## 后端测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_llm_models.py -v

# 运行带覆盖率
pytest tests/ --cov=src/backend --cov-report=html
```

## 前端类型检查

```bash
cd src/frontend
vue-tsc -b          # 类型检查
pnpm build          # 生产构建
```

## 回归防护

### 修 Bug 流程
1. 先写能复现 Bug 的失败测试用例
2. 确认测试失败后再修复
3. 修复后确认测试通过
4. 确认原有测试无回归

### 核心模块变更必须回归
- `routes.py` / `routes_v3.py` — API 路由修改
- `analyzer.py` / `enhanced_analyzer.py` — 分析逻辑修改
- `simulation/engine.py` — 仿真引擎修改
- `services/signal/` — 信号采集修改

## 主线程/异步保护

- FastAPI 路由使用 `async def`，避免阻塞事件循环
- 耗时操作（外部 API 调用）使用 `asyncio.gather` 并发执行
- 数据库操作使用 SQLAlchemy async session

## Gotchas

- **LiteLLM API Key** 必须配置在 `.env`，否则模型调用失败
- **Neo4j/ChromaDB** 必须先启动服务，否则数据库操作失败
- **ffmpeg** 必须安装并配置到 PATH，否则视频处理失败
- **模型路由** 修改 `model_config.yaml` 后需重启后端服务
- **Agnes AI** 图像生成模型不支持 `response_format` 参数（纯文生图时不要传 extra_body）
- **Key 冷却** 模型 Key 限流后自动冷却 300 秒，冷却结束自动回切
