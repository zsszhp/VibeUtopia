"""热榜聚合引擎 - 基于NewsNow API"""

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from backend.services.signal.models import Signal, SignalType, RankPoint

logger = logging.getLogger(__name__)


class HotlistFetcher:
    """热榜数据抓取器"""

    API_URL = "https://newsnow.busiyi.world/api/s"
    REQUEST_INTERVAL = 0.1  # 100ms间隔
    MAX_RETRIES = 2
    RETRY_BACKOFF = (3, 5)
    TIMEOUT = 10.0

    PLATFORM_IDS = [
        "weibo", "baidu", "zhihu", "bilibili-hot-search",
        "douyin", "toutiao", "tieba", "thepaper",
        "wallstreetcn-hot", "cls-hot", "ifeng",
    ]

    async def fetch_platform(self, platform_id: str) -> List[Signal]:
        """抓取单个平台热搜，带重试和错误处理"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://newsnow.busiyi.world/",
        }
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    resp = await client.get(
                        self.API_URL,
                        params={"id": platform_id, "latest": ""},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return self._parse_response(data, platform_id)
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "HotlistFetcher: %s 返回HTTP %s (attempt %d/%d)",
                    platform_id, e.response.status_code, attempt + 1, self.MAX_RETRIES + 1,
                )
            except httpx.RequestError as e:
                logger.warning(
                    "HotlistFetcher: %s 请求失败 %s (attempt %d/%d)",
                    platform_id, type(e).__name__, attempt + 1, self.MAX_RETRIES + 1,
                )
            except Exception as e:
                logger.error(
                    "HotlistFetcher: %s 解析异常 %s", platform_id, e,
                )
                break

            if attempt < self.MAX_RETRIES:
                backoff = random.uniform(*self.RETRY_BACKOFF)
                logger.info("HotlistFetcher: %s 等待 %.1fs 后重试", platform_id, backoff)
                await asyncio.sleep(backoff)

        return []

    async def fetch_all(
        self, platform_ids: Optional[List[str]] = None
    ) -> Dict[str, List[Signal]]:
        """并发抓取多个平台，返回 {platform_id: [Signal]}"""
        if platform_ids is None:
            platform_ids = self.PLATFORM_IDS

        results: Dict[str, List[Signal]] = {}
        for i, pid in enumerate(platform_ids):
            if i > 0:
                await asyncio.sleep(self.REQUEST_INTERVAL)
            signals = await self.fetch_platform(pid)
            results[pid] = signals
            logger.info("HotlistFetcher: %s 获取到 %d 条信号", pid, len(signals))

        return results

    def _parse_response(self, data: dict, platform_id: str) -> List[Signal]:
        """解析NewsNow API响应为Signal列表"""
        items = data.get("items", [])
        if not items:
            logger.debug("HotlistFetcher: %s 无数据", platform_id)
            return []

        now = datetime.now(timezone.utc)
        signals: List[Signal] = []

        for idx, item in enumerate(items):
            title = item.get("title", "").strip()
            if not title:
                continue

            signal = Signal(
                signal_id=str(uuid.uuid4()),
                source_platform=platform_id,
                title=title,
                url=item.get("url") or item.get("mobileUrl"),
                rank=idx + 1,
                rank_timeline=[RankPoint(timestamp=now, rank=idx + 1)],
                first_seen=now,
                last_seen=now,
                appearance_count=1,
                is_new=True,
                signal_type=SignalType.HOTLIST,
                raw_data=item,
            )
            signals.append(signal)

        return signals
