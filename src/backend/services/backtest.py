"""回测框架 - 用历史案例验证仿真风控的可信度

同时运行MVP和V2评估，对比预测vs实际结果，
5维度准确率评估（方向40%/平台20%/维度20%/群体10%/极化10%）

V2.5 增强：
- 多轮一致性检查（3轮仿真一致性验证）
- 可信度标注系统
- V2 vs MVP 对比报告生成
- Go/No-Go 判定逻辑增强
"""

import asyncio
import json
import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.database import SessionLocal
from backend.models import Task, BacktestRecord
from backend.services.enhanced_analyzer import run_enhanced_analysis

logger = logging.getLogger(__name__)


@dataclass
class ActualOutcome:
    """实际结果"""
    overall_direction: str = ""         # 上涨/持平/下降
    platforms_affected: List[str] = field(default_factory=list)
    peak_heat_score: float = 0.0
    duration_days: int = 0
    polarization_occurred: bool = False
    key_groups_affected: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class BacktestCase:
    """回测用例"""
    case_id: str = ""
    title: str = ""
    seed_content: str = ""
    actual_outcome: ActualOutcome = field(default_factory=ActualOutcome)
    risk_dimensions: List[str] = field(default_factory=list)


@dataclass
class DimensionAccuracy:
    """单维度准确率"""
    direction_accuracy: float = 0.0     # 方向准确率
    platform_accuracy: float = 0.0      # 平台准确率
    dimension_accuracy: float = 0.0     # 维度准确率
    group_accuracy: float = 0.0         # 群体准确率
    polarization_accuracy: float = 0.0  # 极化准确率
    weighted_accuracy: float = 0.0      # 加权总准确率


@dataclass
class BacktestComparison:
    """单案例回测对比"""
    case_id: str = ""
    title: str = ""
    mvp_score: int = 0
    v2_score: int = 0
    mvp_dimensions: dict = field(default_factory=dict)
    v2_dimensions: dict = field(default_factory=dict)
    mvp_accuracy: DimensionAccuracy = field(default_factory=DimensionAccuracy)
    v2_accuracy: DimensionAccuracy = field(default_factory=DimensionAccuracy)
    improvement: float = 0.0            # V2 vs MVP改善幅度


