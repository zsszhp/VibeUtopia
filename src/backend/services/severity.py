"""统一 severity 词表映射层

Prompt/落库四档：green / yellow / orange / red
历史三档：low / medium / high
扩展档：critical / elevated / safe

所有评分与触发判定必须经过本模块，禁止在业务代码中直接比较 severity 字符串。
"""

from __future__ import annotations

# 对外四档（Prompt Schema、RiskItem 落库、前端展示）
FOUR_LEVELS = ("green", "yellow", "orange", "red")

# 判定档位（内部）：low / medium / elevated / high
LEVEL_LOW = "low"
LEVEL_MEDIUM = "medium"
LEVEL_ELEVATED = "elevated"
LEVEL_HIGH = "high"

# 任意历史词表 → 判定档位
_TO_LEVEL = {
    "green": LEVEL_LOW,
    "low": LEVEL_LOW,
    "safe": LEVEL_LOW,
    "none": LEVEL_LOW,
    "yellow": LEVEL_MEDIUM,
    "medium": LEVEL_MEDIUM,
    "moderate": LEVEL_MEDIUM,
    "orange": LEVEL_ELEVATED,
    "elevated": LEVEL_ELEVATED,
    "red": LEVEL_HIGH,
    "high": LEVEL_HIGH,
    "critical": LEVEL_HIGH,
    "severe": LEVEL_HIGH,
}

# 判定档位 → 对外四档
_LEVEL_TO_FOUR = {
    LEVEL_LOW: "green",
    LEVEL_MEDIUM: "yellow",
    LEVEL_ELEVATED: "orange",
    LEVEL_HIGH: "red",
}

# 对外四档分数区间（与 risk_assessment_v2 Prompt 标定一致）
_FOUR_SCORE_BANDS = (
    (76, "red"),
    (51, "orange"),
    (26, "yellow"),
    (0, "green"),
)


def severity_level(sev: str | None, score: int = 0) -> str:
    """任意词表的 severity → 判定档位 low/medium/elevated/high

    无法识别时按分数兜底（Prompt 标定：0-25 green / 26-50 yellow / 51-75 orange / 76-100 red）。
    medium 档按分数细分：score>=60 归 elevated（与历史 _normalize_severity 行为一致）。
    """
    key = (sev or "").lower().strip()
    if key in _TO_LEVEL:
        level = _TO_LEVEL[key]
        if level == LEVEL_MEDIUM and score >= 60:
            return LEVEL_ELEVATED
        return level
    return _TO_LEVEL[_four_from_score(score)]


def normalize_severity(sev: str | None, score: int = 0) -> str:
    """任意词表的 severity → 对外四档 green/yellow/orange/red"""
    return _LEVEL_TO_FOUR[severity_level(sev, score)]


def _four_from_score(score: int) -> str:
    for threshold, name in _FOUR_SCORE_BANDS:
        if score >= threshold:
            return name
    return "green"


def is_high_severity(sev: str | None, score: int = 0) -> bool:
    """是否高档风险（对应旧词表 high/critical，Prompt 词表 red）

    score>=76 时即使 severity 缺失/错标也判高档，与 Prompt「red=76-100」标定一致，
    避免 LLM 词表服从失败导致红线保底规则失效。
    """
    return severity_level(sev, score) == LEVEL_HIGH or score >= 76


def is_elevated_or_above(sev: str | None, score: int = 0) -> bool:
    """是否橙档及以上（elevated/high，Prompt 词表 orange/red）"""
    return severity_level(sev, score) in (LEVEL_ELEVATED, LEVEL_HIGH) or score >= 51


def needs_rewrite(sev: str | None, score: int = 0) -> bool:
    """是否需要生成改写建议（旧词表 high/medium，Prompt 词表 red/orange/yellow）"""
    return severity_level(sev, score) != LEVEL_LOW


def score_from_severity(sev: str | None, score: int = 0) -> int:
    """severity 对应的风险分数中值（用于 risk_score 数值列）"""
    return {"green": 10, "yellow": 35, "orange": 60, "red": 85}.get(
        normalize_severity(sev, score), 0
    )


# 红线维度（触碰即 HIGH）：与 Prompt risk_assessment_v2 红线组一致
REDLINE_DIMENSIONS = frozenset({
    "政治敏感", "法律合规", "民族宗教", "事实错误", "平台禁区",
})

# 红线强制分数下限：severity=red 的标定区间起点（76-100 red）
REDLINE_SCORE_FLOOR = 76


def is_redline_dimension(name: str | None) -> bool:
    """是否红线维度"""
    return (name or "") in REDLINE_DIMENSIONS


def enforce_redline_dim_score(name: str, score: int, sev: str | None) -> tuple[int, bool]:
    """红线维度被判 red/high 时，维度分强制抬升到 76+，保证 severity 与分数区间自洽

    Returns:
        (校正后分数, 是否触发强制抬升)
    """
    if not is_redline_dimension(name):
        return int(score), False
    if is_high_severity(sev, score):
        lifted = max(int(score), REDLINE_SCORE_FLOOR)
        return lifted, lifted != int(score)
    return int(score), False


def redline_triggers_floor(dimensions: list[dict] | None) -> bool:
    """任一红线维度 red/high → 总体分应至少 76（红线代码化，不再只写在 Prompt）"""
    for d in dimensions or []:
        if not is_redline_dimension(d.get("name")):
            continue
        if is_high_severity(d.get("severity"), d.get("score", 0)):
            return True
    return False
