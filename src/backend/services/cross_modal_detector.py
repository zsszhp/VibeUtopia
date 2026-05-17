"""跨模态冲突检测器 - 检测视频文案、画面、音频之间的风险信号冲突

预期准确率收益：+7%
单模态漏报靠交叉校验补位，例如：
- 文案安全但画面有风险元素
- 音频提及敏感词但文案未体现
- 画面与文案情感冲突（文案积极但画面消极）
"""

import logging
from typing import Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

CROSS_MODAL_PROMPT = """你是一个多模态内容风控专家。请分析以下三个模态的内容，检测它们之间是否存在风险信号冲突。

【文案内容】
{text}

【画面描述】（OCR识别+物体检测）
{visual}

【音频转写】（语音识别）
{audio}

请分析：
1. 各模态是否包含独立的风险信号
2. 模态之间是否存在冲突（如文案积极但画面消极）
3. 是否存在"某模态安全但其他模态有风险"的情况

输出JSON：
{{
    "conflicts": [
        {{
            "type": "文案vs画面/文案vs音频/画面vs音频",
            "description": "冲突描述",
            "risk_score": 0-100,
            "severity": "low/medium/high",
            "evidence": "具体证据"
        }}
    ],
    "overall_conflict_score": 0-100,
    "has_hidden_risk": true/false,  // 是否存在单模态漏报的隐藏风险
    "summary": "简要总结"
}}"""


class CrossModalConflictDetector:
    """跨模态冲突检测器"""

    async def detect_conflicts(
        self,
        text: str,
        visual_description: Optional[str] = None,
        audio_transcript: Optional[str] = None,
    ) -> dict:
        """检测跨模态冲突

        Args:
            text: 文案内容
            visual_description: 画面描述（OCR+物体检测）
            audio_transcript: 音频转写

        Returns:
            冲突检测结果
        """
        # 如果只有一个模态，无需检测冲突
        modal_count = sum(1 for m in [text, visual_description, audio_transcript] if m and m.strip())
        if modal_count <= 1:
            return {
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "summary": "单模态内容，无需跨模态检测",
            }

        # 填充缺失模态
        visual = visual_description or "无画面信息"
        audio = audio_transcript or "无音频信息"

        prompt = CROSS_MODAL_PROMPT.format(
            text=text[:1000],  # 限制长度
            visual=visual[:1000],
            audio=audio[:1000],
        )

        try:
            response = await call_llm(
                prompt,
                system="你是多模态内容风控专家，擅长检测文案、画面、音频之间的风险冲突。",
                task_type="risk_assessment",
            )

            result = parse_llm_json(response, fallback={
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "summary": "LLM分析失败，使用规则检测",
            })

            # 校验结果
            conflicts = result.get("conflicts", [])
            overall_score = int(result.get("overall_conflict_score", 0))
            overall_score = max(0, min(100, overall_score))

            # 规则兜底：如果LLM未检测到冲突，但模态差异明显，标记潜在风险
            has_hidden_risk = result.get("has_hidden_risk", False)
            if not has_hidden_risk and not conflicts:
                has_hidden_risk = self._rule_based_check(text, visual_description, audio_transcript)

            return {
                "conflicts": conflicts,
                "overall_conflict_score": overall_score,
                "has_hidden_risk": has_hidden_risk,
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            logger.warning("CrossModalConflictDetector: 检测失败 %s", e)
            return {
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": self._rule_based_check(text, visual_description, audio_transcript),
                "summary": f"检测失败: {str(e)}",
            }

    def _rule_based_check(
        self,
        text: str,
        visual: Optional[str],
        audio: Optional[str],
    ) -> bool:
        """规则兜底检测：简单的关键词冲突检测"""
        if not text or (not visual and not audio):
            return False

        # 敏感词列表（简化版）
        sensitive_words = ["暴力", "血腥", "恐怖", "敏感", "禁止", "违法", "犯罪"]

        # 检查文案是否安全
        text_safe = not any(w in text for w in sensitive_words)

        # 检查画面/音频是否有风险
        visual_risky = visual and any(w in visual for w in sensitive_words)
        audio_risky = audio and any(w in audio for w in sensitive_words)

        # 冲突：文案安全但画面/音频有风险
        return text_safe and (visual_risky or audio_risky)


def integrate_cross_modal_score(overall_score: int, conflict_score: int, has_hidden_risk: bool) -> int:
    """将跨模态冲突分数集成到总体风险分

    策略：
    1. 如果有隐藏风险，总体分+15
    2. 如果冲突分数高（>50），总体分+10
    3. 取最高值作为最终分数
    """
    adjusted = overall_score

    if has_hidden_risk:
        adjusted = max(adjusted, overall_score + 15)

    if conflict_score > 50:
        adjusted = max(adjusted, overall_score + 10)

    return min(100, adjusted)
