from __future__ import annotations

"""博主风格画像模块 - V2.R6

分析博主历史内容，生成5维风格画像：
1. 词汇特征：常用词汇、词频分布、专业性
2. 表达风格：语气、句式、修辞手法
3. 主题偏好：常讨论话题、领域分布
4. 受众画像：目标受众特征、互动模式
5. 风险偏好：历史风险模式、敏感度
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class VocabularyProfile:
    """词汇特征"""
    top_words: list = field(default_factory=list)      # [{word, count, ratio}]
    avg_sentence_length: float = 0.0
    professional_ratio: float = 0.0                     # 专业词汇占比
    emotional_words: list = field(default_factory=list)  # 情感词列表
    readability_score: float = 0.0                      # 可读性评分 0-100


@dataclass
class ExpressionStyle:
    """表达风格"""
    tone: str = ""                    # formal/casual/humorous/serious/inspiring
    sentence_patterns: list = field(default_factory=list)  # 常用句式
    rhetoric_devices: list = field(default_factory=list)   # 修辞手法
    emoji_usage: float = 0.0          # emoji使用频率 0-1
    exclamation_ratio: float = 0.0    # 感叹句比例


@dataclass
class TopicPreference:
    """主题偏好"""
    primary_topics: list = field(default_factory=list)   # [{topic, weight}]
    secondary_topics: list = field(default_factory=list)
    content_diversity: float = 0.0    # 内容多样性 0-1
    trending_sensitivity: float = 0.0 # 热点敏感度 0-1


@dataclass
class AudienceProfile:
    """受众画像"""
    target_age: str = ""             # 目标年龄段
    target_gender: str = ""          # 目标性别
    engagement_style: str = ""       # 互动风格
    avg_engagement: float = 0.0      # 平均互动率
    fan_loyalty: float = 0.0         # 粉丝忠诚度 0-1


@dataclass
class RiskPreference:
    """风险偏好"""
    historical_risk_count: int = 0
    risk_dimensions: list = field(default_factory=list)  # 历史风险维度
    risk_tolerance: str = ""          # conservative/moderate/aggressive
    sensitive_topics: list = field(default_factory=list)  # 敏感话题
    near_miss_count: int = 0          # 险些踩雷次数


@dataclass
class BloggerProfile:
    """博主风格画像（5维）"""
    blogger_id: str = ""
    name: str = ""
    platform: str = ""
    content_count: int = 0
    vocabulary: VocabularyProfile = field(default_factory=VocabularyProfile)
    expression: ExpressionStyle = field(default_factory=ExpressionStyle)
    topics: TopicPreference = field(default_factory=TopicPreference)
    audience: AudienceProfile = field(default_factory=AudienceProfile)
    risk: RiskPreference = field(default_factory=RiskPreference)
    overall_style: str = ""           # 综合风格描述
    style_tags: list = field(default_factory=list)  # 风格标签
    confidence: float = 0.0           # 画像置信度


class BloggerProfiler:
    """博主风格画像生成器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._profile_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """加载博主画像Prompt"""
        prompt_path = PROMPTS_DIR / "blogger_profile.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        return """你是一个专业的内容创作者风格分析专家。请分析以下博主的历史内容，生成5维风格画像。

**博主历史内容**:
{contents}

