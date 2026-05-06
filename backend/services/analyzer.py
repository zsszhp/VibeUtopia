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

logger = logging.getLogger(__name__)


def calculate_overall_score(dimensions: list[dict]) -> int:
    """根据各维度分数计算总体风险分 (0-100)"""
    if not dimensions:
        return 0

    # 加权平均：高风险维度权重更大
    total_weight = 0
    weighted_sum = 0
    for d in dimensions:
        score = d.get("score", 0)
        severity = d.get("severity", "low")
        weight = {"high": 3, "medium": 2, "low": 1}.get(severity, 1)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    avg = weighted_sum / total_weight
    return min(100, max(0, int(avg)))


def get_suggestion(score: int) -> str:
    """根据总分给出发布建议"""
    if score <= 25:
        return "可发"
    elif score <= 55:
        return "建议修改"
    else:
        return "不建议发"


async def run_analysis(task_id: str, text: str):
    """编排整个分析流程"""
    db: Session = SessionLocal()
    try:
        # 1. 文本切分
        sentences = split_text(text)
        logger.info(f"任务 {task_id}: 文本切分为 {len(sentences)} 个句子")

        # 2. 并行执行平台人格模拟 + 风险评估
        platform_task = simulate_platforms(text)
        risk_task = assess_risks(text)
        platform_results, risk_results = await asyncio.gather(platform_task, risk_task)

        # 3. 对高风险句子生成改写
        rewrites = []
        risk_sentences = risk_results.get("risk_sentences", [])
        for rs in risk_sentences:
            if rs.get("severity") in ("high", "medium"):
                try:
                    rewrite = await rewrite_sentence(
                        rs.get("sentence", ""),
                        rs.get("dimension", ""),
                        rs.get("severity", "medium"),
                    )
                    rewrites.append(rewrite)
                except Exception as e:
                    logger.error(f"改写失败: {e}")

        # 4. 聚合评分
        dimensions = risk_results.get("dimensions", [])
        overall_score = calculate_overall_score(dimensions)
        suggestion = get_suggestion(overall_score)

        # 5. 存储结果
        # 存储 RiskItem
        for rs in risk_sentences:
            risk_item = RiskItem(
                task_id=task_id,
                sentence=rs.get("sentence", ""),
                dimension=rs.get("dimension", ""),
                severity=rs.get("severity", "low"),
                evidence=rs.get("evidence", ""),
            )
            db.add(risk_item)

        # 存储 PlatformReaction
        for pr in platform_results:
            # 从LLM返回结果中直接读取概率值，若没有则按情感标签降级计算
            positive = pr.get("positive", None)
            neutral = pr.get("neutral", None)
            negative = pr.get("negative", None)

            if positive is None or neutral is None or negative is None:
                # 降级：根据情感标签估算
                sentiment = pr.get("sentiment", "neutral")
                if sentiment == "positive":
                    positive, neutral, negative = 0.65, 0.25, 0.10
                elif sentiment == "negative":
                    positive, neutral, negative = 0.10, 0.20, 0.70
                else:
                    positive, neutral, negative = 0.25, 0.50, 0.25

            # 确保三者之和为1.0（归一化）
            total = (positive or 0) + (neutral or 0) + (negative or 0)
            if total > 0 and abs(total - 1.0) > 0.01:
                positive = round(positive / total, 2)
                neutral = round(neutral / total, 2)
                negative = round(1.0 - positive - neutral, 2)

            reaction = PlatformReaction(
                task_id=task_id,
                platform=pr.get("platform", ""),
                positive=round(positive, 2),
                neutral=round(neutral, 2),
                negative=round(negative, 2),
                reason=pr.get("reason", ""),
            )
            db.add(reaction)


        # 存储 AnalysisSummary
        dimensions_dict = {d.get("name", ""): d.get("score", 0) for d in dimensions}
        summary = AnalysisSummary(
            task_id=task_id,
            overall_score=overall_score,
            suggestion=suggestion,
            dimensions_json=json.dumps(dimensions_dict, ensure_ascii=False),
            rewrites_json=json.dumps(rewrites, ensure_ascii=False),
        )
        db.add(summary)

        # 更新 Task 状态
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

        db.commit()
        logger.info(f"任务 {task_id}: 分析完成，总分 {overall_score}，建议 {suggestion}")

    except Exception as e:
        logger.error(f"任务 {task_id}: 分析失败 - {e}")
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            db.commit()
    finally:
        db.close()
