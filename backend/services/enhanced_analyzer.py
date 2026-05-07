"""增强风控编排器 - V2.R1 4阶段Pipeline

Phase 1: 文本分析（复用MVP）
Phase 2: 信号+图谱增强（新增）
Phase 3: 仿真增强（新增，用户可选）
Phase 4: 综合报告
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
from backend.models import Task, V2AnalysisResult
from backend.services.text_splitter import split_text
from backend.services.agent_simulator import simulate_all_platforms_with_agents
from backend.services.risk_assessor import assess_risks
from backend.services.rewriter import rewrite_sentence
from backend.services.transcript_detector import detect_transcript_quality, is_noise_sentence
from backend.services.analyzer import calculate_overall_score, get_suggestion, _compute_sentiment_ratios
from backend.services.signal_matcher import SignalMatcher, SignalMatchResult
from backend.services.entity_risk_chain import EntityRiskChain, EntityRiskChainResult
from backend.services.dynamic_weights import DynamicWeights, DynamicWeightsResult
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class EnhancedAnalysisResult:
    """增强风控分析结果"""
    task_id: str = ""
    mode: str = "quick"                    # quick / deep

    # Phase 1: MVP结果
    mvp_overall_score: int = 0
    mvp_suggestion: str = ""
    mvp_dimensions: dict = field(default_factory=dict)
    mvp_risk_sentences: list = field(default_factory=list)
    mvp_platform_reactions: list = field(default_factory=list)
    mvp_rewrites: list = field(default_factory=list)

    # Phase 2: 信号+图谱增强
    signal_match_result: Optional[SignalMatchResult] = None
    entity_risk_chain_result: Optional[EntityRiskChainResult] = None
    dynamic_weights_result: Optional[DynamicWeightsResult] = None

    # Phase 3: 仿真增强（deep模式）
    simulation_id: str = ""
    simulation_summary: dict = field(default_factory=dict)

    # Phase 4: 综合报告
    v2_overall_score: int = 0
    v2_suggestion: str = ""
    v2_dimensions: dict = field(default_factory=dict)
    confidence: float = 0.0
    confidence_sources: dict = field(default_factory=dict)
    risk_boosts: dict = field(default_factory=dict)

    # 元数据
    analysis_time_seconds: float = 0.0
    error: str = ""


async def run_enhanced_analysis(
    task_id: str,
    text: str,
    mode: str = "quick",
    enable_signal: bool = True,
    enable_entity_chain: bool = True,
    enable_simulation: bool = False,
) -> EnhancedAnalysisResult:
    """编排增强风控分析4阶段Pipeline

    Args:
        task_id: 任务ID
        text: 用户输入的文案
        mode: quick(快速评估，仅Phase1+2) / deep(深度评估，含Phase3仿真)
        enable_signal: 是否启用信号关联
        enable_entity_chain: 是否启用实体风险链
        enable_simulation: 是否启用仿真增强（deep模式自动启用）

    Returns:
        EnhancedAnalysisResult: 增强分析结果
    """
    start_time = time.time()
    result = EnhancedAnalysisResult(task_id=task_id, mode=mode)

    # deep模式自动启用仿真
    if mode == "deep":
        enable_simulation = True

    try:
        # ===== Phase 1: 文本分析（复用MVP）=====
        logger.info("增强分析 %s: Phase 1 文本分析开始", task_id)
        await _run_phase1(text, result)

        # ===== Phase 2: 信号+图谱增强 =====
        logger.info("增强分析 %s: Phase 2 信号+图谱增强开始", task_id)
        await _run_phase2(text, result, enable_signal, enable_entity_chain)

        # 用动态权重重新计算V2分数
        if result.dynamic_weights_result and result.dynamic_weights_result.adjustments:
            _recalculate_with_dynamic_weights(result)

        # ===== Phase 3: 仿真增强（可选）=====
        if enable_simulation:
            logger.info("增强分析 %s: Phase 3 仿真增强开始", task_id)
            await _run_phase3(text, result)

        # ===== Phase 4: 综合报告 =====
        _compile_final_report(result)

        result.analysis_time_seconds = round(time.time() - start_time, 2)
        logger.info(
            "增强分析 %s: 完成，MVP分数=%d，V2分数=%d，模式=%s，耗时=%.1fs",
            task_id, result.mvp_overall_score, result.v2_overall_score, mode, result.analysis_time_seconds,
        )

    except Exception as e:
        logger.error("增强分析 %s: 失败 - %s", task_id, e)
        result.error = str(e)
        result.analysis_time_seconds = round(time.time() - start_time, 2)

    # 持久化结果
    _persist_result(result)

    return result


async def _run_phase1(text: str, result: EnhancedAnalysisResult):
    """Phase 1: 文本分析（复用MVP流水线）"""
    sentences = split_text(text)

    transcript_quality = await detect_transcript_quality(text, sentences)

    platform_results, risk_results = await asyncio.gather(
        simulate_all_platforms_with_agents(text),
        assess_risks(text, transcript_quality=transcript_quality),
    )

    risk_sentences = risk_results.get("risk_sentences", [])
    rewrite_tasks = [
        rewrite_sentence(
            rs.get("sentence", ""),
            rs.get("dimension", ""),
            rs.get("severity", "medium"),
            is_transcript_noise=is_noise_sentence(rs.get("sentence", ""), transcript_quality),
        )
        for rs in risk_sentences
        if rs.get("severity") in ("high", "medium")
    ]
    rewrites = await asyncio.gather(*rewrite_tasks, return_exceptions=True)
    rewrites = [r for r in rewrites if not isinstance(r, Exception)]

    dimensions = risk_results.get("dimensions", [])
    overall_score, dimension_weights, cross_effects = calculate_overall_score(dimensions)

    result.mvp_overall_score = overall_score
    result.mvp_suggestion = get_suggestion(overall_score)
    result.mvp_dimensions = {d.get("name", ""): d.get("score", 0) for d in dimensions}
    result.mvp_risk_sentences = risk_sentences
    result.mvp_platform_reactions = platform_results
    result.mvp_rewrites = rewrites


async def _run_phase2(
    text: str,
    result: EnhancedAnalysisResult,
    enable_signal: bool,
    enable_entity_chain: bool,
):
    """Phase 2: 信号+图谱增强"""
    # 信号关联
    if enable_signal:
        try:
            matcher = SignalMatcher()
            result.signal_match_result = await matcher.match(text)
        except Exception as e:
            logger.warning("信号关联失败: %s", e)

    # 实体风险链
    if enable_entity_chain:
        try:
            # 尝试使用全局graph_store（如果可用）
            graph_store = _get_graph_store()
            chain_analyzer = EntityRiskChain(graph_store=graph_store)
            result.entity_risk_chain_result = await chain_analyzer.trace(text)
        except Exception as e:
            logger.warning("实体风险链分析失败: %s", e)

    # 动态权重调整
    try:
        dw = DynamicWeights()
        signal_boosts = result.signal_match_result.risk_dimension_boosts if result.signal_match_result else {}
        entity_boosts = result.entity_risk_chain_result.risk_dimension_boosts if result.entity_risk_chain_result else {}
        result.dynamic_weights_result = dw.adjust(
            signal_dimension_boosts=signal_boosts,
            entity_dimension_boosts=entity_boosts,
        )
    except Exception as e:
        logger.warning("动态权重调整失败: %s", e)


async def _run_phase3(text: str, result: EnhancedAnalysisResult):
    """Phase 3: 仿真增强"""
    try:
        from backend.services.simulation.engine import SimulationEngine

        sim_id = f"sim_v2r1_{uuid.uuid4().hex[:8]}"
        engine = SimulationEngine.create_lightweight(
            sim_id=sim_id,
            topic=text[:100],
            seed_content=text,
        )
        await engine.initialize()

        # 运行仿真（同步等待完成）
        await engine.run()

        # 提取仿真摘要
        status = engine.get_status()
        result.simulation_id = sim_id
        result.simulation_summary = {
            "total_ticks": status.get("current_tick", 0),
            "total_agents": status.get("total_agents", 0),
            "propagation": status.get("propagation", {}),
            "platforms": status.get("platforms", {}),
            "monitor": status.get("monitor", {}),
        }

        logger.info("仿真增强完成: %s, %d ticks, %d agents", sim_id, status.get("current_tick", 0), status.get("total_agents", 0))

    except Exception as e:
        logger.error("仿真增强失败: %s", e)
        result.simulation_summary = {"error": str(e)}


def _recalculate_with_dynamic_weights(result: EnhancedAnalysisResult):
    """用动态权重重新计算V2风险分数"""
    dw = result.dynamic_weights_result
    if not dw or not dw.adjustments:
        result.v2_overall_score = result.mvp_overall_score
        result.v2_dimensions = result.mvp_dimensions.copy()
        return

    # 用调整后的权重重新计算
    new_dimensions = result.mvp_dimensions.copy()
    for dim, new_weight in dw.adjusted_weights.items():
        if dim in new_dimensions:
            # 根据权重调整分值
            original_weight = dw.original_weights.get(dim, 1.0)
            ratio = new_weight / original_weight if original_weight > 0 else 1.0
            boost = (ratio - 1.0) * 15  # 每增加1倍权重提升15分
            new_score = min(100, max(0, new_dimensions[dim] + boost))
            new_dimensions[dim] = round(new_score)

    # 重新计算总分
    weighted_sum = 0.0
    weight_total = 0.0
    for dim, score in new_dimensions.items():
        weight = dw.adjusted_weights.get(dim, 1.0)
        weighted_sum += score * weight
        weight_total += weight

    overall = min(100, max(0, int(weighted_sum / weight_total))) if weight_total > 0 else result.mvp_overall_score

    result.v2_overall_score = overall
    result.v2_dimensions = new_dimensions
    result.v2_suggestion = get_suggestion(overall)

    # 记录风险提升
    for adj in dw.adjustments:
        result.risk_boosts[adj.dimension] = adj.boost


def _compile_final_report(result: EnhancedAnalysisResult):
    """Phase 4: 编制综合报告"""
    # 如果没有动态权重调整，V2分数等于MVP分数
    if result.v2_overall_score == 0:
        result.v2_overall_score = result.mvp_overall_score
    if result.v2_suggestion == "":
        result.v2_suggestion = result.mvp_suggestion
    if not result.v2_dimensions:
        result.v2_dimensions = result.mvp_dimensions.copy()

    # 仿真增强可能进一步调整分数
    if result.simulation_summary and "error" not in result.simulation_summary:
        # 基于仿真结果微调
        propagation = result.simulation_summary.get("propagation", {})
        reach = propagation.get("reach_count", 0)
        kinetic = propagation.get("kinetic", 0.0)

        # 传播范围大则风险提升
        if reach > 50 or kinetic > 0.7:
            result.v2_overall_score = min(100, result.v2_overall_score + 10)
            result.v2_suggestion = get_suggestion(result.v2_overall_score)

    # 可信度计算
    confidence = 0.5  # 基线
    sources = {"base": "MVP静态评估"}

    if result.signal_match_result and result.signal_match_result.matches:
        confidence += 0.15
        sources["signal"] = f"热点关联({len(result.signal_match_result.matches)}条)"

    if result.entity_risk_chain_result and result.entity_risk_chain_result.chains:
        confidence += 0.1
        sources["entity_chain"] = f"实体风险链({len(result.entity_risk_chain_result.chains)}条)"

    if result.simulation_id:
        confidence += 0.15
        agent_count = result.simulation_summary.get("total_agents", 0)
        sources["simulation"] = f"轻量仿真({agent_count}Agent)"

    result.confidence = min(1.0, confidence)
    result.confidence_sources = sources


def _get_graph_store():
    """获取全局GraphStore实例（如果可用）"""
    try:
        from backend.main import app
        return app.state.graph_store if hasattr(app.state, "graph_store") else None
    except Exception:
        return None


def _persist_result(result: EnhancedAnalysisResult):
    """持久化V2分析结果到数据库"""
    db = SessionLocal()
    try:
        v2_record = V2AnalysisResult(
            task_id=result.task_id,
            mode=result.mode,
            mvp_score=result.mvp_overall_score,
            v2_score=result.v2_overall_score,
            signal_matches=json.dumps(
                [{"title": m.title, "relevance": m.relevance_score, "risk": m.risk_impact}
                 for m in (result.signal_match_result.matches if result.signal_match_result else [])],
                ensure_ascii=False,
            ),
            entity_risk_chains=json.dumps(
                [{"source": c.source_entity, "score": c.total_risk_score, "dims": c.risk_dimensions}
                 for c in (result.entity_risk_chain_result.chains if result.entity_risk_chain_result else [])],
                ensure_ascii=False,
            ),
            dynamic_weights=json.dumps(
                result.dynamic_weights_result.adjusted_weights if result.dynamic_weights_result else {},
                ensure_ascii=False,
            ),
            simulation_id=result.simulation_id or "",
            simulation_summary=json.dumps(result.simulation_summary, ensure_ascii=False),
            confidence=result.confidence,
            confidence_sources=json.dumps(result.confidence_sources, ensure_ascii=False),
            analysis_time=result.analysis_time_seconds,
        )
        db.add(v2_record)
        db.commit()
    except Exception as e:
        logger.error("持久化V2分析结果失败: %s", e)
        db.rollback()
    finally:
        db.close()
