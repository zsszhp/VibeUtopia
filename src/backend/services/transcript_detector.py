"""转写质量检测器 — 识别ASR语音转写产物的乱码/噪声问题

在风险评估和人格模拟之前，先检测输入文本是否为ASR转写产物，
以及转写质量如何，避免将乱码误判为风险内容。
"""
import logging
import re
from typing import Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 规则预筛：基于文本统计特征快速判断
# ---------------------------------------------------------------------------

def _rule_based_check(sentences: list[str]) -> dict:
    """基于规则的转写质量预筛

    Returns:
        dict: {
            "noise_ratio": float,          # 0-1，噪声句子占比
            "noise_sentences": list[str],   # 被判定为噪声的句子
            "features": dict,               # 检测到的特征
        }
    """
    if not sentences:
        return {"noise_ratio": 0.0, "noise_sentences": [], "features": {}}

    noise_sentences = []
    features = {
        "lack_punctuation": 0,     # 缺乏标点
        "high_repetition": 0,      # 高频重复词
        "meaningless_segments": 0,  # 无意义片段
        "broken_syntax": 0,        # 语法断裂
        "total": len(sentences),
    }

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        is_noise = False
        reasons = []

        # 特征1：句子内缺乏标点（长句无逗号/句号等）
        if len(sent) > 30:
            punctuation_count = sum(1 for c in sent if c in "，。！？、；：""''（）")
            if punctuation_count == 0:
                features["lack_punctuation"] += 1
                is_noise = True
                reasons.append("lack_punctuation")

        # 特征2：同字/同词高频重复（如"的的的"、"了了了"）
        repetition_pattern = re.compile(r"(.)\1{3,}")
        if repetition_pattern.search(sent):
            features["high_repetition"] += 1
            is_noise = True
            reasons.append("high_repetition")

        # 特征3：无意义音节片段（ASR常见错误：音近字替代产生的无意义片段）
        # 匹配连续3个以上无关联单字组合（无标点分隔）
        meaningless_pattern = re.compile(
            r"[\u4e00-\u9fff]{2}"
            r"(?:[的了吗了呢着过地得]"
            r"[\u4e00-\u9fff]{1,3}){3,}"
        )
        if meaningless_pattern.search(sent):
            features["meaningless_segments"] += 1
            is_noise = True
            reasons.append("meaningless_segments")

        # 特征4：语法严重断裂（句子中出现大量不连贯的短语拼接）
        # 如 "给小猫蒸几瓦 屁眼上面叫厚海巨大地巨"
        broken_parts = re.split(r"[，。！？、；：\s]+", sent)
        short_fragments = [p for p in broken_parts if 2 <= len(p.strip()) <= 4]
        if len(short_fragments) >= 4 and len(short_fragments) / max(len(broken_parts), 1) > 0.6:
            features["broken_syntax"] += 1
            is_noise = True
            reasons.append("broken_syntax")

        # 特征5：包含典型ASR乱码特征（拼音近似替代）
        # 如 "忽来忧"="互联网"、"踢击"="行政"、"恶恋"="恶劣"
        asr_noise_indicators = [
            "忽来忧", "踢击", "恶恋", "财量", "攻堵", "亚斯吉利",
            "屁眼上面", "蒸几瓦", "好演好与",
        ]
        for indicator in asr_noise_indicators:
            if indicator in sent:
                is_noise = True
                reasons.append("asr_noise_indicator")
                break

        if is_noise:
            noise_sentences.append(sent)

    noise_ratio = len(noise_sentences) / len(sentences) if sentences else 0.0

    return {
        "noise_ratio": round(noise_ratio, 2),
        "noise_sentences": noise_sentences,
        "features": features,
    }


# ---------------------------------------------------------------------------
# LLM辅助判断：让LLM识别转写质量问题
# ---------------------------------------------------------------------------

_TRANSCRIPT_CHECK_PROMPT = """你是一个文本质量分析专家。请分析以下文本是否为语音自动转写(ASR)产物，以及转写质量如何。

判断依据：
1. 是否存在明显的同音字替代错误（如"忽来忧"代替"互联网"）
2. 是否存在语义不通的片段（无法理解其含义的句子）
3. 是否缺乏合理的标点符号
4. 整体行文是否符合自然语言习惯

请严格按照以下JSON格式输出（不要输出其他内容）：
{
  "is_transcript": true/false,
  "quality_score": 0-100,
  "quality_level": "clean/light_noise/heavy_noise/garbled",
  "noise_sentences": ["存在转写错误的句子1", "句子2"],
  "transcript_hints": ["简要说明识别到的转写特征"]
}

评分标准：
- quality_score 90-100: clean — 正常文本，无转写痕迹
- quality_score 60-89: light_noise — 有轻微转写错误，不影响理解
- quality_score 30-59: heavy_noise — 转写错误较多，部分内容难以理解
- quality_score 0-29: garbled — 转写严重失真，大量内容不可读

待分析文本：
"""


