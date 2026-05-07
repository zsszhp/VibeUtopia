"""事件检测器 - 聚类+因果推理+信号强度"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.signal.models import (
    Signal, SeedEvent, AnnotatedComment, EventCategory, CrawlDepth, EventStatus
)

logger = logging.getLogger(__name__)


class SignalStrengthEvaluator:
    """信号强度评估器"""

    WEIGHTS = {
        "spread": 0.25,
        "velocity": 0.20,
        "resonance": 0.25,
        "engagement": 0.15,
        "persistence": 0.15,
    }

    TOTAL_PLATFORMS = 11

    def evaluate(self, event: SeedEvent) -> float:
        """综合评估信号强度 0-1"""
        scores = {
            "spread": self._spread_score(event),
            "velocity": self._velocity_score(event),
            "resonance": self._resonance_score(event),
            "engagement": self._engagement_score(event),
            "persistence": self._persistence_score(event),
        }
        weighted = sum(
            self.WEIGHTS[k] * v for k, v in scores.items()
        )
        return round(min(1.0, max(0.0, weighted)), 3)

    def _spread_score(self, event: SeedEvent) -> float:
        """传播广度: 出现在N个平台 → N/11"""
        platforms = set(s.source_platform for s in event.sources)
        return min(1.0, len(platforms) / self.TOTAL_PLATFORMS)

    def _velocity_score(self, event: SeedEvent) -> float:
        """上榜速度: 从首次出现到进入Top3的时间越短分越高"""
        # 基于rank_timeline中是否有快速进入Top3的记录
        min_rank = None
        for s in event.sources:
            if s.rank is not None:
                if min_rank is None or s.rank < min_rank:
                    min_rank = s.rank

        if min_rank is None:
            return 0.3

        if min_rank <= 3:
            return 1.0
        elif min_rank <= 10:
            return 0.7
        elif min_rank <= 20:
            return 0.5
        else:
            return 0.3

    def _resonance_score(self, event: SeedEvent) -> float:
        """多平台共振: 同时出现在多个平台 = 高分"""
        platforms = set(s.source_platform for s in event.sources)
        count = len(platforms)
        if count >= 3:
            return 1.0
        elif count >= 2:
            return 0.7
        else:
            return 0.3

    def _engagement_score(self, event: SeedEvent) -> float:
        """互动强度: 评论数多+情感极性大 = 高分"""
        if not event.comments:
            return 0.3

        total = len(event.comments)
        polarized = sum(
            1 for c in event.comments
            if abs(c.sentiment_score) > 0.5
        )
        polar_ratio = polarized / max(total, 1)

        if total >= 30 and polar_ratio > 0.4:
            return 1.0
        elif total >= 15 and polar_ratio > 0.3:
            return 0.7
        elif total >= 5:
            return 0.5
        else:
            return 0.3

    def _persistence_score(self, event: SeedEvent) -> float:
        """持续性: 在榜时间越长越重要"""
        if not event.sources:
            return 0.2

        # 基于first_seen和last_seen的时间差
        first = min(s.first_seen for s in event.sources)
        last = max(s.last_seen for s in event.sources)
        duration_hours = (last - first).total_seconds() / 3600

        if duration_hours >= 24:
            return 1.0
        elif duration_hours >= 12:
            return 0.7
        elif duration_hours >= 6:
            return 0.4
        else:
            return 0.2


class CausalReasoner:
    """因果链推理器"""

    CAUSAL_PROMPT = """已知以下事件序列：
{event_timeline}

请分析这些事件之间的因果关系：
1. 哪些事件是其他事件的原因？
2. 哪些事件是独立发生的？
3. 是否存在隐藏的因果关系？

