"""动态权重模块 - 根据当前热点热度动态调整7维风险权重

当某个风险维度在当前热点中频繁出现时，该维度的权重自动提升，
使风控评估对时事更敏感。
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

# 7维风险维度默认权重（高风险维度权重更高）
DEFAULT_DIMENSION_WEIGHTS = {
    "政治敏感": 1.5,
    "法律合规": 1.5,
    "民族宗教": 1.3,
    "性别议题": 1.0,
    "道德伦理": 1.0,
    "群体冒犯": 1.0,
    "时事踩雷": 1.0,
}

# 权重提升上限
MAX_WEIGHT = 3.0
# 权重提升步长
BOOST_STEP = 0.3


@dataclass
class WeightAdjustment:
    """单个维度的权重调整"""
    dimension: str
    original_weight: float
    adjusted_weight: float
    boost: float                   # 提升幅度
    reason: str                    # 调整原因


@dataclass
class DynamicWeightsResult:
    """动态权重调整结果"""
    original_weights: Dict[str, float]
    adjusted_weights: Dict[str, float]
    adjustments: List[WeightAdjustment]
    signal_dimension_boosts: Dict[str, float]    # 来自信号关联的维度提升
    entity_dimension_boosts: Dict[str, float]    # 来自实体风险链的维度提升
    summary: str


class DynamicWeights:
    """动态权重调整器 - 根据热点热度动态调整7维权重"""

    def adjust(
        self,
        base_weights: Dict[str, float] | None = None,
        signal_dimension_boosts: Dict[str, float] | None = None,
        entity_dimension_boosts: Dict[str, float] | None = None,
    ) -> DynamicWeightsResult:
        """根据信号关联和实体风险链的维度提升，动态调整权重

        Args:
            base_weights: 基础权重（默认使用DEFAULT_DIMENSION_WEIGHTS）
            signal_dimension_boosts: 信号关联产生的维度提升 {维度: 提升值}
            entity_dimension_boosts: 实体风险链产生的维度提升 {维度: 提升值}

        Returns:
            DynamicWeightsResult: 动态权重调整结果
        """
        if base_weights is None:
            base_weights = DEFAULT_DIMENSION_WEIGHTS.copy()
        else:
            # 确保所有维度都存在
            for dim in DEFAULT_DIMENSION_WEIGHTS:
                if dim not in base_weights:
                    base_weights[dim] = DEFAULT_DIMENSION_WEIGHTS[dim]

        signal_boosts = signal_dimension_boosts or {}
        entity_boosts = entity_dimension_boosts or {}

        # 计算综合提升
        adjustments: List[WeightAdjustment] = []
        adjusted_weights: Dict[str, float] = {}

        for dim, base_w in base_weights.items():
            # 来自信号的提升
            s_boost = signal_boosts.get(dim, 0.0)
            # 来自实体风险链的提升
            e_boost = entity_boosts.get(dim, 0.0)
            # 综合提升（取较大值，避免重复叠加过度）
            total_boost = max(s_boost, e_boost) + min(s_boost, e_boost) * 0.3

            # 计算调整后权重
            adjusted_w = base_w + total_boost * BOOST_STEP / 0.1  # 标准化
            adjusted_w = min(MAX_WEIGHT, adjusted_w)  # 不超过上限

            adjusted_weights[dim] = round(adjusted_w, 2)

            if abs(adjusted_w - base_w) > 0.01:
                reasons = []
                if s_boost > 0:
                    reasons.append(f"热点关联(+{s_boost:.1f})")
                if e_boost > 0:
                    reasons.append(f"实体风险链(+{e_boost:.1f})")

                adjustments.append(WeightAdjustment(
                    dimension=dim,
                    original_weight=base_w,
                    adjusted_weight=round(adjusted_w, 2),
                    boost=round(adjusted_w - base_w, 2),
                    reason="; ".join(reasons),
                ))

        summary = self._generate_summary(adjustments)

        return DynamicWeightsResult(
            original_weights=base_weights,
            adjusted_weights=adjusted_weights,
            adjustments=adjustments,
            signal_dimension_boosts=signal_boosts,
            entity_dimension_boosts=entity_boosts,
            summary=summary,
        )

    def _generate_summary(self, adjustments: List[WeightAdjustment]) -> str:
        """生成权重调整说明"""
        if not adjustments:
            return "权重未调整，当前无热点关联风险"

        parts = []
        for a in adjustments:
            if a.boost > 0:
                parts.append(f"{a.dimension}: {a.original_weight}→{a.adjusted_weight}({a.reason})")

        return "动态权重调整: " + "; ".join(parts) if parts else "权重未调整"
