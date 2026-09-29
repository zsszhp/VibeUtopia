from __future__ import annotations

"""选题推荐引擎 - V2.R6

基于热点×博主风格匹配，生成选题推荐。
每个推荐包含：选题、切入点、风险预筛、效果预测。
复用风控引擎做风险预筛。
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
class TopicRecommendation:
    """单个选题推荐"""
    topic: str                       # 选题
    angle: str                       # 切入点
    reason: str                      # 推荐理由
    trend_score: float = 0.0         # 热度匹配分 0-1
    style_match: float = 0.0         # 风格匹配分 0-1
    risk_level: str = "safe"         # 风险预筛: safe/low/medium/high
    risk_note: str = ""              # 风险提示
    estimated_reach: str = ""        # 预估效果
    priority: int = 0                # 优先级 1-5
    safety_score: float = 0.0        # 安全分 0-100，越高越安全
    brief: str = ""                  # 选题简介草稿（可直接进入预审）
    risk_impact: str = ""            # 对「能不能发」的决策映射


@dataclass
class TopicRecommendResult:
    """选题推荐结果"""
    blogger_id: str = ""
    blogger_name: str = ""
    hot_topics_used: int = 0
    recommendations: list = field(default_factory=list)  # List[TopicRecommendation]
    summary: str = ""
    error: Optional[str] = None


class TopicRecommender:
    """选题推荐引擎"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._recommend_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """加载选题推荐Prompt"""
        prompt_path = PROMPTS_DIR / "topic_recommend.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        return """你是一个专业的内容策划顾问。请根据博主风格和当前热点，生成5个选题推荐。

**博主风格**:
{blogger_style}

**当前热点**:
{hot_topics}

请以JSON格式返回：
```json
{
  "recommendations": [
    {
      "topic": "选题标题",
      "angle": "独特切入点",
      "reason": "推荐理由",
      "trend_score": 0.0-1.0,
      "style_match": 0.0-1.0,
      "risk_note": "风险提示",
      "estimated_reach": "预估效果",
      "priority": 1-5,
      "brief": "30-80字选题简介草稿，可直接用于预审"
    }
  ],
  "summary": "推荐总结"
}
```

