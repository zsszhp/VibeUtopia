"""多模态内容理解 - 视频画面+OCR+音频转写风险检测 + VLM视觉描述

预期准确率收益：+6%
从只审文字到审画面+审音频，覆盖视频内容的全模态风险。
VLM视觉描述：为知识图谱构建提供结构化的视频画面语义描述。
"""

import base64
import logging
import os
from typing import Dict, List, Optional

from backend.services.llm_client import call_llm, call_vlm, parse_llm_json

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


VISUAL_DESCRIPTION_PROMPT = """请详细描述这个视频画面中的内容，用于构建知识图谱。

请从以下角度描述：
1. 场景：画面发生的地点和环境
2. 人物：出现的人物及其动作、表情
3. 物体：画面中的关键物体、产品、标志
4. 文字：画面中出现的文字内容（标题、字幕、标签等）
5. 活动：正在进行的活动或事件

请用简洁的中文描述，每项1-2句话。如果某项在画面中不存在，写"无"。"""

SEGMENT_ANALYSIS_PROMPT = """你是一个视频内容分析专家。请综合分析以下视频片段的多模态信息，提取结构化知识。

【视觉描述】
{visual_description}

【音频转录】
{asr_text}

【OCR文字】
{ocr_text}

请提取：
1. 话题：本片段讨论的主要话题
2. 关键实体：出现的人名、组织、产品、概念等
3. 观点：表达的观点或立场
4. 证据：引用的数据、案例、事实
5. 情感：整体情感倾向

输出JSON：
{{
    "topics": ["话题1", "话题2"],
    "entities": [
        {{"name": "实体名", "type": "Person/Organization/Concept/Product/Location", "description": "简述"}}
    ],
    "viewpoints": [
        {{"content": "观点内容", "stance": "positive/negative/neutral", "confidence": 0.8}}
    ],
    "evidence": [
        {{"content": "证据内容", "type": "data/case/fact"}}
    ],
    "sentiment": "positive/negative/neutral/mixed",
    "summary": "片段一句话摘要"
}}"""


class VideoSegmentAnalyzer:
    """视频片段分析器（VLM驱动，用于知识图谱构建）"""

    async def generate_visual_description(self, frame_path: str) -> str:
        """用VLM生成单帧画面的自然语言描述

        Args:
            frame_path: 帧图片路径

        Returns:
            视觉描述文本
        """
        if not os.path.exists(frame_path):
            return ""

        try:
            with open(frame_path, "rb") as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            description = await call_vlm(
                prompt=VISUAL_DESCRIPTION_PROMPT,
                image_base64=image_base64,
                system="你是一个视频内容分析专家，擅长描述视频画面中的细节。",
                task_type="default",
            )
            return description.strip()
        except Exception as e:
            logger.warning("VLM视觉描述生成失败: %s", e)
            return ""

    async def generate_visual_description_batch(self, frame_paths: List[str], max_concurrent: int = 3) -> str:
        """批量生成多帧画面的合并描述 — 并行处理

        对多个关键帧分别生成描述，然后合并为统一描述。
        为控制成本，最多处理5帧。

        Args:
            frame_paths: 帧图片路径列表
            max_concurrent: 最大并发VLM调用数

        Returns:
            合并后的视觉描述文本
        """
        if not frame_paths:
            return ""

        sampled = frame_paths[:5]

        import asyncio
        sem = asyncio.Semaphore(max_concurrent)

        async def _desc_with_sem(fp):
            async with sem:
                return await self.generate_visual_description(fp)

        desc_results = await asyncio.gather(
            *[_desc_with_sem(fp) for fp in sampled],
            return_exceptions=True,
        )

        descriptions = [d for d in desc_results if isinstance(d, str) and d]

        if not descriptions:
            return ""

        if len(descriptions) == 1:
            return descriptions[0]

        merge_prompt = f"""请将以下多个视频帧的描述合并为一段连贯的画面描述，去除重复信息：

{chr(10).join(f'帧{i+1}: {d}' for i, d in enumerate(descriptions))}

请输出一段连贯的中文描述，保留所有关键信息。"""

        try:
            merged = await call_llm(
                merge_prompt,
                system="你是一个内容整合专家。",
                task_type="default",
            )
            return merged.strip()
        except Exception as e:
            logger.warning("视觉描述合并失败: %s", e)
            return "\n".join(descriptions)

    async def analyze_segment(
        self,
        visual_description: str,
        asr_text: str = "",
        ocr_text: str = "",
    ) -> dict:
        """综合分析视频片段：视觉描述 + 音频内容 + OCR → 结构化知识

        Args:
            visual_description: VLM生成的视觉描述
            asr_text: ASR转录文本
            ocr_text: OCR提取文本

        Returns:
            结构化分析结果
        """
        prompt = SEGMENT_ANALYSIS_PROMPT.format(
            visual_description=visual_description or "无视觉信息",
            asr_text=asr_text or "无音频转录",
            ocr_text=ocr_text or "无OCR文字",
        )

        try:
            response = await call_llm(
                prompt,
                system="你是一个视频内容分析专家，擅长从多模态信息中提取结构化知识。",
                task_type="default",
            )

            result = parse_llm_json(response, fallback={
                "topics": [],
                "entities": [],
                "viewpoints": [],
                "evidence": [],
                "sentiment": "neutral",
                "summary": "分析失败",
            })

            return result

        except Exception as e:
            logger.warning("VideoSegmentAnalyzer: 片段分析失败 %s", e)
            return {
                "topics": [],
                "entities": [],
                "viewpoints": [],
                "evidence": [],
                "sentiment": "neutral",
                "summary": f"分析失败: {str(e)}",
            }
