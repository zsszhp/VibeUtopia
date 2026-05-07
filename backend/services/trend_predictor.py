"""趋势预测引擎 - 4阶段流程

Stage 1: 态势感知 - 从仿真轨迹提取态势快照
Stage 2: 模式识别 - 5种舆论模式分类
Stage 3: 走势预测 - 短/中/长期预测+置信度
Stage 4: 决策建议 - 基于预测结果+风险等级生成建议
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


# 5种舆论模式
OPINION_PATTERNS = {
    "rapid_burst": {"name": "快速爆发型", "features": "上榜快、情感强、多平台共振"},
    "slow_rise": {"name": "缓慢升温型", "features": "缓慢升温、多轮讨论、立场渐明"},
    "controversy_split": {"name": "争议分裂型", "features": "两方对立、中间派减少、情绪升温"},
    "brief_heat": {"name": "短暂热度型", "features": "快速上榜、快速消退、情感中等"},
    "sustained_ferment": {"name": "持续发酵型", "features": "持续上榜、新角度不断出现、多轮"},
}


@dataclass
class SituationSnapshot:
    """态势快照"""
    sentiment_distribution: Dict[str, float] = field(default_factory=dict)
    propagation_paths: List[Dict] = field(default_factory=list)
    key_influencers: List[str] = field(default_factory=list)
    polarization_trend: float = 0.0
    kinetic_energy: float = 0.0
    platform_coverage: Dict[str, float] = field(default_factory=dict)
    interaction_velocity: float = 0.0


@dataclass
class PatternMatch:
    """模式匹配结果"""
    pattern_id: str = ""
    pattern_name: str = ""
    confidence: float = 0.0
    similar_cases: List[str] = field(default_factory=list)
    features_match: Dict[str, float] = field(default_factory=dict)


@dataclass
class TrendPrediction:
    """走势预测"""
    timeframe: str = ""             # short_term / medium_term / long_term
    direction: str = ""             # 上涨/持平/下降
    magnitude: float = 0.0          # 变化幅度 0-1
    confidence: float = 0.0         # 置信度 0-1
    key_turning_points: List[str] = field(default_factory=list)
    uncertainty_sources: List[str] = field(default_factory=list)


@dataclass
class DecisionAdvice:
    """决策建议"""
    risk_level: str = ""            # red / orange / yellow / green
    action: str = ""                # 不发布/大幅修改/谨慎修改/可直接发
    suggestions: List[str] = field(default_factory=list)
    counterfactual_options: List[str] = field(default_factory=list)


@dataclass
class TrendPredictionResult:
    """趋势预测总结果"""
    prediction_id: str = field(default_factory=lambda: f"pred_{uuid.uuid4().hex[:8]}")
    situation: Optional[SituationSnapshot] = None
    pattern: Optional[PatternMatch] = None
    predictions: List[TrendPrediction] = field(default_factory=list)
    decision: Optional[DecisionAdvice] = None
    summary: str = ""
    error: str = ""


class TrendPredictor:
    """趋势预测引擎"""

    async def predict(
        self,
        simulation_data: Dict,
        risk_dimensions: Dict[str, float],
        overall_score: int,
    ) -> TrendPredictionResult:
        """4阶段趋势预测

        Args:
            simulation_data: 仿真数据（propagation/monitor等）
            risk_dimensions: 风险维度分值
            overall_score: 总风险分
        """
        result = TrendPredictionResult()

        try:
            # Stage 1: 态势感知
            result.situation = self._extract_situation(simulation_data, risk_dimensions)

            # Stage 2: 模式识别
            result.pattern = await self._classify_pattern(result.situation)

            # Stage 3: 走势预测
            result.predictions = await self._predict_trend(
                result.situation, result.pattern, overall_score
            )

            # Stage 4: 决策建议
            result.decision = await self._generate_decision(
                result.situation, result.pattern, result.predictions, overall_score
            )

            # 摘要
            result.summary = self._generate_summary(result)

        except Exception as e:
            logger.error("TrendPredictor: 预测失败 %s", e)
            result.error = str(e)

        return result

    def _extract_situation(
        self, simulation_data: Dict, risk_dimensions: Dict[str, float]
    ) -> SituationSnapshot:
        """Stage 1: 态势感知"""
        propagation = simulation_data.get("propagation", {})
        monitor = simulation_data.get("monitor", {})

        return SituationSnapshot(
            sentiment_distribution=monitor.get("sentiment_distribution", {}),
            key_influencers=[],
            polarization_trend=monitor.get("polarization_index", 0.0),
            kinetic_energy=propagation.get("kinetic", 0.0),
            platform_coverage={},
            interaction_velocity=propagation.get("reach_count", 0) / max(propagation.get("depth", 1), 1),
        )

    async def _classify_pattern(self, situation: SituationSnapshot) -> PatternMatch:
        """Stage 2: 模式识别"""
        prompt = f"""分析以下舆论态势，判断最匹配的舆论模式。

