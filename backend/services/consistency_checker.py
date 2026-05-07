"""多轮一致性检查 - 同一事件仿真3次，评估结果稳定性

评估方向一致性、平台预测一致性、风险维度一致性，
计算综合一致性分数。
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from backend.services.enhanced_analyzer import run_enhanced_analysis

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyRun:
    """单次仿真运行结果"""
    run_index: int = 0
    overall_score: int = 0
    suggestion: str = ""
    dimensions: dict = field(default_factory=dict)
    signal_matches_count: int = 0
    entity_chains_count: int = 0
    confidence: float = 0.0
    analysis_time: float = 0.0
    error: str = ""


@dataclass
class ConsistencyResult:
    """一致性检查结果"""
    content_hash: str = ""
    run_count: int = 0
    runs: List[ConsistencyRun] = field(default_factory=list)
    direction_consistency: float = 0.0       # 方向一致性
    platform_consistency: float = 0.0        # 平台预测一致性
    dimension_consistency: float = 0.0       # 风险维度一致性
    overall_consistency: float = 0.0         # 综合一致性分数
    score_range: tuple = (0, 0)              # 分数范围(min, max)
    score_std: float = 0.0                   # 分数标准差
    divergent_dimensions: List[str] = field(default_factory=list)  # 分歧维度
    summary: str = ""


class ConsistencyChecker:
    """一致性检查器"""

    def __init__(self, run_count: int = 3):
        self.run_count = run_count

    async def check(self, text: str, mode: str = "quick") -> ConsistencyResult:
        """对同一文案运行多次评估，检查一致性

        Args:
            text: 待评估文案
            mode: 评估模式 quick/deep
            run_count: 运行次数(默认3次)

        Returns:
            ConsistencyResult: 一致性检查结果
        """
        result = ConsistencyResult(
            content_hash=str(hash(text[:200])),
            run_count=run_count,
        )

        # 运行多次
        for i in range(run_count):
            logger.info("ConsistencyChecker: 运行第 %d/%d 次", i + 1, run_count)
            try:
                from backend.database import SessionLocal
                from backend.models import Task

                task_id = f"cons_{uuid.uuid4().hex[:8]}"
                db = SessionLocal()
                try:
                    task = Task(id=task_id, text=text[:500], status="processing", model=f"consistency-{mode}")
                    db.add(task)
                    db.commit()
                finally:
                    db.close()

                start = time.time()
                analysis = await run_enhanced_analysis(
                    task_id=task_id,
                    text=text,
                    mode=mode,
                    enable_signal=True,
                    enable_entity_chain=True,
                    enable_simulation=False,
                )
                elapsed = time.time() - start

                result.runs.append(ConsistencyRun(
                    run_index=i + 1,
                    overall_score=analysis.v2_overall_score or analysis.mvp_overall_score,
                    suggestion=analysis.v2_suggestion or analysis.mvp_suggestion,
                    dimensions=analysis.v2_dimensions or analysis.mvp_dimensions,
                    signal_matches_count=len(analysis.signal_match_result.matches) if analysis.signal_match_result else 0,
                    entity_chains_count=len(analysis.entity_risk_chain_result.chains) if analysis.entity_risk_chain_result else 0,
                    confidence=analysis.confidence,
                    analysis_time=elapsed,
                    error=analysis.error,
                ))

            except Exception as e:
                logger.error("ConsistencyChecker: 第 %d 次运行失败: %s", i + 1, e)
                result.runs.append(ConsistencyRun(
                    run_index=i + 1, error=str(e),
                ))

        # 计算一致性指标
        self._compute_consistency(result)
        return result

    def _compute_consistency(self, result: ConsistencyResult):
        """计算一致性指标"""
        valid_runs = [r for r in result.runs if not r.error]
        if len(valid_runs) < 2:
            result.summary = "有效运行次数不足，无法计算一致性"
            return

        # 方向一致性
        directions = []
        for r in valid_runs:
            if r.overall_score > 50:
                directions.append("不建议发")
            elif r.overall_score > 25:
                directions.append("建议修改")
            else:
                directions.append("可发")

        from collections import Counter
        dir_counts = Counter(directions)
        most_common_dir = dir_counts.most_common(1)[0]
        result.direction_consistency = most_common_dir[1] / len(directions)

        # 平台预测一致性（基于风险维度的相似度）
        dim_sets = [set(r.dimensions.keys()) for r in valid_runs if r.dimensions]
        if dim_sets:
            # 计算交集/并集比
            common_dims = dim_sets[0]
            for ds in dim_sets[1:]:
                common_dims = common_dims & ds
            all_dims = dim_sets[0]
            for ds in dim_sets[1:]:
                all_dims = all_dims | ds
            result.platform_consistency = len(common_dims) / len(all_dims) if all_dims else 0.0

        # 风险维度一致性（同一维度的分数差异）
        all_dim_names = set()
        for r in valid_runs:
            all_dim_names.update(r.dimensions.keys())

        dim_variances = {}
        for dim in all_dim_names:
            scores = [r.dimensions.get(dim, 0) for r in valid_runs]
            if len(scores) >= 2:
                avg = sum(scores) / len(scores)
                variance = sum((s - avg) ** 2 for s in scores) / len(scores)
                dim_variances[dim] = variance

        # 低方差维度占比越高，一致性越高
        if dim_variances:
            low_var_count = sum(1 for v in dim_variances.values() if v < 200)  # 方差<200认为一致
            result.dimension_consistency = low_var_count / len(dim_variances)

            # 找出分歧维度
            result.divergent_dimensions = [dim for dim, var in dim_variances.items() if var >= 200]

        # 分数范围和标准差
        scores = [r.overall_score for r in valid_runs]
        result.score_range = (min(scores), max(scores))
        if len(scores) >= 2:
            avg_score = sum(scores) / len(scores)
            result.score_std = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5

        # 综合一致性
        result.overall_consistency = (
            result.direction_consistency * 0.4 +
            result.platform_consistency * 0.2 +
            result.dimension_consistency * 0.4
        )

        # 摘要
        result.summary = (
            f"方向一致性: {result.direction_consistency:.0%}, "
            f"维度一致性: {result.dimension_consistency:.0%}, "
            f"综合: {result.overall_consistency:.0%}, "
            f"分数范围: {result.score_range[0]}-{result.score_range[1]}, "
            f"标准差: {result.score_std:.1f}"
        )
        if result.divergent_dimensions:
            result.summary += f", 分歧维度: {', '.join(result.divergent_dimensions)}"
