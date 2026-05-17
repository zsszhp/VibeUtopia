"""置信度计算模块

多源交叉验证的置信度量化系统,基于:
- 数据源质量
- 评估一致性
- 模型可靠性
- 证据充分性
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConfidenceCalculator:
    """计算风险评估的置信度
    
    置信度反映评估结果的可信程度,受以下因素影响:
    1. 数据源质量(文本清晰度、完整性)
    2. 评估一致性(多维度是否一致)
    3. 模型可靠性(LLM返回的稳定性)
    4. 证据充分性(证据链完整度)
    """
    
    def __init__(self):
        self.confidence_factors: dict[str, float] = {}
    
    def calculate(
        self,
        dimensions: list[dict],
        risk_sentences: list[dict],
        transcript_quality: dict | None = None,
        evidence_chains: list[dict] | None = None,
        platform_reactions: list[dict] | None = None,
    ) -> dict[str, Any]:
        """计算总体置信度
        
        Args:
            dimensions: 七维评估结果
            risk_sentences: 风险句子列表
            transcript_quality: 转写质量信息
            evidence_chains: 证据链列表
            platform_reactions: 平台反应列表
            
        Returns:
            置信度计算结果
        """
        # 1. 数据源质量因子
        data_quality_score = self._assess_data_quality(
            transcript_quality, risk_sentences
        )
        
        # 2. 评估一致性因子
        consistency_score = self._assess_consistency(dimensions)
        
        # 3. 证据充分性因子
        evidence_score = self._assess_evidence_sufficiency(
            evidence_chains, risk_sentences
        )
        
        # 4. 平台验证因子
        platform_validation_score = self._assess_platform_validation(
            platform_reactions
        )
        
        # 加权计算总体置信度
        weights = {
            "data_quality": 0.25,
            "consistency": 0.30,
            "evidence": 0.25,
            "platform_validation": 0.20,
        }
        
        overall_confidence = (
            data_quality_score * weights["data_quality"]
            + consistency_score * weights["consistency"]
            + evidence_score * weights["evidence"]
            + platform_validation_score * weights["platform_validation"]
        )
        
        self.confidence_factors = {
            "data_quality": data_quality_score,
            "consistency": consistency_score,
            "evidence": evidence_score,
            "platform_validation": platform_validation_score,
        }
        
        return {
            "overall_confidence": round(overall_confidence, 2),
            "factors": self.confidence_factors,
            "breakdown": {
                "data_quality_score": round(data_quality_score, 2),
                "consistency_score": round(consistency_score, 2),
                "evidence_score": round(evidence_score, 2),
                "platform_validation_score": round(platform_validation_score, 2),
            },
        }
    
    def _assess_data_quality(
        self,
        transcript_quality: dict | None,
        risk_sentences: list[dict],
    ) -> float:
        """评估数据源质量
        
        基于:
        - 转写质量(如有)
        - 文本长度
        - 风险句子覆盖率
        """
        score = 0.8  # 默认质量
        
        # 转写质量调整
        if transcript_quality:
            quality_level = transcript_quality.get("quality_level", "clean")
            quality_score = transcript_quality.get("quality_score", 100)
            
            if quality_level == "clean":
                score = 0.95
            elif quality_level == "minor_issues":
                score = 0.85
            elif quality_level == "moderate_issues":
                score = 0.70
            else:
                score = 0.55
            
            # 根据质量分数微调
            score *= (quality_score / 100)
        
        # 文本长度惩罚(太短的文本置信度低)
        total_text_length = sum(len(rs.get("text", "")) for rs in risk_sentences)
        if total_text_length < 100:
            score *= 0.8
        elif total_text_length < 500:
            score *= 0.9
        
        return max(0.0, min(1.0, score))
    
    def _assess_consistency(self, dimensions: list[dict]) -> float:
        """评估评估一致性
        
        检查:
        - 维度分数是否合理分布
        - 是否存在矛盾评估
        - 高风险维度是否有足够证据
        """
        if not dimensions:
            return 0.3
        
        scores = [d.get("score", 0) for d in dimensions]
        
        # 1. 检查分数分布合理性
        avg_score = sum(scores) / len(scores)
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        
        # 方差过大说明评估不稳定
        consistency = 1.0 - min(variance / 1000, 0.5)
        
        # 2. 检查高风险维度是否有证据支撑
        high_risk_dims = [d for d in dimensions if d.get("score", 0) >= 60]
        if high_risk_dims:
            evidence_count = sum(
                len(d.get("risk_sentences", [])) for d in high_risk_dims
            )
            # 高风险维度应该有证据
            if evidence_count == 0:
                consistency *= 0.7
            elif evidence_count < 3:
                consistency *= 0.85
        
        # 3. 维度完整性检查
        if len(dimensions) < 7:
            consistency *= (len(dimensions) / 7)
        
        return max(0.0, min(1.0, consistency))
    
    def _assess_evidence_sufficiency(
        self,
        evidence_chains: list[dict] | None,
        risk_sentences: list[dict],
    ) -> float:
        """评估证据充分性
        
        基于:
        - 证据链完整性
        - 交叉验证数量
        - 证据质量
        """
        if not evidence_chains:
            # 没有证据链,基于风险句子数量估算
            if len(risk_sentences) == 0:
                return 0.5
            elif len(risk_sentences) < 3:
                return 0.6
            else:
                return 0.7
        
        # 计算证据链平均置信度
        avg_confidence = sum(
            ec.get("confidence", 0.5) for ec in evidence_chains
        ) / len(evidence_chains)
        
        # 交叉验证加分
        cross_validated_count = sum(
            1 for ec in evidence_chains
            if len(ec.get("cross_validation", [])) > 0
        )
        cross_validation_ratio = cross_validated_count / len(evidence_chains)
        
        score = avg_confidence * 0.7 + cross_validation_ratio * 0.3
        
        return max(0.0, min(1.0, score))
    
    def _assess_platform_validation(
        self,
        platform_reactions: list[dict] | None,
    ) -> float:
        """评估平台验证分数
        
        多平台反应的一致性作为验证信号
        """
        if not platform_reactions:
            return 0.5  # 中性默认值
        
        # 检查平台反应的一致性
        reactions = []
        for pr in platform_reactions:
            negative = pr.get("negative", 0)
            positive = pr.get("positive", 0)
            # 计算负面情绪比例
            total = negative + positive + pr.get("neutral", 0)
            if total > 0:
                reactions.append(negative / total)
        
        if not reactions:
            return 0.5
        
        # 平台反应一致性高则置信度高
        avg_reaction = sum(reactions) / len(reactions)
        variance = sum((r - avg_reaction) ** 2 for r in reactions) / len(reactions)
        
        # 方差小说明平台反应一致
        consistency = 1.0 - min(variance * 4, 0.5)
        
        return max(0.0, min(1.0, 0.6 + consistency * 0.4))
    
    def get_uncertainty_notes(
        self,
        confidence_result: dict,
        dimensions: list[dict],
    ) -> list[str]:
        """生成不确定性说明
        
        列出可能影响评估准确性的因素
        """
        notes = []
        factors = confidence_result.get("factors", {})
        
        # 数据源不确定性
        if factors.get("data_quality", 1.0) < 0.7:
            notes.append("数据源质量较低,可能影响评估准确性")
        
        # 一致性不确定性
        if factors.get("consistency", 1.0) < 0.7:
            notes.append("多维度评估存在分歧,结果需谨慎参考")
        
        # 证据不确定性
        if factors.get("evidence", 1.0) < 0.6:
            notes.append("证据链不够充分,建议人工复核")
        
        # 平台验证不确定性
        if factors.get("platform_validation", 1.0) < 0.5:
            notes.append("平台反应数据不足或缺乏一致性")
        
        # 维度覆盖不全
        if len(dimensions) < 7:
            missing_count = 7 - len(dimensions)
            notes.append(f"评估维度不完整,缺失{missing_count}个维度")
        
        # 总体置信度过低
        overall = confidence_result.get("overall_confidence", 1.0)
        if overall < 0.6:
            notes.append("总体置信度较低,建议结合人工判断")
        
        return notes
