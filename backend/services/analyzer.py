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

MAX_TEXT_LENGTH = 5000


def calculate_overall_score(dimensions: list[dict]) -> int:
    """根据各维度分数计算总体风险分 (0-100)

    使用简单算术平均，避免score与severity双重加权导致评分失真。
    score本身已编码严重程度（0-20低, 21-50中, 51-100高）。
    """
    if not dimensions:
        return 0

    scores = [d.get("score", 0) for d in dimensions]
    avg = sum(scores) / len(scores)
    return min(100, max(0, int(avg)))


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

        # 2. 并行执行平台人格模拟 + 风险评估
        platform_results, risk_results = await asyncio.gather(
            simulate_platforms(text),
            assess_risks(text),
        )

        # 3. 并行对高风险句子生成改写
        risk_sentences = risk_results.get("risk_sentences", [])
        rewrite_tasks = [
            rewrite_sentence(
                rs.get("sentence", ""),
                rs.get("dimension", ""),
                rs.get("severity", "medium"),
            )
            for rs in risk_sentences
            if rs.get("severity") in ("high", "medium")
        ]
        rewrites = await asyncio.gather(*rewrite_tasks, return_exceptions=True)
        rewrites = [r for r in rewrites if not isinstance(r, Exception)]

        # 4. 聚合评分
        dimensions = risk_results.get("dimensions", [])
        overall_score = calculate_overall_score(dimensions)
        suggestion = get_suggestion(overall_score)

        # 5. 存储结果
        for rs in risk_sentences:
            db.add(RiskItem(
                task_id=task_id,
                sentence=rs.get("sentence", ""),
                dimension=rs.get("dimension", ""),
                severity=rs.get("severity", "low"),
                evidence=rs.get("evidence", ""),
            ))

        for pr in platform_results:
            positive, neutral, negative = _compute_sentiment_ratios(pr)
            db.add(PlatformReaction(
                task_id=task_id,
                platform=pr.get("platform", ""),
                positive=positive,
                neutral=neutral,
                negative=negative,
                reason=pr.get("reason", ""),
            ))

        dimensions_dict = {d.get("name", ""): d.get("score", 0) for d in dimensions}
        db.add(AnalysisSummary(
            task_id=task_id,
            overall_score=overall_score,
            suggestion=suggestion,
            dimensions_json=json.dumps(dimensions_dict, ensure_ascii=False),
            rewrites_json=json.dumps(rewrites, ensure_ascii=False),
        ))

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)

        db.commit()
        logger.info("任务 %s: 分析完成，总分 %d，建议 %s", task_id, overall_score, suggestion)

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
