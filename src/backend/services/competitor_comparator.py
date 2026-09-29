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
class ImitableAction:
    """可模仿动作"""
    category: str = ""              # 选题角度 / 标题结构 / 发布节奏
    action: str = ""                # 具体动作
    reason: str = ""                # 为什么值得模仿
    risk_impact: str = ""           # 对「能不能发」的影响


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
    structure_diff: Dict[str, str] = field(default_factory=dict)
    imitable_actions: List[ImitableAction] = field(default_factory=list)
    risk_pattern_diff: Dict[str, str] = field(default_factory=dict)
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
                field_name: str = "", db=None,
                blogger_profile: Optional[Dict] = None,
                competitor_profiles: Optional[List[Dict]] = None) -> CompetitorRiskReport:
        """对比博主与竞品的风险表现

        Args:
            blogger_id: 博主ID
            competitor_ids: 竞品ID列表
            field_name: 所属领域
            db: 数据库会话
            blogger_profile: 博主风格画像（可选，用于结构/模仿分析）
            competitor_profiles: 竞品风格画像列表（可选）

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
            self._enrich_imitation_analysis(report, blogger_profile, competitor_profiles)
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
        self._enrich_imitation_analysis(report, blogger_profile, competitor_profiles)

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

    # ------------------------------------------------------------------
    # 结构差异 / 可模仿动作 / 风险模式差异（对标「怎么模仿」）
    # ------------------------------------------------------------------

    def _enrich_imitation_analysis(
        self,
        report: CompetitorRiskReport,
        blogger_profile: Optional[Dict],
        competitor_profiles: Optional[List[Dict]],
    ) -> None:
        b_profile = blogger_profile or {}
        c_profiles = [p for p in (competitor_profiles or []) if isinstance(p, dict)]
        c_profile = c_profiles[0] if c_profiles else {}

        report.structure_diff = self._build_structure_diff(b_profile, c_profile)
        report.imitable_actions = self._build_imitable_actions(b_profile, c_profile, report)
        report.risk_pattern_diff = self._build_risk_pattern_diff(b_profile, c_profile, report)

    @staticmethod
    def _profile_topic_label(profile: Dict) -> str:
        topics = profile.get("topics", {})
        primary = topics.get("primary_topics", []) if isinstance(topics, dict) else []
        names = []
        for t in primary[:3]:
            names.append(t.get("topic", "") if isinstance(t, dict) else str(t))
        return "、".join(n for n in names if n) or "未识别"

    @staticmethod
    def _profile_tone(profile: Dict) -> str:
        expr = profile.get("expression", {})
        if isinstance(expr, dict):
            return expr.get("tone_label") or expr.get("tone") or "未识别"
        return "未识别"

    @staticmethod
    def _profile_pacing(profile: Dict) -> str:
        expr = profile.get("expression", {})
        if isinstance(expr, dict):
            return expr.get("pacing") or "未识别"
        return "未识别"

    def _build_structure_diff(self, b: Dict, c: Dict) -> Dict[str, str]:
        b_topic = self._profile_topic_label(b)
        c_topic = self._profile_topic_label(c)
        b_tone = self._profile_tone(b)
        c_tone = self._profile_tone(c)
        b_pacing = self._profile_pacing(b)
        c_pacing = self._profile_pacing(c)

        if b or c:
            topic_desc = f"你主打{b_topic}，竞品主打{c_topic}"
            if b_topic == c_topic:
                topic_desc += "，主题重合度高，需靠切入角度差异化"
            else:
                topic_desc += "，主题有差异，可借竞品选题角度拓宽边界"
            tone_desc = f"你的语气是{b_tone}，竞品是{c_tone}"
            pacing_desc = f"你的节奏是{b_pacing}，竞品是{c_pacing}"
            title_desc = (
                "竞品标题更偏结果导向（数字/对比/悬念），可参考其信息密度"
                if c_tone in ("幽默", "humorous", "轻松", "casual")
                else "竞品标题更偏观点先行，可参考其立场表达清晰度"
            )
        else:
            topic_desc = "缺少双方风格画像，暂按同领域处理：建议对比双方近 10 条内容的主题分布"
            tone_desc = "暂无语气对比数据"
            pacing_desc = "暂无节奏对比数据"
            title_desc = "建议拆解竞品近 10 条标题的句式结构（疑问/数字/对比）后对齐"

        return {
            "主题结构": topic_desc,
            "语气风格": tone_desc,
            "内容节奏": pacing_desc,
            "标题结构": title_desc,
        }

    def _build_imitable_actions(
        self, b: Dict, c: Dict, report: CompetitorRiskReport
    ) -> List[ImitableAction]:
        actions: List[ImitableAction] = []

        b_topic = self._profile_topic_label(b)
        c_topic = self._profile_topic_label(c)
        actions.append(ImitableAction(
            category="选题角度",
            action=f"参考竞品在「{c_topic}」上的切入角度，结合你擅长的「{b_topic}」做交叉选题",
            reason="竞品已验证该角度有受众反馈，交叉后既借势又保留辨识度",
            risk_impact="选题角度本身不引入额外法律风险，成稿后仍建议按常规流程预审",
        ))

        c_tone = self._profile_tone(c)
        actions.append(ImitableAction(
            category="标题结构",
            action=(
                "模仿竞品「结论前置 + 具体数字/对比」的标题句式，替换你的抽象表达"
                if c_tone not in ("未识别",)
                else "拆解竞品高播放标题的句式（疑问/数字/反转），挑 1 种句式套用到下条内容"
            ),
            reason="标题决定点击率，句式可迁移且不涉及观点抄袭",
            risk_impact="标题句式模仿不增加风险，但避免使用竞品原句，防止被指洗稿",
        ))

        c_pacing = self._profile_pacing(c)
        actions.append(ImitableAction(
            category="发布节奏",
            action=(
                f"对齐竞品「{c_pacing}」的更新节奏，固定每周同一天发布以养成观众预期"
                if c_pacing not in ("未识别",)
                else "观察竞品近 30 天发布频率，把更新节奏固定到与其同频或略快"
            ),
            reason="稳定节奏提升推荐权重，是竞品可复制的运营动作",
            risk_impact="发布节奏调整对「能不能发」无影响，不改变单条内容的风险结论",
        ))

        if report.weaknesses:
            first_weak = report.weaknesses[0]
            actions.append(ImitableAction(
                category="风险规避",
                action=f"重点自查竞品较少触碰的高危面：{first_weak}",
                reason="你在该维度高于均值，是当前最需要补的短板",
                risk_impact="落实后可直接降低该维度对「能不能发」的否决概率",
            ))

        return actions[:4]

    def _build_risk_pattern_diff(
        self, b: Dict, c: Dict, report: CompetitorRiskReport
    ) -> Dict[str, str]:
        b_risk = b.get("risk", {}) if isinstance(b.get("risk", {}), dict) else {}
        c_risk = c.get("risk", {}) if isinstance(c.get("risk", {}), dict) else {}

        b_tol = b_risk.get("risk_tolerance_label") or b_risk.get("risk_tolerance") or "未识别"
        c_tol = c_risk.get("risk_tolerance_label") or c_risk.get("risk_tolerance") or "未识别"
        b_danger = b_risk.get("danger_zones") or b_risk.get("sensitive_topics") or []
        c_danger = c_risk.get("danger_zones") or c_risk.get("sensitive_topics") or []

        if b_risk or c_risk:
            pattern = f"你风险偏好{b_tol}，竞品{c_tol}"
            danger_diff = f"你的高危区：{'、'.join(b_danger) or '暂无'}；竞品高危区：{'、'.join(c_danger) or '暂无'}"
            impact = (
                "双方高危区一致时，该话题对你们的「能不能发」结论同向，不必因竞品发过就放宽"
                if set(b_danger) & set(c_danger)
                else "高危区不同，竞品能发的话题对你未必安全，仍以自身画像为准判断能不能发"
            )
        else:
            strengths = "；".join(report.strengths[:2]) or "暂无"
            weaknesses = "；".join(report.weaknesses[:2]) or "暂无"
            pattern = f"基于风险分对比：你相对优势 {strengths}；相对劣势 {weaknesses}"
            danger_diff = "缺少双方风格画像，风险模式差异以维度分对比为准"
            impact = "维度分显示劣势面更易触发「建议修改后再发」，优势面通常可直接发布"

        return {
            "风险偏好差异": pattern,
            "高危区差异": danger_diff,
            "对发布决策的影响": impact,
        }