@dataclass
class BacktestReport:
    """回测报告"""
    report_id: str = field(default_factory=lambda: f"bt_{uuid.uuid4().hex[:8]}")
    total_cases: int = 0
    comparisons: List[BacktestComparison] = field(default_factory=list)
    mvp_avg_accuracy: float = 0.0
    v2_avg_accuracy: float = 0.0
    overall_improvement: float = 0.0
    go_no_go: str = ""                  # Go / No-Go / Conditional Go
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# 预定义回测用例（基于cases/paperwork/中的已知案例）
PREDEFINED_CASES = [
    BacktestCase(
        case_id="bt_01",
        title="哈佛蒋雨融演讲争议",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["weibo", "zhihu", "bilibili"],
            peak_heat_score=0.9,
            duration_days=7,
            polarization_occurred=True,
            key_groups_affected=["留学生", "精英群体", "普通网民"],
            description="演讲内容引发留学生群体与普通网民对立，持续多日热搜",
        ),
        risk_dimensions=["道德伦理", "群体冒犯", "时事踩雷"],
    ),
    BacktestCase(
        case_id="bt_02",
        title="全红婵饭圈侵入式监控",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["weibo", "douyin", "bilibili"],
            peak_heat_score=0.85,
            duration_days=5,
            polarization_occurred=True,
            key_groups_affected=["饭圈粉丝", "体育爱好者", "普通网民"],
            description="饭圈文化侵入体育领域引发广泛讨论",
        ),
        risk_dimensions=["群体冒犯", "道德伦理"],
    ),
    BacktestCase(
        case_id="bt_03",
        title="同济大学教师论文造假",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["zhihu", "weibo"],
            peak_heat_score=0.7,
            duration_days=4,
            polarization_occurred=False,
            key_groups_affected=["学术界", "学生群体"],
            description="学术造假事件引发学术界和公众关注",
        ),
        risk_dimensions=["道德伦理", "法律合规"],
    ),
    BacktestCase(
        case_id="bt_04",
        title="王妈背刺打工人",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["weibo", "douyin", "xiaohongshu"],
            peak_heat_score=0.9,
            duration_days=10,
            polarization_occurred=True,
            key_groups_affected=["打工人", "网红粉丝", "品牌方"],
            description="网红与打工人群体对立，引发社会议题讨论",
        ),
        risk_dimensions=["群体冒犯", "道德伦理"],
    ),
    BacktestCase(
        case_id="bt_05",
        title="网红小英卖惨塌房",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["douyin", "weibo", "bilibili"],
            peak_heat_score=0.8,
            duration_days=6,
            polarization_occurred=False,
            key_groups_affected=["粉丝", "普通网民"],
            description="网红虚假卖惨被揭穿，粉丝信任崩塌",
        ),
        risk_dimensions=["道德伦理", "群体冒犯"],
    ),
    BacktestCase(
        case_id="bt_06",
        title="闫学晶直播翻车",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["douyin", "weibo"],
            peak_heat_score=0.5,
            duration_days=2,
            polarization_occurred=False,
            key_groups_affected=["粉丝", "直播观众"],
            description="直播言论不当引发短暂争议",
        ),
        risk_dimensions=["道德伦理"],
    ),
    BacktestCase(
        case_id="bt_07",
        title="优思益假洋牌事件",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["xiaohongshu", "weibo"],
            peak_heat_score=0.7,
            duration_days=5,
            polarization_occurred=False,
            key_groups_affected=["消费者", "品牌关注者"],
            description="品牌虚假宣传被揭发，消费者维权",
        ),
        risk_dimensions=["法律合规", "群体冒犯"],
    ),
    BacktestCase(
        case_id="bt_08",
        title="张雨绮代孕风波",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["weibo", "zhihu", "douyin"],
            peak_heat_score=0.95,
            duration_days=14,
            polarization_occurred=True,
            key_groups_affected=["女性群体", "法律界", "普通网民"],
            description="代孕话题引发社会伦理大讨论，多群体对立",
        ),
        risk_dimensions=["道德伦理", "法律合规"],
    ),
    BacktestCase(
        case_id="bt_09",
        title="AI一键脱衣黑产",
        seed_content="",
        actual_outcome=ActualOutcome(
            overall_direction="上涨",
            platforms_affected=["weibo", "zhihu", "bilibili"],
            peak_heat_score=0.85,
            duration_days=8,
            polarization_occurred=False,
            key_groups_affected=["女性群体", "科技界", "法律界"],
            description="AI技术滥用引发法律和伦理讨论",
        ),
        risk_dimensions=["法律合规", "道德伦理"],
    ),
    BacktestCase(
        case_id="bt_10",
        title="安全文案基准",
        seed_content="今天天气真不错，阳光明媚，适合出门散步。路边的花开得正好，微风拂面，心情愉快。",
        actual_outcome=ActualOutcome(
            overall_direction="持平",
            platforms_affected=[],
            peak_heat_score=0.0,
            duration_days=0,
            polarization_occurred=False,
            key_groups_affected=[],
            description="安全文案无舆论风险",
        ),
        risk_dimensions=[],
    ),
]