async def _llm_check(text: str) -> Optional[dict]:
    """使用LLM判断文本是否为ASR转写产物

    调用lite层级模型以控制成本。
    """
    # 截取前2000字，避免token浪费
    truncated = text[:2000]
    prompt = _TRANSCRIPT_CHECK_PROMPT + truncated

    try:
        response = await call_llm(prompt, task_type="transcript_detection")
        result = parse_llm_json(response, fallback=None)
        if result and "quality_level" in result:
            return result
        return None
    except Exception as e:
        logger.error("LLM转写质量检测失败: %s", e)
        return None


# ---------------------------------------------------------------------------
# 主入口：综合规则+LLM的检测结果
# ---------------------------------------------------------------------------

async def detect_transcript_quality(text: str, sentences: list[str]) -> dict:
    """检测文本的转写质量

    Args:
        text: 原始文本
        sentences: 切分后的句子列表

    Returns:
        dict: {
            "is_transcript": bool,
            "quality_score": int (0-100, 越高越好),
            "quality_level": str (clean/light_noise/heavy_noise/garbled),
            "noise_sentences": list[str],
            "transcript_hints": list[str],
            "detection_method": str (rule_only/rule_and_llm),
        }
    """
    # 1. 规则预筛
    rule_result = _rule_based_check(sentences)

    # 如果规则检测噪声比例很低，直接返回clean
    if rule_result["noise_ratio"] <= 0.1:
        return {
            "is_transcript": False,
            "quality_score": 95,
            "quality_level": "clean",
            "noise_sentences": [],
            "transcript_hints": ["规则检测未发现转写特征"],
            "detection_method": "rule_only",
        }

    # 2. LLM辅助判断（仅当规则检测到可疑特征时才调用）
    llm_result = await _llm_check(text)

    # 3. 综合结果
    if llm_result:
        # 合并规则和LLM的noise_sentences（取并集）
        rule_noise = set(rule_result["noise_sentences"])
        llm_noise = set(llm_result.get("noise_sentences", []))
        combined_noise = list(rule_noise | llm_noise)

        # 以LLM的判断为主，但如果规则检测噪声更高，取更保守的估计
        llm_score = llm_result.get("quality_score", 80)
        rule_score = _noise_ratio_to_score(rule_result["noise_ratio"])
        final_score = min(llm_score, rule_score)  # 取更保守的

        return {
            "is_transcript": llm_result.get("is_transcript", True),
            "quality_score": final_score,
            "quality_level": _score_to_level(final_score),
            "noise_sentences": combined_noise,
            "transcript_hints": llm_result.get("transcript_hints", []),
            "detection_method": "rule_and_llm",
        }
    else:
        # LLM失败，仅使用规则结果
        score = _noise_ratio_to_score(rule_result["noise_ratio"])
        return {
            "is_transcript": rule_result["noise_ratio"] > 0.3,
            "quality_score": score,
            "quality_level": _score_to_level(score),
            "noise_sentences": rule_result["noise_sentences"],
            "transcript_hints": ["LLM检测失败，仅使用规则检测结果"],
            "detection_method": "rule_only",
        }


def _noise_ratio_to_score(ratio: float) -> int:
    """噪声比例转换为质量分数"""
    if ratio <= 0.1:
        return 95
    elif ratio <= 0.3:
        return 75
    elif ratio <= 0.5:
        return 50
    elif ratio <= 0.7:
        return 30
    else:
        return 15


def _score_to_level(score: int) -> str:
    """分数转换为质量等级"""
    if score >= 90:
        return "clean"
    elif score >= 60:
        return "light_noise"
    elif score >= 30:
        return "heavy_noise"
    else:
        return "garbled"


def is_noise_sentence(sentence: str, transcript_quality: dict) -> bool:
    """判断某个句子是否为ASR噪声句子

    用于改写逻辑：噪声句子不应尝试改写。
    """
    noise_sentences = transcript_quality.get("noise_sentences", [])
    return sentence.strip() in [ns.strip() for ns in noise_sentences]