当前态势：
- 情感分布: {situation.sentiment_distribution}
- 极化趋势: {situation.polarization_trend:.2f}
- 传播动能: {situation.kinetic_energy:.2f}

5种舆论模式:
1. 快速爆发型: 上榜快、情感强、多平台共振
2. 缓慢升温型: 缓慢升温、多轮讨论、立场渐明
3. 争议分裂型: 两方对立、中间派减少、情绪升温
4. 短暂热度型: 快速上榜、快速消退、情感中等
5. 持续发酵型: 持续上榜、新角度不断出现、多轮

输出JSON:
{{
    "pattern_id": "rapid_burst|slow_rise|controversy_split|brief_heat|sustained_ferment",
    "pattern_name": "模式名称",
    "confidence": 0.8,
    "features_match": {{"传播速度": 0.9, "情感强度": 0.7}},
    "similar_cases": ["类似的历史案例1"]
}}"""

        try:
            response = await call_llm(
                prompt,
                system="你是一个舆论趋势分析专家，擅长识别舆论模式。",
                task_type="risk_assessment",
            )
            data = parse_llm_json(response, fallback={"pattern_id": "brief_heat", "confidence": 0.5})

            return PatternMatch(
                pattern_id=data.get("pattern_id", "brief_heat"),
                pattern_name=data.get("pattern_name", OPINION_PATTERNS.get(data.get("pattern_id", ""), {}).get("name", "未知")),
                confidence=min(1.0, max(0.0, data.get("confidence", 0.5))),
                similar_cases=data.get("similar_cases", []),
                features_match=data.get("features_match", {}),
            )
        except Exception as e:
            logger.error("模式识别失败: %s", e)
            return PatternMatch(pattern_id="brief_heat", pattern_name="短暂热度型", confidence=0.3)

    async def _predict_trend(
        self,
        situation: SituationSnapshot,
        pattern: PatternMatch,
        overall_score: int,
    ) -> List[TrendPrediction]:
        """Stage 3: 走势预测"""
        prompt = f"""基于以下信息，预测舆论走势。

态势: 极化={situation.polarization_trend:.2f}, 动能={situation.kinetic_energy:.2f}
匹配模式: {pattern.pattern_name} (置信度{pattern.confidence:.0%})
当前风险分: {overall_score}/100

预测3个时间段的走势：

