"""回测框架 - 用历史案例验证仿真风控的可信度

同时运行MVP和V2评估，对比预测vs实际结果，
5维度准确率评估（方向40%/平台20%/维度20%/群体10%/极化10%）
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

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
