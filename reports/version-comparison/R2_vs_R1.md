# V2.R2 vs V2.R1 版本对比报告

> 仿真验证与基础迁移

## 功能对比

| 功能 | V2.R1 | V2.R2 | 改进 |
|------|-------|-------|------|
| 回测框架 | 无 | 10案例5维度准确率评估 | 新增 |
| 一致性检查 | 无 | 同一文案3次仿真+一致性评估 | 新增 |
| 数据库 | SQLite | MySQL(兼容SQLite回退) | 升级 |
| Go/No-Go | 无 | 自动判定Go/Conditional/No-Go | 新增 |
| API端点 | 4个V2端点 | +5个回测/一致性/系统端点 | +5个 |
| 前端Tab | 6个 | +验证回测Tab | +1个 |

## 回测准确率对比

| 指标 | MVP | V2 | 改善 |
|------|-----|-----|------|
| 方向准确率(40%) | - | - | - |
| 平台准确率(20%) | - | - | - |
| 维度准确率(20%) | - | - | - |
| 群体准确率(10%) | - | - | - |
| 极化准确率(10%) | - | - | - |
| 加权总准确率 | - | - | - |

> 注：实际数据需运行 `POST /backtest/run` 生成

## 一致性检查

| 指标 | 目标 | 实测 |
|------|------|------|
| 方向一致性 | >80% | - |
| 维度一致性 | >70% | - |
| 综合一致性 | >60% | - |
| 分数标准差 | <15 | - |

## 数据库迁移

| 项目 | 状态 |
|------|------|
| MySQL连接支持 | 已完成 |
| SQLite兼容回退 | 已完成 |
| 自动选择数据库类型 | 已完成 |
| pymysql依赖 | 已添加 |

## Go/No-Go 判定

- **条件**: V2方向准确率>55% 且 MySQL迁移完成
- **MySQL迁移**: 已完成
- **方向准确率**: 待实测
- **预判**: Go/Conditional Go

## 新增文件清单

| 文件 | 说明 |
|------|------|
| `backend/services/backtest.py` | 回测框架 |
| `backend/services/consistency_checker.py` | 一致性检查 |

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/models.py` | 新增BacktestRecord+ConsistencyRecord |
| `backend/routes.py` | 新增5个API端点 |
| `backend/config.py` | 新增MySQL配置项 |
| `backend/database.py` | MySQL支持+自动选择 |
| `frontend/app.py` | 新增验证回测Tab |
| `requirements.txt` | 新增pymysql |