输出JSON:
{{
    "predictions": [
        {{
            "timeframe": "short_term",
            "direction": "上涨/持平/下降",
            "magnitude": 0.7,
            "confidence": 0.85,
            "key_turning_points": ["6小时内可能登上热搜"],
            "uncertainty_sources": ["取决于关键KOL是否转发"]
        }},
        {{
            "timeframe": "medium_term",
            "direction": "上涨/持平/下降",
            "magnitude": 0.5,
            "confidence": 0.6,
            "key_turning_points": ["1-3天内可能引发立场对立"],
            "uncertainty_sources": ["是否有官方回应"]
        }},
        {{
            "timeframe": "long_term",
            "direction": "上涨/持平/下降",
            "magnitude": 0.3,
            "confidence": 0.35,
            "key_turning_points": ["1-2周后可能被新热点替代"],
            "uncertainty_sources": ["新热点替代效应", "政策干预"]
        }}
    ]
}}"""

        try:
            response = await call_llm(
                prompt,
                system="你是一个舆论趋势预测专家，基于态势和模式进行走势预测。",
                task_type="risk_assessment",
            )
            data = parse_llm_json(response, fallback={"predictions": []})

            predictions = []
            for p in data.get("predictions", []):
                predictions.append(TrendPrediction(
                    timeframe=p.get("timeframe", "short_term"),
                    direction=p.get("direction", "持平"),
                    magnitude=min(1.0, max(0.0, p.get("magnitude", 0.0))),
                    confidence=min(1.0, max(0.0, p.get("confidence", 0.0))),
                    key_turning_points=p.get("key_turning_points", []),
                    uncertainty_sources=p.get("uncertainty_sources", []),
                ))

            if not predictions:
                # 降级：基于风险分简单推断
                predictions = self._fallback_predictions(overall_score)

            return predictions

        except Exception as e:
            logger.error("走势预测失败: %s", e)
            return self._fallback_predictions(overall_score)

    def _fallback_predictions(self, score: int) -> List[TrendPrediction]:
        """降级预测"""
        direction = "上涨" if score > 50 else ("持平" if score > 25 else "下降")
        return [
            TrendPrediction(timeframe="short_term", direction=direction, magnitude=0.5, confidence=0.6),
            TrendPrediction(timeframe="medium_term", direction="持平", magnitude=0.3, confidence=0.4),
            TrendPrediction(timeframe="long_term", direction="下降", magnitude=0.2, confidence=0.3),
        ]

    async def _generate_decision(
        self,
        situation: SituationSnapshot,
        pattern: PatternMatch,
        predictions: List[TrendPrediction],
        overall_score: int,
    ) -> DecisionAdvice:
        """Stage 4: 决策建议"""
        # 基于风险分和预测确定风险等级
        if overall_score > 70:
            risk_level = "red"
            action = "不建议发布"
        elif overall_score > 50:
            risk_level = "orange"
            action = "需大幅修改后发布"
        elif overall_score > 30:
            risk_level = "yellow"
            action = "建议谨慎修改后发布"
        else:
            risk_level = "green"
            action = "可直接发布"

        # 生成建议
        suggestions = []
        if situation.polarization_trend > 0.6:
            suggestions.append("内容涉及争议性话题，建议调整表述避免立场偏颇")
        if situation.kinetic_energy > 0.5:
            suggestions.append("传播动能较高，建议增加缓冲性表述")

        # 反事实选项
        counterfactual_options = [
            "如果修改争议性表述，传播动能可能降低30-50%",
            "如果增加正面案例，群体对立可能减轻",
        ]

        return DecisionAdvice(
            risk_level=risk_level,
            action=action,
            suggestions=suggestions or ["当前风险可控，建议正常发布"],
            counterfactual_options=counterfactual_options,
        )

    def _generate_summary(self, result: TrendPredictionResult) -> str:
        """生成预测摘要"""
        parts = []
        if result.pattern:
            parts.append(f"模式: {result.pattern.pattern_name}({result.pattern.confidence:.0%})")
        if result.predictions:
            short = next((p for p in result.predictions if p.timeframe == "short_term"), None)
            if short:
                parts.append(f"短期: {short.direction}({short.confidence:.0%})")
        if result.decision:
            parts.append(f"建议: {result.decision.action}")
        return " | ".join(parts) if parts else "预测完成"
