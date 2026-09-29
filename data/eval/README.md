# 评测基线说明（data/eval）

本目录存放评测回归门禁的报告与基线文件，由 `tests/run_eval_regression.py` 产出。

## 目录内容

| 文件 | 说明 |
|------|------|
| `eval_<时间戳>.json` / `.md` | 单次评测报告（JSON 机器可读 + Markdown 可读） |
| `latest.json` / `latest.md` | 最近一次评测报告的副本 |
| `baseline.json` | **门禁基线**（当前尚未生成，见下文「生成基线」） |
| `README.md` | 本说明 |

当前目录内已有的 `eval_*` / `latest.*` 报告均为 **mock 模式**产物（`mode: mock`），
仅验证评测链路与报告产出，**不代表模型真实准确率**，不得当作 live 基线使用。

## 口径说明

- `valid_accuracy` = 命中数 / 有效样本数（排除 API 失败样本）
- `valid_ratio` = 有效样本数 / 总样本数（衡量环境完整性，避免 429 / 无 Key 污染准确率）
- mock 模式仅供验证评测链路，不代表真实准确率；live 数字只能由真实 LLM 调用产生

## 运行评测

在仓库根目录执行（需要 `PYTHONPATH=src`）：

```bash
# auto：有 API Key 走 live，否则 mock
PYTHONPATH=src python tests/run_eval_regression.py

# 离线子集（mock LLM，验证链路）
PYTHONPATH=src python tests/run_eval_regression.py --mode mock

# 全量真实 LLM（需配置 API Key，不配置 Key 不得伪造结果）
PYTHONPATH=src python tests/run_eval_regression.py --mode live

# 限量抽样
PYTHONPATH=src python tests/run_eval_regression.py --mode live --limit 10
```

## 生成基线

基线必须由 **live 模式** 真实跑出后写入，禁止用 mock 报告或手工填写数字冒充：

```bash
PYTHONPATH=src python tests/run_eval_regression.py --mode live --save-baseline
```

执行后会把本次结果写入 `data/eval/baseline.json`（字段：`saved_at` / `mode` /
`valid_accuracy` / `valid_ratio` / `total_cases`）。生成前请确认：

1. 已配置可用的模型 API Key（live 调用真实 LLM）；
2. `valid_ratio` 接近 1（有效样本占比过低说明环境不完整，基线不可信）；
3. 报告 `mode` 字段为 `live`。

**当前状态：`baseline.json` 尚未生成。** 在完成一次可信的 live 评测之前，
门禁自动跳过基线对比（`_check_baseline` 检测到基线不存在时直接放行）。

## 回归门禁

提供 `--baseline`（默认 `data/eval/baseline.json`）时，脚本对比当前 `valid_accuracy`
与基线的跌幅，超过 `--max-drop`（默认 5 个百分点）退出码为 2：

```bash
PYTHONPATH=src python tests/run_eval_regression.py --mode live \
  --baseline data/eval/baseline.json --max-drop 5
```

退出码：`0` 通过（或无基线跳过门禁）；`2` 跌幅超限；其他为运行错误。
