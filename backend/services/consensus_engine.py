"""多轮仿真共识机制 - 同一事件运行3-5次仿真取共识

方向共识计算+置信度+不确定性标注+分歧来源分析
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List

from backend.services.enhanced_analyzer import run_enhanced_analysis

logger = logging.getLogger(__name__)


@dataclass
class ConsensusRun:
    """单次仿真结果"""
    run_index: int = 0
    overall_score: int = 0
    suggestion: str = ""
    dimensions: Dict[str, int] = field(default_factory=dict)
    confidence: float = 0.0
    simulation_data: Dict = field(default_factory=dict)
    error: str = ""


@dataclass
class ConsensusResult:
    """共识结果"""
    consensus_id: str = field(default_factory=lambda: f"cons_{uuid.uuid4().hex[:8]}")
    run_count: int = 0
    runs: List[ConsensusRun] = field(default_factory=list)

    # 方向共识
    direction_consensus: str = ""        # unanimous / majority / split
    direction_confidence: float = 0.0
    majority_direction: str = ""         # 可发/建议修改/不建议发

    # 维度共识
    dimension_consensus: Dict[str, float] = field(default_factory=dict)  # {维度: 一致性0-1}

    # 总体置信度
    overall_confidence: float = 0.0

    # 不确定性
    uncertainty_sources: List[str] = field(default_factory=list)
    divergent_dimensions: List[str] = field(default_factory=list)

    # 综合结果
    consensus_score: int = 0
    consensus_suggestion: str = ""
    summary: str = ""


class ConsensusEngine:
    """多轮仿真共识引擎"""

    def __init__(self, run_count: int = 3):
        self.run_count = run_count

    async def run_consensus(
        self, text: str, mode: str = "deep"
    ) -> ConsensusResult:
        """运行多轮仿真共识

        Args:
            text: 待评估文案
            mode: 评估模式

        Returns:
            ConsensusResult: 共识结果
        """
        result = ConsensusResult(run_count=self.run_count)

        # 运行多次
        for i in range(self.run_count):
            logger.info("ConsensusEngine: 第 %d/%d 轮仿真", i + 1, self.run_count)
            try:
                from backend.database import SessionLocal
                from backend.models import Task

                task_id = f"consensus_{uuid.uuid4().hex[:8]}"
                db = SessionLocal()
                try:
                    task = Task(id=task_id, text=text[:500], status="processing", model=f"consensus-{mode}")
                    db.add(task)
                    db.commit()
                finally:
                    db.close()

                analysis = await run_enhanced_analysis(
                    task_id=task_id,
                    text=text,
                    mode=mode,
                    enable_signal=True,
                    enable_entity_chain=True,
                    enable_simulation=(mode == "deep"),
                )

                result.runs.append(ConsensusRun(
                    run_index=i + 1,
                    overall_score=analysis.v2_overall_score or analysis.mvp_overall_score,
                    suggestion=analysis.v2_suggestion or analysis.mvp_suggestion,
                    dimensions=analysis.v2_dimensions or analysis.mvp_dimensions,
                    confidence=analysis.confidence,
                    simulation_data=analysis.simulation_summary,
                ))

            except Exception as e:
                logger.error("ConsensusEngine: 第 %d 轮失败: %s", i + 1, e)
                result.runs.append(ConsensusRun(run_index=i + 1, error=str(e)))

        # 计算共识
        self._compute_consensus(result)
        return result

    def _compute_consensus(self, result: ConsensusResult):
        """计算共识指标"""
        valid_runs = [r for r in result.runs if not r.error]
        if not valid_runs:
            result.summary = "所有仿真均失败"
            return

        # 方向共识
        from collections import Counter
        directions = [r.suggestion for r in valid_runs]
        dir_counts = Counter(directions)
        most_common = dir_counts.most_common(1)[0]
        result.majority_direction = most_common[0]

        if most_common[1] == len(directions):
            result.direction_consensus = "unanimous"
            result.direction_confidence = 1.0
        elif most_common[1] >= len(directions) * 0.6:
            result.direction_consensus = "majority"
            result.direction_confidence = most_common[1] / len(directions)
        else:
            result.direction_consensus = "split"
            result.direction_confidence = most_common[1] / len(directions)

        # 维度共识
        all_dims = set()
        for r in valid_runs:
            all_dims.update(r.dimensions.keys())

        for dim in all_dims:
            scores = [r.dimensions.get(dim, 0) for r in valid_runs]
            if len(scores) >= 2:
                avg = sum(scores) / len(scores)
                variance = sum((s - avg) ** 2 for s in scores) / len(scores)
                consistency = max(0, 1 - variance / 2500)  # 方差2500以下视为一致
                result.dimension_consensus[dim] = round(consistency, 2)
                if consistency < 0.5:
                    result.divergent_dimensions.append(dim)

        # 综合置信度
        result.overall_confidence = (
            result.direction_confidence * 0.5 +
            (sum(result.dimension_consensus.values()) / len(result.dimension_consensus) if result.dimension_consensus else 0) * 0.3 +
            (sum(r.confidence for r in valid_runs) / len(valid_runs)) * 0.2
        )

        # 共识分数（取中位数）
        scores = sorted([r.overall_score for r in valid_runs])
        mid = len(scores) // 2
        result.consensus_score = scores[mid] if len(scores) % 2 == 1 else (scores[mid - 1] + scores[mid]) // 2
        result.consensus_suggestion = result.majority_direction

        # 不确定性来源
        if result.direction_consensus != "unanimous":
            result.uncertainty_sources.append("仿真方向存在分歧")
        if result.divergent_dimensions:
            result.uncertainty_sources.append(f"维度分歧: {', '.join(result.divergent_dimensions)}")
        avg_conf = sum(r.confidence for r in valid_runs) / len(valid_runs)
        if avg_conf < 0.6:
            result.uncertainty_sources.append("单次仿真可信度较低")

        # 摘要
        result.summary = (
            f"共识方向: {result.direction_consensus}({result.direction_confidence:.0%}), "
            f"共识分数: {result.consensus_score}, "
            f"综合置信度: {result.overall_confidence:.0%}, "
            f"基于{len(valid_runs)}次仿真"
        )
        if result.uncertainty_sources:
            result.summary += f", 不确定性: {'; '.join(result.uncertainty_sources)}"
