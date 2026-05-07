import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import Task, RiskItem, PlatformReaction, AnalysisSummary
from backend.services.text_splitter import split_text
from backend.services.persona_simulator import simulate_platforms
from backend.services.risk_assessor import assess_risks
from backend.services.rewriter import rewrite_sentence
from backend.services.transcript_detector import detect_transcript_quality, is_noise_sentence

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 5000

# 维度默认权重（高风险维度权重更高）
DIMENSION_WEIGHTS = {
    "政治敏感": 1.5,
    "法律合规": 1.5,
    "民族宗教": 1.3,
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

    Returns:
        tuple: (overall_score, dimension_weights, cross_effects)
    """
    if not dimensions:
        return 0, {}, []

    # 收集各维度分数和权重
    weighted_sum = 0.0
    weight_total = 0.0
    dimension_weights = {}
    high_dims = []
    cross_effects = []

    for d in dimensions:
        name = d.get("name", "")
        score = d.get("score", 0)
        severity = d.get("severity", "low")
        # 使用LLM返回的权重，如无则用默认权重
        weight = d.get("dimension_weight", DIMENSION_WEIGHTS.get(name, 1.0))
        dimension_weights[name] = weight

        weighted_sum += score * weight
        weight_total += weight

        if severity == "high":
            high_dims.append(name)

    # 加权平均
    if weight_total > 0:
        avg = weighted_sum / weight_total
    else:
        avg = 0

    overall = min(100, max(0, int(avg)))

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
    """编排整个分析流程"""
    db: Session = SessionLocal()
    try:
        # 1. 文本切分
        sentences = split_text(text)
        logger.info("任务 %s: 文本切分为 %d 个句子", task_id, len(sentences))

        # 2. 转写质量检测（新增步骤）
        transcript_quality = await detect_transcript_quality(text, sentences)
        tq_level = transcript_quality.get("quality_level", "clean")
        logger.info(
            "任务 %s: 转写质量检测完成，等级=%s，分数=%d",
            task_id, tq_level, transcript_quality.get("quality_score", 100),
        )

        # 3. 并行执行平台人格模拟 + 风险评估（传入转写质量信息）
        platform_results, risk_results = await asyncio.gather(
            simulate_platforms(text),
            assess_risks(text, transcript_quality=transcript_quality),
        )

        # 4. 并行对高风险句子生成改写（区分转写噪声）
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

        # 5. 加权评分（替代简单算术平均）
        dimensions = risk_results.get("dimensions", [])
        overall_score, dimension_weights, auto_cross_effects = calculate_overall_score(dimensions)

        # 合并自动交叉效应和LLM识别的交叉效应
        llm_cross_effects = risk_results.get("cross_effects", [])
        all_cross_effects = auto_cross_effects + [
            ce for ce in llm_cross_effects
            if ce not in auto_cross_effects
        ]

        suggestion = get_suggestion(overall_score)

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

        for pr in platform_results:
            positive, neutral, negative = _compute_sentiment_ratios(pr)
            # 序列化 sub_reactions 到 reason 字段末尾
            reason = pr.get("reason", "")
            sub_reactions = pr.get("sub_reactions", [])
            if sub_reactions:
                reason += "\n[群体分化] " + "; ".join(
                    f"{sr.get('group', '')}({sr.get('ratio', 0):.0%}): {sr.get('reaction', '')}"
                    for sr in sub_reactions
                )
            db.add(PlatformReaction(
                task_id=task_id,
                platform=pr.get("platform", ""),
                positive=positive,
                neutral=neutral,
                negative=negative,
                reason=reason,
            ))

        dimensions_dict = {d.get("name", ""): d.get("score", 0) for d in dimensions}
        db.add(AnalysisSummary(
            task_id=task_id,
            overall_score=overall_score,
            suggestion=suggestion,
            dimensions_json=json.dumps(dimensions_dict, ensure_ascii=False),
            rewrites_json=json.dumps(rewrites, ensure_ascii=False),
            transcript_quality=json.dumps(transcript_quality, ensure_ascii=False),
            dimension_weights=json.dumps(dimension_weights, ensure_ascii=False),
            cross_effects=json.dumps(all_cross_effects, ensure_ascii=False),
        ))

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("任务 %s: 分析完成，总分 %d，建议 %s，转写质量 %s", task_id, overall_score, suggestion, tq_level)

    except Exception as e:
        logger.error("任务 %s: 分析失败 - %s", task_id, e)
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
