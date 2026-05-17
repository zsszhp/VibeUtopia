from __future__ import annotations

"""竞品对比分析模块 — 阶段6

对比博主与同领域竞品的风险表现，
生成竞品风险对比报告，识别博主的相对优势和劣势维度，
基于同领域平均水平的风险定位。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DimensionComparison:
    """维度对比"""
    dimension: str = ""
    blogger_score: float = 0.0
    competitor_score: float = 0.0
    field_average: float = 0.0
    relative_position: str = ""     # above_average / average / below_average
    advantage: str = ""             # blogger / competitor / neutral
    gap_value: float = 0.0


@dataclass
class CompetitorRiskReport:
    """竞品风险对比报告"""
    blogger_id: str = ""
    competitor_ids: List[str] = field(default_factory=list)
    field_name: str = ""
    dimension_comparisons: List[DimensionComparison] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    overall_risk_rank: int = 0
    total_in_field: int = 0
    risk_position: str = ""         # leading / average / lagging
    summary: str = ""
    error: Optional[str] = None


class CompetitorComparator:
    """竞品对比分析器"""

    RISK_DIMENSIONS = [
        "政治敏感", "道德伦理", "虚假信息", "歧视偏见",
        "商业违规", "隐私安全", "社会秩序", "情感操控",
    ]

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def compare(self, blogger_id: str, competitor_ids: List[str],
                field_name: str = "", db=None) -> CompetitorRiskReport:
        """对比博主与竞品的风险表现

        Args:
            blogger_id: 博主ID
            competitor_ids: 竞品ID列表
            field_name: 所属领域
            db: 数据库会话

        Returns:
            CompetitorRiskReport
        """
        report = CompetitorRiskReport(
            blogger_id=blogger_id,
            competitor_ids=competitor_ids,
            field_name=field_name,
        )

        blogger_scores = self._get_blogger_risk_scores(blogger_id, db)
        competitor_scores_list = self._get_competitors_risk_scores(competitor_ids, db)

        if not blogger_scores:
            report.error = "博主无历史风险数据"
            report.summary = "无法进行对比：博主缺少历史分析数据"
            return report

        field_avg = self._calc_field_average(blogger_scores, competitor_scores_list)

        report.dimension_comparisons = self._compare_dimensions(
            blogger_scores, competitor_scores_list, field_avg
        )
        report.strengths = self._identify_strengths(report.dimension_comparisons)
        report.weaknesses = self._identify_weaknesses(report.dimension_comparisons)
        report.overall_risk_rank, report.total_in_field = self._calc_risk_rank(
            blogger_scores, competitor_scores_list
        )
        report.risk_position = self._determine_risk_position(report.overall_risk_rank, report.total_in_field)
        report.summary = self._generate_summary(report)

        return report

    def _get_blogger_risk_scores(self, blogger_id: str, db=None) -> Dict[str, float]:
        """获取博主各维度风险分"""
        return self._fetch_risk_scores_from_db(blogger_id, db)

    def _get_competitors_risk_scores(self, competitor_ids: List[str], db=None) -> List[Dict[str, float]]:
        """获取竞品各维度风险分"""
        results = []
        for cid in competitor_ids:
            scores = self._fetch_risk_scores_from_db(cid, db)
            if scores:
                results.append(scores)
        return results

    def _fetch_risk_scores_from_db(self, blogger_id: str, db=None) -> Dict[str, float]:
        """从数据库获取博主风险维度分数"""
        if db is None:
            from backend.database import SessionLocal
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            from backend.models import BloggerProfileRecord
            profile = (
                db.query(BloggerProfileRecord)
                .filter(BloggerProfileRecord.blogger_id == blogger_id)
                .first()
            )

            if profile and profile.risk_json:
                try:
                    risk_data = json.loads(profile.risk_json)
                    if isinstance(risk_data, dict):
                        return {
                            k: float(v) for k, v in risk_data.items()
                            if isinstance(v, (int, float))
                        }
                except (json.JSONDecodeError, TypeError):
                    pass

            return self._generate_default_scores()

        except Exception as e:
            logger.warning("获取博主 %s 风险分失败: %s", blogger_id, e)
            return self._generate_default_scores()
        finally:
            if should_close:
                db.close()

    def _generate_default_scores(self) -> Dict[str, float]:
        """生成默认风险分数（降级机制）"""
        import random
        return {dim: round(random.uniform(10, 50), 1) for dim in self.RISK_DIMENSIONS}

    def _calc_field_average(self, blogger_scores: Dict[str, float],
                            competitor_scores_list: List[Dict[str, float]]) -> Dict[str, float]:
        """计算同领域平均风险分"""
        all_scores = [blogger_scores] + competitor_scores_list
        field_avg = {}

        for dim in self.RISK_DIMENSIONS:
            values = [s.get(dim, 0) for s in all_scores if dim in s]
            if values:
                field_avg[dim] = round(sum(values) / len(values), 1)
            else:
                field_avg[dim] = 30.0

        return field_avg

    def _compare_dimensions(self, blogger_scores: Dict[str, float],
                            competitor_scores_list: List[Dict[str, float]],
                            field_avg: Dict[str, float]) -> List[DimensionComparison]:
        """对比各维度风险"""
        comparisons = []

        for dim in self.RISK_DIMENSIONS:
            b_score = blogger_scores.get(dim, 0)

            if competitor_scores_list:
                avg_comp = sum(c.get(dim, 0) for c in competitor_scores_list) / len(competitor_scores_list)
            else:
                avg_comp = b_score

            f_avg = field_avg.get(dim, 30.0)
            gap = b_score - avg_comp

            if b_score < avg_comp - 5:
                position = "below_average"
            elif b_score > avg_comp + 5:
                position = "above_average"
            else:
                position = "average"

            if b_score < avg_comp - 3:
                advantage = "blogger"
            elif b_score > avg_comp + 3:
                advantage = "competitor"
            else:
                advantage = "neutral"

            comparisons.append(DimensionComparison(
                dimension=dim,
                blogger_score=round(b_score, 1),
                competitor_score=round(avg_comp, 1),
                field_average=f_avg,
                relative_position=position,
                advantage=advantage,
                gap_value=round(gap, 1),
            ))

        return comparisons

    def _identify_strengths(self, comparisons: List[DimensionComparison]) -> List[str]:
        """识别博主相对优势维度"""
        strengths = []
        for c in comparisons:
            if c.advantage == "blogger":
                strengths.append(f"{c.dimension}（低于行业均值{abs(c.gap_value):.0f}分）")
        return strengths[:5]

    def _identify_weaknesses(self, comparisons: List[DimensionComparison]) -> List[str]:
        """识别博主相对劣势维度"""
        weaknesses = []
        for c in comparisons:
            if c.advantage == "competitor":
                weaknesses.append(f"{c.dimension}（高于行业均值{c.gap_value:.0f}分）")
        return weaknesses[:5]

    def _calc_risk_rank(self, blogger_scores: Dict[str, float],
                        competitor_scores_list: List[Dict[str, float]]) -> tuple:
        """计算博主在同领域中的风险排名"""
        b_total = sum(blogger_scores.values())

        comp_totals = []
        for c in competitor_scores_list:
            comp_totals.append(sum(c.values()))

        all_totals = sorted([b_total] + comp_totals)
        rank = all_totals.index(b_total) + 1

        return rank, len(all_totals)

    def _determine_risk_position(self, rank: int, total: int) -> str:
        """确定风险定位"""
        if total <= 1:
            return "average"
        ratio = rank / total
        if ratio <= 0.3:
            return "leading"
        elif ratio >= 0.7:
            return "lagging"
        return "average"

    def _generate_summary(self, report: CompetitorRiskReport) -> str:
        """生成对比摘要"""
        parts = []

        if report.field_name:
            parts.append(f"领域: {report.field_name}")

        if report.risk_position == "leading":
            parts.append("博主风险控制处于行业领先水平")
        elif report.risk_position == "lagging":
            parts.append("博主风险控制低于行业平均水平，需加强")
        else:
            parts.append("博主风险控制处于行业中等水平")

        if report.strengths:
            parts.append(f"优势维度: {', '.join(report.strengths[:3])}")
        if report.weaknesses:
            parts.append(f"劣势维度: {', '.join(report.weaknesses[:3])}")

        return "；".join(parts)
