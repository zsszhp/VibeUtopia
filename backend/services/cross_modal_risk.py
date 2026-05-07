"""交叉风险检测模块 - V2.R4

检测文字×画面×音频之间的交叉风险：
1. 矛盾风险：文字与画面/音频内容矛盾
2. 潜在冲突：画面暗示与文字表述不一致
3. 多模态风险聚合：综合所有模态风险生成最终评估
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class CrossModalRisk:
    """交叉模态风险项"""
    risk_type: str          # contradiction/implicit_conflict/misleading/deceptive/other
    modalities: list        # 涉及的模态: ["text","image","audio"]
    description: str        # 风险描述
    severity: str           # high/medium/low
    confidence: float       # 置信度 0-1
    evidence: str = ""      # 证据描述
    suggestion: str = ""    # 修改建议


@dataclass
class CrossModalResult:
    """交叉风险检测结果"""
    task_id: str = ""
    text_risks: dict = field(default_factory=dict)       # 文字风控结果摘要
    image_risks: list = field(default_factory=list)       # 画面风险列表
    audio_risks: dict = field(default_factory=dict)       # 音频风险摘要
    ocr_text: str = ""                                    # OCR识别文字
    audio_text: str = ""                                  # 音频转写文字
    cross_risks: list = field(default_factory=list)       # List[CrossModalRisk]
    overall_risk_level: str = "safe"                      # 综合风险等级
    overall_risk_score: float = 0.0                       # 综合风险分数 0-100
    risk_breakdown: dict = field(default_factory=dict)    # 分模态风险分解
    summary: str = ""
    error: Optional[str] = None


# ─── 风险分数映射 ──────────────────────────────────────────────

SEVERITY_SCORE = {
    "high": 80,
    "medium": 50,
    "low": 25,
}

MODALITY_WEIGHTS = {
    "text": 0.4,       # 文字风控权重最高
    "image": 0.3,      # 画面风险次之
    "audio": 0.2,      # 音频风险
    "cross": 0.1,      # 交叉风险加成
}


class CrossModalRiskDetector:
    """交叉风险检测器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._cross_prompt = self._load_cross_prompt()

    def _load_cross_prompt(self) -> str:
        """加载交叉风险检测prompt"""
        prompt_path = PROMPTS_DIR / "cross_modal_risk.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        return """你是一个专业的多模态内容风险评估专家。请分析以下多模态内容中的交叉风险：

**文字内容**: {text}
**OCR识别文字**: {ocr_text}
**音频转写文字**: {audio_text}
**画面风险**: {image_risks}
**音频情感**: {audio_sentiment}

请重点检测以下交叉风险：
1. **矛盾风险**(contradiction): 文字与画面/音频内容直接矛盾
2. **隐性冲突**(implicit_conflict): 画面暗示与文字表述不一致
3. **误导风险**(misleading): 多模态组合可能产生误导性理解
4. **欺骗风险**(deceptive): 内容可能故意隐藏或歪曲事实

