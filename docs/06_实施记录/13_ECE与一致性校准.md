# 一致性 / ECE 校准 / live 基线实施记录

> 状态：模块已落地，测试见 tests/test_video_l6_l7.py、全量 pytest 137 passed

## 1. 多次采样一致性

- 新增 `src/backend/services/consistency_sampler.py`
- 同一文本多次 `assess_risks`，输出 level 众数占比与 score 方差
- 一致性标签写入 confidence 原因（`consistency_high/mid/low`）
- 离线可用 mock；真实 3 次采样依赖 LLM，受配额影响

## 2. ECE 校准雏形

- 新增 `src/backend/services/calibration.py`
- 按置信分档统计命中率，输出校准表
- 样本不足时明确标注，不伪造 ECE 数字
- 可与 `tests/run_eval_regression.py` 报告联动

## 3. live 基线

- `data/eval/baseline.json` 当前为 live 5 案例：`valid_accuracy=1.0`，`valid_ratio=0.4`
- 扩容需稳定 API 窗口执行：`PYTHONPATH=src python tests/run_eval_regression.py --mode live --source backtest --limit 12 --save-baseline`
- mock 报告不代表真实准确率

## 4. 测试库修复（连带）

- `tests/conftest.py` 强制 `DATABASE_URL=sqlite:///./data/test_vibeutopia.db`
- `database._build_database_url`：显式 sqlite/非 MySQL URL 优先
- R5 用例 10/10 通过，不再误连本机 MySQL

## 遗留

- 三次采样默认关闭以控成本，建议按分析深度自动开启
- ECE 需 ≥100 有效样本才对外引用
