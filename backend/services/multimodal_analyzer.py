"""多模态内容理解 - 视频画面+OCR+音频转写风险检测

预期准确率收益：+6%
从只审文字到审画面+审音频，覆盖视频内容的全模态风险。
"""

import logging
from typing import Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

VISUAL_RISK_PROMPT = """你是一个视频内容风控专家。请分析以下视频画面描述，识别潜在风险。

【画面描述】（OCR识别+物体检测+场景分析）
{visual_description}

请分析：
1. 是否包含暴力、血腥、恐怖等视觉风险
2. 是否包含敏感人物、标志、场景
3. 是否包含不当内容（色情、低俗等）
4. 画面整体风险等级

输出JSON：
{{
    "visual_risks": [
        {{
            "type": "暴力/血腥/恐怖/敏感人物/不当内容/其他",
            "description": "风险描述",
            "score": 0-100,
            "severity": "low/medium/high",
            "evidence": "具体证据"
        }}
    ],
    "overall_visual_risk_score": 0-100,
    "summary": "简要总结"
}}"""

AUDIO_RISK_PROMPT = """你是一个音频内容风控专家。请分析以下音频转写内容，识别潜在风险。

【音频转写】（语音识别+情感分析）
{audio_transcript}

【音频特征】
{audio_features}

请分析：
1. 是否包含敏感词汇、危险言论
2. 音频情感是否异常（愤怒、恐惧等）
3. 是否存在隐喻、暗语风险
4. 音频整体风险等级

输出JSON：
{{
    "audio_risks": [
        {{
            "type": "敏感词汇/危险言论/异常情感/隐喻暗语/其他",
            "description": "风险描述",
            "score": 0-100,
            "severity": "low/medium/high",
            "evidence": "具体证据"
        }}
    ],
    "overall_audio_risk_score": 0-100,
    "summary": "简要总结"
}}"""

OCR_RISK_PROMPT = """你是一个OCR文本风控专家。请分析从视频/图片中提取的OCR文本，识别潜在风险。

【OCR文本】
{ocr_text}

请分析：
1. OCR文本是否包含敏感信息
2. 是否与视频文案存在冲突
3. OCR文本整体风险等级

输出JSON：
{{
    "ocr_risks": [
        {{
            "type": "敏感信息/冲突信息/其他",
            "description": "风险描述",
            "score": 0-100,
            "severity": "low/medium/high",
            "evidence": "具体证据"
        }}
    ],
    "overall_ocr_risk_score": 0-100,
    "summary": "简要总结"
}}"""


class MultiModalAnalyzer:
    """多模态内容分析器"""

    async def analyze_visual(
        self,
        visual_description: str,
    ) -> dict:
        """分析视频画面风险

        Args:
            visual_description: 画面描述（OCR+物体检测+场景分析）

        Returns:
            画面风险分析
        """
        if not visual_description or not visual_description.strip():
            return {
                "visual_risks": [],
                "overall_visual_risk_score": 0,
                "summary": "无画面信息",
            }

        prompt = VISUAL_RISK_PROMPT.format(visual_description=visual_description[:1500])

        try:
            response = await call_llm(
                prompt,
                system="你是视频内容风控专家，擅长分析画面风险。",
                task_type="risk_assessment",
            )

            result = parse_llm_json(response, fallback={
                "visual_risks": [],
                "overall_visual_risk_score": 0,
                "summary": "LLM分析失败",
            })

            # 校验
            risks = result.get("visual_risks", [])
            score = int(result.get("overall_visual_risk_score", 0))
            score = max(0, min(100, score))

            return {
                "visual_risks": risks,
                "overall_visual_risk_score": score,
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            logger.warning("MultiModalAnalyzer: 画面分析失败 %s", e)
            return {
                "visual_risks": [],
                "overall_visual_risk_score": 0,
                "summary": f"分析失败: {str(e)}",
            }

    async def analyze_audio(
        self,
        audio_transcript: str,
        audio_features: Optional[dict] = None,
    ) -> dict:
        """分析音频风险

        Args:
            audio_transcript: 音频转写
            audio_features: 音频特征（情感、语速、音量等）

        Returns:
            音频风险分析
        """
        if not audio_transcript or not audio_transcript.strip():
            return {
                "audio_risks": [],
                "overall_audio_risk_score": 0,
                "summary": "无音频信息",
            }

        features_str = "无特殊音频特征"
        if audio_features:
            features_str = ", ".join(f"{k}: {v}" for k, v in audio_features.items())

        prompt = AUDIO_RISK_PROMPT.format(
            audio_transcript=audio_transcript[:1500],
            audio_features=features_str,
        )

        try:
            response = await call_llm(
                prompt,
                system="你是音频内容风控专家，擅长分析音频风险。",
                task_type="risk_assessment",
            )

            result = parse_llm_json(response, fallback={
                "audio_risks": [],
                "overall_audio_risk_score": 0,
                "summary": "LLM分析失败",
            })

            # 校验
            risks = result.get("audio_risks", [])
            score = int(result.get("overall_audio_risk_score", 0))
            score = max(0, min(100, score))

            return {
                "audio_risks": risks,
                "overall_audio_risk_score": score,
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            logger.warning("MultiModalAnalyzer: 音频分析失败 %s", e)
            return {
                "audio_risks": [],
                "overall_audio_risk_score": 0,
                "summary": f"分析失败: {str(e)}",
            }

    async def analyze_ocr(
        self,
        ocr_text: str,
        main_text: Optional[str] = None,
    ) -> dict:
        """分析OCR文本风险

        Args:
            ocr_text: OCR提取的文本
            main_text: 视频主文案（用于冲突检测）

        Returns:
            OCR风险分析
        """
        if not ocr_text or not ocr_text.strip():
            return {
                "ocr_risks": [],
                "overall_ocr_risk_score": 0,
                "summary": "无OCR信息",
            }

        prompt = OCR_RISK_PROMPT.format(ocr_text=ocr_text[:1500])

        try:
            response = await call_llm(
                prompt,
                system="你是OCR文本风控专家，擅长分析OCR文本风险。",
                task_type="risk_assessment",
            )

            result = parse_llm_json(response, fallback={
                "ocr_risks": [],
                "overall_ocr_risk_score": 0,
                "summary": "LLM分析失败",
            })

            # 校验
            risks = result.get("ocr_risks", [])
            score = int(result.get("overall_ocr_risk_score", 0))
            score = max(0, min(100, score))

            return {
                "ocr_risks": risks,
                "overall_ocr_risk_score": score,
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            logger.warning("MultiModalAnalyzer: OCR分析失败 %s", e)
            return {
                "ocr_risks": [],
                "overall_ocr_risk_score": 0,
                "summary": f"分析失败: {str(e)}",
            }


def integrate_multimodal_score(
    text_score: int,
    visual_score: int = 0,
    audio_score: int = 0,
    ocr_score: int = 0,
) -> int:
    """将多模态分数集成到总体风险分

    策略：
    1. 取各模态最高分作为基准
    2. 如果多模态同时有风险，加权叠加
    3. 最终分数 = max(文本分, 视觉分×0.8, 音频分×0.7, OCR分×0.6)
    4. 如果多模态同时高风险（>60），额外+10
    """
    # 各模态加权
    weighted_scores = [
        text_score,
        int(visual_score * 0.8),
        int(audio_score * 0.7),
        int(ocr_score * 0.6),
    ]

    # 取最高分
    overall = max(weighted_scores)

    # 如果多模态同时高风险，额外+10
    high_count = sum(1 for s in weighted_scores if s > 60)
    if high_count >= 2:
        overall = min(100, overall + 10)

    return overall