class BacktestRunner:
    """回测运行器"""

    def __init__(self):
        self.results: List[BacktestComparison] = []

    async def run_backtest(self, cases: List[BacktestCase] | None = None) -> BacktestReport:
        """运行回测"""
        if cases is None:
            cases = self._load_cases()

        logger.info("BacktestRunner: 开始回测，共 %d 个案例", len(cases))
        self.results = []

        for case in cases:
            comparison = await self._run_single_case(case)
            self.results.append(comparison)

        return self._generate_report()

    def _load_cases(self) -> List[BacktestCase]:
        """加载回测用例（从预定义+文件）"""
        cases = PREDEFINED_CASES.copy()

        # 从文件加载文案内容
        from pathlib import Path
        cases_dir = Path(__file__).parent.parent.parent / "cases" / "paperwork"
        for case in cases:
            if not case.seed_content and case.case_id != "bt_10":
                # 尝试从文件读取
                file_path = cases_dir / f"{case.title}.md"
                if file_path.exists():
                    case.seed_content = file_path.read_text(encoding="utf-8")[:2000]

        return cases

    async def _run_single_case(self, case: BacktestCase) -> BacktestComparison:
        """运行单个回测案例"""
        comparison = BacktestComparison(
            case_id=case.case_id,
            title=case.title,
        )

        if not case.seed_content or len(case.seed_content.strip()) < 10:
            logger.warning("回测案例 %s 无有效文案，跳过", case.title)
            return comparison

        try:
            # 运行V2 quick模式（包含MVP结果）
            db = SessionLocal()
            try:
                task_id = f"bt_{case.case_id}_{uuid.uuid4().hex[:6]}"
                task = Task(id=task_id, text=case.seed_content[:500], status="processing", model="backtest")
                db.add(task)
                db.commit()
            finally:
                db.close()

            result = await run_enhanced_analysis(
                task_id=task_id,
                text=case.seed_content,
                mode="quick",
                enable_signal=True,
                enable_entity_chain=True,
                enable_simulation=False,
            )

            comparison.mvp_score = result.mvp_overall_score
            comparison.v2_score = result.v2_overall_score
            comparison.mvp_dimensions = result.mvp_dimensions
            comparison.v2_dimensions = result.v2_dimensions

            # 计算准确率
            comparison.mvp_accuracy = self._calc_accuracy(result.mvp_dimensions, result.mvp_overall_score, case)
            comparison.v2_accuracy = self._calc_accuracy(result.v2_dimensions, result.v2_overall_score, case)

            # 改善幅度
            comparison.improvement = comparison.v2_accuracy.weighted_accuracy - comparison.mvp_accuracy.weighted_accuracy

        except Exception as e:
            logger.error("回测案例 %s 失败: %s", case.title, e)

        return comparison

    def _calc_accuracy(self, dimensions: dict, score: int, case: BacktestCase) -> DimensionAccuracy:
        """计算预测准确率"""
        accuracy = DimensionAccuracy()

        # 1. 方向准确率（分数>50 = 上涨，<=25 = 持平，否则看趋势）
        predicted_direction = "上涨" if score > 50 else ("持平" if score <= 25 else "上涨")
        actual_direction = case.actual_outcome.overall_direction
        accuracy.direction_accuracy = 1.0 if predicted_direction == actual_direction else 0.0

        # 2. 维度准确率（预测的高风险维度与实际是否一致）
        if case.risk_dimensions:
            predicted_dims = set(k for k, v in dimensions.items() if v > 40)
            actual_dims = set(case.risk_dimensions)
            if actual_dims:
                overlap = predicted_dims & actual_dims
                accuracy.dimension_accuracy = len(overlap) / len(actual_dims)

        # 3. 平台准确率（分数>30的平台与实际波及平台对比）
        # 简化：基于分数推断波及平台
        if case.actual_outcome.platforms_affected:
            # 高分意味着更多平台波及
            if score > 60 and len(case.actual_outcome.platforms_affected) >= 2:
                accuracy.platform_accuracy = 0.8
            elif score > 30 and len(case.actual_outcome.platforms_affected) >= 1:
                accuracy.platform_accuracy = 0.6
            else:
                accuracy.platform_accuracy = 0.3

        # 4. 群体准确率
        if case.actual_outcome.key_groups_affected:
            # 高"群体冒犯"维度的分数
            group_dim_score = dimensions.get("群体冒犯", 0)
            if group_dim_score > 40 and len(case.actual_outcome.key_groups_affected) >= 2:
                accuracy.group_accuracy = 0.7
            elif group_dim_score > 20:
                accuracy.group_accuracy = 0.4

        # 5. 极化准确率
        polarization_dim = dimensions.get("群体冒犯", 0) + dimensions.get("性别议题", 0)
        predicted_polarization = polarization_dim > 60
        accuracy.polarization_accuracy = 1.0 if predicted_polarization == case.actual_outcome.polarization_occurred else 0.0

        # 加权总准确率
        accuracy.weighted_accuracy = (
            accuracy.direction_accuracy * 0.4 +
            accuracy.platform_accuracy * 0.2 +
            accuracy.dimension_accuracy * 0.2 +
            accuracy.group_accuracy * 0.1 +
            accuracy.polarization_accuracy * 0.1
        )

        return accuracy

    def _generate_report(self) -> BacktestReport:
        """生成回测报告"""
        report = BacktestReport(total_cases=len(self.results))
        report.comparisons = self.results

        if self.results:
            report.mvp_avg_accuracy = sum(c.mvp_accuracy.weighted_accuracy for c in self.results) / len(self.results)
            report.v2_avg_accuracy = sum(c.v2_accuracy.weighted_accuracy for c in self.results) / len(self.results)
            report.overall_improvement = report.v2_avg_accuracy - report.mvp_avg_accuracy

        # Go/No-Go判定
        if report.v2_avg_accuracy > 0.55 and report.overall_improvement > 0.1:
            report.go_no_go = "Go"
        elif report.v2_avg_accuracy > 0.45:
            report.go_no_go = "Conditional Go"
        else:
            report.go_no_go = "No-Go"

        return report

    def persist_report(self, report: BacktestReport):
        """持久化回测报告"""
        db = SessionLocal()
        try:
            record = BacktestRecord(
                case_id=report.report_id,
                title=f"回测报告_{report.total_cases}案例",
                seed_content="",
                actual_outcome=json.dumps({"total": report.total_cases}, ensure_ascii=False),
                mvp_prediction=json.dumps({"avg_accuracy": report.mvp_avg_accuracy}, ensure_ascii=False),
                v2_prediction=json.dumps({"avg_accuracy": report.v2_avg_accuracy}, ensure_ascii=False),
                accuracy_scores=json.dumps({
                    "mvp_avg": report.mvp_avg_accuracy,
                    "v2_avg": report.v2_avg_accuracy,
                    "improvement": report.overall_improvement,
                    "go_no_go": report.go_no_go,
                }, ensure_ascii=False),
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.error("持久化回测报告失败: %s", e)
            db.rollback()
        finally:
            db.close()


# ==================== V2.5 多轮一致性检查 ====================

@dataclass
class ConsistencyRunResult:
    """单轮回测运行结果"""
    run_index: int = 0
    mvp_score: int = 0
    v2_score: int = 0
    mvp_dimensions: dict = field(default_factory=dict)
    v2_dimensions: dict = field(default_factory=dict)
    v2_accuracy: float = 0.0
    error: str = ""


@dataclass
class MultiRunConsistency:
    """多轮一致性检查结果"""
    case_id: str = ""
    title: str = ""
    run_count: int = 3
    runs: List[ConsistencyRunResult] = field(default_factory=list)
    direction_consistency: float = 0.0
    score_consistency: float = 0.0
    dimension_consistency: float = 0.0
    overall_consistency: float = 0.0
    confidence_label: str = ""
    confidence_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "run_count": self.run_count,
            "direction_consistency": round(self.direction_consistency, 3),
            "score_consistency": round(self.score_consistency, 3),
            "dimension_consistency": round(self.dimension_consistency, 3),
            "overall_consistency": round(self.overall_consistency, 3),
            "confidence_label": self.confidence_label,
            "confidence_score": round(self.confidence_score, 3),
        }


