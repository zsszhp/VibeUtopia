"""跨模态冲突检测器 - 检测视频文案、画面、音频之间的风险信号冲突

预期准确率收益：+7%
单模态漏报靠交叉校验补位，例如：
- 文案安全但画面有风险元素
- 音频提及敏感词但文案未体现
- 画面与文案情感冲突（文案积极但画面消极）

V3.5增强：视频画面与文案联合理解
- 帧序列描述与文案叙事的冲突检测
- 因果链与文案逻辑的矛盾检测
- 动作事件与文案描述的不一致检测
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

    async def detect_video_text_conflicts(
        self,
        text: str,
        sequence_descriptions: Optional[list] = None,
        causal_chain: Optional[object] = None,
        action_events: Optional[list] = None,
    ) -> dict:
        """视频画面与文案联合理解 - 检测帧序列分析结果与文案的冲突

        Args:
            text: 文案内容
            sequence_descriptions: 帧序列描述列表（SequenceDescription对象）
            causal_chain: 因果链（CausalChain对象）
            action_events: 动作事件列表（ActionEvent对象）

        Returns:
            冲突检测结果
        """
        if not text or not text.strip():
            return {
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "narrative_consistency": 100,
                "summary": "无文案内容，无法检测视频-文案冲突",
            }

        # 构建画面叙事摘要
        sequence_narrative = self._build_sequence_narrative(sequence_descriptions)
        causal_events_str = self._build_causal_events_str(causal_chain)
        action_events_str = self._build_action_events_str(action_events)

        # 如果没有任何画面分析结果，无法检测
        if not sequence_narrative and not causal_events_str and not action_events_str:
            return {
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "narrative_consistency": 100,
                "summary": "无画面分析结果，无法检测视频-文案冲突",
            }

        prompt = VIDEO_TEXT_CONFLICT_PROMPT.format(
            text=text[:1500],
            sequence_narrative=sequence_narrative[:1500],
            causal_events=causal_events_str[:800],
            action_events=action_events_str[:800],
        )

        try:
            response = await call_llm(
                prompt,
                system="你是视频内容风控专家，擅长检测视频画面叙事与文案内容之间的冲突和不一致。",
                task_type="video_text_conflict",
            )

            result = parse_llm_json(response, fallback={
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "narrative_consistency": 100,
                "summary": "LLM分析失败",
            })

            conflicts = result.get("conflicts", [])
            overall_score = int(result.get("overall_conflict_score", 0))
            overall_score = max(0, min(100, overall_score))

            return {
                "conflicts": conflicts,
                "overall_conflict_score": overall_score,
                "has_hidden_risk": result.get("has_hidden_risk", False),
                "narrative_consistency": int(result.get("narrative_consistency", 100)),
                "summary": result.get("summary", ""),
            }

        except Exception as e:
            logger.warning("detect_video_text_conflicts: 检测失败 %s", e)
            return {
                "conflicts": [],
                "overall_conflict_score": 0,
                "has_hidden_risk": False,
                "narrative_consistency": 100,
                "summary": f"检测失败: {str(e)}",
            }

    @staticmethod
    def _build_sequence_narrative(descriptions: Optional[list]) -> str:
        """从帧序列描述构建叙事文本"""
        if not descriptions:
            return ""
        parts = []
        for desc in descriptions:
            if hasattr(desc, "description") and desc.description:
                time_range = f"[{desc.start_time:.1f}s-{desc.end_time:.1f}s]"
                parts.append(f"{time_range} {desc.description}")
        return "\n".join(parts)

    @staticmethod
    def _build_causal_events_str(causal_chain: Optional[object]) -> str:
        """从因果链构建事件文本"""
        if not causal_chain:
            return ""
        parts = []
        if hasattr(causal_chain, "narrative") and causal_chain.narrative:
            parts.append(f"叙事摘要: {causal_chain.narrative}")
        if hasattr(causal_chain, "links") and causal_chain.links:
            for link in causal_chain.links[:10]:
                cause_desc = link.cause.description if hasattr(link, "cause") and hasattr(link.cause, "description") else str(link.cause)
                effect_desc = link.effect.description if hasattr(link, "effect") and hasattr(link.effect, "description") else str(link.effect)
                relation = link.relation_type if hasattr(link, "relation_type") else "→"
                parts.append(f"- {cause_desc} [{relation}] {effect_desc}")
        return "\n".join(parts)

    @staticmethod
    def _build_action_events_str(actions: Optional[list]) -> str:
        """从动作事件构建文本"""
        if not actions:
            return ""
        parts = []
        for action in actions[:10]:
            if hasattr(action, "description") and action.description:
                time_range = f"[{action.start_time:.1f}s-{action.end_time:.1f}s]"
                action_type = action.action_type if hasattr(action, "action_type") else "unknown"
                parts.append(f"- {time_range} ({action_type}) {action.description}")
        return "\n".join(parts)


VIDEO_TEXT_CONFLICT_PROMPT = """你是一个视频内容风控专家。请分析视频画面叙事与文案内容之间是否存在冲突或不一致。

【文案内容】
{text}

【视频画面叙事】（基于帧序列描述）
{sequence_narrative}

【画面中的因果事件链】
{causal_events}

【画面中检测到的动作/变化】
{action_events}

请分析：
1. 画面叙事与文案内容是否一致（画面在说A，文案在说B？）
2. 因果链与文案逻辑是否矛盾
3. 动作事件与文案描述是否不一致
4. 画面中出现的风险元素是否在文案中未被提及
5. 是否存在"文案安全但画面有风险"的隐藏风险

输出JSON：
{{
    "conflicts": [
        {{
            "type": "叙事冲突/因果矛盾/动作不一致/风险遗漏",
            "description": "冲突描述",
            "risk_score": 0-100,
            "severity": "low/medium/high",
            "evidence": "具体证据"
        }}
    ],
    "overall_conflict_score": 0-100,
    "has_hidden_risk": true/false,
    "narrative_consistency": 0-100,
    "summary": "简要总结"
}}"""


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
