from __future__ import annotations

"""决策辅助模块 — 阶段6

基于风险评估结果，给出具体的发布建议。
建议类型：直接发布/修改后发布/暂缓发布/不建议发布。
给出修改优先级排序，预估修改后的风险降低幅度，生成决策报告。
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModificationPriority:
    """修改优先级项"""
    priority: int = 0
    dimension: str = ""
    sentence: str = ""
    severity: str = ""
    suggested_action: str = ""
    estimated_risk_reduction: float = 0.0
    effort: str = "low"             # low / medium / high


@dataclass
class DecisionAdvice:
    """决策建议"""
    advice_type: str = ""           # publish / publish_with_modification / postpone / do_not_publish
    advice_label: str = ""          # 直接发布 / 修改后发布 / 暂缓发布 / 不建议发布
    confidence: float = 0.0
    overall_risk_score: float = 0.0
    risk_level: str = "green"
    modification_priorities: List[ModificationPriority] = field(default_factory=list)
    estimated_final_risk: float = 0.0
    estimated_risk_reduction: float = 0.0
    key_risk_factors: List[str] = field(default_factory=list)
    reasoning: str = ""
    error: Optional[str] = None


@dataclass
class DecisionReport:
    """决策报告"""
    report_id: str = ""
    task_id: str = ""
    advice: Optional[DecisionAdvice] = None
    risk_summary: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    created_at: str = ""


class DecisionAdvisor:
    """决策辅助器"""

    ADVICE_THRESHOLDS = {
        "publish": {"max_score": 30, "max_severity": "low"},
        "publish_with_modification": {"max_score": 60, "max_severity": "medium"},
        "postpone": {"max_score": 80, "max_severity": "high"},
        "do_not_publish": {"max_score": 100, "max_severity": "critical"},
    }

    SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "green": 0}

    ADVICE_LABELS = {
        "publish": "直接发布",
        "publish_with_modification": "修改后发布",
        "postpone": "暂缓发布",
        "do_not_publish": "不建议发布",
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def advise(self, risk_report: Dict) -> DecisionAdvice:
        """基于风险评估结果给出发布建议

        Args:
            risk_report: 风险评估报告

        Returns:
            DecisionAdvice
        """
        advice = DecisionAdvice()

        overall_score = risk_report.get("overall_risk", risk_report.get("overall_score", 0))
        risk_level = risk_report.get("risk_level", "green")
        dimensions = risk_report.get("dimensions", [])
        suggestions = risk_report.get("suggestions", [])

        advice.overall_risk_score = float(overall_score)
        advice.risk_level = risk_level

        advice.advice_type = self._determine_advice_type(overall_score, risk_level, dimensions)
        advice.advice_label = self.ADVICE_LABELS.get(advice.advice_type, "未知")

        advice.modification_priorities = self._prioritize_modifications(dimensions, suggestions)
        advice.estimated_risk_reduction = self._estimate_risk_reduction(advice.modification_priorities)
        advice.estimated_final_risk = max(0, overall_score - advice.estimated_risk_reduction)

        advice.key_risk_factors = self._extract_key_risk_factors(dimensions)
        advice.confidence = self._calculate_confidence(risk_report)
        advice.reasoning = self._generate_reasoning(advice, risk_report)

        return advice

    def generate_report(self, task_id: str, risk_report: Dict) -> DecisionReport:
        """生成完整决策报告"""
        from datetime import datetime, timezone

        advice = self.advise(risk_report)

        return DecisionReport(
            report_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            advice=advice,
            risk_summary={
                "overall_score": advice.overall_risk_score,
                "risk_level": advice.risk_level,
                "dimension_count": len(risk_report.get("dimensions", [])),
                "high_risk_count": sum(
                    1 for d in risk_report.get("dimensions", [])
                    if d.get("severity") in ("high", "critical")
                ),
            },
            recommendations=self._generate_recommendations(advice),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _determine_advice_type(self, score: float, risk_level: str,
                                dimensions: List[dict]) -> str:
        """确定建议类型"""
        max_severity = "green"
        for dim in dimensions:
            sev = dim.get("severity", "green")
            if self.SEVERITY_ORDER.get(sev, 0) > self.SEVERITY_ORDER.get(max_severity, 0):
                max_severity = sev

        if score >= 80 or max_severity == "critical":
            return "do_not_publish"
        elif score >= 60 or max_severity == "high":
            return "postpone"
        elif score >= 30 or max_severity == "medium":
            return "publish_with_modification"
        return "publish"

    def _prioritize_modifications(self, dimensions: List[dict],
                                   suggestions: List[dict]) -> List[ModificationPriority]:
        """修改优先级排序"""
        priorities = []

        sorted_dims = sorted(
            dimensions,
            key=lambda d: self.SEVERITY_ORDER.get(d.get("severity", "green"), 0),
            reverse=True,
        )

        for i, dim in enumerate(sorted_dims):
            severity = dim.get("severity", "green")
            if severity in ("green", "low"):
                continue

            dim_name = dim.get("name", dim.get("dimension", "未知"))
            sentence = dim.get("evidence", dim.get("sentence", ""))
            score = dim.get("score", 0)

            suggested_action = self._suggest_action(severity, dim_name)
            estimated_reduction = self._estimate_dimension_reduction(severity, score)
            effort = self._estimate_effort(severity)

            matching_suggestion = None
            for s in suggestions:
                s_dim = s.get("dimension", "")
                if s_dim == dim_name:
                    matching_suggestion = s.get("suggestion", "")
                    break

            priorities.append(ModificationPriority(
                priority=i + 1,
                dimension=dim_name,
                sentence=sentence[:100],
                severity=severity,
                suggested_action=matching_suggestion or suggested_action,
                estimated_risk_reduction=estimated_reduction,
                effort=effort,
            ))

        return priorities[:10]

    def _suggest_action(self, severity: str, dimension: str) -> str:
        """生成修改建议"""
        if severity == "critical":
            return f"必须删除或彻底重写{dimension}相关内容"
        elif severity == "high":
            return f"建议大幅修改{dimension}相关表述"
        elif severity == "medium":
            return f"建议适当调整{dimension}相关措辞"
        return f"可选择性优化{dimension}相关内容"

    def _estimate_dimension_reduction(self, severity: str, score: float) -> float:
        """预估单维度风险降低幅度"""
        reduction_rates = {
            "critical": 0.5,
            "high": 0.4,
            "medium": 0.3,
            "low": 0.2,
            "green": 0.1,
        }
        rate = reduction_rates.get(severity, 0.2)
        return round(score * rate, 1)

    def _estimate_effort(self, severity: str) -> str:
        """预估修改难度"""
        effort_map = {"critical": "high", "high": "high", "medium": "medium", "low": "low", "green": "low"}
        return effort_map.get(severity, "medium")

    def _estimate_risk_reduction(self, priorities: List[ModificationPriority]) -> float:
        """预估总体风险降低幅度"""
        if not priorities:
            return 0.0

        total_reduction = sum(p.estimated_risk_reduction for p in priorities[:3])
        diminishing_factor = 0.7

        adjusted = total_reduction * diminishing_factor
        return round(adjusted, 1)

    def _extract_key_risk_factors(self, dimensions: List[dict]) -> List[str]:
        """提取关键风险因素"""
        factors = []
        for dim in dimensions:
            severity = dim.get("severity", "green")
            if severity in ("high", "critical", "medium"):
                name = dim.get("name", dim.get("dimension", "未知"))
                evidence = dim.get("evidence", "")[:60]
                factors.append(f"{name}: {evidence}" if evidence else name)

        return factors[:5]

    def _calculate_confidence(self, risk_report: Dict) -> float:
        """计算决策置信度"""
        confidence = 0.5

        dimensions = risk_report.get("dimensions", [])
        if len(dimensions) >= 3:
            confidence += 0.15

        if risk_report.get("confidence"):
            confidence += 0.15

        if risk_report.get("evidence_chains"):
            confidence += 0.1

        if risk_report.get("signal_correlations"):
            confidence += 0.1

        return round(min(confidence, 1.0), 2)

    def _generate_reasoning(self, advice: DecisionAdvice, risk_report: Dict) -> str:
        """生成决策推理过程"""
        parts = []

        parts.append(f"综合风险评分: {advice.overall_risk_score:.0f}分（{advice.risk_level}级）")

        if advice.advice_type == "publish":
            parts.append("各项风险指标均在安全范围内，可直接发布")
        elif advice.advice_type == "publish_with_modification":
            parts.append(f"存在{len(advice.modification_priorities)}项需修改的内容")
            if advice.estimated_risk_reduction > 0:
                parts.append(f"预计修改后风险可降低{advice.estimated_risk_reduction:.0f}分至{advice.estimated_final_risk:.0f}分")
        elif advice.advice_type == "postpone":
            parts.append("存在较高风险因素，建议暂缓发布并重新评估")
        elif advice.advice_type == "do_not_publish":
            parts.append("存在严重风险因素，强烈建议不发布此内容")

        high_priority = [p for p in advice.modification_priorities if p.severity in ("high", "critical")]
        if high_priority:
            dims = ", ".join(p.dimension for p in high_priority[:3])
            parts.append(f"高风险维度: {dims}")

        return "；".join(parts)

    def _generate_recommendations(self, advice: DecisionAdvice) -> List[str]:
        """生成推荐行动列表"""
        recs = []

        if advice.advice_type == "publish":
            recs.append("内容安全，可以正常发布")
            recs.append("建议持续关注发布后的舆论反馈")
        elif advice.advice_type == "publish_with_modification":
            recs.append("按优先级修改高风险内容后发布")
            for p in advice.modification_priorities[:3]:
                recs.append(f"[P{p.priority}] {p.suggested_action}")
            recs.append(f"预计修改后风险降至{advice.estimated_final_risk:.0f}分")
        elif advice.advice_type == "postpone":
            recs.append("暂缓发布，等待热点降温或重新评估")
            recs.append("重点关注高风险维度并考虑彻底重写")
            recs.append("建议24小时后重新评估风险")
        elif advice.advice_type == "do_not_publish":
            recs.append("不建议发布此内容")
            recs.append("如需发布，须彻底重写高风险部分")
            recs.append("建议咨询专业风控团队")

        return recs