请以JSON格式返回：
```json
{
  "cross_risks": [
    {
      "risk_type": "contradiction|implicit_conflict|misleading|deceptive|other",
      "modalities": ["text","image","audio"],
      "description": "风险描述",
      "severity": "high|medium|low",
      "confidence": 0.0-1.0,
      "evidence": "证据",
      "suggestion": "修改建议"
    }
  ],
  "overall_risk_level": "safe|low|medium|high|critical",
  "overall_risk_score": 0-100,
  "risk_breakdown": {
    "text": 0-100,
    "image": 0-100,
    "audio": 0-100,
    "cross": 0-100
  },
  "summary": "综合风险评估摘要"
}
```"""

    async def detect(
        self,
        text_analysis: dict | None = None,
        image_risks: list | None = None,
        audio_analysis: dict | None = None,
        ocr_text: str = "",
        audio_text: str = "",
        task_id: str = "",
    ) -> CrossModalResult:
        """检测交叉模态风险

        Args:
            text_analysis: 文字风控结果摘要
            image_risks: 画面风险列表
            audio_analysis: 音频分析结果摘要
            ocr_text: OCR识别的文字
            audio_text: 音频转写文字
            task_id: 任务ID

        Returns:
            CrossModalResult
        """
        result = CrossModalResult(
            task_id=task_id,
            text_risks=text_analysis or {},
            image_risks=image_risks or [],
            audio_risks=audio_analysis or {},
            ocr_text=ocr_text,
            audio_text=audio_text,
        )

        # 1. 基于规则快速检测交叉风险
        rule_risks = self._rule_based_detection(
            text_analysis, image_risks, audio_analysis, ocr_text, audio_text
        )
        result.cross_risks.extend(rule_risks)

        # 2. LLM深度交叉分析
        if self._has_multi_modal_input(text_analysis, image_risks, audio_analysis, ocr_text, audio_text):
            try:
                llm_risks = await self._llm_cross_analysis(
                    text_analysis, image_risks, audio_analysis, ocr_text, audio_text
                )
                if llm_risks:
                    result.cross_risks.extend(llm_risks.get("cross_risks", []))
                    if llm_risks.get("overall_risk_level"):
                        result.overall_risk_level = llm_risks["overall_risk_level"]
                    if llm_risks.get("overall_risk_score") is not None:
                        result.overall_risk_score = llm_risks["overall_risk_score"]
                    if llm_risks.get("risk_breakdown"):
                        result.risk_breakdown = llm_risks["risk_breakdown"]
                    if llm_risks.get("summary"):
                        result.summary = llm_risks["summary"]
            except Exception as e:
                logger.warning("LLM交叉分析失败: %s", e)

        # 3. 如果没有LLM结果，用规则计算综合风险
        if not result.overall_risk_score:
            result.overall_risk_score = self._calculate_overall_score(
                text_analysis, image_risks, audio_analysis, result.cross_risks
            )
            result.overall_risk_level = self._score_to_level(result.overall_risk_score)
            result.risk_breakdown = self._calculate_breakdown(text_analysis, image_risks, audio_analysis)
            result.summary = self._generate_summary(result)

        return result

    def _rule_based_detection(
        self,
        text_analysis: dict | None,
        image_risks: list | None,
        audio_analysis: dict | None,
        ocr_text: str,
        audio_text: str,
    ) -> list[CrossModalRisk]:
        """基于规则的快速交叉检测"""
        risks = []

        # 检测：OCR文字与文案不一致
        if ocr_text and text_analysis:
            original_text = text_analysis.get("text", "")
            if original_text and ocr_text:
                # 简单关键词匹配
                ocr_keywords = set(ocr_text.lower().split())
                text_keywords = set(original_text.lower().split())
                overlap = ocr_keywords & text_keywords
                if len(overlap) < len(ocr_keywords) * 0.2 and len(ocr_keywords) > 3:
                    risks.append(CrossModalRisk(
                        risk_type="contradiction",
                        modalities=["text", "image"],
                        description="画面中OCR文字与文案内容严重不一致",
                        severity="medium",
                        confidence=0.6,
                        evidence=f"OCR关键词: {list(ocr_keywords)[:5]}, 文案关键词: {list(text_keywords)[:5]}",
                        suggestion="检查画面文字是否与文案表述一致",
                    ))

        # 检测：音频转写与文案不一致
        if audio_text and text_analysis:
            original_text = text_analysis.get("text", "")
            if original_text and audio_text:
                audio_keywords = set(audio_text.lower().split())
                text_keywords = set(original_text.lower().split())
                overlap = audio_keywords & text_keywords
                if len(overlap) < len(audio_keywords) * 0.2 and len(audio_keywords) > 3:
                    risks.append(CrossModalRisk(
                        risk_type="contradiction",
                        modalities=["text", "audio"],
                        description="音频内容与文案表述不一致",
                        severity="medium",
                        confidence=0.6,
                        evidence=f"音频关键词与文案重叠度低于20%",
                        suggestion="检查音频内容是否与文案一致",
                    ))

        # 检测：画面高风险+音频负面情绪
        has_image_risk = image_risks and any(
            r.severity in ("high", "medium") if hasattr(r, "severity") else False
            for r in image_risks
        )
        has_negative_audio = (
            audio_analysis and
            audio_analysis.get("sentiment", {}).get("sentiment") == "negative"
        )
        if has_image_risk and has_negative_audio:
            risks.append(CrossModalRisk(
                risk_type="implicit_conflict",
                modalities=["image", "audio"],
                description="画面存在风险且音频情感负面，可能构成隐性冲突",
                severity="high",
                confidence=0.7,
                evidence="画面风险+音频负面情感双重信号",
                suggestion="重点关注画面与音频的组合效果",
            ))

        return risks

    async def _llm_cross_analysis(
        self,
        text_analysis: dict | None,
        image_risks: list | None,
        audio_analysis: dict | None,
        ocr_text: str,
        audio_text: str,
    ) -> dict | None:
        """LLM深度交叉分析"""
        from backend.services.llm_client import call_llm

        # 构造输入
        text_summary = ""
        if text_analysis:
            text_summary = json.dumps({
                "risk_level": text_analysis.get("risk_level", "unknown"),
                "top_risks": text_analysis.get("top_risks", [])[:3],
            }, ensure_ascii=False)

        image_summary = "无画面风险"
        if image_risks:
            risk_items = []
            for r in image_risks[:5]:
                if hasattr(r, "description"):
                    risk_items.append(f"- {r.risk_type}: {r.description} ({r.severity})")
                elif isinstance(r, dict):
                    risk_items.append(f"- {r.get('risk_type', '')}: {r.get('description', '')}")
            image_summary = "\n".join(risk_items) if risk_items else "无画面风险"

        audio_summary = "无音频数据"
        if audio_analysis:
            audio_summary = json.dumps({
                "language": audio_analysis.get("language", ""),
                "sentiment": audio_analysis.get("sentiment", {}),
                "segment_count": audio_analysis.get("segment_count", 0),
            }, ensure_ascii=False)

        prompt = self._cross_prompt.format(
            text=text_summary,
            ocr_text=ocr_text or "无OCR数据",
            audio_text=audio_text or "无音频转写",
            image_risks=image_summary,
            audio_sentiment=audio_summary,
        )

        system = "你是一个专业的多模态内容风险评估专家，请严格按照JSON格式输出分析结果。"

        try:
            response = await call_llm(prompt, system, task_type="risk_assessment")
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error("LLM交叉分析调用失败: %s", e)
            return None

    def _parse_llm_response(self, response: str) -> dict | None:
        """解析LLM返回的JSON"""
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(json_str[start:end])
            else:
                return None
        except json.JSONDecodeError:
            logger.warning("交叉风险JSON解析失败: %s", response[:200])
            return None

        # 转换cross_risks
        cross_risks = []
        for item in data.get("cross_risks", []):
            cross_risks.append(CrossModalRisk(
                risk_type=item.get("risk_type", "other"),
                modalities=item.get("modalities", []),
                description=item.get("description", ""),
                severity=item.get("severity", "low"),
                confidence=float(item.get("confidence", 0.5)),
                evidence=item.get("evidence", ""),
                suggestion=item.get("suggestion", ""),
            ))

        return {
            "cross_risks": cross_risks,
            "overall_risk_level": data.get("overall_risk_level", "safe"),
            "overall_risk_score": float(data.get("overall_risk_score", 0)),
            "risk_breakdown": data.get("risk_breakdown", {}),
            "summary": data.get("summary", ""),
        }

    @staticmethod
    def _has_multi_modal_input(*inputs) -> bool:
        """判断是否有多个模态的输入"""
        modality_count = 0
        for inp in inputs:
            if inp:
                modality_count += 1
        return modality_count >= 2

    @staticmethod
    def _calculate_overall_score(
        text_analysis: dict | None,
        image_risks: list | None,
        audio_analysis: dict | None,
        cross_risks: list,
    ) -> float:
        """计算综合风险分数"""
        scores = {}

        # 文字风险分数
        if text_analysis:
            level = text_analysis.get("risk_level", "safe")
            score_map = {"safe": 0, "low": 20, "medium": 50, "high": 75, "critical": 95}
            scores["text"] = score_map.get(level, 0)
        else:
            scores["text"] = 0

        # 画面风险分数
        if image_risks:
            max_severity = max(
                (SEVERITY_SCORE.get(r.severity, 0) if hasattr(r, "severity") else 0 for r in image_risks),
                default=0,
            )
            scores["image"] = min(max_severity * len(image_risks) / max(len(image_risks), 5), 100)
        else:
            scores["image"] = 0

        # 音频风险分数
        if audio_analysis:
            sentiment = audio_analysis.get("sentiment", {})
            sentiment_score = {
                "negative": 60, "angry": 70, "fearful": 50,
                "mixed": 40, "neutral": 10, "positive": 0,
            }
            scores["audio"] = sentiment_score.get(sentiment.get("sentiment", ""), 20)
        else:
            scores["audio"] = 0

        # 交叉风险加成
        cross_bonus = sum(SEVERITY_SCORE.get(r.severity, 0) * 0.1 for r in cross_risks) if cross_risks else 0

        # 加权计算
        overall = (
            scores.get("text", 0) * MODALITY_WEIGHTS["text"]
            + scores.get("image", 0) * MODALITY_WEIGHTS["image"]
            + scores.get("audio", 0) * MODALITY_WEIGHTS["audio"]
            + cross_bonus * MODALITY_WEIGHTS["cross"]
        )

        return round(min(overall, 100), 1)

    @staticmethod
    def _calculate_breakdown(
        text_analysis: dict | None,
        image_risks: list | None,
        audio_analysis: dict | None,
    ) -> dict:
        """计算分模态风险分解"""
        breakdown = {}
        score_map = {"safe": 0, "low": 20, "medium": 50, "high": 75, "critical": 95}

        if text_analysis:
            breakdown["text"] = score_map.get(text_analysis.get("risk_level", "safe"), 0)
        if image_risks:
            breakdown["image"] = max(
                (SEVERITY_SCORE.get(r.severity, 0) if hasattr(r, "severity") else 0 for r in image_risks),
                default=0,
            )
        if audio_analysis:
            sentiment = audio_analysis.get("sentiment", {})
            s_score = {"negative": 60, "angry": 70, "fearful": 50, "mixed": 40, "neutral": 10, "positive": 0}
            breakdown["audio"] = s_score.get(sentiment.get("sentiment", ""), 20)

        return breakdown

    @staticmethod
    def _score_to_level(score: float) -> str:
        """分数转风险等级"""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        elif score >= 20:
            return "low"
        return "safe"

    @staticmethod
    def _generate_summary(result: CrossModalResult) -> str:
        """生成风险摘要"""
        parts = []
        if result.cross_risks:
            types = [r.risk_type for r in result.cross_risks]
            parts.append(f"检测到{len(result.cross_risks)}个交叉风险: {', '.join(set(types))}")
        if result.overall_risk_level != "safe":
            parts.append(f"综合风险等级: {result.overall_risk_level}({result.overall_risk_score}分)")
        if result.risk_breakdown:
            for modality, score in result.risk_breakdown.items():
                if score > 0:
                    parts.append(f"{modality}模态风险: {score}分")
        return "；".join(parts) if parts else "未检测到交叉风险"
