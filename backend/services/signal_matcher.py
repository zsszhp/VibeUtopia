"""信号关联模块 - 文案与当前热点事件的关联分析

将用户输入的文案关键词与数据库中的SignalRecord/SeedEventRecord匹配，
识别文案是否与当前热点事件相关，评估热点关联带来的额外风险。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import SignalRecord, SeedEventRecord
from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class SignalMatch:
    """单条信号关联结果"""
    signal_id: str = ""
    title: str = ""
    source_platform: str = ""
    relevance_score: float = 0.0        # 与文案的关联度 0-1
    risk_impact: str = "low"            # low / medium / high
    risk_dimension: str = ""            # 关联的风险维度
    impact_description: str = ""        # 风险影响描述
    signal_type: str = "hotlist"        # hotlist / seed_event
    appearance_count: int = 0           # 热度
    rank: Optional[int] = None


@dataclass
class SignalMatchResult:
    """信号关联总结果"""
    keywords: List[str] = field(default_factory=list)
    matches: List[SignalMatch] = field(default_factory=list)
    overall_risk_boost: float = 0.0     # 因热点关联带来的整体风险提升 0-1
    risk_dimension_boosts: dict = field(default_factory=dict)  # {维度: 提升值}
    analysis_summary: str = ""


# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------

KEYWORD_EXTRACT_PROMPT = """请从以下文案中提取3-8个关键词和命名实体，用于搜索当前热点事件。

文案内容：
{text}

输出JSON格式：
{{
    "keywords": [
        {{"keyword": "关键词", "type": "entity/topic/brand/person", "importance": 1}}
    ]
}}

要求：
1. 提取人名、品牌名、组织名等命名实体
2. 提取话题关键词
3. importance: 1=最重要, 2=重要, 3=相关
4. 关键词要具体，能匹配到热点事件"""

SIGNAL_MATCH_PROMPT = """以下是文案关键词和当前热点事件列表，请判断每条热点与文案的关联性。

文案关键词：{keywords}

热点事件列表：
{events}

请对每条热点评估：
1. 与文案的关联度(0-1)
2. 风险影响级别(low/medium/high)
3. 关联的风险维度(政治敏感/法律合规/民族宗教/性别议题/道德伦理/群体冒犯/时事踩雷)
4. 风险影响描述

输出JSON格式：
{{
    "matches": [
        {{
            "event_index": 0,
            "relevance_score": 0.8,
            "risk_impact": "high",
            "risk_dimension": "时事踩雷",
            "impact_description": "文案涉及的品牌当前正陷入质量争议，发布相关内容可能被卷入舆论"
        }}
    ],
    "overall_risk_boost": 0.15,
    "risk_dimension_boosts": {{"时事踩雷": 0.2, "群体冒犯": 0.1}},
    "analysis_summary": "文案涉及2个当前热点，需注意时事踩雷风险"
}}