class BacktestConsistencyChecker:
    """回测多轮一致性检查器

    对同一案例运行3次仿真，验证结果稳定性。
    """

    def __init__(self, run_count: int = 3):
        self.run_count = run_count

    async def check_case(self, case: BacktestCase) -> MultiRunConsistency:
        """对单个案例运行多轮回测一致性检查"""
        result = MultiRunConsistency(
            case_id=case.case_id,
            title=case.title,
            run_count=self.run_count,
        )

        for i in range(self.run_count):
            logger.info(
                "BacktestConsistencyChecker: 案例 %s 第 %d/%d 轮",
                case.title, i + 1, self.run_count,
            )
            try:
                run_result = await self._run_single(case, i)
                result.runs.append(run_result)
            except Exception as e:
                logger.error("案例 %s 第 %d 轮失败: %s", case.title, i + 1, e)
                result.runs.append(ConsistencyRunResult(run_index=i, error=str(e)))

        self._compute_consistency(result)
        return result

    async def _run_single(self, case: BacktestCase, run_index: int) -> ConsistencyRunResult:
        """运行单轮回测"""
        run_result = ConsistencyRunResult(run_index=run_index)

        if not case.seed_content or len(case.seed_content.strip()) < 10:
            run_result.error = "无有效文案"
            return run_result

        db = SessionLocal()
        try:
            task_id = f"btc_{case.case_id}_r{run_index}_{uuid.uuid4().hex[:6]}"
            task = Task(id=task_id, text=case.seed_content[:500], status="processing", model="backtest-consistency")
            db.add(task)
            db.commit()
        finally:
            db.close()

        analysis = await run_enhanced_analysis(
            task_id=task_id,
            text=case.seed_content,
            mode="quick",
            enable_signal=True,
            enable_entity_chain=True,
            enable_simulation=False,
        )

        runner = BacktestRunner()
        run_result.mvp_score = analysis.mvp_overall_score
        run_result.v2_score = analysis.v2_overall_score
        run_result.mvp_dimensions = analysis.mvp_dimensions
        run_result.v2_dimensions = analysis.v2_dimensions
        run_result.v2_accuracy = runner._calc_accuracy(
            analysis.v2_dimensions, analysis.v2_overall_score, case
        ).weighted_accuracy

        return run_result

    def _compute_consistency(self, result: MultiRunConsistency):
        """计算多轮一致性指标"""
        valid_runs = [r for r in result.runs if not r.error]
        if len(valid_runs) < 2:
            result.confidence_label = "数据不足"
            return

        # 方向一致性
        directions = []
        for r in valid_runs:
            if r.v2_score > 50:
                directions.append("不建议发")
            elif r.v2_score > 25:
                directions.append("建议修改")
            else:
                directions.append("可发")

        from collections import Counter
        dir_counts = Counter(directions)
        most_common = dir_counts.most_common(1)[0]
        result.direction_consistency = most_common[1] / len(directions)

        # 分数一致性（变异系数的逆）
        scores = [r.v2_score for r in valid_runs]
        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score > 0:
                std_score = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5
                cv = std_score / avg_score
                result.score_consistency = max(0.0, 1.0 - cv)

        # 维度一致性
        dim_sets = [set(r.v2_dimensions.keys()) for r in valid_runs if r.v2_dimensions]
        if len(dim_sets) >= 2:
            common = dim_sets[0]
            for ds in dim_sets[1:]:
                common = common & ds
            all_dims = dim_sets[0]
            for ds in dim_sets[1:]:
                all_dims = all_dims | ds
            result.dimension_consistency = len(common) / len(all_dims) if all_dims else 0.0

        # 综合一致性
        result.overall_consistency = (
            result.direction_consistency * 0.4 +
            result.score_consistency * 0.3 +
            result.dimension_consistency * 0.3
        )

        # 可信度标注
        result.confidence_score = result.overall_consistency
        if result.overall_consistency >= 0.8:
            result.confidence_label = "高可信"
        elif result.overall_consistency >= 0.6:
            result.confidence_label = "中可信"
        elif result.overall_consistency >= 0.4:
            result.confidence_label = "低可信"
        else:
            result.confidence_label = "不可信"


