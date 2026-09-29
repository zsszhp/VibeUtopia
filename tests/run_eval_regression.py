#!/usr/bin/env python
"""评测回归门禁：黄金案例集自动回测（valid_accuracy + valid_ratio 双口径）

数据源:
  - data/backtest/cases.json          结构化回测案例（expected_risk_level / risk_score_range）
  - data/test/cases/paperwork/*.md    真实案例文案（期望等级取自 回测案例库索引.md）

用法（prompts/** 变更后手动触发）:
  PYTHONPATH=src python tests/run_eval_regression.py                 # auto：有 Key 走 live，否则 mock
  PYTHONPATH=src python tests/run_eval_regression.py --mode mock     # 离线子集（mock LLM，验证链路）
  PYTHONPATH=src python tests/run_eval_regression.py --mode live     # 全量真实 LLM（需 API Key）
  PYTHONPATH=src python tests/run_eval_regression.py --mode live --limit 10
  PYTHONPATH=src python tests/run_eval_regression.py --save-baseline # 记录基线
  PYTHONPATH=src python tests/run_eval_regression.py --baseline data/eval/baseline.json

门禁: 提供 --baseline 且 valid_accuracy 跌幅超过 --max-drop（默认 5 个百分点）时退出码 2。

输出: data/eval/eval_<时间戳>.json/.md 以及 data/eval/latest.json/.md

口径说明:
  - valid_accuracy = 命中数 / 有效样本数（排除 API 失败样本）
  - valid_ratio    = 有效样本数 / 总样本数（衡量环境完整性，避免 429/无 Key 污染准确率）
  - mock 模式仅供验证评测链路与报告产出，不代表模型真实准确率
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BACKTEST_PATH = ROOT / "data" / "backtest" / "cases.json"
CASES_DIR = ROOT / "data" / "test" / "cases"
CASES_INDEX = CASES_DIR / "回测案例库索引.md"
OUT_DIR = ROOT / "data" / "eval"

LEVEL_ORDER = ("green", "yellow", "orange", "red")
INDEX_LEVEL_MAP = {"高": "red", "中": "orange", "低": "green"}


# ---------------------------------------------------------------------------
# 案例装载
# ---------------------------------------------------------------------------

def _score_to_level(score: int) -> str:
    if score >= 76:
        return "red"
    if score >= 51:
        return "orange"
    if score >= 26:
        return "yellow"
    return "green"


def load_backtest_cases() -> list[dict]:
    data = json.loads(BACKTEST_PATH.read_text(encoding="utf-8"))
    cases = []
    for c in data:
        expected = (c.get("expected_risk_level") or "").lower().strip()
        if expected not in LEVEL_ORDER:
            continue
        cases.append({
            "case_id": c.get("case_id", ""),
            "source": "backtest",
            "title": c.get("title", ""),
            "text": c.get("content", ""),
            "expected_level": expected,
            "expected_high_dimensions": c.get("expected_high_dimensions") or [],
            "risk_score_range": c.get("risk_score_range"),
        })
    return cases


def load_paperwork_cases() -> list[dict]:
    """从案例库索引解析期望等级，再读取对应文案。"""
    label_map: dict[str, str] = {}
    if CASES_INDEX.exists():
        pattern = re.compile(r"`([^`]+\.md)`[^\n（]*（(高|中|低)）")
        for match in pattern.finditer(CASES_INDEX.read_text(encoding="utf-8")):
            label_map[match.group(1)] = INDEX_LEVEL_MAP.get(match.group(2), "green")

    cases = []
    paperwork = CASES_DIR / "paperwork"
    if not paperwork.exists():
        return cases
    for path in sorted(paperwork.glob("*.md")):
        expected = label_map.get(path.name)
        if not expected:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        cases.append({
            "case_id": f"TC-{path.stem}",
            "source": "paperwork",
            "title": path.stem,
            "text": text,
            "expected_level": expected,
            "expected_high_dimensions": [],
            "risk_score_range": None,
        })
    return cases


# ---------------------------------------------------------------------------
# 预测：live（真实 LLM）/ mock（离线子集）
# ---------------------------------------------------------------------------

async def predict_live(text: str, sample_runs: int = 1) -> dict:
    """真实链路：11 维评估 + 统一评分 + 置信度（可选多次采样一致性）"""
    from backend.services.analyzer import calculate_overall_score
    from backend.services.confidence_calculator import ConfidenceCalculator
    from backend.services.consistency_sampler import sample_assess_risk_levels

    result, sampling = await sample_assess_risk_levels(text, runs=sample_runs)
    if not result:
        raise RuntimeError("assess_risks 返回空维度（视为 API/解析失败）")
    dimensions = result.get("dimensions") or []
    if not dimensions:
        raise RuntimeError("assess_risks 返回空维度（视为 API/解析失败）")
    overall, _weights, _cross = calculate_overall_score(dimensions)
    conf = ConfidenceCalculator().calculate(
        dimensions=dimensions,
        risk_sentences=result.get("risk_sentences") or [],
        sampling_summary=sampling or None,
    )
    return {
        "score": int(overall),
        "level": _score_to_level(int(overall)),
        "dimensions": dimensions,
        "confidence": conf["overall_confidence"],
        "confidence_level": conf.get("confidence_level"),
        "reason_labels": conf.get("reason_labels", []),
        "sampling": sampling or None,
    }


_KEYWORD_RULES: list[tuple[str, list[str], int]] = [
    ("政治敏感", ["政治", "政府", "政策", "抵制", "联合起来", "领导", "政权"], 82),
    ("法律合规", ["违法", "诈骗", "造假", "黑产", "侵权", "赌博", "贩毒", "割韭菜"], 84),
    ("民族宗教", ["民族", "宗教", "信仰", "亵渎", "穆斯林", "佛", "教会"], 80),
    ("事实错误", ["谣言", "偏方", "伪科学", "包治百病", "内幕消息", "千万不要相信"], 78),
    ("平台禁区", ["软色情", "色情", "自残", "虐待", "封禁", "下架", "擦边"], 86),
    ("情绪极化", ["抵制", "联合起来", "翻车", "互撕", "骂战", "对立"], 70),
    ("价值观倾向", ["炫富", "拜金", "崇洋", "价值观"], 65),
    ("性别议题", ["性别", "女性", "男性", "歧视", "代孕", "女权"], 72),
    ("道德伦理", ["背刺", "塌房", "欺骗", "缺德", "无良"], 68),
    ("群体冒犯", ["地域黑", "歧视", "冒犯", "底层", "打工人"], 70),
    ("时事踩雷", ["热搜", "点名", "翻车", "舆论"], 60),
]


def predict_mock(text: str) -> dict:
    """离线 mock：关键词启发式出维度，只用于跑通评测链路，不代表真实准确率。"""
    from backend.services.analyzer import calculate_overall_score
    from backend.services.confidence_calculator import ConfidenceCalculator

    dimensions = []
    for name, keywords, base_score in _KEYWORD_RULES:
        hits = [k for k in keywords if k in text]
        if not hits:
            continue
        score = min(100, base_score + 4 * len(hits))
        severity = "red" if score >= 76 else ("orange" if score >= 51 else "yellow")
        dimensions.append({"name": name, "score": score, "severity": severity, "dimension_weight": 1.0})
    if not dimensions:
        dimensions = [
            {"name": n, "score": 8, "severity": "green", "dimension_weight": 1.0}
            for n, _kw, _s in _KEYWORD_RULES
        ]
    overall, _weights, _cross = calculate_overall_score(dimensions)
    conf = ConfidenceCalculator().calculate(dimensions=dimensions, risk_sentences=[])
    return {
        "score": int(overall),
        "level": _score_to_level(int(overall)),
        "dimensions": dimensions,
        "confidence": conf["overall_confidence"],
        "confidence_level": conf.get("confidence_level"),
        "reason_labels": conf.get("reason_labels", []),
        "sampling": None,
    }


# ---------------------------------------------------------------------------
# 评测主流程
# ---------------------------------------------------------------------------

def _hit_level(predicted: str, expected: str) -> bool:
    return predicted == expected


def _hit_score_range(score: int, range_: list | None) -> bool | None:
    if not range_ or len(range_) != 2:
        return None
    low, high = int(range_[0]), int(range_[1])
    return low <= score <= high


async def run_eval(mode: str, limit: int | None, source: str, sample_runs: int = 1) -> dict:
    cases: list[dict] = []
    if source in ("all", "backtest"):
        cases.extend(load_backtest_cases())
    if source in ("all", "cases"):
        cases.extend(load_paperwork_cases())
    if limit:
        cases = cases[:limit]

    use_mock = mode == "mock"
    if mode == "auto":
        import os
        use_mock = not any(
            (os.getenv(k) or "").strip()
            for k in (
                "OAIFREE_API_KEY",
                "DEEPSEEK_API_KEY",
                "LONGCAT_API_KEY",
                "SILICONFLOW_API_KEY",
                "OPENAI_API_KEY",
                "SENSENOVA_API_KEY",
            )
        )

    started = time.perf_counter()
    records = []
    valid = 0
    hits = 0
    score_range_hits = 0
    score_range_valid = 0
    api_failures = 0

    total = len(cases)
    for idx, case in enumerate(cases, 1):
        rec = {
            "case_id": case["case_id"],
            "source": case["source"],
            "title": case["title"],
            "expected_level": case["expected_level"],
            "risk_score_range": case["risk_score_range"],
        }
        print(f"[eval] {idx}/{total} {case['case_id']} start", flush=True)
        try:
            if use_mock:
                pred = predict_mock(case["text"])
            else:
                pred = await predict_live(case["text"])
            rec.update({
                "status": "ok",
                "predicted_level": pred["level"],
                "score": pred["score"],
                "level_hit": _hit_level(pred["level"], case["expected_level"]),
            })
            sr = _hit_score_range(pred["score"], case["risk_score_range"])
            if sr is not None:
                rec["score_range_hit"] = sr
                score_range_valid += 1
                score_range_hits += 1 if sr else 0
            valid += 1
            hits += 1 if rec["level_hit"] else 0
            print(f"[eval] {idx}/{total} {case['case_id']} ok pred={pred.get('level')} expect={case['expected_level']}", flush=True)
        except Exception as e:
            rec.update({"status": "api_error", "error": f"{type(e).__name__}: {e}"[:200], "level_hit": False})
            api_failures += 1
            print(f"[eval] {idx}/{total} {case['case_id']} FAIL {type(e).__name__}: {e}", flush=True)
        records.append(rec)

    total = len(records)
    valid_ratio = round(valid / total, 4) if total else 0.0
    valid_accuracy = round(hits / valid, 4) if valid else None
    score_range_accuracy = round(score_range_hits / score_range_valid, 4) if score_range_valid else None

    confusion: dict[str, dict[str, int]] = {}
    for rec in records:
        if rec.get("status") != "ok":
            continue
        row = confusion.setdefault(rec["expected_level"], {})
        key = rec["predicted_level"]
        row[key] = row.get(key, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock" if use_mock else "live",
        "source_filter": source,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "total_cases": total,
        "valid_cases": valid,
        "api_failed_cases": api_failures,
        "valid_ratio": valid_ratio,
        "valid_accuracy": valid_accuracy,
        "level_hits": hits,
        "score_range_accuracy": score_range_accuracy,
        "confusion_matrix": confusion,
        "cases": records,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 评测回归报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 模式：{report['mode']}" + ("（mock LLM，仅验证链路，不代表真实准确率）" if report["mode"] == "mock" else ""),
        f"- 数据源：{report['source_filter']}",
        f"- 耗时：{report['duration_seconds']}s",
        "",
        "## 双口径指标",
        "",
        "| 指标 | 数值 | 含义 |",
        "|------|------|------|",
        f"| valid_accuracy | {report['valid_accuracy']} | 命中数/有效样本数（排除 API 失败） |",
        f"| valid_ratio | {report['valid_ratio']} | 有效样本数/总样本数（环境完整性） |",
        f"| score_range_accuracy | {report['score_range_accuracy']} | 落入期望分数区间占比（仅有区间的案例） |",
        f"| 总案例 | {report['total_cases']} |  |",
        f"| 有效案例 | {report['valid_cases']} |  |",
        f"| API 失败 | {report['api_failed_cases']} | 不计入 valid_accuracy |",
        "",
        "## 混淆矩阵（期望 → 预测）",
        "",
        "| 期望 \\ 预测 | green | yellow | orange | red |",
        "|-------------|-------|--------|--------|-----|",
    ]
    for exp in LEVEL_ORDER:
        row = report.get("confusion_matrix", {}).get(exp, {})
        cells = " | ".join(str(row.get(pred, 0)) for pred in LEVEL_ORDER)
        lines.append(f"| {exp} | {cells} |")

    lines += ["", "## 逐案例明细", "",
              "| case_id | 源 | 期望 | 预测 | 分数 | 命中 | 状态 |",
              "|---------|----|------|------|------|------|------|"]
    for rec in report["cases"]:
        hit = "Y" if rec.get("level_hit") else ("-" if rec.get("status") != "ok" else "N")
        lines.append(
            f"| {rec['case_id']} | {rec['source']} | {rec.get('expected_level', '')} "
            f"| {rec.get('predicted_level', '')} | {rec.get('score', '')} | {hit} | {rec['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _check_baseline(report: dict, baseline_path: Path, max_drop: float) -> int:
    if not baseline_path.exists():
        print(f"[gate] 基线不存在: {baseline_path}（跳过门禁）")
        return 0
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    base_acc = base.get("valid_accuracy")
    cur_acc = report.get("valid_accuracy")
    if base_acc is None or cur_acc is None:
        print("[gate] 基线或当前 valid_accuracy 为空，跳过门禁")
        return 0
    drop = (base_acc - cur_acc) * 100
    print(f"[gate] baseline valid_accuracy={base_acc} → current={cur_acc}（跌幅 {drop:.2f} 个百分点）")
    if drop > max_drop:
        print(f"[gate] FAIL：跌幅超过 {max_drop} 个百分点")
        return 2
    print("[gate] PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="评测回归门禁（valid_accuracy + valid_ratio 双口径）")
    parser.add_argument("--mode", choices=("auto", "mock", "live"), default="auto")
    parser.add_argument("--limit", type=int, default=None, help="限制案例数（mock 默认 6，live 默认全量）")
    parser.add_argument("--source", choices=("all", "backtest", "cases"), default="all")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--save-baseline", action="store_true", help="把本次结果写入 baseline.json")
    parser.add_argument("--baseline", default=str(OUT_DIR / "baseline.json"), help="门禁对比基线路径")
    parser.add_argument("--max-drop", type=float, default=5.0, help="允许的 valid_accuracy 跌幅（百分点）")
    args = parser.parse_args()

    limit = args.limit
    if limit is None and args.mode == "mock":
        limit = 6  # 离线 demo 子集

    report = asyncio.run(run_eval(args.mode, limit, args.source))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"eval_{stamp}.json"
    md_path = out_dir / f"eval_{stamp}.md"
    json_text = json.dumps(report, ensure_ascii=False, indent=2)
    md_text = render_markdown(report)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    (out_dir / "latest.json").write_text(json_text, encoding="utf-8")
    (out_dir / "latest.md").write_text(md_text, encoding="utf-8")

    print(f"模式={report['mode']} 总案例={report['total_cases']} 有效={report['valid_cases']} "
          f"API失败={report['api_failed_cases']}")
    print(f"valid_accuracy={report['valid_accuracy']}  valid_ratio={report['valid_ratio']}")
    print(f"报告: {json_path}")
    print(f"报告: {md_path}")

    if args.save_baseline:
        base_path = out_dir / "baseline.json"
        base_path.write_text(json.dumps({
            "saved_at": report["generated_at"],
            "mode": report["mode"],
            "valid_accuracy": report["valid_accuracy"],
            "valid_ratio": report["valid_ratio"],
            "total_cases": report["total_cases"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"基线已保存: {base_path}")

    return _check_baseline(report, Path(args.baseline), args.max_drop)


if __name__ == "__main__":
    sys.exit(main())