输出JSON格式：
{{
    "causal_chains": [
        {{
            "cause": "事件A标题",
            "effect": "事件B标题",
            "confidence": 0.8,
            "reasoning": "因为..."
        }}
    ],
    "independent_events": ["事件C标题"]
}}"""

    async def reason(self, events: List[SeedEvent]) -> None:
        """推理事件间因果关系，更新事件的causal_parents/causal_children"""
        if len(events) < 2:
            return

        timeline = "\n".join(
            f"- [{e.created_at.strftime('%H:%M')}] {e.title}"
            for e in sorted(events, key=lambda x: x.created_at)
        )

        prompt = self.CAUSAL_PROMPT.format(event_timeline=timeline)

        try:
            response = await call_llm(
                prompt,
                system="你是一个事件因果分析专家，擅长分析事件之间的因果关联。",
                task_type="persona_simulation",
            )
            data = parse_llm_json(response, fallback={"causal_chains": [], "independent_events": []})

            # 构建标题到事件的映射
            title_map = {e.title: e for e in events}

            for chain in data.get("causal_chains", []):
                cause_title = chain.get("cause", "")
                effect_title = chain.get("effect", "")
                cause_event = title_map.get(cause_title)
                effect_event = title_map.get(effect_title)

                if cause_event and effect_event:
                    effect_event.causal_parents.append(cause_event.event_id)
                    cause_event.causal_children.append(effect_event.event_id)

        except Exception as e:
            logger.warning("CausalReasoner: 因果推理失败 %s", e)


class EventDetector:
    """事件检测器"""

    def __init__(self):
        self.strength_evaluator = SignalStrengthEvaluator()
        self.causal_reasoner = CausalReasoner()

    async def detect_events(
        self,
        signals: List[Signal],
        comments: Optional[List[AnnotatedComment]] = None,
    ) -> List[SeedEvent]:
        """从信号中检测事件"""
        if not signals:
            return []

        # Step 1: 主题聚类
        clusters = self.cluster_events(signals)
        logger.info("EventDetector: 聚类得到 %d 个事件组", len(clusters))

        # Step 2: 合并为种子事件
        events: List[SeedEvent] = []
        for cluster in clusters:
            event = self._merge_cluster(cluster)
            events.append(event)

        # Step 3: 信号强度评估
        for event in events:
            event.signal_strength = self.strength_evaluator.evaluate(event)

        # Step 4: 附加评论（如果有）
        if comments:
            self._attach_comments(events, comments)

        # Step 5: 因果推理
        if len(events) > 1:
            await self.causal_reasoner.reason(events)

        # Step 6: 根据强度标记爬取深度
        for event in events:
            if event.signal_strength >= 0.7:
                event.crawl_depth = CrawlDepth.DEEP
            elif event.signal_strength >= 0.4:
                event.crawl_depth = CrawlDepth.SHALLOW
            else:
                event.crawl_depth = CrawlDepth.NONE

        return events

    def cluster_events(self, signals: List[Signal]) -> List[List[Signal]]:
        """基于标题相似度聚类（关键词Jaccard系数）"""
        if not signals:
            return []

        # 提取关键词集合
        signal_keywords: List[Set[str]] = []
        for s in signals:
            keywords = self._extract_keywords(s.title)
            signal_keywords.append(keywords)

        # Union-Find 聚类
        n = len(signals)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        threshold = 0.4
        for i in range(n):
            if not signal_keywords[i]:
                continue
            for j in range(i + 1, n):
                if not signal_keywords[j]:
                    continue
                sim = self._jaccard(signal_keywords[i], signal_keywords[j])
                if sim >= threshold:
                    union(i, j)

        # 收集聚类
        cluster_map: Dict[int, List[Signal]] = defaultdict(list)
        for i in range(n):
            root = find(i)
            cluster_map[root].append(signals[i])

        # 过滤太小的聚类（单信号也保留）
        return list(cluster_map.values())

    def _merge_cluster(self, cluster: List[Signal]) -> SeedEvent:
        """合并聚类为种子事件"""
        # 使用出现平台最多的信号标题作为主标题
        # 如果有多个平台，选择rank最高的标题
        best_signal = min(
            cluster,
            key=lambda s: s.rank if s.rank is not None else 999,
        )

        # 生成描述：汇总所有来源标题
        descriptions = set()
        for s in cluster[:5]:
            if s.title != best_signal.title:
                descriptions.add(s.title)
        description = f"来源：{best_signal.source_platform}"
        if descriptions:
            description += f"。其他表述：{'；'.join(list(descriptions)[:3])}"

        # 推断事件分类
        category = self._infer_category(cluster)

        return SeedEvent(
            title=best_signal.title,
            description=description,
            category=category,
            sources=cluster,
            comments=[],
        )

    def _attach_comments(
        self, events: List[SeedEvent], comments: List[AnnotatedComment]
    ) -> None:
        """将评论关联到事件（简单策略：按平台匹配）"""
        event_platforms: Dict[str, Set[str]] = {}
        for event in events:
            platforms = set(s.source_platform for s in event.sources)
            event_platforms[event.event_id] = platforms

        for comment in comments:
            # 将评论分配到匹配平台的事件
            for event in events:
                if comment.platform in event_platforms.get(event.event_id, set()):
                    event.comments.append(comment)
                    break

    @staticmethod
    def _extract_keywords(title: str) -> Set[str]:
        """从标题中提取关键词（简单分词：2-4字组合）"""
        # 去除标点和特殊字符
        clean = re.sub(r"[^\u4e00-\u9fff\w]", "", title)
        keywords: Set[str] = set()

        # 2-4字滑动窗口
        for length in (2, 3, 4):
            for i in range(len(clean) - length + 1):
                word = clean[i : i + length]
                if word:
                    keywords.add(word)

        return keywords

    @staticmethod
    def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
        """Jaccard相似系数"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union else 0.0

    @staticmethod
    def _infer_category(signals: List[Signal]) -> EventCategory:
        """推断事件分类"""
        # 优先使用信号自带的分类
        for s in signals:
            if s.category:
                return s.category

        # 基于平台和标题关键词推断
        title = " ".join(s.title for s in signals)
        platforms = set(s.source_platform for s in signals)

        # 财经平台
        finance_platforms = {"wallstreetcn-hot", "cls-hot"}
        if platforms & finance_platforms:
            return EventCategory.ECONOMY

        # 关键词分类
        politics_kw = {"政策", "法规", "政府", "国务院", "人大", "外交", "制裁"}
        economy_kw = {"股市", "A股", "经济", "GDP", "加息", "通胀", "房价"}
        tech_kw = {"AI", "科技", "芯片", "5G", "互联网", "苹果", "华为"}

        for kw in politics_kw:
            if kw in title:
                return EventCategory.POLITICS
        for kw in economy_kw:
            if kw in title:
                return EventCategory.ECONOMY
        for kw in tech_kw:
            if kw in title:
                return EventCategory.TECH

        return EventCategory.SOCIETY