# ==================== V2.5 可信度标注系统 ====================

class CredibilityLevel(str, Enum):
    """可信度等级"""
    HIGH = "high"            # 高可信（一致性>80%）
    MEDIUM = "medium"        # 中可信（60-80%）
    LOW = "low"              # 低可信（40-60%）
    UNRELIABLE = "unreliable"  # 不可信（<40%）


CREDIBILITY_LABELS = {
    CredibilityLevel.HIGH: "高可信",
    CredibilityLevel.MEDIUM: "中可信",
    CredibilityLevel.LOW: "低可信",
    CredibilityLevel.UNRELIABLE: "不可信",
}


@dataclass
class CredibilityAnnotation:
    """可信度标注"""
    level: CredibilityLevel = CredibilityLevel.MEDIUM
    level_label: str = ""
    consistency_score: float = 0.0
    direction_stability: float = 0.0
    score_stability: float = 0.0
    dimension_stability: float = 0.0
    sample_size: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "level_label": self.level_label,
            "consistency_score": round(self.consistency_score, 3),
            "direction_stability": round(self.direction_stability, 3),
            "score_stability": round(self.score_stability, 3),
            "dimension_stability": round(self.dimension_stability, 3),
            "sample_size": self.sample_size,
            "notes": self.notes,
        }


