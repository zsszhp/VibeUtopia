import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)


async def rewrite_sentence(
    sentence: str,
    dimension: str,
    severity: str,
    is_transcript_noise: bool = False,
) -> dict:
    """对高风险句子生成安全改写版本

    Args:
        sentence: 需要改写的句子
        dimension: 风险维度名称
        severity: 风险等级 (high/medium/low)
        is_transcript_noise: 是否为转写噪声（True则不尝试改写，返回标注）
    """
    # 如果是转写噪声，直接返回标注，不调用LLM
    if is_transcript_noise:
        return {
            "original": sentence,
            "is_transcript_noise": True,
            "transcript_note": "此句疑似语音转写错误，建议核实原文后再评估风险",
            "rewrites": [],
        }

    prompt_template = load_prompt("rewrite.txt")
    prompt = (
        prompt_template
        .replace("{sentence}", sentence)
        .replace("{dimension}", dimension)
        .replace("{severity}", severity)
        .replace("{is_transcript_noise}", "false")
    )

    try:
        response = await call_llm(prompt, task_type="rewrite")
        result = parse_llm_json(response, fallback=None)
        if result and ("rewrites" in result or "is_transcript_noise" in result):
            result.setdefault("original", sentence)
            result.setdefault("is_transcript_noise", False)
            result.setdefault("transcript_note", "")
            result.setdefault("rewrites", [])
            return result
        return {"original": sentence, "is_transcript_noise": False, "transcript_note": "", "rewrites": []}
    except Exception as e:
        logger.error("改写失败: %s", e)
        return {"original": sentence, "is_transcript_noise": False, "transcript_note": "", "rewrites": []}
