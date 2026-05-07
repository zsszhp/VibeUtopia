"""RSS补充源抓取器"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import httpx

from backend.services.signal.models import Signal, SignalType, EventCategory

logger = logging.getLogger(__name__)


class RssFetcher:
    """RSS源抓取器"""

    TIMEOUT = 15.0

    async def fetch_feed(self, feed_config: dict) -> List[Signal]:
        """抓取单个RSS源"""
        feed_url = feed_config.get("url", "")
        feed_id = feed_config.get("id", "unknown")
        feed_category = feed_config.get("category", "")

        if not feed_url:
            logger.warning("RssFetcher: %s 无URL配置", feed_id)
            return []

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.get(feed_url)
                resp.raise_for_status()
        except httpx.RequestError as e:
            logger.warning("RssFetcher: %s 请求失败 %s", feed_id, type(e).__name__)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("RssFetcher: %s HTTP %s", feed_id, e.response.status_code)
            return []

        try:
            import feedparser
            parsed = feedparser.parse(resp.text)
        except Exception as e:
            logger.error("RssFetcher: %s 解析失败 %s", feed_id, e)
            return []

        if parsed.bozo and not parsed.entries:
            logger.warning("RssFetcher: %s RSS格式异常", feed_id)
            return []

        signals: List[Signal] = []
        for entry in parsed.entries:
            signal = self._parse_entry(entry, feed_config)
            if signal:
                signals.append(signal)

        logger.info("RssFetcher: %s 获取到 %d 条信号", feed_id, len(signals))
        return signals

    async def fetch_all(self, feed_configs: List[dict]) -> Dict[str, List[Signal]]:
        """批量抓取所有RSS源"""
        results: Dict[str, List[Signal]] = {}
        for fc in feed_configs:
            feed_id = fc.get("id", "unknown")
            signals = await self.fetch_feed(fc)
            results[feed_id] = signals
        return results

    def _parse_entry(self, entry, feed_config: dict) -> Optional[Signal]:
        """解析RSS条目为Signal"""
        title = getattr(entry, "title", "").strip()
        if not title:
            return None

        link = getattr(entry, "link", "")
        feed_id = feed_config.get("id", "unknown")
        feed_category = feed_config.get("category", "")

        # 解析发布时间
        published = getattr(entry, "published_parsed", None)
        if published:
            try:
                from time import mktime
                pub_dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
            except Exception:
                pub_dt = datetime.now(timezone.utc)
        else:
            pub_dt = datetime.now(timezone.utc)

        # 新鲜度过滤
        freshness_days = feed_config.get("max_age_days", 1)
        if (datetime.now(timezone.utc) - pub_dt).days > freshness_days:
            return None

        category = None
        category_map = {
            "tech": EventCategory.TECH,
            "finance": EventCategory.ECONOMY,
            "news": EventCategory.SOCIETY,
            "politics": EventCategory.POLITICS,
            "culture": EventCategory.CULTURE,
        }
        if feed_category in category_map:
            category = category_map[feed_category]

        return Signal(
            signal_id=str(uuid.uuid4()),
            source_platform=feed_id,
            title=title,
            url=link,
            signal_type=SignalType.RSS,
            category=category,
            first_seen=pub_dt,
            last_seen=pub_dt,
        )

    def filter_by_freshness(
        self, signals: List[Signal], max_age_days: int = 1
    ) -> List[Signal]:
        """过滤超出新鲜度窗口的条目"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        return [s for s in signals if s.first_seen >= cutoff]
