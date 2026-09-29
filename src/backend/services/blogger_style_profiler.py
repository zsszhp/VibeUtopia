from __future__ import annotations

"""博主风格画像 — R4

输入历史文案/视频元数据，输出风格维度画像（话题/语气/节奏/风险偏好/人设）。
LLM 不可用时降级为规则分析，保证接口始终可返回结构化结果。
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

TONE_LABELS = {
    "formal": "正式",
    "casual": "轻松",
    "humorous": "幽默",
    "serious": "严肃",
    "inspiring": "激励",
}

RISK_TOLERANCE_LABELS = {
    "conservative": "保守",
    "moderate": "中等",
    "aggressive": "激进",
}

_HIGH_RISK_KEYWORDS = (
    "政治", "体制", "领导人", "革命", "颠覆",
    "暴力", "杀", "血", "武器",
    "色情", "裸", "赌博", "毒品",
)

_MEDIUM_RISK_KEYWORDS = (
    "争议", "批评", "质疑", "对立",
    "歧视", "偏见", "性别", "宗教", "民族",
)

_TOPIC_KEYWORDS = {
    "美妆护肤": ("美妆", "护肤", "化妆", "粉底", "口红", "成分"),
    "美食": ("美食", "吃", "餐厅", "食谱", "做饭", "零食"),
    "数码科技": ("数码", "手机", "电脑", "测评", "开箱", "芯片"),
    "生活方式": ("生活", "日常", "vlog", "旅行", "家居", "收纳"),
    "知识科普": ("科普", "知识", "原理", "历史", "物理", "数学"),
    "社会话题": ("社会", "职场", "性别", "婚恋", "教育", "内卷"),
    "游戏": ("游戏", "电竞", "攻略", "主播", "开黑"),
    "娱乐": ("综艺", "明星", "影视", "追剧", "偶像"),
}


@dataclass
class StyleProfileResult:
    """博主风格画像结果"""

    blogger_id: str = ""
    blogger_name: str = ""
    # 5 维风格
    topics: Dict[str, Any] = field(default_factory=dict)          # 话题偏好
    expression: Dict[str, Any] = field(default_factory=dict)      # 语气 / 节奏
    risk: Dict[str, Any] = field(default_factory=dict)            # 风险偏好
    persona: Dict[str, Any] = field(default_factory=dict)         # 人设
    vocabulary: Dict[str, Any] = field(default_factory=dict)      # 词汇
    audience: Dict[str, Any] = field(default_factory=dict)        # 受众
    # 衍生
    overall_style: str = ""
    style_tags: List[str] = field(default_factory=list)
    style_summary: str = ""
    strengths: List[str] = field(default_factory=list)
    risk_areas: List[str] = field(default_factory=list)
    risk_impact: str = ""
    confidence: float = 0.0
    source: str = "rule_based"     # llm / rule_based
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blogger_id": self.blogger_id,
            "blogger_name": self.blogger_name,
            "topics": self.topics,
            "expression": self.expression,
            "risk": self.risk,
            "persona": self.persona,
            "vocabulary": self.vocabulary,
            "audience": self.audience,
            "overall_style": self.overall_style,
            "style_tags": self.style_tags,
            "style_summary": self.style_summary,
            "strengths": self.strengths,
            "risk_areas": self.risk_areas,
            "risk_impact": self.risk_impact,
            "confidence": self.confidence,
            "source": self.source,
            "error": self.error,
        }


class BloggerStyleProfiler:
    """博主风格画像生成器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / "blogger_profile.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "你是一个专业的内容创作者风格分析专家。请分析以下博主的历史内容，生成风格画像。\n"
            "博主历史内容:\n{contents}\n"
            "请以JSON格式返回，包含 vocabulary / expression / topics / audience / risk / "
            "overall_style / style_tags / confidence 字段。"
        )

    async def analyze(
        self,
        contents: List[str],
        video_metadata: Optional[List[Dict[str, Any]]] = None,
        blogger_id: str = "",
        blogger_name: str = "",
    ) -> StyleProfileResult:
        """分析历史文案与视频元数据，生成风格画像

        Args:
            contents: 历史文案列表
            video_metadata: 视频元数据 [{title, duration, platform, publish_date}]
            blogger_id: 博主ID
            blogger_name: 博主名称
        """
        result = StyleProfileResult(blogger_id=blogger_id, blogger_name=blogger_name)

        texts = [c.strip() for c in (contents or []) if c and c.strip()]
        meta = video_metadata or []

        if not texts and not meta:
            result.error = "缺少历史文案或视频元数据"
            result.risk_impact = "无历史数据时无法判断风格风险倾向，新内容建议逐条预审"
            return result

        # 先用规则生成底座，保证任何情况下都有完整结构
        self._rule_analyze(result, texts, meta)

        # LLM 增强（失败则保留规则结果）
        try:
            llm_data = await self._llm_analyze(texts, meta)
            if llm_data:
                self._merge_llm(result, llm_data)
                result.source = "llm"
                result.confidence = max(result.confidence, float(llm_data.get("confidence", 0.75)))
        except Exception as e:
            logger.warning("风格画像LLM分析失败，使用规则结果: %s", e)

        self._finalize(result)
        return result

    # ------------------------------------------------------------------
    # 规则分析（降级路径）
    # ------------------------------------------------------------------

    def _rule_analyze(
        self,
        result: StyleProfileResult,
        texts: List[str],
        meta: List[Dict[str, Any]],
    ) -> None:
        joined = "\n".join(texts)
        meta_titles = " ".join(str(m.get("title", "")) for m in meta)
        corpus = f"{joined}\n{meta_titles}".strip()

        result.topics = self._analyze_topics(corpus, texts)
        result.expression = self._analyze_expression(texts, meta)
        result.risk = self._analyze_risk(corpus)
        result.persona = self._analyze_persona(result)
        result.vocabulary = self._analyze_vocabulary(joined)
        result.audience = self._analyze_audience(result)
        result.confidence = 0.55 if texts else 0.4

    def _analyze_topics(self, corpus: str, texts: List[str]) -> Dict[str, Any]:
        matched: List[Dict[str, Any]] = []
        for topic, keywords in _TOPIC_KEYWORDS.items():
            hits = sum(corpus.count(kw) for kw in keywords)
            if hits > 0:
                matched.append({"topic": topic, "weight": hits})
        matched.sort(key=lambda x: x["weight"], reverse=True)
        total = sum(m["weight"] for m in matched) or 1
        for m in matched:
            m["weight"] = round(m["weight"] / total, 2)

        primary = matched[:3]
        secondary = matched[3:6]
        return {
            "primary_topics": primary,
            "secondary_topics": secondary,
            "content_diversity": round(min(len(matched) / 5, 1.0), 2),
            "trending_sensitivity": 0.5,
        }

    def _analyze_expression(
        self, texts: List[str], meta: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not texts:
            durations = [float(m.get("duration", 0) or 0) for m in meta if m.get("duration")]
            avg_dur = sum(durations) / len(durations) if durations else 0
            pacing = "快节奏" if 0 < avg_dur <= 180 else ("慢叙事" if avg_dur > 600 else "混合")
            return {
                "tone": "casual",
                "tone_label": TONE_LABELS["casual"],
                "pacing": pacing,
                "narrative_style": "待补充",
                "structure": "待补充",
                "interaction_style": "待补充",
                "avg_sentence_length": 0.0,
            }

        sentences = re.split(r"[。！？!?\n]", joined := "\n".join(texts))
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

        excl = sum(t.count("!") + t.count("！") for t in texts)
        ques = sum(t.count("?") + t.count("？") for t in texts)
        casual_marks = sum(t.count("哈哈") + t.count("hhh") + t.count("绝了") + t.count("yyds") for t in texts)

        if casual_marks >= 2 or excl >= 4:
            tone = "humorous"
        elif excl >= 2 or ques >= 2:
            tone = "casual"
        elif avg_len > 30:
            tone = "formal"
        else:
            tone = "casual"

        if avg_len <= 15:
            pacing = "快节奏"
        elif avg_len >= 35:
            pacing = "慢叙事"
        else:
            pacing = "混合"

        if ques > excl:
            interaction = "提问互动"
        elif casual_marks > 0:
            interaction = "吐槽共情"
        else:
            interaction = "教学分享"

        return {
            "tone": tone,
            "tone_label": TONE_LABELS.get(tone, tone),
            "pacing": pacing,
            "narrative_style": "情感型" if tone in ("casual", "humorous") else "说理型",
            "structure": "开门见山" if pacing == "快节奏" else "铺垫高潮",
            "interaction_style": interaction,
            "avg_sentence_length": round(avg_len, 1),
        }

    def _analyze_risk(self, corpus: str) -> Dict[str, Any]:
        high_hits = [kw for kw in _HIGH_RISK_KEYWORDS if kw in corpus]
        medium_hits = [kw for kw in _MEDIUM_RISK_KEYWORDS if kw in corpus]

        if high_hits:
            tolerance = "conservative"
        elif len(medium_hits) >= 3:
            tolerance = "moderate"
        elif medium_hits:
            tolerance = "moderate"
        else:
            tolerance = "aggressive"

        safe_zones = ["日常生活", "知识分享", "经验教程"]
        danger_zones = []
        if any(kw in corpus for kw in ("性别", "对立", "歧视")):
            danger_zones.append("性别议题")
        if any(kw in corpus for kw in ("政治", "体制", "领导人")):
            danger_zones.append("政治敏感")
        if any(kw in corpus for kw in ("争议", "批评", "质疑")):
            danger_zones.append("争议批评")

        return {
            "risk_tolerance": tolerance,
            "risk_tolerance_label": RISK_TOLERANCE_LABELS.get(tolerance, tolerance),
            "historical_risk_count": len(high_hits),
            "risk_dimensions": (["政治敏感"] if any(k in corpus for k in ("政治", "体制")) else [])
            + (["道德伦理"] if medium_hits else []),
            "sensitive_topics": danger_zones,
            "safe_zones": safe_zones,
            "danger_zones": danger_zones,
            "near_miss_count": len(medium_hits),
        }

    def _analyze_persona(self, result: StyleProfileResult) -> Dict[str, Any]:
        tone = result.expression.get("tone", "casual")
        topics = result.topics.get("primary_topics", [])
        main_topic = topics[0]["topic"] if topics else "综合内容"

        persona_map = {
            "humorous": "幽默接地气的陪伴型创作者",
            "casual": "亲切自然的生活分享者",
            "formal": "严谨专业的知识输出者",
            "serious": "观点鲜明的深度评论者",
            "inspiring": "积极向上的激励型博主",
        }
        return {
            "role": persona_map.get(tone, persona_map["casual"]),
            "main_field": main_topic,
            "tone": tone,
            "tone_label": TONE_LABELS.get(tone, tone),
        }

    def _analyze_vocabulary(self, text: str) -> Dict[str, Any]:
        words = re.findall(r"[\u4e00-\u9fa5]{2,4}", text)
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "top_words": [{"word": w, "count": c} for w, c in top],
            "avg_sentence_length": 0.0,
        }

    def _analyze_audience(self, result: StyleProfileResult) -> Dict[str, Any]:
        tone = result.expression.get("tone", "casual")
        topics = result.topics.get("primary_topics", [])
        main = topics[0]["topic"] if topics else ""
        if main in ("美妆护肤", "生活方式"):
            gender = "女性为主"
        elif main in ("数码科技", "游戏"):
            gender = "男性为主"
        else:
            gender = "较为均衡"
        return {
            "target_age": "18-35",
            "target_gender": gender,
            "engagement_style": "积极互动" if tone in ("casual", "humorous") else "理性讨论",
        }

    # ------------------------------------------------------------------
    # LLM 增强
    # ------------------------------------------------------------------

    async def _llm_analyze(
        self, texts: List[str], meta: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        from backend.services.llm_client import call_llm

        content_str = "\n---\n".join(texts)[:4000]
        if meta:
            meta_str = json.dumps(meta[:10], ensure_ascii=False)
            content_str = f"{content_str}\n[视频元数据]\n{meta_str}"

        prompt = self._prompt.format(contents=content_str)
        system = "你是一个专业的内容创作者风格分析专家，请严格按照JSON格式输出。"
        response = await call_llm(prompt, system, task_type="default")
        return self._parse_json(response)

    @staticmethod
    def _parse_json(response: str) -> Optional[Dict[str, Any]]:
        if not response:
            return None
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", response, re.DOTALL)
        raw = json_match.group(1).strip() if json_match else response.strip()
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            logger.warning("风格画像JSON解析失败: %s", response[:200])
        return None

    def _merge_llm(self, result: StyleProfileResult, data: Dict[str, Any]) -> None:
        for key in ("vocabulary", "expression", "topics", "audience", "risk"):
            if isinstance(data.get(key), dict):
                merged = getattr(result, key) or {}
                merged.update(data[key])
                setattr(result, key, merged)
        if data.get("overall_style"):
            result.overall_style = str(data["overall_style"])
        if isinstance(data.get("style_tags"), list):
            result.style_tags = [str(t) for t in data["style_tags"][:8]]

    # ------------------------------------------------------------------
    # 收尾：摘要 / 决策映射
    # ------------------------------------------------------------------

    def _finalize(self, result: StyleProfileResult) -> None:
        if not result.overall_style:
            tone_label = result.expression.get("tone_label", "轻松")
            main = result.persona.get("main_field", "综合内容")
            result.overall_style = f"{tone_label}风格的{main}创作者"

        if not result.style_tags:
            tags = []
            for t in result.topics.get("primary_topics", []):
                tags.append(t["topic"] if isinstance(t, dict) else str(t))
            tags.append(result.expression.get("tone_label", "轻松"))
            result.style_tags = [t for t in tags if t][:6]

        topics_str = "、".join(
            t["topic"] if isinstance(t, dict) else str(t)
            for t in result.topics.get("primary_topics", [])[:3]
        ) or "综合内容"
        result.style_summary = (
            f"{result.persona.get('role', '内容创作者')}，主打{topics_str}，"
            f"语气{result.expression.get('tone_label', '轻松')}，节奏{result.expression.get('pacing', '混合')}"
        )

        result.strengths = [
            f"话题聚焦：{topics_str}",
            f"表达风格稳定：{result.expression.get('tone_label', '轻松')}/{result.expression.get('pacing', '混合')}",
        ]
        danger = result.risk.get("danger_zones") or []
        if danger:
            result.strengths.append("历史内容已识别风险边界，可据此规避")
        else:
            result.strengths.append("历史内容风险面较窄，选题自由度较高")

        result.risk_areas = list(danger) or ["暂无明显风险倾向"]
        result.risk_impact = self._build_risk_impact(result)

    @staticmethod
    def _build_risk_impact(result: StyleProfileResult) -> str:
        tolerance = result.risk.get("risk_tolerance", "moderate")
        danger = result.risk.get("danger_zones") or []
        parts = []
        if tolerance == "conservative":
            parts.append("历史内容显示风险偏好保守，新内容涉及敏感话题时「能不能发」的门槛应更严")
        elif tolerance == "aggressive":
            parts.append("历史内容风险面窄，常规选题对「能不能发」的影响较小")
        else:
            parts.append("风险偏好中等，触及高危维度时仍需预审后再发")
        if danger:
            parts.append(f"需重点回避：{'、'.join(danger)}，命中时建议先改后发")
        else:
            parts.append("当前风格画像未发现高危习惯，法律与平台处罚风险较低")
        return "；".join(parts)
