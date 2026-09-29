"""多次采样一致性：同一文本重复 assess_risks，量化 score/level 分布稳定性

口径：
- 一致性率 = 多数 level 出现次数 / 有效采样次数
- 原因标签（consistency_*）写入 ConfidenceCalculator.reason_labels
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

LEVEL_ORDER = ("green", "yellow", "orange", "red")

# 与 tests/run_eval_regression.py 的分档阈值保持一致
_SCORE_LEVEL_THRESHOLDS = ((76, "red"), (51, "orange"), (26, "yellow"), (0, "green"))

LABEL_FULL = "consistency_full"
LABEL_MAJORITY = "consistency_majority"
LABEL_SPLIT = "consistency_split"
LABEL_UNKNOWN = "consistency_unknown"


def score_to_level(score: int | float) -> str:
    """总体分数 → 4 档风险等级（阈值 26/51/76）"""
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "green"
    for threshold, name in _SCORE_LEVEL_THRESHOLDS:
        if s >= threshold:
            return name
    return "green"


def consistency_label(rate: float, distinct_levels: int, runs: int) -> str:
    """一致性率 → consistency_* 原因标签"""
    if runs <= 0:
        return LABEL_UNKNOWN
    if rate >= 1.0:
        return LABEL_FULL
    if rate >= 0.5 and distinct_levels <= 2:
        return LABEL_MAJORITY
    return LABEL_SPLIT


def summarize_samples(samples: list[dict]) -> dict[str, Any]:
    """汇总多次采样的 score/level 分布

    Args:
        samples: [{"score": int, "level": str}, ...]，level 缺失时由 score 推断

    Returns:
        runs / levels / scores / majority_level / majority_count /
        consistency_rate / distinct_levels / label
    """
    levels: list[str] = []
    scores: list[int] = []
    for s in samples or []:
        score = s.get("score")
        level = s.get("level") or (score_to_level(score) if score is not None else None)
        if level is None or level not in LEVEL_ORDER:
            continue
        levels.append(level)
        if score is not None:
            try:
                scores.append(int(score))
            except (TypeError, ValueError):
                pass

    runs = len(levels)
    if runs == 0:
        return {
            "runs": 0,
            "levels": [],
            "scores": [],
            "majority_level": None,
            "majority_count": 0,
            "consistency_rate": 0.0,
            "distinct_levels": 0,
            "label": LABEL_UNKNOWN,
        }

    counter = Counter(levels)
    majority_level, majority_count = counter.most_common(1)[0]
    rate = majority_count / runs
    distinct = len(counter)
    return {
        "runs": runs,
        "levels": levels,
        "scores": scores,
        "majority_level": majority_level,
        "majority_count": majority_count,
        "consistency_rate": round(rate, 4),
        "distinct_levels": distinct,
        "label": consistency_label(rate, distinct, runs),
    }


def result_score_level(result: dict | None) -> dict:
    """assess_risks 结果 → 单次采样摘要（score/level）"""
    from backend.services.analyzer import calculate_overall_score

    dimensions = (result or {}).get("dimensions") or []
    if not dimensions:
        return {"score": None, "level": None}
    overall, _weights, _cross = calculate_overall_score(dimensions)
    score = int(overall)
    return {"score": score, "level": score_to_level(score)}


Assessor = Callable[[str], Awaitable[dict]]


def _default_assessor() -> Assessor:
    from backend.services.risk_assessor import assess_risks

    return assess_risks


async def _run_once(assessor: Assessor, text: str) -> dict | None:
    """单次评估；失败返回 None（不拖垮整组采样）"""
    try:
        result = await assessor(text)
        if not (result or {}).get("dimensions"):
            return None
        return result
    except Exception as e:
        logger.warning("一致性采样单次失败: %s", e)
        return None


async def sample_assess_risk_levels(
    text: str,
    runs: int = 3,
    assessor: Assessor | None = None,
    first_result: dict | None = None,
    concurrency: int = 1,
) -> tuple[dict | None, dict]:
    """同一文本多次 assess_risks，返回 (主结果, 一致性摘要)

    Args:
        text: 待评估文本
        runs: 采样次数（<2 时不采样，仅返回主结果，summary 为空字典）
        assessor: 可注入评估器（测试用 mock）；默认 risk_assessor.assess_risks
        first_result: 可复用的首次评估结果（避免重复调用）
        concurrency: 并发采样上限（1 = 串行）

    Returns:
        (primary_result, sampling_summary)：
        - primary_result 取首个成功样本；全部失败时为 None
        - sampling_summary 含 runs=成功次数 / consistency_rate=多数 level 占比 / label=consistency_*
        - runs<2 时 summary 为空字典，表示未做多次采样
    """
    if runs < 2:
        if first_result is not None:
            return first_result, {}
        return await _run_once(assessor or _default_assessor(), text), {}

    if assessor is None:
        assessor = _default_assessor()

    results: list[dict] = []
    if first_result is not None:
        results.append(first_result)

    remaining = runs - len(results)
    if remaining > 0:
        if concurrency <= 1:
            for _ in range(remaining):
                results.append(await _run_once(assessor, text))
        else:
            sem = asyncio.Semaphore(concurrency)

            async def _one() -> dict | None:
                async with sem:
                    return await _run_once(assessor, text)

            gathered = await asyncio.gather(*[_one() for _ in range(remaining)])
            results.extend(gathered)

    ok_results = [r for r in results if r is not None]
    samples = [result_score_level(r) for r in ok_results]
    summary = summarize_samples(samples)
    summary["failed_runs"] = runs - len(ok_results)
    summary["primary_differs_from_majority"] = bool(
        summary.get("majority_level")
        and samples
        and summary["majority_level"] != samples[0].get("level")
    )
    if summary.get("runs"):
        logger.info(
            "一致性采样完成 ok=%s/%s rate=%s majority=%s label=%s",
            summary.get("runs"), runs, summary.get("consistency_rate"),
            summary.get("majority_level"), summary.get("label"),
        )
    return (ok_results[0] if ok_results else None), summary
