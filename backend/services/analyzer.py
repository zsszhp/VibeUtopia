import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Task, RiskItem, PlatformReaction, AnalysisSummary
from backend.services.text_splitter import split_text
from backend.services.agent_simulator import simulate_all_platforms_with_agents
from backend.services.risk_assessor import assess_risks
from backend.services.rewriter import rewrite_sentence
from backend.services.transcript_detector import detect_transcript_quality, is_noise_sentence
from backend.services.cross_modal_detector import CrossModalConflictDetector, integrate_cross_modal_score
from backend.services.evidence_chain import EvidenceChainBuilder
from backend.services.confidence_calculator import ConfidenceCalculator

logger = logging.getLogger(__name__)

# WebSocket广播函数（由main.py注入）
_broadcast_func = None


def set_broadcast_func(func):
    """设置WebSocket广播函数"""
    global _broadcast_func
    _broadcast_func = func


async def _broadcast_step(task_id: str, step: str, progress: float, detail: str, completed_dims: list = None, remaining_dims: list = None):
    """广播步骤更新"""
    if _broadcast_func:
        await _broadcast_func(task_id, {
            "type": "step_update",
            "task_id": task_id,
            "step": step,
            "progress": progress,
            "detail": detail,
            "completed_dimensions": completed_dims or [],
            "remaining_dimensions": remaining_dims or [],
        })


async def _broadcast_risk_alert(task_id: str, dimension: str, score: int, severity: str, evidence: str):
    """广播风险预警"""
    if _broadcast_func:
        await _broadcast_func(task_id, {
            "type": "risk_alert",
            "task_id": task_id,
            "dimension": dimension,
            "score": score,
            "severity": severity,
            "evidence": evidence,
        })


async def _broadcast_complete(task_id: str, risk_level: str, overall_risk: int, dimensions_count: int):
    """广播分析完成"""
    if _broadcast_func:
        await _broadcast_func(task_id, {
            "type": "review_complete",
            "task_id": task_id,
            "risk_level": risk_level,
            "overall_risk": overall_risk,
            "dimensions_count": dimensions_count,
        })

MAX_TEXT_LENGTH = 5000

# 维度默认权重（高风险维度权重更高）
DIMENSION_WEIGHTS = {
    "政治敏感": 1.5,
    "法律合规": 1.5,
    "民族宗教": 1.3,
    "事实错误": 1.3,
    "平台禁区": 1.3,
    "情绪极化": 1.2,
    "价值观倾向": 1.2,
    "性别议题": 1.0,
    "道德伦理": 1.0,
    "群体冒犯": 1.0,
    "时事踩雷": 1.0,
}


