"""舆论极化指数计算 — 基于Agent立场分布的双峰性量化极化程度"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


def calc_polarization_index(stance_values: List[float]) -> float:
    """基于Agent立场值分布计算极化指数 (0-1)

    使用双峰性系数 (Bimodality Coefficient):
    BC = (n-1)^2 * (skewness^2 + 1) / ((n-2)(n-3) * kurtosis)

    BC 范围 0-1:
    - BC < 0.555: 单峰分布（共识）
    - BC >= 0.555: 双峰分布（极化）

    Args:
        stance_values: 每个Agent的立场值，范围 -1(强烈反对) 到 1(强烈支持)，0=中立

    Returns:
        极化指数 0-1
    """
    n = len(stance_values)
    if n < 4:
        return 0.0

    mean = sum(stance_values) / n
    variance = sum((x - mean) ** 2 for x in stance_values) / n
    if variance < 1e-10:
        return 0.0

    std = math.sqrt(variance)

    # 三阶矩（偏度）
    skewness = sum((x - mean) ** 3 for x in stance_values) / (n * std ** 3)

    # 四阶矩（峰度）— 使用超额峰度
    kurtosis = sum((x - mean) ** 4 for x in stance_values) / (n * std ** 4)

    # 双峰性系数
    # 当 kurtosis 接近 0 时设下限避免除零
    kurtosis = max(kurtosis, 0.01)
    bc = ((n - 1) ** 2 * (skewness ** 2 + 1)) / ((n - 2) * (n - 3) * kurtosis)

    # 钳制到 [0, 1]
    return min(max(bc, 0.0), 1.0)


def detect_camps(stance_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """检测对立阵营

    将Agent按立场值分为支持/反对/中立三个阵营，并提取各方核心特征。

    Args:
        stance_data: [{"agent_id": str, "stance": float, "content": str}, ...]

    Returns:
        [{"camp": str, "label": str, "agent_count": int, "avg_stance": float,
          "agents": [agent_id, ...], "sample_contents": [str, ...]}, ...]
    """
    if not stance_data:
        return []

    # 按立场分区: 支持(>0.3), 反对(<-0.3), 中立(-0.3~0.3)
    camps: Dict[str, List[Dict]] = {
        "support": [],
        "oppose": [],
        "neutral": [],
    }
    for item in stance_data:
        stance = item.get("stance", 0.0)
        if stance > 0.3:
            camps["support"].append(item)
        elif stance < -0.3:
            camps["oppose"].append(item)
        else:
            camps["neutral"].append(item)

    labels = {
        "support": "支持方",
        "oppose": "反对方",
        "neutral": "中立方",
    }

    result = []
    for camp_key, members in camps.items():
        if not members:
            continue
        avg_stance = sum(m.get("stance", 0.0) for m in members) / len(members)
        sample_contents = [m.get("content", "") for m in members[:5] if m.get("content")]
        result.append({
            "camp": camp_key,
            "label": labels[camp_key],
            "agent_count": len(members),
            "avg_stance": round(avg_stance, 3),
            "agents": [m.get("agent_id", "") for m in members],
            "sample_contents": sample_contents,
        })

    # 按阵营大小降序排列
    result.sort(key=lambda x: x["agent_count"], reverse=True)
    return result


def extract_stance_values(actions: List[Dict[str, Any]]) -> List[float]:
    """从Agent行为中提取立场值

    基于行为类型和内容推断Agent立场:
    - like/share/repost: 与源内容立场一致 (+0.5 ~ +1.0)
    - dislike/flag: 与源内容立场相反 (-0.5 ~ -1.0)
    - comment: 根据内容情感分析推断 (-1.0 ~ +1.0)
    - post: 根据内容情感推断 (-1.0 ~ +1.0)

    Args:
        actions: PlatformAction dict 列表

    Returns:
        立场值列表 [-1, 1]
    """
    if not actions:
        return []

    stance_values = []
    for action in actions:
        action_type = action.get("action_type", "view")
        content = action.get("content", "")

        if action_type in ("like", "share", "repost", "quote_post"):
            # 与源内容立场一致（近似为轻微正面）
            stance = 0.5
        elif action_type in ("dislike", "flag"):
            # 反对立场
            stance = -0.7
        elif action_type in ("comment", "post") and content:
            # 基于简单关键词的立场推断
            stance = _infer_stance_from_text(content)
        else:
            stance = 0.0

        stance_values.append(stance)

    return stance_values


def _infer_stance_from_text(text: str) -> float:
    """基于简单关键词推断文本立场

    简化实现：使用正/负面关键词计数
    后续可替换为LLM情感分析
    """
    if not text:
        return 0.0

    positive_keywords = [
        "支持", "赞同", "同意", "好", "棒", "对", "应该", "正确",
        "赞", "加油", "厉害", "喜欢", "希望", "感谢", "感动",
    ]
    negative_keywords = [
        "反对", "不同意", "错", "差", "离谱", "过分", "不满",
        "愤怒", "恶心", "失望", "批评", "质疑", "荒谬", "过分",
    ]

    positive_count = sum(1 for kw in positive_keywords if kw in text)
    negative_count = sum(1 for kw in negative_keywords if kw in text)

    total = positive_count + negative_count
    if total == 0:
        return 0.0

    # 归一化到 [-1, 1]
    stance = (positive_count - negative_count) / total
    return round(stance, 2)


class PolarizationCalculator:
    """极化指数计算器 — 封装极化相关计算"""

    def __init__(self):
        self._history: List[Dict[str, Any]] = []  # 历史极化记录

    def calculate(self, stance_values: List[float]) -> float:
        """计算极化指数"""
        return calc_polarization_index(stance_values)

    def calculate_from_actions(self, actions: List[Dict[str, Any]]) -> float:
        """从行为数据计算极化指数"""
        stance_values = extract_stance_values(actions)
        return calc_polarization_index(stance_values)

    def record(self, tick: int, polarization_index: float,
               stance_values: List[float], camps: List[Dict]):
        """记录极化历史"""
        self._history.append({
            "tick": tick,
            "polarization_index": polarization_index,
            "stance_count": len(stance_values),
            "camps": camps,
        })

    def get_trend(self, window: int = 5) -> str:
        """获取极化趋势

        Returns:
            "rising" / "falling" / "stable"
        """
        if len(self._history) < 2:
            return "stable"

        recent = self._history[-window:]
        if len(recent) < 2:
            return "stable"

        first = recent[0]["polarization_index"]
        last = recent[-1]["polarization_index"]
        diff = last - first

        if diff > 0.05:
            return "rising"
        elif diff < -0.05:
            return "falling"
        return "stable"

    def get_history(self) -> List[Dict[str, Any]]:
        """获取极化历史"""
        return self._history
