import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)

# 红线维度：触碰即禁止输出改写版本（对齐 risk_assessment_v2.txt 红线标准）
REDLINE_DIMENSIONS = {"政治敏感", "法律合规", "民族宗教", "事实错误", "平台禁区"}


def _normalize_rewrites(raw_rewrites) -> list[dict]:
    """统一 rewrites 为 [{text, rewrite_note}] 结构

    兼容旧格式（纯字符串列表）与新格式（对象列表）。
    """
    normalized: list[dict] = []
    for item in raw_rewrites or []:
        if isinstance(item, str):
            normalized.append({"text": item, "rewrite_note": ""})
        elif isinstance(item, dict):
            normalized.append({
                "text": item.get("text", ""),
                "rewrite_note": item.get("rewrite_note", ""),
            })
    return normalized


async def rewrite_sentence(
    sentence: str,
    dimension: str,
    severity: str,
    is_transcript_noise: bool = False,
) -> dict:
    """对高风险句子生成透明的安全表达优化建议

    定性：帮助作者保留原意、降低误伤；不用于规避平台审核，不伪装原文。

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
            "is_redline": False,
            "rewrites": [],
        }

    # 红线维度禁止输出改写版本，仅给出「建议不予发布」说明
    if dimension in REDLINE_DIMENSIONS:
        return {
            "original": sentence,
            "is_transcript_noise": False,
            "transcript_note": "",
            "is_redline": True,
            "redline_note": "该内容触及红线维度，建议不予发布。改写建议不适用于规避审核用途。",
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
            result.setdefault("is_redline", False)
            result["rewrites"] = _normalize_rewrites(result.get("rewrites", []))
            return result
        return {
            "original": sentence,
            "is_transcript_noise": False,
            "transcript_note": "",
            "is_redline": False,
            "rewrites": [],
        }
    except Exception as e:
        logger.error("改写失败: %s", e)
        return {
            "original": sentence,
            "is_transcript_noise": False,
            "transcript_note": "",
            "is_redline": False,
            "rewrites": [],
        }