def calculate_overall_score(dimensions: list[dict]) -> tuple[int, dict, list[dict]]:
    """根据各维度分数计算总体风险分 (0-100) — 加权评分算法

    改进点：
    1. 高风险维度（政治敏感、法律合规、民族宗教）权重更高
    2. 任一维度HIGH则整体评分不低于50
    3. 多维度同时HIGH则交叉叠加+15
    4. 新增：最高分维度优先机制，避免平均分稀释高风险
    5. 新增：红线维度（政治/法律/民族）分数放大1.5倍计入总体

    Returns:
        tuple: (overall_score, dimension_weights, cross_effects)
    """
    if not dimensions:
        return 0, {}, []

    # 红线维度列表（触碰即高风险）
    REDLINE_DIMS = {"政治敏感", "法律合规", "民族宗教", "事实错误", "平台禁区"}

    # 收集各维度分数和权重
    weighted_sum = 0.0
    weight_total = 0.0
    dimension_weights = {}
    high_dims = []
    max_score = 0
    redline_max = 0
    cross_effects = []

    for d in dimensions:
        name = d.get("name", "")
        score = d.get("score", 0)
        severity = d.get("severity", "low")
        # 使用LLM返回的权重，如无则用默认权重
        weight = d.get("dimension_weight", DIMENSION_WEIGHTS.get(name, 1.0))
        dimension_weights[name] = weight

        # 红线维度分数放大1.5倍
        if name in REDLINE_DIMS:
            adjusted_score = min(100, int(score * 1.5))
            redline_max = max(redline_max, adjusted_score)
        else:
            adjusted_score = score

        weighted_sum += adjusted_score * weight
        weight_total += weight
        max_score = max(max_score, score)

        if severity == "high":
            high_dims.append(name)

    # 加权平均
    if weight_total > 0:
        avg = weighted_sum / weight_total
    else:
        avg = 0

    # 总体分数 = max(加权平均, 最高分×0.8, 红线最高分×0.6)
    # 这样确保高风险维度不被平均分稀释
    overall = max(
        int(avg),
        int(max_score * 0.8),
        int(redline_max * 0.6)
    )
    overall = min(100, max(0, overall))

    # 规则1：任一维度HIGH，整体不低于50
    if high_dims and overall < 50:
        overall = 50

    # 规则2：多维度同时HIGH，交叉叠加
    if len(high_dims) >= 2:
        # 从risk_results的cross_effects中获取交叉信息，或者自动生成
        for i in range(len(high_dims)):
            for j in range(i + 1, len(high_dims)):
                cross_effects.append({
                    "dimensions": [high_dims[i], high_dims[j]],
                    "description": f"{high_dims[i]}与{high_dims[j]}同时触发，组合风险显著提升",
                    "combined_severity": "high",
                })
        overall = min(100, overall + 15)

    return overall, dimension_weights, cross_effects


def get_suggestion(score: int) -> str:
    """根据总分给出发布建议"""
    if score <= 25:
        return "可发"
    elif score <= 55:
        return "建议修改"
    else:
        return "不建议发"


def _compute_sentiment_ratios(pr: dict) -> tuple[float, float, float]:
    """从平台反应中计算正面/中性/负面比例，确保归一化"""
    positive = pr.get("positive")
    neutral = pr.get("neutral")
    negative = pr.get("negative")

    if positive is not None and neutral is not None and negative is not None:
        total = positive + neutral + negative
        if total > 0 and abs(total - 1.0) > 0.01:
            positive = positive / total
            neutral = neutral / total
            negative = 1.0 - positive - neutral
        return round(positive, 2), round(neutral, 2), round(negative, 2)

    # 降级：根据情感标签估算
    sentiment = pr.get("sentiment", "neutral")
    if sentiment == "positive":
        return 0.65, 0.25, 0.10
    elif sentiment == "negative":
        return 0.10, 0.20, 0.70
    else:
        return 0.25, 0.50, 0.25


