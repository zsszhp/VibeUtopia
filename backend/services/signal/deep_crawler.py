"""深度评论爬取器 - API优先策略"""

import logging
import uuid
from typing import Dict, List, Optional

import httpx

from backend.services.signal.models import SearchKeyword, AnnotatedComment
from backend.services.signal.sentiment import SentimentAnnotator

logger = logging.getLogger(__name__)


class ApiCrawler:
    """平台API爬取器"""

    TIMEOUT = 15.0

    async def crawl_weibo(self, keyword: str, max_comments: int = 50) -> List[dict]:
        """微博搜索 - 通过微博移动端搜索页"""
        comments: List[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # 微博移动端搜索API
                resp = await client.get(
                    "https://m.weibo.cn/api/container/getIndex",
                    params={
                        "containerid": f"100103type=1&q={keyword}",
                        "page_type": "searchall",
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    cards = (
                        data.get("data", {})
                        .get("cards", [])
                    )
                    for card in cards:
                        card_group = card.get("card_group", [card])
                        for item in card_group:
                            mblog = item.get("mblog", {})
                            text = mblog.get("text", "")
                            # 去除HTML标签
                            import re
                            text = re.sub(r"<[^>]+>", "", text).strip()
                            if text:
                                comments.append({
                                    "content": text,
                                    "platform": "weibo",
                                    "like_count": mblog.get("attitudes_count", 0),
                                    "reply_count": mblog.get("comments_count", 0),
                                    "user_type": "kol" if mblog.get("user", {}).get("verified_type") in (0, 1) else "ordinary",
                                })
                                if len(comments) >= max_comments:
                                    return comments
        except Exception as e:
            logger.warning("ApiCrawler: 微博爬取失败 %s", e)
        return comments

    async def crawl_zhihu(self, keyword: str, max_comments: int = 50) -> List[dict]:
        """知乎搜索API"""
        comments: List[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.get(
                    "https://www.zhihu.com/api/v4/search_v3",
                    params={
                        "q": keyword,
                        "t": "general",
                        "correction": 1,
                        "offset": 0,
                        "limit": min(max_comments, 20),
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", []):
                        obj = item.get("object", {})
                        content = obj.get("content", "") or obj.get("excerpt", "")
                        # 去除HTML标签
                        import re
                        content = re.sub(r"<[^>]+>", "", content).strip()
                        if content:
                            comments.append({
                                "content": content[:500],
                                "platform": "zhihu",
                                "like_count": obj.get("voteup_count", 0),
                                "reply_count": obj.get("comment_count", 0),
                                "user_type": "ordinary",
                            })
                            if len(comments) >= max_comments:
                                return comments
        except Exception as e:
            logger.warning("ApiCrawler: 知乎爬取失败 %s", e)
        return comments

    async def crawl_bilibili(self, keyword: str, max_comments: int = 50) -> List[dict]:
        """B站搜索API"""
        comments: List[dict] = []
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                # B站搜索视频
                resp = await client.get(
                    "https://api.bilibili.com/x/web-interface/search/type",
                    params={
                        "search_type": "video",
                        "keyword": keyword,
                        "page_size": min(max_comments // 5, 10),
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": "https://www.bilibili.com",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("data", {}).get("result", [])
                    # 取搜索结果中的视频评论
                    for video in results[:5]:
                        aid = video.get("aid")
                        if not aid:
                            continue
                        # 获取视频评论
                        comment_resp = await client.get(
                            "https://api.bilibili.com/x/v2/reply",
                            params={
                                "type": 1,
                                "oid": aid,
                                "sort": 1,  # 按热度
                                "ps": 10,
                            },
                            headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                "Referer": "https://www.bilibili.com",
                            },
                        )
                        if comment_resp.status_code == 200:
                            cdata = comment_resp.json()
                            for reply in cdata.get("data", {}).get("replies", []) or []:
                                content = reply.get("content", {}).get("message", "").strip()
                                if content:
                                    comments.append({
                                        "content": content,
                                        "platform": "bilibili",
                                        "like_count": reply.get("like", 0),
                                        "reply_count": reply.get("rcount", 0),
                                        "user_type": "ordinary",
                                    })
                                    if len(comments) >= max_comments:
                                        return comments
        except Exception as e:
            logger.warning("ApiCrawler: B站爬取失败 %s", e)
        return comments


class DeepCrawler:
    """深度评论爬取器 - API优先策略"""

    def __init__(self):
        self.api_crawler = ApiCrawler()
        self.sentiment_annotator = SentimentAnnotator()

    async def crawl_comments(
        self, keyword: SearchKeyword, max_comments: int = 50
    ) -> List[AnnotatedComment]:
        """按关键词爬取评论并标注情感"""
        raw_comments: List[dict] = []

        platform_crawlers: Dict[str, callable] = {
            "微博": self.api_crawler.crawl_weibo,
            "知乎": self.api_crawler.crawl_zhihu,
            "B站": self.api_crawler.crawl_bilibili,
        }

        per_platform_limit = max(max_comments // len(keyword.platforms), 10)

        for platform_name in keyword.platforms:
            crawler = platform_crawlers.get(platform_name)
            if not crawler:
                logger.debug("DeepCrawler: 平台 %s 暂不支持API爬取", platform_name)
                continue

            try:
                results = await crawler(keyword.keyword, per_platform_limit)
                raw_comments.extend(results)
            except Exception as e:
                logger.warning(
                    "DeepCrawler: %s 爬取失败 keyword=%s error=%s",
                    platform_name, keyword.keyword, e,
                )

        # 去重（基于内容前50字符）
        seen = set()
        unique_comments = []
        for c in raw_comments:
            key = c["content"][:50]
            if key not in seen:
                seen.add(key)
                unique_comments.append(c)

        # 情感标注
        if unique_comments:
            texts = [c["content"] for c in unique_comments]
            sentiments = await self.sentiment_annotator.batch_annotate(texts)

            annotated: List[AnnotatedComment] = []
            for c, s in zip(unique_comments, sentiments):
                annotated.append(
                    AnnotatedComment(
                        comment_id=str(uuid.uuid4()),
                        platform=c.get("platform", ""),
                        content=c["content"],
                        sentiment=s["sentiment"],
                        sentiment_score=s["score"],
                        confidence=s["confidence"],
                        like_count=c.get("like_count"),
                        reply_count=c.get("reply_count"),
                        user_type=c.get("user_type"),
                    )
                )
            return annotated

        return []
