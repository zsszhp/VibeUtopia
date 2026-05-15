"""舆论极化指数计算 — 基于Agent立场分布的双峰性量化极化程度

V2.5 增强功能：
- 极化预警：5级（无极化→极端极化）
- 舆论转折预测：基于传播阶段+极化趋势+关键节点
- 转折点检测算法
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
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


# ==================== V2.5 极化预警系统 ====================

class PolarizationLevel(str, Enum):
    """极化预警等级（5级）"""
    NONE = "none"            # 无极化
    LOW = "low"              # 轻微极化
    MODERATE = "moderate"    # 中度极化
    HIGH = "high"            # 高度极化
    EXTREME = "extreme"      # 极端极化


POLARIZATION_LEVEL_LABELS = {
    PolarizationLevel.NONE: "无极化",
    PolarizationLevel.LOW: "轻微极化",
    PolarizationLevel.MODERATE: "中度极化",
    PolarizationLevel.HIGH: "高度极化",
    PolarizationLevel.EXTREME: "极端极化",
}

POLARIZATION_LEVEL_THRESHOLDS = {
    PolarizationLevel.NONE: 0.0,
    PolarizationLevel.LOW: 0.2,
    PolarizationLevel.MODERATE: 0.4,
    PolarizationLevel.HIGH: 0.6,
    PolarizationLevel.EXTREME: 0.8,
}


def classify_polarization_level(polarization_index: float) -> PolarizationLevel:
    """根据极化指数分类预警等级

    Args:
        polarization_index: 极化指数 0-1

    Returns:
        PolarizationLevel: 预警等级
    """
    if polarization_index < 0.2:
        return PolarizationLevel.NONE
    elif polarization_index < 0.4:
        return PolarizationLevel.LOW
    elif polarization_index < 0.6:
        return PolarizationLevel.MODERATE
    elif polarization_index < 0.8:
        return PolarizationLevel.HIGH
    return PolarizationLevel.EXTREME


@dataclass
class PolarizationWarning:
    """极化预警信息"""
    level: PolarizationLevel = PolarizationLevel.NONE
    level_label: str = ""
    polarization_index: float = 0.0
    trend: str = "stable"
    camps_ratio: Dict[str, float] = field(default_factory=dict)
    description: str = ""
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "level_label": self.level_label,
            "polarization_index": round(self.polarization_index, 3),
            "trend": self.trend,
            "camps_ratio": self.camps_ratio,
            "description": self.description,
            "recommendations": self.recommendations,
        }


def generate_polarization_warning(
    polarization_index: float,
    trend: str = "stable",
    camps: Optional[List[Dict[str, Any]]] = None,
) -> PolarizationWarning:
    """生成极化预警

    Args:
        polarization_index: 极化指数
        trend: 极化趋势 rising/falling/stable
        camps: 阵营数据

    Returns:
        PolarizationWarning
    """
    level = classify_polarization_level(polarization_index)

    # 计算阵营比例
    camps_ratio = {}
    if camps:
        total = sum(c.get("agent_count", 0) for c in camps)
        if total > 0:
            for c in camps:
                camps_ratio[c.get("camp", "")] = round(c.get("agent_count", 0) / total, 3)

    # 生成描述
    descriptions = {
        PolarizationLevel.NONE: "舆论场呈现共识状态，无明显对立",
        PolarizationLevel.LOW: "出现轻微立场分化，部分群体持不同意见",
        PolarizationLevel.MODERATE: "立场分化明显，支持与反对阵营形成对峙",
        PolarizationLevel.HIGH: "高度极化，阵营对立激烈，中立空间缩小",
        PolarizationLevel.EXTREME: "极端极化，阵营完全对立，理性讨论空间消失",
    }

    # 趋势附加描述
    trend_desc = ""
    if trend == "rising":
        trend_desc = "（且极化趋势正在加剧）"
    elif trend == "falling":
        trend_desc = "（但极化趋势正在缓解）"

    # 生成建议
    recommendations = _generate_recommendations(level, trend, camps_ratio)

    return PolarizationWarning(
        level=level,
        level_label=POLARIZATION_LEVEL_LABELS.get(level, ""),
        polarization_index=polarization_index,
        trend=trend,
        camps_ratio=camps_ratio,
        description=descriptions.get(level, "") + trend_desc,
        recommendations=recommendations,
    )


def _generate_recommendations(
    level: PolarizationLevel,
    trend: str,
    camps_ratio: Dict[str, float],
) -> List[str]:
    """根据极化等级和趋势生成建议"""
    recs = []

    if level == PolarizationLevel.NONE:
        return ["当前舆论环境健康，继续保持"]

    if level in (PolarizationLevel.LOW, PolarizationLevel.MODERATE):
        recs.append("关注对立阵营的核心诉求，避免激化矛盾")
        if trend == "rising":
            recs.append("极化趋势上升，建议提前准备回应策略")

    if level in (PolarizationLevel.HIGH, PolarizationLevel.EXTREME):
        recs.append("高度极化风险，建议暂停发布争议性内容")
        recs.append("准备多角度回应方案，照顾各方关切")
        if camps_ratio.get("neutral", 0) < 0.2:
            recs.append("中立群体过少，舆论场缺乏缓冲，风险极高")

    if trend == "rising" and level.value in ("high", "extreme"):
        recs.append("极化正在加剧且已达高危水平，强烈建议暂缓发布")

    return recs


# ==================== V2.5 舆论转折预测 ====================

class TurningPointType(str, Enum):
    """转折类型"""
    ESCALATION = "escalation"      # 升级（极化加剧）
    DEESCALATION = "deescalation"  # 缓解（极化减弱）
    REVERSAL = "reversal"          # 反转（主流立场翻转）
    FRAGMENTATION = "fragmentation"  # 碎片化（多阵营涌现）
    CONSENSUS = "consensus"        # 共识形成


TURNING_POINT_LABELS = {
    TurningPointType.ESCALATION: "极化升级",
    TurningPointType.DEESCALATION: "极化缓解",
    TurningPointType.REVERSAL: "立场反转",
    TurningPointType.FRAGMENTATION: "阵营碎片化",
    TurningPointType.CONSENSUS: "共识形成",
}


@dataclass
class TurningPointPrediction:
    """舆论转折预测结果"""
    turning_type: Optional[TurningPointType] = None
    turning_label: str = ""
    probability: float = 0.0
    estimated_tick: int = 0
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    key_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turning_type": self.turning_type.value if self.turning_type else None,
            "turning_label": self.turning_label,
            "probability": round(self.probability, 3),
            "estimated_tick": self.estimated_tick,
            "confidence": round(self.confidence, 3),
            "signals": self.signals,
            "key_factors": self.key_factors,
        }


def predict_turning_point(
    polarization_history: List[Dict[str, Any]],
    spread_stage: str = "",
    current_tick: int = 0,
    key_node_count: int = 0,
) -> TurningPointPrediction:
    """舆论转折预测

    基于传播阶段 + 极化趋势 + 关键节点预测舆论转折。

    Args:
        polarization_history: 极化历史记录 [{"tick", "polarization_index", ...}, ...]
        spread_stage: 当前传播阶段
        current_tick: 当前 tick
        key_node_count: 关键影响者数量

    Returns:
        TurningPointPrediction
    """
    if len(polarization_history) < 3:
        return TurningPointPrediction(
            turning_type=None,
            turning_label="数据不足",
            probability=0.0,
            confidence=0.0,
            signals=["历史数据不足，无法预测转折"],
        )

    # 提取极化指数序列
    indices = [h.get("polarization_index", 0.0) for h in polarization_history]
    recent_indices = indices[-10:]  # 最近10个tick

    # 计算极化变化率
    changes = []
    for i in range(1, len(recent_indices)):
        changes.append(recent_indices[i] - recent_indices[i - 1])

    avg_change = sum(changes) / len(changes) if changes else 0.0

    # 计算加速度（变化率的变化率）
    accelerations = []
    for i in range(1, len(changes)):
        accelerations.append(changes[i] - changes[i - 1])

    avg_acceleration = sum(accelerations) / len(accelerations) if accelerations else 0.0

    # 当前极化水平
    current_polarization = indices[-1] if indices else 0.0

    # 分析信号
    signals = []
    key_factors = []
    turning_type = None
    probability = 0.0
    estimated_tick = current_tick + 5

    # 信号1：极化加速上升 → 可能升级
    if avg_change > 0.03 and avg_acceleration > 0.01:
        signals.append("极化指数加速上升")
        key_factors.append("极化加速度为正")
        turning_type = TurningPointType.ESCALATION
        probability = min(0.8, 0.3 + abs(avg_acceleration) * 10)
        estimated_tick = current_tick + max(2, int(3 / max(avg_change, 0.01)))

    # 信号2：极化高位减速 → 可能缓解
    elif current_polarization > 0.5 and avg_change < -0.02:
        signals.append("极化高位开始回落")
        key_factors.append("极化指数下降趋势")
        turning_type = TurningPointType.DEESCALATION
        probability = min(0.7, 0.3 + abs(avg_change) * 5)
        estimated_tick = current_tick + max(3, int(2 / max(abs(avg_change), 0.01)))

    # 信号3：传播阶段从社群扩散到立场分化 → 可能反转
    elif spread_stage in ("community", "polarization") and current_polarization > 0.4:
        signals.append("传播进入立场分化阶段")
        key_factors.append(f"传播阶段: {spread_stage}")
        if key_node_count > 3:
            signals.append("关键影响者数量较多，可能引发立场反转")
            key_factors.append(f"关键节点数: {key_node_count}")
            turning_type = TurningPointType.REVERSAL
            probability = min(0.6, 0.2 + key_node_count * 0.05)
            estimated_tick = current_tick + 8

    # 信号4：极化高位但阵营数增多 → 碎片化
    elif current_polarization > 0.6:
        camps_data = polarization_history[-1].get("camps", [])
        if len(camps_data) >= 3:
            neutral_ratio = 0.0
            for c in camps_data:
                if c.get("camp") == "neutral":
                    neutral_ratio = c.get("agent_count", 0) / max(
                        sum(cc.get("agent_count", 0) for cc in camps_data), 1
                    )
            if neutral_ratio < 0.15:
                signals.append("中立群体极少，阵营碎片化风险")
                key_factors.append(f"中立比例: {neutral_ratio:.1%}")
                turning_type = TurningPointType.FRAGMENTATION
                probability = min(0.5, 0.2 + (0.15 - neutral_ratio) * 3)
                estimated_tick = current_tick + 6

    # 信号5：极化持续下降 → 共识形成
    elif current_polarization < 0.3 and avg_change < -0.01:
        signals.append("极化持续下降，共识正在形成")
        key_factors.append("极化指数低位且持续下降")
        turning_type = TurningPointType.CONSENSUS
        probability = min(0.7, 0.3 + (0.3 - current_polarization) * 2)
        estimated_tick = current_tick + 4

    # 降级：无明确信号
    if turning_type is None:
        return TurningPointPrediction(
            turning_type=None,
            turning_label="暂无明显转折信号",
            probability=0.0,
            confidence=0.0,
            signals=["当前舆论态势稳定，暂无转折迹象"],
            key_factors=[],
        )

    # 计算置信度
    confidence = _calc_prediction_confidence(
        len(polarization_history), probability, len(signals)
    )

    return TurningPointPrediction(
        turning_type=turning_type,
        turning_label=TURNING_POINT_LABELS.get(turning_type, ""),
        probability=probability,
        estimated_tick=estimated_tick,
        confidence=confidence,
        signals=signals,
        key_factors=key_factors,
    )


def _calc_prediction_confidence(
    data_points: int,
    probability: float,
    signal_count: int,
) -> float:
    """计算预测置信度

    基于数据量、概率和信号数量综合评估
    """
    # 数据量因子（数据越多越可信）
    data_factor = min(1.0, data_points / 20)

    # 信号因子（信号越多越可信）
    signal_factor = min(1.0, signal_count / 3)

    # 概率因子（概率适中时置信度最高）
    prob_factor = 1.0 - abs(probability - 0.6) * 0.5

    confidence = data_factor * 0.3 + signal_factor * 0.4 + prob_factor * 0.3
    return round(min(max(confidence, 0.1), 0.95), 3)


# ==================== V2.5 转折点检测算法 ====================

@dataclass
class DetectedTurningPoint:
    """检测到的转折点"""
    tick: int = 0
    polarization_before: float = 0.0
    polarization_after: float = 0.0
    change_magnitude: float = 0.0
    turning_type: Optional[TurningPointType] = None
    turning_label: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "polarization_before": round(self.polarization_before, 3),
            "polarization_after": round(self.polarization_after, 3),
            "change_magnitude": round(self.change_magnitude, 3),
            "turning_type": self.turning_type.value if self.turning_type else None,
            "turning_label": self.turning_label,
            "confidence": round(self.confidence, 3),
        }


def detect_turning_points(
    polarization_history: List[Dict[str, Any]],
    threshold: float = 0.1,
    min_interval: int = 3,
) -> List[DetectedTurningPoint]:
    """转折点检测算法

    基于极化指数的变化率检测舆论转折点。
    使用滑动窗口计算局部变化率，当变化率超过阈值时标记为转折点。

    Args:
        polarization_history: 极化历史记录
        threshold: 变化幅度阈值（默认0.1）
        min_interval: 最小转折点间隔（tick数，避免密集检测）

    Returns:
        检测到的转折点列表
    """
    if len(polarization_history) < 5:
        return []

    indices = [h.get("polarization_index", 0.0) for h in polarization_history]
    ticks = [h.get("tick", i) for i, h in enumerate(polarization_history)]

    turning_points = []
    last_tp_tick = -min_interval  # 确保第一个可以检测

    # 滑动窗口（窗口大小3）
    window_size = 3
    for i in range(window_size, len(indices)):
        # 窗口前半段均值
        before_window = indices[i - window_size:i]
        before_mean = sum(before_window) / len(before_window)

        # 当前值
        current = indices[i]

        # 变化幅度
        change = current - before_mean

        # 检查是否超过阈值
        if abs(change) >= threshold:
            tick = ticks[i]

            # 检查最小间隔
            if tick - last_tp_tick < min_interval:
                continue

            # 判断转折类型
            if change > 0:
                if before_mean < 0.3 and current > 0.5:
                    tp_type = TurningPointType.ESCALATION
                else:
                    tp_type = TurningPointType.ESCALATION
            else:
                if current < 0.3:
                    tp_type = TurningPointType.CONSENSUS
                else:
                    tp_type = TurningPointType.DEESCALATION

            # 置信度基于变化幅度
            confidence = min(0.95, 0.4 + abs(change) * 2)

            tp = DetectedTurningPoint(
                tick=tick,
                polarization_before=round(before_mean, 3),
                polarization_after=round(current, 3),
                change_magnitude=round(change, 3),
                turning_type=tp_type,
                turning_label=TURNING_POINT_LABELS.get(tp_type, ""),
                confidence=round(confidence, 3),
            )
            turning_points.append(tp)
            last_tp_tick = tick

    return turning_points


class EnhancedPolarizationCalculator(PolarizationCalculator):
    """增强版极化计算器 — 包含预警、转折预测和转折点检测"""

    def __init__(self):
        super().__init__()
        self._turning_points: List[DetectedTurningPoint] = []
        self._last_warning: Optional[PolarizationWarning] = None

    def get_warning(self, trend: str = "stable") -> PolarizationWarning:
        """获取当前极化预警"""
        if not self._history:
            return generate_polarization_warning(0.0, trend)

        latest = self._history[-1]
        polarization_index = latest.get("polarization_index", 0.0)
        camps = latest.get("camps", [])

        warning = generate_polarization_warning(polarization_index, trend, camps)
        self._last_warning = warning
        return warning

    def predict_turning(
        self,
        spread_stage: str = "",
        current_tick: int = 0,
        key_node_count: int = 0,
    ) -> TurningPointPrediction:
        """预测舆论转折"""
        return predict_turning_point(
            self._history,
            spread_stage,
            current_tick,
            key_node_count,
        )

    def detect_historical_turning_points(self, threshold: float = 0.1) -> List[DetectedTurningPoint]:
        """检测历史转折点"""
        self._turning_points = detect_turning_points(self._history, threshold)
        return self._turning_points

    def get_enhanced_summary(self, spread_stage: str = "", current_tick: int = 0) -> Dict[str, Any]:
        """获取增强版极化摘要（含预警和转折预测）"""
        trend = self.get_trend()
        warning = self.get_warning(trend)
        prediction = self.predict_turning(spread_stage, current_tick)
        turning_points = self.detect_historical_turning_points()

        return {
            "current_polarization": self._history[-1].get("polarization_index", 0.0) if self._history else 0.0,
            "trend": trend,
            "warning": warning.to_dict(),
            "turning_prediction": prediction.to_dict(),
            "detected_turning_points": [tp.to_dict() for tp in turning_points[-5:]],
            "history_length": len(self._history),
        }