注意：
1. 选题要与博主风格匹配，不要推荐风格差异过大的选题
2. 切入点要独特，避免同质化
3. 必须标注风险提示
4. priority越高越推荐
5. brief是给用户直接拿去预审的草稿简介"""

    async def recommend(self, blogger_profile: dict, hot_topics: list[dict] | None = None,
                         blogger_id: str = "", blogger_name: str = "") -> TopicRecommendResult:
        """生成选题推荐

        Args:
            blogger_profile: 博主画像数据
            hot_topics: 当前热点列表 [{title, platform, strength}]
            blogger_id: 博主ID
            blogger_name: 博主名称

        Returns:
            TopicRecommendResult
        """
        result = TopicRecommendResult(
            blogger_id=blogger_id,
            blogger_name=blogger_name,
        )

        # 获取热点（如果没有传入，从信号系统获取）
        if not hot_topics:
            hot_topics = await self._fetch_hot_topics()

        result.hot_topics_used = len(hot_topics)

        if not hot_topics:
            result.error = "无可用热点数据"
            return result

        # LLM生成推荐
        try:
            llm_result = await self._llm_recommend(blogger_profile, hot_topics)
            if llm_result:
                result.recommendations = self._parse_recommendations(llm_result)
                result.summary = llm_result.get("summary", "")
        except Exception as e:
            logger.warning("LLM选题推荐失败: %s", e)

        # 如果LLM失败，基于规则生成
        if not result.recommendations:
            result.recommendations = self._rule_based_recommend(blogger_profile, hot_topics)
            result.summary = "基于规则生成的选题推荐"

        # 风险预筛
        await self._risk_screening(result.recommendations, blogger_profile)

        # 按优先级排序，取 3 张选题卡
        result.recommendations.sort(key=lambda r: r.priority, reverse=True)
        result.recommendations = result.recommendations[:3]

        # 补齐决策映射字段
        for rec in result.recommendations:
            self._fill_decision_fields(rec, blogger_profile)

        return result

    async def _fetch_hot_topics(self) -> list[dict]:
        """从信号系统获取热点"""
        try:
            from backend.database import SessionLocal
            from backend.models import SignalRecord

            db = SessionLocal()
            try:
                signals = db.query(SignalRecord).order_by(
                    SignalRecord.appearance_count.desc()
                ).limit(20).all()

                return [
                    {
                        "title": s.title,
                        "platform": s.source_platform,
                        "strength": s.appearance_count,
                        "category": s.category,
                    }
                    for s in signals
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning("获取热点失败: %s", e)
            return []

    async def _llm_recommend(self, blogger_profile: dict, hot_topics: list[dict]) -> dict | None:
        """LLM生成选题推荐"""
        from backend.services.llm_client import call_llm

        style_str = json.dumps(blogger_profile, ensure_ascii=False, indent=2) if isinstance(blogger_profile, dict) else str(blogger_profile)
        topics_str = "\n".join(f"- {t['title']} ({t.get('platform', '')}, 热度: {t.get('strength', 0)})" for t in hot_topics[:15])

        prompt = self._recommend_prompt.format(
            blogger_style=style_str[:3000],
            hot_topics=topics_str,
        )
        system = "你是一个专业的内容策划顾问，请严格按照JSON格式输出推荐。"

        try:
            response = await call_llm(prompt, system, task_type="default")
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error("LLM选题推荐调用失败: %s", e)
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
                return json.loads(json_str[start:end])
        except json.JSONDecodeError:
            logger.warning("选题推荐JSON解析失败: %s", response[:200])
        return None

    def _parse_recommendations(self, data: dict) -> list[TopicRecommendation]:
        """解析推荐列表"""
        recs = []
        for item in data.get("recommendations", []):
            recs.append(TopicRecommendation(
                topic=item.get("topic", ""),
                angle=item.get("angle", ""),
                reason=item.get("reason", ""),
                trend_score=float(item.get("trend_score", 0)),
                style_match=float(item.get("style_match", 0)),
                risk_note=item.get("risk_note", ""),
                estimated_reach=item.get("estimated_reach", ""),
                priority=int(item.get("priority", 3)),
                brief=item.get("brief", ""),
                safety_score=float(item.get("safety_score", 0) or 0),
                risk_impact=item.get("risk_impact", ""),
            ))
        return recs

    def _rule_based_recommend(self, blogger_profile: dict, hot_topics: list[dict]) -> list[TopicRecommendation]:
        """基于规则的选题推荐"""
        recs = []
        topics = blogger_profile.get("topics", {})
        primary = topics.get("primary_topics", [])

        for ht in hot_topics[:10]:
            # 计算与博主主题的匹配度
            style_match = 0.3  # 基础分
            ht_title = ht.get("title", "")
            for pt in primary:
                if isinstance(pt, dict):
                    topic_name = pt.get("topic", "")
                    if topic_name and (topic_name in ht_title or ht_title in topic_name):
                        style_match = 0.9
                elif isinstance(pt, str) and pt in ht_title:
                    style_match = 0.8

            trend_score = min(ht.get("strength", 0) / 100, 1.0)
            priority = int((trend_score * 0.5 + style_match * 0.5) * 5)

            recs.append(TopicRecommendation(
                topic=ht_title,
                angle=f"从{blogger_profile.get('expression', {}).get('tone', '专业')}角度切入",
                reason=f"热点与博主主题相关度高",
                trend_score=round(trend_score, 2),
                style_match=round(style_match, 2),
                risk_note="需进一步评估",
                estimated_reach="中等",
                priority=priority,
                brief=f"围绕「{ht_title}」展开，结合个人经历给出真实看法，结尾引导理性讨论。",
            ))

        return recs[:5]

    def _fill_decision_fields(self, rec: TopicRecommendation, blogger_profile: dict):
        """补齐安全分、草稿与决策映射字段"""
        risk_level = rec.risk_level or "safe"
        level_score = {"safe": 90, "low": 75, "medium": 55, "high": 30, "critical": 15}
        base = level_score.get(risk_level, 60)
        # 风格匹配越高、热度越高，整体越值得发
        rec.safety_score = round(
            min(100.0, base * 0.7 + rec.style_match * 20 + rec.trend_score * 10), 1
        )

        if not rec.brief:
            rec.brief = f"围绕「{rec.topic}」，从{rec.angle}展开，给出可落地的观点与建议。"

        impact_map = {
            "safe": "此选题法律与平台风险较低，可直接推进成稿",
            "low": "此选题整体风险可控，成稿后建议快速过一遍预审即可发",
            "medium": "此选题存在争议面，建议先预审草稿、按提示修改后再发",
            "high": "此选题法律/舆情风险偏高，不建议原样发布，需改角度或暂缓",
            "critical": "此选题命中高危维度，「能不能发」结论为否，建议放弃或彻底换角度",
        }
        risk_impact = impact_map.get(risk_level, "建议预审后再决定是否发布")
        if rec.risk_note:
            risk_impact = f"{risk_impact}（{rec.risk_note}）"
        if not rec.risk_impact:
            rec.risk_impact = risk_impact

    async def _risk_screening(self, recommendations: list[TopicRecommendation],
                               blogger_profile: dict):
        """使用风控引擎对选题进行风险预筛"""
        try:
            from backend.services.analyzer import run_analysis

            for rec in recommendations[:5]:
                # 简单风控：检查选题文本
                topic_text = f"{rec.topic} {rec.angle}"
                try:
                    # 直接调用风控核心逻辑（同步方式简化处理）
                    risk_level = self._quick_risk_check(topic_text, blogger_profile)
                    rec.risk_level = risk_level
                    if risk_level in ("high", "critical"):
                        rec.priority = max(rec.priority - 2, 1)
                        rec.risk_note = "高风险选题，建议规避"
                except Exception:
                    rec.risk_level = "low"

        except Exception as e:
            logger.warning("风险预筛失败: %s", e)

    @staticmethod
    def _quick_risk_check(text: str, blogger_profile: dict) -> str:
        """快速风险检查（基于关键词）"""
        high_risk_keywords = [
            "政治", "体制", "领导人", "革命", "颠覆",
            "暴力", "杀", "血", "武器",
            "色情", "裸", "性",
            "赌博", "毒品",
        ]

        medium_risk_keywords = [
            "争议", "批评", "质疑", "对立",
            "歧视", "偏见", "性别",
            "宗教", "民族", "信仰",
        ]

        text_lower = text.lower()

        for kw in high_risk_keywords:
            if kw in text_lower:
                return "high"

        # 博主风险容忍度
        risk_tolerance = blogger_profile.get("risk", {}).get("risk_tolerance", "moderate")
        for kw in medium_risk_keywords:
            if kw in text_lower:
                if risk_tolerance == "conservative":
                    return "medium"
                return "low"

        return "safe"
