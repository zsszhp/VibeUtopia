"""ECE（Expected Calibration Error）校准雏形

把评测报告中的「预测置信度 vs 是否命中」按置信度分档，
计算分档校准误差。样本不足时明确标注，不伪造数字。
"""
from __future__ import annotations

from typing import Any

# 置信度分档（左闭右开，最后一档右闭）
DEFAULT_BINS: list[tuple[float, float]] = [
    (0.0, 0.5),
    (0.5, 0.7),
    (0.7, 0.85),
    (0.85, 1.0),
]

# 低于该样本数视为「样本不足」（只出描述，不下结论）
MIN_SAMPLES_FOR_CONCLUSION = 10
MIN_SAMPLES_PER_BIN = 3


def _bin_of(confidence: float, bins: list[tuple[float, float]]) -> int | None:
    for idx, (lo, hi) in enumerate(bins):
        if lo <= confidence < hi or (idx == len(bins) - 1 and confidence == hi):
            return idx
    return None


def extract_samples(reports: list[dict]) -> list[dict]:
    """从评测报告 JSON 提取可用校准样本

    样本条件：status=ok 且带 confidence 字段（预测置信度）与 level_hit（是否命中）
    """
    samples: list[dict] = []
    for report in reports or []:
        mode = report.get("mode", "unknown")
        generated_at = report.get("generated_at", "")
        for case in report.get("cases") or []:
            if case.get("status") != "ok":
                continue
            confidence = case.get("confidence")
            hit = case.get("level_hit")
            if confidence is None or hit is None:
                continue
            try:
                conf = float(confidence)
            except (TypeError, ValueError):
                continue
            if not 0.0 <= conf <= 1.0:
                continue
            samples.append({
                "case_id": case.get("case_id", ""),
                "mode": mode,
                "generated_at": generated_at,
                "confidence": conf,
                "hit": bool(hit),
                "expected_level": case.get("expected_level"),
                "predicted_level": case.get("predicted_level"),
            })
    return samples


def compute_calibration(
    samples: list[dict],
    bins: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """计算分档校准误差（ECE）

    Args:
        samples: [{"confidence": float, "hit": bool}, ...]
        bins: 置信度分档，默认 DEFAULT_BINS

    Returns:
        {
          "n": 样本数,
          "ece": 分档加权 |acc - conf|（样本为 0 时为 None），
          "bins": [{lo, hi, n, avg_confidence, hit_rate, gap}, ...],
          "insufficient": bool（总样本或分档样本不足）,
          "notes": [str, ...],
        }
    """
    bins = bins or DEFAULT_BINS
    notes: list[str] = []
    usable = []
    for s in samples or []:
        try:
            conf = float(s.get("confidence"))
        except (TypeError, ValueError):
            continue
        if s.get("hit") is None:
            continue
        usable.append((conf, bool(s.get("hit"))))

    n = len(usable)
    if n == 0:
        return {
            "n": 0,
            "ece": None,
            "bins": [],
            "insufficient": True,
            "notes": ["样本不足：无带 confidence 与命中标记的评测样本，无法计算 ECE"],
        }

    if n < MIN_SAMPLES_FOR_CONCLUSION:
        notes.append(f"样本不足：仅 {n} 条样本（阈值 {MIN_SAMPLES_FOR_CONCLUSION}），ECE 仅供参考，不作校准结论")

    bin_rows: list[dict] = []
    weighted_gap = 0.0
    for lo, hi in bins:
        bucket = [(c, h) for c, h in usable if _bin_of(c, bins) == bins.index((lo, hi))]
        count = len(bucket)
        row: dict[str, Any] = {"lo": lo, "hi": hi, "n": count}
        if count == 0:
            row.update({"avg_confidence": None, "hit_rate": None, "gap": None})
            notes.append(f"分档 [{lo:.2f}, {hi:.2f}] 样本不足：0 条，跳过")
        else:
            avg_conf = sum(c for c, _ in bucket) / count
            hit_rate = sum(1 for _, h in bucket if h) / count
            gap = abs(hit_rate - avg_conf)
            row.update({
                "avg_confidence": round(avg_conf, 4),
                "hit_rate": round(hit_rate, 4),
                "gap": round(gap, 4),
            })
            weighted_gap += (count / n) * gap
            if count < MIN_SAMPLES_PER_BIN:
                notes.append(f"分档 [{lo:.2f}, {hi:.2f}] 样本不足：仅 {count} 条（阈值 {MIN_SAMPLES_PER_BIN}）")
        bin_rows.append(row)

    return {
        "n": n,
        "ece": round(weighted_gap, 4),
        "bins": bin_rows,
        "insufficient": n < MIN_SAMPLES_FOR_CONCLUSION,
        "notes": notes,
    }


def render_calibration_markdown(result: dict[str, Any], source_files: list[str] | None = None) -> str:
    """渲染校准报告 Markdown"""
    lines = [
        "# ECE 校准报告（雏形）",
        "",
        "> 口径：预测 confidence 分档 vs 该档命中率（level_hit）；ECE = Σ (n_i/N) × |acc_i − conf_i|",
        "> 样本来源：`data/eval/eval_*.json` 中 status=ok 且带 confidence 字段的案例记录。",
        "",
    ]
    if source_files:
        lines.append("## 样本来源")
        lines.append("")
        for f in source_files:
            lines.append(f"- `{f}`")
        lines.append("")

    n = result.get("n", 0)
    lines += [
        "## 总览",
        "",
        f"- 有效样本数：{n}",
        f"- ECE：{result.get('ece') if result.get('ece') is not None else '—'}",
        f"- 样本充足性：{'样本不足' if result.get('insufficient') else '样本量达到参考阈值'}",
        "",
    ]

    lines += [
        "## 分档校准",
        "",
        "| 分档 | 样本数 | 平均预测置信度 | 命中率 | gap |",
        "|------|--------|----------------|--------|-----|",
    ]
    for row in result.get("bins") or []:
        conf = row.get("avg_confidence")
        hit = row.get("hit_rate")
        gap = row.get("gap")
        lines.append(
            f"| [{row['lo']:.2f}, {row['hi']:.2f}] | {row['n']} "
            f"| {'—' if conf is None else conf} | {'—' if hit is None else hit} "
            f"| {'—' if gap is None else gap} |"
        )
    lines.append("")

    notes = result.get("notes") or []
    if notes:
        lines += ["## 说明", ""]
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    if result.get("insufficient"):
        lines += [
            "**样本不足**：当前结果不构成校准结论，需积累更多带 confidence 的 live 评测样本后重算。",
            "",
        ]
    return "\n".join(lines)
