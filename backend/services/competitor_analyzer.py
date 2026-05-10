from __future__ import annotations

"""竞品对标分析模块 - V2.R6

对比博主与竞品的风格/主题/受众差异，
分析竞品爆款内容，生成差异化建议。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class StyleComparison:
    """风格对比"""
    dimension: str = ""
    blogger_value: str = ""
    competitor_value: str = ""
    gap: str = ""           # 差异: same/similar/different/opposite
    advantage: str = ""     # 优势方: blogger/competitor/neutral


@dataclass
class ContentGap:
    """内容缺口"""
    topic: str = ""
    competitor_coverage: float = 0.0   # 竞品覆盖度 0-1
    blogger_coverage: float = 0.0      # 博主覆盖度 0-1
    opportunity: str = ""              # 机会描述
    difficulty: str = "medium"         # 进入难度: easy/medium/hard


@dataclass
class爆款Analysis:
    """爆款分析"""
    title: str = ""
    topic: str = ""
    style: str = ""
    success_factors: list = field(default_factory=list)  # 成功因素
    replicability: float = 0.0          # 可复制性 0-1
    blogger_fit: float = 0.0           # 博主适配度 0-1


@dataclass
class DifferentiationSuggestion:
    """差异化建议"""
    strategy: str = ""
    description: str = ""
    priority: int = 3
    effort: str = "medium"             # low/medium/high
    expected_impact: str = ""


@dataclass
class CompetitorCompareResult:
    """竞品对标分析结果"""
    blogger_id: str = ""
    blogger_name: str = ""
    competitor_id: str = ""
    competitor_name: str = ""
    style_comparisons: list = field(default_factory=list)  # List[StyleComparison]
    content_gaps: list = field(default_factory=list)       # List[ContentGap]
    hit_analysis: list = field(default_factory=list)        # List[爆款Analysis]
    suggestions: list = field(default_factory=list)         # List[DifferentiationSuggestion]
    overall_assessment: str = ""
    error: Optional[str] = None


class CompetitorAnalyzer:
    """竞品对标分析器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def compare(self, blogger_profile: dict, competitor_profile: dict,
                       blogger_id: str = "", blogger_name: str = "",
                       competitor_id: str = "", competitor_name: str = "") -> CompetitorCompareResult:
        """对比博主与竞品

        Args:
            blogger_profile: 博主画像
            competitor_profile: 竞品画像
            blogger_id/name: 博主标识
            competitor_id/name: 竞品标识

        Returns:
            CompetitorCompareResult
        """
        result = CompetitorCompareResult(
            blogger_id=blogger_id,
            blogger_name=blogger_name,
            competitor_id=competitor_id,
            competitor_name=competitor_name,
        )

        # 1. 风格维度对比
        result.style_comparisons = self._compare_styles(blogger_profile, competitor_profile)

        # 2. 内容缺口分析
        result.content_gaps = self._analyze_content_gaps(blogger_profile, competitor_profile)

        # 3. 差异化建议
        result.suggestions = self._generate_suggestions(result.style_comparisons, result.content_gaps)

        # 4. LLM深度分析
        try:
            llm_result = await self._llm_deep_analysis(blogger_profile, competitor_profile, result)
            if llm_result:
                result.overall_assessment = llm_result.get("overall_assessment", "")
                if llm_result.get("suggestions"):
                    result.suggestions.extend(self._parse_suggestions(llm_result["suggestions"]))
        except Exception as e:
            logger.warning("LLM深度分析失败: %s", e)

        if not result.overall_assessment:
            result.overall_assessment = self._generate_assessment(result)

        return result

    def _compare_styles(self, blogger: dict, competitor: dict) -> list[StyleComparison]:
        """风格维度对比"""
        comparisons = []

        # 表达风格
        b_expr = blogger.get("expression", {})
        c_expr = competitor.get("expression", {})
        comparisons.append(StyleComparison(
            dimension="表达风格",
            blogger_value=b_expr.get("tone", "未知"),
            competitor_value=c_expr.get("tone", "未知"),
            gap="same" if b_expr.get("tone") == c_expr.get("tone") else "different",
            advantage="neutral",
        ))

        # 句子长度
        b_vocab = blogger.get("vocabulary", {})
        c_vocab = competitor.get("vocabulary", {})
        b_len = b_vocab.get("avg_sentence_length", 0)
        c_len = c_vocab.get("avg_sentence_length", 0)
        comparisons.append(StyleComparison(
            dimension="平均句长",
            blogger_value=f"{b_len:.0f}字",
            competitor_value=f"{c_len:.0f}字",
            gap="similar" if abs(b_len - c_len) < 5 else "different",
            advantage="blogger" if b_len < c_len else "competitor",
        ))

        # Emoji使用
        b_emoji = b_expr.get("emoji_usage", 0)
        c_emoji = c_expr.get("emoji_usage", 0)
        comparisons.append(StyleComparison(
            dimension="Emoji使用",
            blogger_value=f"{b_emoji:.1f}",
            competitor_value=f"{c_emoji:.1f}",
            gap="similar" if abs(b_emoji - c_emoji) < 0.1 else "different",
            advantage="neutral",
        ))

        # 内容多样性
        b_topics = blogger.get("topics", {})
        c_topics = competitor.get("topics", {})
        b_div = b_topics.get("content_diversity", 0)
        c_div = c_topics.get("content_diversity", 0)
        comparisons.append(StyleComparison(
            dimension="内容多样性",
            blogger_value=f"{b_div:.2f}",
            competitor_value=f"{c_div:.2f}",
            gap="similar" if abs(b_div - c_div) < 0.2 else "different",
            advantage="blogger" if b_div > c_div else "competitor",
        ))

        # 风险偏好
        b_risk = blogger.get("risk", {})
        c_risk = competitor.get("risk", {})
        comparisons.append(StyleComparison(
            dimension="风险偏好",
            blogger_value=b_risk.get("risk_tolerance", "未知"),
            competitor_value=c_risk.get("risk_tolerance", "未知"),
            gap="same" if b_risk.get("risk_tolerance") == c_risk.get("risk_tolerance") else "different",
            advantage="neutral",
        ))

        return comparisons

    def _analyze_content_gaps(self, blogger: dict, competitor: dict) -> list[ContentGap]:
        """内容缺口分析"""
        gaps = []

        b_topics = set()
        for t in blogger.get("topics", {}).get("primary_topics", []):
            if isinstance(t, dict):
                b_topics.add(t.get("topic", ""))
            elif isinstance(t, str):
                b_topics.add(t)

        c_topics = set()
        for t in competitor.get("topics", {}).get("primary_topics", []):
            if isinstance(t, dict):
                c_topics.add(t.get("topic", ""))
            elif isinstance(t, str):
                c_topics.add(t)

        # 竞品有博主没有的主题
        for topic in c_topics - b_topics:
            gaps.append(ContentGap(
                topic=topic,
                competitor_coverage=0.8,
                blogger_coverage=0.0,
                opportunity=f"竞品已覆盖'{topic}'，博主尚未涉足",
                difficulty="medium",
            ))

        # 博主有竞品没有的主题
        for topic in b_topics - c_topics:
            gaps.append(ContentGap(
                topic=topic,
                competitor_coverage=0.0,
                blogger_coverage=0.8,
                opportunity=f"博主独有'{topic}'领域，差异化优势",
                difficulty="easy",
            ))

        return gaps

    def _generate_suggestions(self, comparisons: list, gaps: list) -> list[DifferentiationSuggestion]:
        """生成差异化建议"""
        suggestions = []

        # 基于风格差异
        for comp in comparisons:
            if comp.gap == "different":
                if comp.dimension == "表达风格":
                    suggestions.append(DifferentiationSuggestion(
                        strategy="风格差异化",
                        description=f"博主{comp.blogger_value}风格与竞品{comp.competitor_value}形成差异，保持特色",
                        priority=4,
                        effort="low",
                        expected_impact="品牌辨识度提升",
                    ))

        # 基于内容缺口
        for gap in gaps:
            if gap.blogger_coverage == 0 and gap.competitor_coverage > 0:
                suggestions.append(DifferentiationSuggestion(
                    strategy="内容补缺",
                    description=gap.opportunity,
                    priority=3,
                    effort=gap.difficulty,
                    expected_impact="覆盖竞品受众",
                ))
            elif gap.blogger_coverage > 0 and gap.competitor_coverage == 0:
                suggestions.append(DifferentiationSuggestion(
                    strategy="优势强化",
                    description=gap.opportunity,
                    priority=5,
                    effort="low",
                    expected_impact="巩固差异化壁垒",
                ))

        suggestions.sort(key=lambda s: s.priority, reverse=True)
        return suggestions[:5]

    async def _llm_deep_analysis(self, blogger: dict, competitor: dict,
                                  current_result: CompetitorCompareResult) -> dict | None:
        """LLM深度分析"""
        from backend.services.llm_client import call_llm

        prompt = f"""分析以下博主与竞品的对比，给出深度洞察和差异化建议：

博主风格: {json.dumps(blogger, ensure_ascii=False)[:2000]}
竞品风格: {json.dumps(competitor, ensure_ascii=False)[:2000]}

已有分析:
- 风格差异: {len(current_result.style_comparisons)}个维度
- 内容缺口: {len(current_result.content_gaps)}个

请以JSON格式返回：
```json
{{
  "overall_assessment": "综合评估",
  "suggestions": [
    {{
      "strategy": "策略名",
      "description": "具体描述",
      "priority": 1-5,
      "effort": "low/medium/high",
      "expected_impact": "预期效果"
    }}
  ]
}}
```"""

        system = "你是一个专业的内容战略分析专家，请严格按照JSON格式输出。"

        try:
            response = await call_llm(prompt, system, task_type="default")
            import re
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = response.strip()

            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(json_str[start:end])
        except Exception as e:
            logger.warning("LLM竞品分析解析失败: %s", e)
        return None

    def _parse_suggestions(self, data: list) -> list[DifferentiationSuggestion]:
        """解析LLM建议"""
        suggestions = []
        for item in data:
            suggestions.append(DifferentiationSuggestion(
                strategy=item.get("strategy", ""),
                description=item.get("description", ""),
                priority=int(item.get("priority", 3)),
                effort=item.get("effort", "medium"),
                expected_impact=item.get("expected_impact", ""),
            ))
        return suggestions

    @staticmethod
    def _generate_assessment(result: CompetitorCompareResult) -> str:
        """生成综合评估"""
        parts = []

        # 差异维度统计
        diff_count = sum(1 for c in result.style_comparisons if c.gap == "different")
        total = len(result.style_comparisons) if result.style_comparisons else 1
        diff_ratio = diff_count / total

        if diff_ratio > 0.6:
            parts.append("博主与竞品风格差异显著，差异化优势明显")
        elif diff_ratio > 0.3:
            parts.append("博主与竞品存在一定风格差异，需强化独特性")
        else:
            parts.append("博主与竞品风格相似度高，需寻找差异化突破点")

        # 内容缺口
        unique_topics = sum(1 for g in result.content_gaps if g.blogger_coverage > 0 and g.competitor_coverage == 0)
        if unique_topics > 0:
            parts.append(f"博主有{unique_topics}个独有内容领域")
        missing = sum(1 for g in result.content_gaps if g.blogger_coverage == 0 and g.competitor_coverage > 0)
        if missing > 0:
            parts.append(f"有{missing}个竞品已覆盖的空白领域")

        return "；".join(parts)