注意：只输出确实有关联的事件，无关联的不要输出。"""


class SignalMatcher:
    """信号关联器 - 文案与当前热点的关联分析"""

    def __init__(self, db: Session | None = None):
        self._db = db

    def _get_db(self) -> Session:
        return self._db or SessionLocal()

    async def match(self, text: str, top_k: int = 10) -> SignalMatchResult:
        """主入口：文案与热点信号关联分析

        Args:
            text: 用户输入的文案
            top_k: 返回最相关的K条关联

        Returns:
            SignalMatchResult: 关联分析结果
        """
        # 1. LLM提取文案关键词
        keywords = await self._extract_keywords(text)
        logger.info("SignalMatcher: 提取到 %d 个关键词: %s", len(keywords), keywords)

        if not keywords:
            return SignalMatchResult(keywords=[], matches=[], analysis_summary="未提取到关键词")

        # 2. 从数据库查询当前热点信号和种子事件
        signals, events = self._query_signals(keywords, top_k)
        logger.info("SignalMatcher: 查询到 %d 条信号, %d 条种子事件", len(signals), len(events))

        if not signals and not events:
            return SignalMatchResult(
                keywords=keywords,
                matches=[],
                analysis_summary="当前无相关热点",
            )

        # 3. LLM评估关联度和风险影响
        result = await self._evaluate_matches(text, keywords, signals, events)
        return result

    async def _extract_keywords(self, text: str) -> List[str]:
        """LLM提取文案关键词"""
        prompt = KEYWORD_EXTRACT_PROMPT.format(text=text[:2000])

        try:
            response = await call_llm(
                prompt,
                system="你是一个关键词提取专家，擅长从中文文案中提取搜索关键词和命名实体。",
                task_type="persona_simulation",
            )
            data = parse_llm_json(response, fallback={"keywords": []})
            keywords_data = data.get("keywords", [])

            keywords = []
            for kw in keywords_data:
                word = kw.get("keyword", "").strip()
                if word:
                    keywords.append(word)

            # 降级：如果LLM未返回关键词，用文本分割
            if not keywords:
                keywords = self._fallback_keywords(text)

            return keywords

        except Exception as e:
            logger.error("SignalMatcher: 关键词提取失败 %s", e)
            return self._fallback_keywords(text)

    def _fallback_keywords(self, text: str) -> List[str]:
        """降级：简单分词提取关键词"""
        # 去除标点，按2-4字窗口切分
        import re
        clean = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
        words = [w for w in clean.split() if len(w) >= 2][:8]
        return words

    def _query_signals(self, keywords: List[str], top_k: int) -> tuple[list, list]:
        """从数据库查询相关信号和种子事件"""
        db = self._get_db()
        own_db = self._db is None
        try:
            # 查询近期信号（最近72小时内的热搜）
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
            signals = (
                db.query(SignalRecord)
                .filter(SignalRecord.last_seen >= cutoff)
                .order_by(SignalRecord.appearance_count.desc())
                .limit(100)
                .all()
            )

            # 查询活跃种子事件
            events = (
                db.query(SeedEventRecord)
                .filter(SeedEventRecord.status == "active")
                .order_by(SeedEventRecord.signal_strength.desc())
                .limit(50)
                .all()
            )

            # 关键词过滤：标题包含任一关键词的优先
            def keyword_score(title: str) -> int:
                return sum(1 for kw in keywords if kw in title)

            signals = sorted(signals, key=lambda s: keyword_score(s.title), reverse=True)[:top_k * 2]
            events = sorted(events, key=lambda e: keyword_score(e.title), reverse=True)[:top_k]

            return signals, events

        except Exception as e:
            logger.error("SignalMatcher: 查询信号失败 %s", e)
            return [], []
        finally:
            if own_db:
                db.close()

    async def _evaluate_matches(
        self,
        text: str,
        keywords: List[str],
        signals: list,
        events: list,
    ) -> SignalMatchResult:
        """LLM评估热点与文案的关联性和风险影响"""
        # 构建事件列表文本
        events_text = ""
        for i, s in enumerate(signals[:20]):
            events_text += f"{i}. [热搜/{s.source_platform}] {s.title} (热度:{s.appearance_count})\n"
        for i, e in enumerate(events[:10]):
            idx = len(signals[:20]) + i
            events_text += f"{idx}. [种子事件/{e.category}] {e.title} (强度:{e.signal_strength:.1f})\n"

        if not events_text.strip():
            return SignalMatchResult(keywords=keywords, matches=[], analysis_summary="无热点数据")

        prompt = SIGNAL_MATCH_PROMPT.format(
            keywords=", ".join(keywords),
            events=events_text,
        )

        try:
            response = await call_llm(
                prompt,
                system="你是一个舆情风险分析专家，擅长判断文案与当前热点事件的关联性和潜在风险。",
                task_type="risk_assessment",
            )
            data = parse_llm_json(response, fallback={
                "matches": [],
                "overall_risk_boost": 0.0,
                "risk_dimension_boosts": {},
                "analysis_summary": "评估失败",
            })

            # 构建匹配结果
            matches: List[SignalMatch] = []
            all_items = list(signals[:20]) + list(events[:10])

            for m in data.get("matches", []):
                idx = m.get("event_index", -1)
                if 0 <= idx < len(all_items):
                    item = all_items[idx]
                    is_signal = isinstance(item, SignalRecord)
                    matches.append(SignalMatch(
                        signal_id=item.signal_id if is_signal else item.event_id,
                        title=item.title,
                        source_platform=item.source_platform if is_signal else item.category,
                        relevance_score=min(1.0, max(0.0, m.get("relevance_score", 0.0))),
                        risk_impact=m.get("risk_impact", "low"),
                        risk_dimension=m.get("risk_dimension", ""),
                        impact_description=m.get("impact_description", ""),
                        signal_type="hotlist" if is_signal else "seed_event",
                        appearance_count=item.appearance_count if is_signal else int(item.signal_strength * 10),
                        rank=item.rank if is_signal else None,
                    ))

            # 按关联度排序
            matches.sort(key=lambda m: m.relevance_score, reverse=True)
            matches = matches[:10]

            return SignalMatchResult(
                keywords=keywords,
                matches=matches,
                overall_risk_boost=min(1.0, max(0.0, data.get("overall_risk_boost", 0.0))),
                risk_dimension_boosts=data.get("risk_dimension_boosts", {}),
                analysis_summary=data.get("analysis_summary", ""),
            )

        except Exception as e:
            logger.error("SignalMatcher: 关联评估失败 %s", e)
            # 降级：基于关键词命中做简单匹配
            return self._fallback_match(keywords, signals, events)

    def _fallback_match(
        self,
        keywords: List[str],
        signals: list,
        events: list,
    ) -> SignalMatchResult:
        """降级：基于关键词命中的简单匹配"""
        matches: List[SignalMatch] = []

        for s in signals[:10]:
            hit_count = sum(1 for kw in keywords if kw in s.title)
            if hit_count > 0:
                relevance = min(1.0, hit_count * 0.3)
                matches.append(SignalMatch(
                    signal_id=s.signal_id,
                    title=s.title,
                    source_platform=s.source_platform,
                    relevance_score=relevance,
                    risk_impact="medium" if relevance > 0.5 else "low",
                    risk_dimension="时事踩雷",
                    impact_description=f"文案关键词命中当前热搜: {s.title}",
                    signal_type="hotlist",
                    appearance_count=s.appearance_count,
                    rank=s.rank,
                ))

        for e in events[:5]:
            hit_count = sum(1 for kw in keywords if kw in e.title)
            if hit_count > 0:
                relevance = min(1.0, hit_count * 0.3)
                matches.append(SignalMatch(
                    signal_id=e.event_id,
                    title=e.title,
                    source_platform=e.category,
                    relevance_score=relevance,
                    risk_impact="medium" if relevance > 0.5 else "low",
                    risk_dimension="时事踩雷",
                    impact_description=f"文案关键词命中种子事件: {e.title}",
                    signal_type="seed_event",
                    appearance_count=int(e.signal_strength * 10),
                ))

        matches.sort(key=lambda m: m.relevance_score, reverse=True)

        boost = min(1.0, len(matches) * 0.1) if matches else 0.0
        return SignalMatchResult(
            keywords=keywords,
            matches=matches[:10],
            overall_risk_boost=boost,
            risk_dimension_boosts={"时事踩雷": boost} if matches else {},
            analysis_summary=f"关键词命中 {len(matches)} 条热点（降级模式）" if matches else "无相关热点",
        )
