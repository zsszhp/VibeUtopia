"""报告质量优化服务 — 提供更可操作的风险标注和修改建议

优化方向：
1. 风险等级标注更具体（高/中/低 + 细分维度）
2. 修改建议更具可操作性（具体到句子级别）
3. 证据链更清晰（引用原文 + 位置标注）
4. 平台差异化建议（针对不同平台给出不同修改策略）
"""

import logging
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


class ReportOptimizer:
    """报告质量优化器"""

    # 风险等级定义
    RISK_LEVELS = {
        "critical": {
            "label": "严重风险",
            "color": "red",
            "description": "可能引发大规模负面舆论，建议立即处理",
        },
        "high": {
            "label": "高风险",
            "color": "orange",
            "description": "可能引发中等规模争议，建议优先处理",
        },
        "medium": {
            "label": "中风险",
            "color": "yellow",
            "description": "存在一定风险，建议关注并适时调整",
        },
        "low": {
            "label": "低风险",
            "color": "green",
            "description": "风险可控，保持关注即可",
        },
    }

    # 风险维度
    RISK_DIMENSIONS = [
        "价值观风险",
        "事实准确性",
        "情绪煽动性",
        "群体对立",
        "敏感话题",
        "平台合规",
    ]

    async def optimize_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """优化风险报告质量

        Args:
            report: 原始风险报告

        Returns:
            优化后的报告
        """
        # 1. 细化风险等级
        report["risk_level_detail"] = await self._refine_risk_level(report)

        # 2. 生成句子级修改建议
        report["sentence_suggestions"] = await self._generate_sentence_suggestions(report)

        # 3. 平台差异化建议
        report["platform_specific_advice"] = await self._generate_platform_advice(report)

        # 4. 证据链优化
        report["evidence_chain"] = self._optimize_evidence_chain(report)

        # 5. 可操作性评分
        report["actionability_score"] = self._calculate_actionability_score(report)

        return report

    async def _refine_risk_level(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """细化风险等级评估"""
        original_risk = report.get("risk_level", "medium")

        # 分析各维度风险
        dimension_scores = {}
        for dimension in self.RISK_DIMENSIONS:
            score = await self._assess_dimension_risk(report, dimension)
            dimension_scores[dimension] = score

        # 计算综合风险分
        avg_score = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.5

        # 确定最终风险等级
        if avg_score >= 0.8:
            final_level = "critical"
        elif avg_score >= 0.6:
            final_level = "high"
        elif avg_score >= 0.4:
            final_level = "medium"
        else:
            final_level = "low"

        return {
            "original_level": original_risk,
            "refined_level": final_level,
            "dimension_scores": dimension_scores,
            "average_score": avg_score,
            "level_info": self.RISK_LEVELS.get(final_level, self.RISK_LEVELS["medium"]),
        }

    async def _assess_dimension_risk(self, report: Dict[str, Any], dimension: str) -> float:
        """评估单个维度的风险分数 (0-1)"""
        content = report.get("analyzed_content", "")
        risk_analysis = report.get("risk_analysis", "")

        prompt = f"""请评估以下内容在"{dimension}"维度的风险分数 (0-1)。

内容摘要：
{content[:500]}

风险分析：
{risk_analysis[:500]}

评分标准：
- 0.0-0.2: 几乎无风险
- 0.2-0.4: 低风险
- 0.4-0.6: 中等风险
- 0.6-0.8: 高风险
- 0.8-1.0: 严重风险

只输出 0-1 之间的数字，保留两位小数。"""

        try:
            resp = await call_llm(prompt, task_type="risk_assessment")
            score = float(resp.strip())
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.warning("维度风险评估失败 (%s): %s", dimension, e)
            return 0.5

    async def _generate_sentence_suggestions(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成句子级别的修改建议"""
        content = report.get("analyzed_content", "")
        risk_points = report.get("risk_points", [])

        # 分割句子
        sentences = self._split_sentences(content)

        suggestions = []
        for i, sentence in enumerate(sentences):
            # 检查该句子是否涉及风险点
            related_risks = []
            for risk in risk_points:
                if self._sentence_contains_risk(sentence, risk):
                    related_risks.append(risk)

            if related_risks:
                # 生成修改建议
                suggestion = await self._suggest_sentence_revision(sentence, related_risks)
                suggestions.append({
                    "sentence_id": i,
                    "original": sentence,
                    "risks": [r.get("type", "未知风险") for r in related_risks],
                    "suggestion": suggestion,
                    "priority": "high" if len(related_risks) > 1 else "medium",
                })

        return suggestions[:10]  # 最多返回 10 条

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        import re
        # 按中文句号、问号、感叹号分割
        sentences = re.split(r'[。！？!?]', text)
        return [s.strip() for s in sentences if s.strip()][:50]  # 最多 50 句

    def _sentence_contains_risk(self, sentence: str, risk: Dict[str, Any]) -> bool:
        """判断句子是否包含风险点"""
        risk_keywords = risk.get("keywords", [])
        return any(keyword in sentence for keyword in risk_keywords)

    async def _suggest_sentence_revision(self, sentence: str, risks: List[Dict[str, Any]]) -> str:
        """为句子生成修改建议"""
        risk_types = ", ".join([r.get("type", "风险") for r in risks])

        prompt = f"""请为以下句子提供修改建议，使其更加安全、中性、客观。

原句：{sentence}

涉及风险：{risk_types}

要求：
1. 保持原意但降低风险
2. 使用更中性、客观的表述
3. 避免煽动性和绝对化语言
4. 给出修改后的完整句子

只输出修改后的句子，不要解释。"""

        try:
            resp = await call_llm(prompt, task_type="rewrite")
            return resp.strip()
        except Exception as e:
            logger.warning("句子修改建议生成失败：%s", e)
            return "建议删除或重写此句"

    async def _generate_platform_advice(self, report: Dict[str, Any]) -> Dict[str, str]:
        """生成平台差异化建议"""
        platforms = report.get("platform_reactions", {}).keys() or ["微博", "B 站", "小红书", "抖音", "知乎"]

        advice = {}
        for platform in platforms:
            advice[platform] = await self._get_platform_specific_advice(report, platform)

        return advice

    async def _get_platform_specific_advice(self, report: Dict[str, Any], platform: str) -> str:
        """获取特定平台的建议"""
        platform_chars = {
            "微博": "公开广场，传播快，易引发热议",
            "B 站": "年轻用户，重视创意和真诚",
            "小红书": "女性用户多，重视真实体验",
            "抖音": "短视频，重视视觉冲击和情绪共鸣",
            "知乎": "知识讨论，重视逻辑和证据",
        }

        prompt = f"""基于以下风险报告，为{platform}平台提供具体的应对建议。

平台特点：{platform_chars.get(platform, "综合性平台")}

风险等级：{report.get("risk_level", "medium")}

主要风险点：
{self._format_risk_points(report.get("risk_points", []))}

请提供 3 条具体建议：
1. 是否建议修改内容？如何修改？
2. 发布时机建议
3. 评论区引导策略

每条建议不超过 50 字。"""

        try:
            resp = await call_llm(prompt, task_type="risk_assessment")
            return resp.strip()
        except Exception as e:
            logger.warning("平台建议生成失败 (%s): %s", platform, e)
            return "建议根据实际情况审慎处理"

    def _format_risk_points(self, risk_points: List[Dict[str, Any]]) -> str:
        """格式化风险点"""
        if not risk_points:
            return "无明显风险点"
        return "\n".join([f"- {p.get('type', '风险')}: {p.get('description', '未知')}" for p in risk_points[:5]])

    def _optimize_evidence_chain(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """优化证据链"""
        evidence = report.get("evidence", [])
        optimized = []

        for i, ev in enumerate(evidence):
            optimized.append({
                "evidence_id": i,
                "quote": ev.get("quote", ""),
                "location": ev.get("location", f"第{i+1}段"),
                "risk_type": ev.get("risk_type", "未知"),
                "severity": ev.get("severity", "medium"),
                "explanation": ev.get("explanation", ""),
            })

        return sorted(optimized, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 1))[:10]

    def _calculate_actionability_score(self, report: Dict[str, Any]) -> float:
        """计算可操作性评分 (0-1)"""
        score = 0.0

        # 有细化风险等级 +0.2
        if "risk_level_detail" in report:
            score += 0.2

        # 有句子级建议 +0.3
        if "sentence_suggestions" in report and len(report["sentence_suggestions"]) > 0:
            score += 0.3

        # 有平台差异化建议 +0.3
        if "platform_specific_advice" in report:
            score += 0.3

        # 有优化证据链 +0.2
        if "evidence_chain" in report:
            score += 0.2

        return score


# 快捷函数
async def optimize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """优化风险报告（快捷函数）"""
    optimizer = ReportOptimizer()
    return await optimizer.optimize_report(report)


def get_risk_level_info(level: str) -> Dict[str, Any]:
    """获取风险等级信息"""
    optimizer = ReportOptimizer()
    return optimizer.RISK_LEVELS.get(level, optimizer.RISK_LEVELS["medium"])


def get_risk_dimensions() -> List[str]:
    """获取风险维度列表"""
    optimizer = ReportOptimizer()
    return optimizer.RISK_DIMENSIONS.copy()