async def run_analysis(task_id: str, text: str):
    """编排整个分析流程 - 集成WebSocket进度推送"""
    db: Session = SessionLocal()
    try:
        # ═══════════════════════════════════════════════════════════════════════
        # 步骤1: 内容理解 (0% - 15%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "understanding", 0.05, "正在理解内容结构...")

        sentences = split_text(text)
        logger.info("任务 %s: 文本切分为 %d 个句子", task_id, len(sentences))
        await _broadcast_step(task_id, "understanding", 0.1, f"内容已切分为{len(sentences)}个句子")

        # 转写质量检测
        await _broadcast_step(task_id, "understanding", 0.12, "正在检测内容质量...")
        transcript_quality = await detect_transcript_quality(text, sentences)
        tq_level = transcript_quality.get("quality_level", "clean")
        logger.info(
            "任务 %s: 转写质量检测完成，等级=%s，分数=%d",
            task_id, tq_level, transcript_quality.get("quality_score", 100),
        )
        await _broadcast_step(task_id, "understanding", 0.15, f"内容质量检测完成: {tq_level}")

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤2: 风险评估 (15% - 50%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "assessment", 0.2, "开始进行风险评估...")

        # 先启动风险评估获取维度列表
        risk_results = await assess_risks(text, transcript_quality=transcript_quality)
        dimensions = risk_results.get("dimensions", [])
        risk_sentences = risk_results.get("risk_sentences", [])

        # 广播各维度评估进度
        dimension_names = [d.get("name", "") for d in dimensions]
        completed_dims = []
        for i, dim in enumerate(dimensions):
            dim_name = dim.get("name", f"维度{i+1}")
            progress = 0.2 + (i + 1) / len(dimensions) * 0.25 if dimensions else 0.3
            await _broadcast_step(
                task_id, "assessment", progress,
                f"正在评估: {dim_name}",
                completed_dims.copy(),
                dimension_names[i+1:]
            )
            completed_dims.append(dim_name)

            # 高风险维度发送预警
            if dim.get("severity") in ("high", "critical"):
                await _broadcast_risk_alert(
                    task_id,
                    dim_name,
                    dim.get("score", 0),
                    dim.get("severity", "high"),
                    dim.get("evidence", "")[:100]
                )

        await _broadcast_step(task_id, "assessment", 0.5, "风险评估完成", dimension_names, [])

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤3: 信号采集 (50% - 60%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "signal", 0.55, "正在采集平台热点信号...")
        signal_correlations = []
        try:
            from backend.services.signal_matcher import SignalMatcher
            matcher = SignalMatcher()
            signal_result = await matcher.match(text)
            signal_correlations = signal_result.matches
            if signal_correlations:
                await _broadcast_step(
                    task_id, "signal", 0.58,
                    f"发现{len(signal_correlations)}个热点关联",
                )
        except Exception as e:
            logger.warning("信号采集失败(降级继续): %s", e)
        await _broadcast_step(task_id, "signal", 0.6, "信号采集完成")

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤3.5: 实体风险链分析 (60% - 65%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "entity_chain", 0.62, "正在分析实体风险传导链...")
        entity_chain_result = None
        entity_dimension_boosts = {}
        try:
            from backend.services.entity_risk_chain import analyze_entity_risk_chain
            entity_chain_result = await analyze_entity_risk_chain(text)
            if entity_chain_result and entity_chain_result.chains:
                entity_dimension_boosts = entity_chain_result.risk_dimension_boosts
                await _broadcast_step(
                    task_id, "entity_chain", 0.65,
                    f"发现{len(entity_chain_result.chains)}条风险传导链",
                )
            else:
                await _broadcast_step(task_id, "entity_chain", 0.65, "未发现显著风险传导链")
        except Exception as e:
            logger.warning("实体风险链分析失败(降级继续): %s", e)

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤3.6: 动态权重调整 (65% - 68%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "dynamic_weights", 0.66, "正在调整风险维度权重...")
        signal_dimension_boosts = {}
        if signal_correlations:
            from backend.services.signal_matcher import SignalMatchResult
            if hasattr(signal_result, 'risk_dimension_boosts'):
                signal_dimension_boosts = signal_result.risk_dimension_boosts

        try:
            from backend.services.dynamic_weights import DynamicWeights
            dw = DynamicWeights()
            weights_result = dw.adjust(
                signal_dimension_boosts=signal_dimension_boosts,
                entity_dimension_boosts=entity_dimension_boosts,
            )
            # 应用动态权重到维度结果
            for dim in dimensions:
                dim_name = dim.get("name", "")
                if dim_name in weights_result.adjusted_weights:
                    dim["dimension_weight"] = weights_result.adjusted_weights[dim_name]
            await _broadcast_step(task_id, "dynamic_weights", 0.68, "动态权重调整完成")
        except Exception as e:
            logger.warning("动态权重调整失败(降级继续): %s", e)

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤3.7: 平台权重仿真 (68% - 70%) — 阶段2新增
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "platform_sim", 0.69, "正在模拟平台用户反应...")
        platform_sim_reactions = {}
        try:
            from backend.services.platform_simulator import PlatformSimulator, get_platform_risk_summary
            simulator = PlatformSimulator()

            # 计算基础风险分数映射
            base_risk_scores = {d.get("name", ""): d.get("score", 0) for d in dimensions}

            # 并行仿真P0核心平台
            platform_reactions = await simulator.simulate_all_platforms(
                text=text,
                platforms=None,  # 默认P0平台
                base_risk_scores=base_risk_scores,
                max_concurrent=3,
            )

            if platform_reactions:
                platform_sim_reactions = {pid: r.to_dict() for pid, r in platform_reactions.items()}
                sim_summary = get_platform_risk_summary(platform_reactions)
                logger.info("平台权重仿真完成: %d个平台, 综合风险%.1f, 最高风险平台=%s",
                           sim_summary["platform_count"],
                           sim_summary["overall_risk"],
                           sim_summary.get("highest_risk_platform"))
                await _broadcast_step(
                    task_id, "platform_sim", 0.70,
                    f"平台仿真完成: {sim_summary['platform_count']}个平台，最高风险={sim_summary.get('highest_risk_platform', '')}",
                )
            else:
                await _broadcast_step(task_id, "platform_sim", 0.70, "平台仿真完成(无结果)")
        except Exception as e:
            logger.warning("平台权重仿真失败(降级继续): %s", e)

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤4: 仿真推演 (70% - 85%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "simulation", 0.72, "正在推演平台用户反应...")
        platform_results = await simulate_all_platforms_with_agents(text)
        await _broadcast_step(task_id, "simulation", 0.8, "平台反应推演完成")

        # 并行对高风险句子生成改写
        await _broadcast_step(task_id, "simulation", 0.82, "正在生成改写建议...")
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
        await _broadcast_step(task_id, "simulation", 0.85, "改写建议生成完成")

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤4.5: 跨模态冲突检测 (85% - 90%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "cross_modal", 0.87, "正在进行跨模态冲突检测...")
        cross_modal_result = None
        try:
            detector = CrossModalConflictDetector()
            cross_modal_result = await detector.detect_conflicts(
                text=text,
                visual_description=None,  # MVP阶段暂无画面分析
                audio_transcript=None,    # MVP阶段暂无音频分析
            )
            logger.info("跨模态检测完成: 冲突分数=%d, 隐藏风险=%s",
                       cross_modal_result.get("overall_conflict_score", 0),
                       cross_modal_result.get("has_hidden_risk", False))
            if cross_modal_result.get("conflicts"):
                await _broadcast_step(
                    task_id, "cross_modal", 0.90,
                    f"发现{len(cross_modal_result['conflicts'])}个跨模态冲突",
                )
            else:
                await _broadcast_step(task_id, "cross_modal", 0.90, "跨模态检测完成，无冲突")
        except Exception as e:
            logger.warning("跨模态检测失败(降级继续): %s", e, exc_info=True)

        # ═══════════════════════════════════════════════════════════════════════
        # 步骤5: 报告生成 (90% - 100%)
        # ═══════════════════════════════════════════════════════════════════════
        await _broadcast_step(task_id, "report", 0.92, "正在构建证据链...")

        # 5.1 构建证据链
        evidence_builder = EvidenceChainBuilder()
        evidence_chains = evidence_builder.build_chains_for_task(
            risk_sentences=risk_sentences,
            dimensions=dimensions,
        )
        evidence_summary = evidence_builder.get_summary()
        logger.info("证据链构建完成: 总数=%d, 平均置信度=%.2f, 交叉验证=%d",
                   evidence_summary["total_chains"],
                   evidence_summary["avg_confidence"],
                   evidence_summary["cross_validated_count"])

        await _broadcast_step(task_id, "report", 0.94, "正在计算置信度...")

        # 5.2 计算置信度
        confidence_calc = ConfidenceCalculator()
        confidence_result = confidence_calc.calculate(
            dimensions=dimensions,
            risk_sentences=risk_sentences,
            transcript_quality=transcript_quality,
            evidence_chains=evidence_chains,
            platform_reactions=platform_results,
        )
        uncertainty_notes = confidence_calc.get_uncertainty_notes(
            confidence_result, dimensions
        )
        logger.info("置信度计算完成: 总体=%.2f, 数据质量=%.2f, 一致性=%.2f, 证据=%.2f, 平台验证=%.2f",
                   confidence_result["overall_confidence"],
                   confidence_result["breakdown"]["data_quality_score"],
                   confidence_result["breakdown"]["consistency_score"],
                   confidence_result["breakdown"]["evidence_score"],
                   confidence_result["breakdown"]["platform_validation_score"])

        await _broadcast_step(task_id, "report", 0.96, "正在计算综合评分...")

        # 5.3 加权评分
        overall_score, dimension_weights, auto_cross_effects = calculate_overall_score(dimensions)

        # 跨模态冲突分数集成
        if cross_modal_result:
            conflict_score = cross_modal_result.get("overall_conflict_score", 0)
            has_hidden_risk = cross_modal_result.get("has_hidden_risk", False)
            overall_score = integrate_cross_modal_score(overall_score, conflict_score, has_hidden_risk)
            logger.info("跨模态冲突集成: 原始分=%d, 冲突分=%d, 隐藏风险=%s, 调整后=%d",
                       overall_score, conflict_score, has_hidden_risk, overall_score)

        # 信号关联风险提升
        signal_risk_boost = 0.0
        signal_dimension_boosts = {}
        if signal_correlations:
            from backend.services.signal_matcher import SignalMatchResult
            if hasattr(signal_result, 'overall_risk_boost'):
                signal_risk_boost = signal_result.overall_risk_boost
                signal_dimension_boosts = signal_result.risk_dimension_boosts
            for dim in dimensions:
                dim_name = dim.get("name", "")
                if dim_name in signal_dimension_boosts:
                    boost = signal_dimension_boosts[dim_name]
                    dim["score"] = min(100, int(dim.get("score", 0) + boost * 20))
            overall_score = min(100, int(overall_score + signal_risk_boost * 15))

        # 合并自动交叉效应和LLM识别的交叉效应
        llm_cross_effects = risk_results.get("cross_effects", [])
        all_cross_effects = auto_cross_effects + [
            ce for ce in llm_cross_effects
            if ce not in auto_cross_effects
        ]

        suggestion = get_suggestion(overall_score)

        # 计算风险等级
        risk_level = "green"
        if overall_score > 75:
            risk_level = "red"
        elif overall_score > 55:
            risk_level = "orange"
        elif overall_score > 25:
            risk_level = "yellow"

        await _broadcast_step(task_id, "report", 0.92, "正在保存分析结果...")

        # 6. 存储结果
        for rs in risk_sentences:
            db.add(RiskItem(
                task_id=task_id,
                sentence=rs.get("sentence", ""),
                dimension=rs.get("dimension", ""),
                severity=rs.get("severity", "low"),
                evidence=rs.get("evidence", ""),
                affected_groups=",".join(rs.get("affected_groups", [])) if rs.get("affected_groups") else None,
                dimension_weight=rs.get("dimension_weight"),
            ))

        # 保存信号关联结果
        if signal_correlations:
            from backend.models import HotspotCorrelationRecord
            for sc in signal_correlations:
                db.add(HotspotCorrelationRecord(
                    task_id=task_id,
                    signal_id=sc.signal_id,
                    signal_title=sc.title,
                    signal_platform=sc.source_platform,
                    correlation_score=sc.relevance_score,
                    correlation_type=sc.signal_type,
                    risk_boost=sc.relevance_score * 0.2,
                ))

        for pr in platform_results:
            positive, neutral, negative = _compute_sentiment_ratios(pr)
            # 序列化 sub_reactions 和 agent_details 到 reason 字段
            reason = pr.get("reason", "")
            sub_reactions = pr.get("sub_reactions", [])
            if sub_reactions:
                reason += "\n[群体分化] " + "; ".join(
                    f"{sr.get('group', '')}({sr.get('ratio', 0):.0%}): {sr.get('reaction', '')}"
                    for sr in sub_reactions
                )
            # agent_details 存入 reason
            agent_details = pr.get("agent_details", [])
            if agent_details:
                reason += "\n[Agent反应] " + "; ".join(
                    f"{ad.get('persona_name', '')}({ad.get('reaction_type', '')}): {ad.get('comment', '')[:60]}"
                    for ad in agent_details
                )
            db.add(PlatformReaction(
                task_id=task_id,
                platform=pr.get("platform", ""),
                positive=positive,
                neutral=neutral,
                negative=negative,
                reason=reason,
            ))

        # 收集所有平台的agent_details
        all_agent_details = []
        for pr in platform_results:
            for ad in pr.get("agent_details", []):
                all_agent_details.append(ad)

        dimensions_dict = {}
        for d in dimensions:
            dim_name = d.get("name", "")
            dimensions_dict[dim_name] = {
                "score": d.get("score", 0),
                "severity": d.get("severity", "low"),
                "evidence": d.get("evidence", ""),
                "evidence_source": d.get("evidence_source", {}),
                "confidence": d.get("confidence", 0.8),
                "suggestion": d.get("suggestion", ""),
                "affected_groups": d.get("affected_groups", []),
                "dimension_weight": d.get("dimension_weight", DIMENSION_WEIGHTS.get(dim_name, 1.0)),
            }
        db.add(AnalysisSummary(
            task_id=task_id,
            overall_score=overall_score,
            suggestion=suggestion,
            dimensions_json=json.dumps(dimensions_dict, ensure_ascii=False),
            rewrites_json=json.dumps(rewrites, ensure_ascii=False),
            transcript_quality=json.dumps(transcript_quality, ensure_ascii=False),
            dimension_weights=json.dumps(dimension_weights, ensure_ascii=False),
            cross_effects=json.dumps(all_cross_effects, ensure_ascii=False),
            agents_json=json.dumps(all_agent_details, ensure_ascii=False) if all_agent_details else None,
            # 阶段1.2新增: 保存证据链和置信度
            evidence_chains_json=json.dumps(evidence_chains, ensure_ascii=False),
            confidence_json=json.dumps(confidence_result, ensure_ascii=False),
            uncertainty_notes_json=json.dumps(uncertainty_notes, ensure_ascii=False),
            # 阶段2新增: 保存平台权重仿真结果
            platform_simulation_json=json.dumps(platform_sim_reactions, ensure_ascii=False) if platform_sim_reactions else None,
        ))

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("任务 %s: 分析完成，总分 %d，建议 %s，转写质量 %s", task_id, overall_score, suggestion, tq_level)

        # 广播分析完成
        await _broadcast_step(task_id, "report", 1.0, "分析完成")
        await _broadcast_complete(task_id, risk_level, overall_score, len(dimensions))
        
        # 返回分析结果
        return {
            "task_id": task_id,
            "status": "completed",
            "risk_level": risk_level,
            "overall_score": overall_score,
            "suggestion": suggestion,
            "dimensions": dimensions,
            "platform_reactions": platform_results,
            "transcript_quality": transcript_quality,
            "cross_modal_result": cross_modal_result,
            "confidence": confidence_result,
        }

    except Exception as e:
        logger.error("任务 %s: 分析失败 - %s", task_id, e)
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error = str(e)
                db.commit()
            # 广播失败
            if _broadcast_func:
                await _broadcast_func(task_id, {
                    "type": "error",
                    "task_id": task_id,
                    "error": str(e),
                })
        except Exception:
            db.rollback()
    finally:
        db.close()
