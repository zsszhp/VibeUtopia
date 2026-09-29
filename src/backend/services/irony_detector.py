"""隐喻/反讽风险启发式：在 LLM 评估之外做最低限度兜底

当文案同时出现「反讽修辞标记」与「敏感指向词」时，至少抬到 orange，
避免模型把「不是字面意思」误判为 green（BT015 类场景）。
"""
from __future__ import annotations

import re

# 反讽/阴阳怪气修辞标记
IRONY_MARKERS = (
    "真是优秀", "太厉害了", "可真行", "绝了", "好一个", "可还行",
    "懂的都懂", "你懂的", "厉害了", "赢麻了", "遥遥领先",
    "当然啦", "可不是嘛", "真是棒", "笑死", "典中典",
    "怎么说呢", "有一说一，确实", "难绷", "难崩",
    "光辉", "感人", "精彩", "优秀", "伟大", "光荣",
    "所谓的", "所谓的英雄", "编出来的", "根本不存在",
)

# 民族宗教贬损/改造话语（硬抬民族宗教维度）
ETHNIC_BELITTLE = (
    "落后", "改造他们", "不符合现代文明", "所谓文化", "所谓传统",
    "劣根", "野蛮", "不开化", "应该用先进",
)


def apply_ethnic_floor(dimensions: list[dict], text: str) -> list[dict]:
    """民族贬损/文明改造话语 → 民族宗教维度至少 70（硬红线软阈）"""
    text = text or ""
    if not any(k in text for k in ETHNIC_BELITTLE):
        return dimensions
    for d in dimensions or []:
        if d.get("name") == "民族宗教":
            try:
                score = int(d.get("score", 0) or 0)
            except (TypeError, ValueError):
                score = 0
            if score < 70:
                d["score"] = 70
                d["severity"] = "red"
                ev = d.get("evidence") or ""
                note = "【民族贬损兜底】检测到文明改造/习俗贬损表述，按红线触碰处理"
                if note not in ev:
                    d["evidence"] = (ev + note).strip()
    return dimensions

# 敏感指向（时事/政策/历史/群体/体制）
SENSITIVE_TARGETS = (
    "历史", "英雄", "政策", "政府", "体制", "官员", "领导",
    "民族", "宗教", "台湾", "香港", "新疆", "领土",
    "地域", "河南人", "东北人", "上海人", "农村", "城里人",
    "专家", "官方", "权威", "教材", "课本", "纪念碑",
    "习俗", "传统", "落后", "改造他们", "文明", "劣根",
    "英雄事迹", "编出来的", "胜利者", "光辉",
)

_IRONY_RE = re.compile("|".join(re.escape(m) for m in IRONY_MARKERS))
_TARGET_RE = re.compile("|".join(re.escape(m) for m in SENSITIVE_TARGETS))


def detect_irony_risk(text: str) -> dict:
    """检测暗讽/隐喻风险信号

    Returns:
        {
          "has_irony_markers": bool,
          "has_sensitive_targets": bool,
          "suggested_min_score": int,  # 建议相关维度不低于此分
          "notes": list[str],
        }
    """
    text = text or ""
    has_irony = bool(_IRONY_RE.search(text))
    has_target = bool(_TARGET_RE.search(text))
    notes: list[str] = []
    suggested = 0

    if has_irony and has_target:
        suggested = 55
        notes.append("检测到反讽修辞+敏感指向，相关维度建议不低于 orange(55)")
    elif has_irony:
        notes.append("存在反讽修辞标记，请按暗示含义评估，勿按字面降为 green")

    return {
        "has_irony_markers": has_irony,
        "has_sensitive_targets": has_target,
        "suggested_min_score": suggested,
        "notes": notes,
    }


def apply_irony_floor(dimensions: list[dict], text: str) -> list[dict]:
    """对时事踩雷/群体冒犯/价值观/政治敏感 等维度做反讽兜底抬分"""
    signal = detect_irony_risk(text)
    floor = signal["suggested_min_score"]
    if floor <= 0:
        return dimensions

    target_dims = {"时事踩雷", "群体冒犯", "价值观倾向", "政治敏感", "情绪极化"}
    for d in dimensions or []:
        name = d.get("name")
        if name in target_dims:
            try:
                score = int(d.get("score", 0) or 0)
            except (TypeError, ValueError):
                continue
            if score < floor:
                d["score"] = floor
                if d.get("severity") in (None, "green", "low"):
                    d["severity"] = "orange"
                note = "；".join(signal["notes"])
                ev = d.get("evidence") or ""
                if note and note not in ev:
                    d["evidence"] = (ev + "【反讽兜底】" + note).strip()
    return dimensions
