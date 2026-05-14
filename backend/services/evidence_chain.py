"""证据链构建模块

为每个风险结论提供可追溯的证据链,支持:
- 原始文本片段定位
- 多维度交叉验证
- 风险传导路径追踪
- 证据可信度评分
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EvidenceChainBuilder:
    """构建风险证据链
    
    每个风险结论都应包含:
    1. 原始证据(文本片段)
    2. 评估依据(维度规则)
    3. 交叉验证(其他维度佐证)
    4. 传导路径(风险如何升级)
    """
    
    def __init__(self):
        self.chains: list[dict[str, Any]] = []
    
    def build_chain(
        self,
        risk_sentence: dict,
        dimension: str,
        score: int,
        severity: str,
        all_dimensions: list[dict] | None = None,
    ) -> dict[str, Any]:
        """为单个风险条目构建证据链
        
        Args:
            risk_sentence: 风险句子信息
            dimension: 风险维度名称
            score: 风险分数
            severity: 严重程度
            all_dimensions: 所有维度评估结果(用于交叉验证)
            
        Returns:
            证据链字典
        """
        chain = {
            "dimension": dimension,
            "score": score,
            "severity": severity,
            "primary_evidence": {
                "text": risk_sentence.get("text", ""),
                "position": risk_sentence.get("position", {"start": 0, "end": 0}),
                "context": risk_sentence.get("context", ""),
            },
            "assessment_basis": {
                "rule": risk_sentence.get("rule", ""),
                "reasoning": risk_sentence.get("reasoning", ""),
                "keywords": risk_sentence.get("keywords", []),
            },
            "cross_validation": [],
            "propagation_path": [],
            "confidence": 0.8,
        }
        
        # 交叉验证: 检查其他维度是否也标记了此句子
        if all_dimensions:
            chain["cross_validation"] = self._cross_validate(
                risk_sentence, dimension, all_dimensions
            )
        
        # 传导路径: 分析风险如何从低到高升级
        chain["propagation_path"] = self._build_propagation_path(
            risk_sentence, dimension, score
        )
        
        # 计算证据置信度
        chain["confidence"] = self._calculate_evidence_confidence(chain)
        
        return chain
    
    def _cross_validate(
        self,
        risk_sentence: dict,
        primary_dimension: str,
        all_dimensions: list[dict],
    ) -> list[dict]:
        """交叉验证: 检查其他维度是否也识别到此风险
        
        Args:
            risk_sentence: 风险句子
            primary_dimension: 主维度
            all_dimensions: 所有维度结果
            
        Returns:
            交叉验证结果列表
        """
        validations = []
        sentence_text = risk_sentence.get("text", "")
        
        for dim in all_dimensions:
            dim_name = dim.get("name", "")
            if dim_name == primary_dimension:
                continue
            
            # 检查该维度的风险句子是否包含相同文本
            dim_sentences = dim.get("risk_sentences", [])
            for rs in dim_sentences:
                if rs.get("text", "") == sentence_text:
                    validations.append({
                        "dimension": dim_name,
                        "score": dim.get("score", 0),
                        "severity": dim.get("severity", "low"),
                        "corroboration": True,
                        "reasoning": rs.get("reasoning", ""),
                    })
                    break
        
        return validations
    
    def _build_propagation_path(
        self,
        risk_sentence: dict,
        dimension: str,
        score: int,
    ) -> list[dict]:
        """构建风险传导路径
        
        分析风险如何从低严重程度升级到当前级别
        """
        path = []
        
        # 根据分数推断传导阶段
        if score >= 80:
            path = [
                {"stage": "initial", "severity": "low", "description": "初始风险信号"},
                {"stage": "escalation", "severity": "medium", "description": "风险升级触发"},
                {"stage": "critical", "severity": "high", "description": "高风险阈值突破"},
                {"stage": "current", "severity": "critical", "description": f"当前风险等级: {score}分"},
            ]
        elif score >= 60:
            path = [
                {"stage": "initial", "severity": "low", "description": "初始风险信号"},
                {"stage": "escalation", "severity": "medium", "description": "风险升级触发"},
                {"stage": "current", "severity": "high", "description": f"当前风险等级: {score}分"},
            ]
        elif score >= 30:
            path = [
                {"stage": "initial", "severity": "low", "description": "初始风险信号"},
                {"stage": "current", "severity": "medium", "description": f"当前风险等级: {score}分"},
            ]
        else:
            path = [
                {"stage": "current", "severity": "low", "description": f"当前风险等级: {score}分"},
            ]
        
        # 添加触发因素
        keywords = risk_sentence.get("keywords", [])
        if keywords:
            path[-1]["trigger_keywords"] = keywords
        
        return path
    
    def _calculate_evidence_confidence(self, chain: dict) -> float:
        """计算证据链置信度
        
        基于:
        - 交叉验证数量(越多越高)
        - 证据完整性(字段是否齐全)
        - 风险分数(越高风险越确定)
        """
        confidence = 0.5  # 基础置信度
        
        # 交叉验证加分
        cross_validations = chain.get("cross_validation", [])
        confidence += len(cross_validations) * 0.1
        
        # 证据完整性加分
        primary = chain.get("primary_evidence", {})
        if primary.get("text"):
            confidence += 0.1
        if primary.get("context"):
            confidence += 0.05
        if chain.get("assessment_basis", {}).get("reasoning"):
            confidence += 0.1
        
        # 风险分数加成(高风险更有把握)
        score = chain.get("score", 0)
        if score >= 80:
            confidence += 0.15
        elif score >= 60:
            confidence += 0.1
        elif score >= 30:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def build_chains_for_task(
        self,
        risk_sentences: list[dict],
        dimensions: list[dict],
    ) -> list[dict]:
        """为整个任务的所有风险条目构建证据链
        
        Args:
            risk_sentences: 所有风险句子
            dimensions: 所有维度评估结果
            
        Returns:
            证据链列表
        """
        chains = []
        
        for rs in risk_sentences:
            dimension = rs.get("dimension", "未知")
            score = rs.get("score", 0)
            severity = rs.get("severity", "low")
            
            chain = self.build_chain(
                risk_sentence=rs,
                dimension=dimension,
                score=score,
                severity=severity,
                all_dimensions=dimensions,
            )
            chains.append(chain)
        
        self.chains = chains
        return chains
    
    def get_summary(self) -> dict:
        """获取证据链摘要
        
        Returns:
            摘要统计
        """
        if not self.chains:
            return {"total_chains": 0, "avg_confidence": 0, "cross_validated_count": 0}
        
        total_confidence = sum(c.get("confidence", 0) for c in self.chains)
        cross_validated = sum(
            1 for c in self.chains if len(c.get("cross_validation", [])) > 0
        )
        
        return {
            "total_chains": len(self.chains),
            "avg_confidence": round(total_confidence / len(self.chains), 2),
            "cross_validated_count": cross_validated,
            "high_confidence_count": sum(
                1 for c in self.chains if c.get("confidence", 0) >= 0.8
            ),
        }