def annotate_credibility(consistency: MultiRunConsistency) -> CredibilityAnnotation:
    """根据多轮一致性结果标注可信度"""
    score = consistency.overall_consistency

    if score >= 0.8:
        level = CredibilityLevel.HIGH
    elif score >= 0.6:
        level = CredibilityLevel.MEDIUM
    elif score >= 0.4:
        level = CredibilityLevel.LOW
    else:
        level = CredibilityLevel.UNRELIABLE

    notes = []
    if consistency.direction_consistency < 0.6:
        notes.append("方向判断不稳定，多次运行结果不一致")
    if consistency.score_consistency < 0.5:
        notes.append("评分波动较大，绝对分数参考价值有限")
    if consistency.dimension_consistency < 0.5:
        notes.append("风险维度检测不稳定，建议关注共同检测到的维度")

    if level == CredibilityLevel.HIGH:
        notes.append("结果高度可信，可作为决策参考")
    elif level == CredibilityLevel.MEDIUM:
        notes.append("结果基本可信，建议结合人工判断")

    return CredibilityAnnotation(
        level=level,
        level_label=CREDIBILITY_LABELS.get(level, ""),
        consistency_score=score,
        direction_stability=consistency.direction_consistency,
        score_stability=consistency.score_consistency,
        dimension_stability=consistency.dimension_consistency,
        sample_size=consistency.run_count,
        notes=notes,
    )


# ==================== V2.5 V2 vs MVP 对比报告 ====================

@dataclass
class ComparisonDetail:
    """V2 vs MVP 单维度对比"""
    dimension: str = ""
    mvp_score: int = 0
    v2_score: int = 0
    improvement: float = 0.0
    accuracy_gain: float = 0.0


@dataclass
class V2VsMVPReport:
    """V2 vs MVP 对比报告"""
    report_id: str = field(default_factory=lambda: f"cmp_{uuid.uuid4().hex[:8]}")
    total_cases: int = 0
    mvp_avg_accuracy: float = 0.0
    v2_avg_accuracy: float = 0.0
    overall_improvement: float = 0.0
    dimension_comparisons: List[ComparisonDetail] = field(default_factory=list)
    consistency_results: List[MultiRunConsistency] = field(default_factory=list)
    credibility_annotations: List[CredibilityAnnotation] = field(default_factory=list)
    go_no_go: str = ""
    go_no_go_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_cases": self.total_cases,
            "mvp_avg_accuracy": round(self.mvp_avg_accuracy, 3),
            "v2_avg_accuracy": round(self.v2_avg_accuracy, 3),
            "overall_improvement": round(self.overall_improvement, 3),
            "go_no_go": self.go_no_go,
            "go_no_go_reason": self.go_no_go_reason,
            "dimension_comparisons": [
                {
                    "dimension": d.dimension,
                    "mvp_score": d.mvp_score,
                    "v2_score": d.v2_score,
                    "improvement": round(d.improvement, 3),
                    "accuracy_gain": round(d.accuracy_gain, 3),
                }
                for d in self.dimension_comparisons
            ],
            "consistency_summary": [c.to_dict() for c in self.consistency_results],
            "credibility_summary": [c.to_dict() for c in self.credibility_annotations],
            "created_at": self.created_at,
        }


