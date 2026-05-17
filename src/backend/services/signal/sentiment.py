"""LLM情感标注器 - 替代BERT-LoRA方案"""

import logging
from typing import List

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.signal.models import AnnotatedComment

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """请对以下文本进行情感分析，输出JSON格式：
文本：{text}

输出：
{{
    "sentiment": "positive/negative/neutral",
    "score": -1到1的浮点数(负=消极,正=积极),
    "confidence": 0到1的置信度,
    "is_irony": true或false(是否反讽)
}}"""

BATCH_SENTIMENT_PROMPT = """请对以下文本逐条进行情感分析，输出JSON数组：
{texts}

输出格式：
[
    {{"sentiment": "positive/negative/neutral", "score": 浮点数, "confidence": 浮点数, "is_irony": bool}},
    ...
]"""

# 规则兜底：简单关键词匹配
_POSITIVE_WORDS = {"好", "赞", "棒", "优秀", "支持", "喜欢", "厉害", "感动", "暖心", "加油"}
_NEGATIVE_WORDS = {"差", "烂", "垃圾", "恶心", "愤怒", "失望", "可耻", "黑", "骂", "抵制", "封杀"}


class SentimentAnnotator:
    """LLM情感标注器"""

    async def annotate(self, text: str) -> dict:
        """单条情感标注"""
        if not text or not text.strip():
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "is_irony": False}

        prompt = SENTIMENT_PROMPT.format(text=text)

        try:
            response = await call_llm(
                prompt,
                system="你是一个情感分析专家，擅长分析中文文本的情感倾向。",
                task_type="persona_simulation",
            )
            result = parse_llm_json(
                response,
                fallback=self._rule_based(text),
            )
            # 校验字段
            sentiment = result.get("sentiment", "neutral")
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            score = float(result.get("score", 0.0))
            score = max(-1.0, min(1.0, score))
            confidence = float(result.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            return {
                "sentiment": sentiment,
                "score": score,
                "confidence": confidence,
                "is_irony": bool(result.get("is_irony", False)),
            }
        except Exception as e:
            logger.warning("SentimentAnnotator: LLM标注失败，降级到规则 %s", e)
            return self._rule_based(text)

    async def batch_annotate(
        self, texts: List[str], batch_size: int = 10
    ) -> List[dict]:
        """批量情感标注，分批调用LLM"""
        results: List[dict] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            if len(batch) == 1:
                result = await self.annotate(batch[0])
                results.append(result)
                continue

            # 批量处理
            numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch))
            prompt = BATCH_SENTIMENT_PROMPT.format(texts=numbered)

            try:
                response = await call_llm(
                    prompt,
                    system="你是一个情感分析专家，擅长批量分析中文文本的情感倾向。",
                    task_type="persona_simulation",
                )
                parsed = parse_llm_json(response, fallback=None)

                if isinstance(parsed, list) and len(parsed) == len(batch):
                    for item in parsed:
                        sentiment = item.get("sentiment", "neutral")
                        if sentiment not in ("positive", "negative", "neutral"):
                            sentiment = "neutral"
                        results.append({
                            "sentiment": sentiment,
                            "score": max(-1.0, min(1.0, float(item.get("score", 0.0)))),
                            "confidence": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                            "is_irony": bool(item.get("is_irony", False)),
                        })
                else:
                    # 批量解析失败，逐条处理
                    for text in batch:
                        results.append(await self.annotate(text))
            except Exception as e:
                logger.warning("SentimentAnnotator: 批量标注失败，降级逐条 %s", e)
                for text in batch:
                    results.append(self._rule_based(text))

        return results

    @staticmethod
    def _rule_based(text: str) -> dict:
        """规则兜底：基于关键词的简单情感判断"""
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.3, "is_irony": False}

        pos_count = sum(1 for w in _POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in _NEGATIVE_WORDS if w in text)

        if pos_count > neg_count:
            score = min(1.0, 0.3 + 0.2 * pos_count)
            return {"sentiment": "positive", "score": score, "confidence": 0.4, "is_irony": False}
        elif neg_count > pos_count:
            score = max(-1.0, -0.3 - 0.2 * neg_count)
            return {"sentiment": "negative", "score": score, "confidence": 0.4, "is_irony": False}
        else:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.3, "is_irony": False}
