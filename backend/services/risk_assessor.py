import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)


async def assess_risks(text: str, transcript_quality: dict | None = None) -> dict:
    """对文本进行七维风险评估

    Args:
        text: 待评估文本
        transcript_quality: 转写质量检测结果（如有），会在prompt中注入提示
    """
    prompt_template = load_prompt("risk_assessment.txt")
    prompt = prompt_template + text

    # 如果检测到转写质量问题，在prompt前注入提醒
    if transcript_quality and transcript_quality.get("quality_level") not in ("clean", None):
        level = transcript_quality.get("quality_level", "unknown")
        score = transcript_quality.get("quality_score", 100)
        noise_count = len(transcript_quality.get("noise_sentences", []))
        transcript_hint = (
            f"\n【系统检测提示】本文案疑似语音自动转写产物，转写质量等级：{level}，"
            f"质量分数：{score}/100，检测到{noise_count}处疑似转写错误。"
            f"请在评估时区分转写错误和真实风险内容。\n"
        )
        # 插入到"文案内容："之前
        prompt = prompt.replace("文案内容：", transcript_hint + "文案内容：")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = await call_llm(prompt, task_type="risk_assessment")
            result = parse_llm_json(response, fallback=None)

            if result is None:
                logger.warning("风险评估LLM返回无法解析 (尝试%d/%d)", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    continue
                result = {"dimensions": [], "risk_sentences": [], "cross_effects": []}

            # 确保必要字段存在
            result.setdefault("dimensions", [])
            result.setdefault("risk_sentences", [])
            result.setdefault("cross_effects", [])

            # 如果dimensions为空但有risk_sentences，尝试从risk_sentences推断dimensions
            if not result["dimensions"] and result["risk_sentences"]:
                logger.warning("dimensions为空但存在risk_sentences，尝试推断维度")
                result["dimensions"] = _infer_dimensions_from_risks(result["risk_sentences"])

            # 如果仍然为空且非首次尝试，使用空结果
            if not result["dimensions"] and attempt < max_retries - 1:
                logger.warning("风险评估返回空维度 (尝试%d/%d)，重试", attempt + 1, max_retries)
                continue

            break
        except Exception as e:
            logger.error("风险评估失败 (尝试%d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                continue
            return {"dimensions": [], "risk_sentences": [], "cross_effects": []}

    # 为每个dimension补充默认dimension_weight和affected_groups
    for dim in result.get("dimensions", []):
        dim.setdefault("dimension_weight", _default_weight(dim.get("name", "")))
        dim.setdefault("affected_groups", [])

    # 为每个risk_sentence补充默认字段
    for rs in result.get("risk_sentences", []):
        rs.setdefault("affected_groups", [])
        rs.setdefault("is_transcript_noise", False)
        rs.setdefault("cross_effects", [])

    return result


def _default_weight(dimension_name: str) -> float:
    """根据维度名称返回默认权重"""
    weights = {
        "政治敏感": 1.5,
        "法律合规": 1.5,
        "民族宗教": 1.3,
        "性别议题": 1.0,
        "道德伦理": 1.0,
        "群体冒犯": 1.0,
        "时事踩雷": 1.0,
    }
    return weights.get(dimension_name, 1.0)


def _infer_dimensions_from_risks(risk_sentences: list[dict]) -> list[dict]:
    """当LLM返回的dimensions为空但risk_sentences非空时，从risk_sentences推断维度

    按维度分组聚合风险句子，生成维度分数
    """
    dim_scores: dict[str, list[int]] = {}
    for rs in risk_sentences:
        dim_name = rs.get("dimension", "未知")
        severity = rs.get("severity", "low")
        # 根据severity推断分数
        score_map = {"high": 70, "medium": 40, "low": 15}
        score = score_map.get(severity, 15)
        if dim_name not in dim_scores:
            dim_scores[dim_name] = []
        dim_scores[dim_name].append(score)

    dimensions = []
    for name, scores in dim_scores.items():
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        # 取平均与最大值的中值，避免单一句子过度影响
        final_score = int((avg_score + max_score) / 2)
        severity = "high" if final_score >= 60 else ("medium" if final_score >= 30 else "low")
        dimensions.append({
            "name": name,
            "score": final_score,
            "severity": severity,
            "dimension_weight": _default_weight(name),
            "affected_groups": [],
            "evidence": f"从{len(scores)}个风险条目推断",
        })

    return dimensions