class V2VsMVPComparator:
    """V2 vs MVP 对比报告生成器"""

    def __init__(self, consistency_run_count: int = 3):
        self._runner = BacktestRunner()
        self._consistency_checker = BacktestConsistencyChecker(run_count=consistency_run_count)

    async def generate_report(
        self,
        cases: Optional[List[BacktestCase]] = None,
        enable_consistency: bool = True,
    ) -> V2VsMVPReport:
        """生成 V2 vs MVP 对比报告"""
        if cases is None:
            cases = self._runner._load_cases()

        report = V2VsMVPReport(total_cases=len(cases))

        # 运行基础回测
        backtest_report = await self._runner.run_backtest(cases)
        report.mvp_avg_accuracy = backtest_report.mvp_avg_accuracy
        report.v2_avg_accuracy = backtest_report.v2_avg_accuracy
        report.overall_improvement = backtest_report.overall_improvement

        # 维度对比
        report.dimension_comparisons = self._compare_dimensions(backtest_report)

        # 多轮一致性检查
        if enable_consistency:
            for case in cases:
                if case.seed_content and len(case.seed_content.strip()) >= 10:
                    consistency = await self._consistency_checker.check_case(case)
                    report.consistency_results.append(consistency)

                    credibility = annotate_credibility(consistency)
                    report.credibility_annotations.append(credibility)

        # Go/No-Go 判定
        report.go_no_go, report.go_no_go_reason = self._judge_go_no_go(report)

        return report

    def _compare_dimensions(self, backtest_report: BacktestReport) -> List[ComparisonDetail]:
        """对比各维度的 MVP vs V2 表现"""
        dim_stats: Dict[str, Dict[str, List[float]]] = {}

        for comp in backtest_report.comparisons:
            for dim, score in comp.mvp_dimensions.items():
                dim_stats.setdefault(dim, {"mvp": [], "v2": [], "mvp_acc": [], "v2_acc": []})
                dim_stats[dim]["mvp"].append(score)

            for dim, score in comp.v2_dimensions.items():
                dim_stats.setdefault(dim, {"mvp": [], "v2": [], "mvp_acc": [], "v2_acc": []})
                dim_stats[dim]["v2"].append(score)

            # 准确率增益
            for dim in dim_stats:
                mvp_acc = comp.mvp_accuracy.dimension_accuracy
                v2_acc = comp.v2_accuracy.dimension_accuracy
                dim_stats[dim]["mvp_acc"].append(mvp_acc)
                dim_stats[dim]["v2_acc"].append(v2_acc)

        comparisons = []
        for dim, stats in dim_stats.items():
            mvp_avg = sum(stats["mvp"]) / len(stats["mvp"]) if stats["mvp"] else 0
            v2_avg = sum(stats["v2"]) / len(stats["v2"]) if stats["v2"] else 0
            mvp_acc_avg = sum(stats["mvp_acc"]) / len(stats["mvp_acc"]) if stats["mvp_acc"] else 0
            v2_acc_avg = sum(stats["v2_acc"]) / len(stats["v2_acc"]) if stats["v2_acc"] else 0

            comparisons.append(ComparisonDetail(
                dimension=dim,
                mvp_score=int(mvp_avg),
                v2_score=int(v2_avg),
                improvement=v2_avg - mvp_avg,
                accuracy_gain=v2_acc_avg - mvp_acc_avg,
            ))

        return comparisons

    def _judge_go_no_go(self, report: V2VsMVPReport) -> Tuple[str, str]:
        """Go/No-Go 判定逻辑（增强版）

        判定标准：
        - Go: V2准确率>55% 且 改善>10% 且 一致性>60%
        - Conditional Go: V2准确率>45% 或 改善>5%
        - No-Go: V2准确率<45% 且 改善<5%
        """
        v2_acc = report.v2_avg_accuracy
        improvement = report.overall_improvement

        # 计算平均一致性
        avg_consistency = 0.0
        if report.consistency_results:
            avg_consistency = sum(c.overall_consistency for c in report.consistency_results) / len(report.consistency_results)

        # 计算可信度分布
        high_cred_count = sum(1 for c in report.credibility_annotations if c.level == CredibilityLevel.HIGH)
        medium_cred_count = sum(1 for c in report.credibility_annotations if c.level == CredibilityLevel.MEDIUM)

        # Go 判定
        if v2_acc > 0.55 and improvement > 0.1 and avg_consistency > 0.6:
            reason = (
                f"V2准确率{v2_acc:.1%}，改善{improvement:.1%}，"
                f"一致性{avg_consistency:.1%}，高可信占比{high_cred_count}/{len(report.credibility_annotations)}"
            )
            return "Go", reason

        # Conditional Go 判定
        if v2_acc > 0.45 or improvement > 0.05:
            reason = (
                f"V2准确率{v2_acc:.1%}，改善{improvement:.1%}，"
                f"一致性{avg_consistency:.1%}，需关注低可信案例"
            )
            return "Conditional Go", reason

        # No-Go 判定
        reason = (
            f"V2准确率{v2_acc:.1%}（<45%），改善{improvement:.1%}（<5%），"
            f"一致性{avg_consistency:.1%}，不建议上线"
        )
        return "No-Go", reason
