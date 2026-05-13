# BettaFish

## 项目信息

- **仓库**: https://github.com/666ghj/BettaFish
- **许可证**: GPL-2.0 + Non-Commercial Learning License 1.1 + Apache-2.0 + MIT
- **领域**: 多Agent协作、舆情分析

## 项目定位

4专职Agent舆情分析系统，核心创新是ForumEngine论坛式协作机制，Agent通过日志文件异步交流，ForumHost主持讨论，最终由ReportEngine生成结构化报告。

## 核心架构

```
[Flask Web] ──▶ [3Agent并行分析] ──▶ [ForumEngine协作] ──▶ [ReportEngine] ──▶ [HTML报告]
                  │                      │
         InsightEngine            ForumHost主持
         MediaEngine              每5条发言触发
         QueryEngine
```

## 精华借鉴

| 精华项 | 说明 |
|--------|------|
| ForumEngine协作思想 | Agent异步交流，Host主持引导，避免无序讨论 |
| 专职Agent分工 | 每个Agent有独立工具集和LLM配置 |
| 两阶段爬取策略 | 先广度提取关键词，再深度爬取情感数据 |
| 反思-总结循环 | Agent基于论坛反馈调整研究方向 |
| 多模型情感分析 | 覆盖不同场景的情感分析需求 |

## 采纳决策

| 项 | 决策 | 目标阶段 |
|----|------|---------|
| ForumEngine协作思想 | 采纳(改进) | 4-5 |
| 专职Agent分工模式 | 采纳(改进) | 3-5 |
| 两阶段爬取策略 | 采纳 | 1-2 |
| 反思-总结循环 | 采纳(改进) | 4 |
| 多模型情感分析 | 采纳 | 2-3 |
| 日志文件通信 | 不采纳 | - |

## 详细分析

见 [analysis.md](./analysis.md)