请以JSON格式返回画像：
```json
{
  "vocabulary": {
    "top_words": [{"word": "词汇", "count": 10, "ratio": 0.05}],
    "avg_sentence_length": 15.0,
    "professional_ratio": 0.3,
    "emotional_words": ["感动", "愤怒"],
    "readability_score": 75.0
  },
  "expression": {
    "tone": "casual",
    "sentence_patterns": ["疑问句", "感叹句"],
    "rhetoric_devices": ["比喻", "反问"],
    "emoji_usage": 0.5,
    "exclamation_ratio": 0.3
  },
  "topics": {
    "primary_topics": [{"topic": "美食", "weight": 0.4}],
    "secondary_topics": [{"topic": "旅行", "weight": 0.2}],
    "content_diversity": 0.6,
    "trending_sensitivity": 0.7
  },
  "audience": {
    "target_age": "18-35",
    "target_gender": "女性为主",
    "engagement_style": "积极互动",
    "avg_engagement": 0.05,
    "fan_loyalty": 0.7
  },
  "risk": {
    "historical_risk_count": 1,
    "risk_dimensions": ["道德伦理"],
    "risk_tolerance": "moderate",
    "sensitive_topics": ["争议性社会话题"],
    "near_miss_count": 2
  },
  "overall_style": "轻松幽默的美食生活博主，善于用比喻和互动吸引观众",
  "style_tags": ["美食", "生活", "幽默", "互动型"],
  "confidence": 0.8
}
```"""

    async def generate_profile(self, blogger_id: str, name: str = "",
                                platform: str = "", contents: list[str] | None = None,
                                analysis_results: list[dict] | None = None) -> BloggerProfile:
        """生成博主风格画像

        Args:
            blogger_id: 博主ID
            name: 博主名称
            platform: 平台
            contents: 历史内容列表
            analysis_results: 历史风控结果列表

        Returns:
            BloggerProfile
        """
        profile = BloggerProfile(
            blogger_id=blogger_id,
            name=name,
            platform=platform,
            content_count=len(contents) if contents else 0,
        )

        # 1. 如果有历史内容，先用LLM生成画像
        if contents and len(contents) >= 2:
            try:
                llm_profile = await self._llm_profile(contents)
                if llm_profile:
                    self._merge_llm_profile(profile, llm_profile)
            except Exception as e:
                logger.warning("LLM画像生成失败: %s", e)

        # 2. 基于规则补充画像
        if contents:
            self._rule_based_vocabulary(profile, contents)

        # 3. 基于历史风控结果补充风险偏好
        if analysis_results:
            self._fill_risk_from_history(profile, analysis_results)

        # 4. 计算置信度
        profile.confidence = self._calculate_confidence(profile, contents, analysis_results)

        return profile

    async def _llm_profile(self, contents: list[str]) -> dict | None:
        """使用LLM生成画像"""
        from backend.services.llm_client import call_llm

        # 合并内容，限制长度
        combined = "\n---\n".join(contents[:20])
        if len(combined) > 8000:
            combined = combined[:8000]

        prompt = self._profile_prompt.format(contents=combined)
        system = "你是一个专业的内容创作者风格分析专家，请严格按照JSON格式输出画像。"

        try:
            response = await call_llm(prompt, system, task_type="default")
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error("LLM画像调用失败: %s", e)
            return None

    def _parse_llm_response(self, response: str) -> dict | None:
        """解析LLM返回的画像JSON"""
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
                return json.loads(json_str[start:end])
        except json.JSONDecodeError:
            logger.warning("博主画像JSON解析失败: %s", response[:200])
        return None

    def _merge_llm_profile(self, profile: BloggerProfile, data: dict):
        """将LLM画像数据合并到profile"""
        # 词汇特征
        vocab = data.get("vocabulary", {})
        if vocab:
            profile.vocabulary = VocabularyProfile(
                top_words=vocab.get("top_words", []),
                avg_sentence_length=float(vocab.get("avg_sentence_length", 0)),
                professional_ratio=float(vocab.get("professional_ratio", 0)),
                emotional_words=vocab.get("emotional_words", []),
                readability_score=float(vocab.get("readability_score", 50)),
            )

        # 表达风格
        expr = data.get("expression", {})
        if expr:
            profile.expression = ExpressionStyle(
                tone=expr.get("tone", "casual"),
                sentence_patterns=expr.get("sentence_patterns", []),
                rhetoric_devices=expr.get("rhetoric_devices", []),
                emoji_usage=float(expr.get("emoji_usage", 0)),
                exclamation_ratio=float(expr.get("exclamation_ratio", 0)),
            )

        # 主题偏好
        topics = data.get("topics", {})
        if topics:
            profile.topics = TopicPreference(
                primary_topics=topics.get("primary_topics", []),
                secondary_topics=topics.get("secondary_topics", []),
                content_diversity=float(topics.get("content_diversity", 0)),
                trending_sensitivity=float(topics.get("trending_sensitivity", 0)),
            )

        # 受众画像
        audience = data.get("audience", {})
        if audience:
            profile.audience = AudienceProfile(
                target_age=audience.get("target_age", ""),
                target_gender=audience.get("target_gender", ""),
                engagement_style=audience.get("engagement_style", ""),
                avg_engagement=float(audience.get("avg_engagement", 0)),
                fan_loyalty=float(audience.get("fan_loyalty", 0)),
            )

        # 风险偏好
        risk = data.get("risk", {})
        if risk:
            profile.risk = RiskPreference(
                historical_risk_count=int(risk.get("historical_risk_count", 0)),
                risk_dimensions=risk.get("risk_dimensions", []),
                risk_tolerance=risk.get("risk_tolerance", "moderate"),
                sensitive_topics=risk.get("sensitive_topics", []),
                near_miss_count=int(risk.get("near_miss_count", 0)),
            )

        profile.overall_style = data.get("overall_style", "")
        profile.style_tags = data.get("style_tags", [])

    def _rule_based_vocabulary(self, profile: BloggerProfile, contents: list[str]):
        """基于规则补充词汇特征"""
        import re
        all_text = " ".join(contents)

        # 句子长度
        sentences = re.split(r'[。！？.!?\n]', all_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            profile.vocabulary.avg_sentence_length = round(avg_len, 1)

        # 感叹句比例
        excl_count = sum(1 for s in sentences if s.endswith('！') or s.endswith('!'))
        profile.expression.exclamation_ratio = round(excl_count / max(len(sentences), 1), 2)

        # Emoji频率
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
        emoji_count = len(emoji_pattern.findall(all_text))
        profile.expression.emoji_usage = round(emoji_count / max(len(all_text), 1) * 100, 2)

        # 简单词频统计
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', all_text)
        from collections import Counter
        word_counts = Counter(words)
        total = sum(word_counts.values())
        top = word_counts.most_common(10)
        profile.vocabulary.top_words = [
            {"word": w, "count": c, "ratio": round(c / max(total, 1), 4)}
            for w, c in top
        ]

    def _fill_risk_from_history(self, profile: BloggerProfile, results: list[dict]):
        """从历史风控结果填充风险偏好"""
        risk_count = 0
        risk_dims = set()
        near_miss = 0

        for r in results:
            level = r.get("risk_level", "safe")
            if level in ("high", "critical"):
                risk_count += 1
            elif level == "medium":
                near_miss += 1

            for item in r.get("risk_items", []):
                dim = item.get("dimension", "")
                if dim:
                    risk_dims.add(dim)

        profile.risk.historical_risk_count = risk_count
        profile.risk.risk_dimensions = list(risk_dims)
        profile.risk.near_miss_count = near_miss

        # 风险容忍度推断
        total = len(results)
        if total > 0:
            risk_ratio = risk_count / total
            if risk_ratio > 0.3:
                profile.risk.risk_tolerance = "aggressive"
            elif risk_ratio > 0.1:
                profile.risk.risk_tolerance = "moderate"
            else:
                profile.risk.risk_tolerance = "conservative"

    @staticmethod
    def _calculate_confidence(profile: BloggerProfile, contents: list | None,
                              results: list | None) -> float:
        """计算画像置信度"""
        confidence = 0.0

        # 内容数量贡献
        content_count = len(contents) if contents else 0
        if content_count >= 20:
            confidence += 0.4
        elif content_count >= 10:
            confidence += 0.3
        elif content_count >= 5:
            confidence += 0.2
        elif content_count >= 2:
            confidence += 0.1

        # LLM画像贡献
        if profile.overall_style:
            confidence += 0.3

        # 风控历史贡献
        result_count = len(results) if results else 0
        if result_count >= 5:
            confidence += 0.3
        elif result_count >= 2:
            confidence += 0.2
        elif result_count >= 1:
            confidence += 0.1

        return round(min(confidence, 1.0), 2)
