"""APScheduler定时调度器 - 信号采集调度"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import SeedEventRecord, SignalRecord
from backend.services.signal.fetcher import HotlistFetcher
from backend.services.signal.rss_fetcher import RssFetcher
from backend.services.signal.incremental import IncrementalDetector
from backend.services.signal.keyword_extractor import KeywordExtractor
from backend.services.signal.deep_crawler import DeepCrawler
from backend.services.signal.event_detector import EventDetector
from backend.services.signal.models import Signal, SeedEvent, EventCategory

logger = logging.getLogger(__name__)

SCHEDULE_PRESETS = {
    "realtime": {
        "hotlist_interval": 300,
        "rss_interval": 1800,
        "deep_crawl_threshold": 0.7,
        "event_detect_interval": 3600,
    },
    "standard": {
        "hotlist_interval": 600,
        "rss_interval": 3600,
        "deep_crawl_threshold": 0.7,
        "event_detect_interval": 3600,
    },
    "economy": {
        "hotlist_interval": 1800,
        "rss_interval": 7200,
        "deep_crawl_threshold": 0.9,
        "event_detect_interval": 7200,
    },
    "manual": {
        "hotlist_interval": 0,
        "rss_interval": 0,
        "deep_crawl_threshold": 1.0,
        "event_detect_interval": 0,
    },
}


def _load_signal_config() -> dict:
    """加载信号采集配置"""
    try:
        with open(settings.SIGNAL_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning("SignalScheduler: 配置加载失败，使用默认值 %s", e)
        return {"signal": {}}


class SignalScheduler:
    """信号采集调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.fetcher = HotlistFetcher()
        self.rss_fetcher = RssFetcher()
        self.event_detector = EventDetector()
        self.keyword_extractor = KeywordExtractor()
        self.deep_crawler = DeepCrawler()
        self.config = _load_signal_config()
        self.current_mode: str = "manual"  # 默认手动模式，不自动启动
        self._platform_map: Dict[str, str] = {}
        self._load_platform_map()

    def _load_platform_map(self):
        """加载平台ID到名称的映射"""
        platforms = self.config.get("signal", {}).get("hotlist", {}).get("platforms", [])
        for p in platforms:
            if isinstance(p, dict):
                self._platform_map[p.get("id", "")] = p.get("name", p.get("id", ""))
            else:
                self._platform_map[str(p)] = str(p)

    @property
    def is_running(self) -> bool:
        return self.scheduler.running

    def start(self, mode: str = "standard") -> bool:
        """启动调度器"""
        if self.scheduler.running:
            self.stop()

        preset = SCHEDULE_PRESETS.get(mode)
        if not preset:
            logger.warning("SignalScheduler: 未知模式 %s", mode)
            return False

        if mode == "manual":
            self.current_mode = mode
            logger.info("SignalScheduler: 手动模式，不启动自动调度")
            return True

        self.current_mode = mode

        # 热榜定时任务
        if preset["hotlist_interval"] > 0:
            self.scheduler.add_job(
                self._crawl_hotlist,
                IntervalTrigger(seconds=preset["hotlist_interval"]),
                id="crawl_hotlist",
                replace_existing=True,
            )

        # RSS定时任务
        if preset["rss_interval"] > 0:
            self.scheduler.add_job(
                self._crawl_rss,
                IntervalTrigger(seconds=preset["rss_interval"]),
                id="crawl_rss",
                replace_existing=True,
            )

        # 事件检测定时任务
        if preset["event_detect_interval"] > 0:
            self.scheduler.add_job(
                self._detect_events,
                IntervalTrigger(seconds=preset["event_detect_interval"]),
                id="detect_events",
                replace_existing=True,
            )

        self.scheduler.start()
        logger.info("SignalScheduler: 启动模式=%s", mode)
        return True

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.current_mode = "manual"
        logger.info("SignalScheduler: 已停止")

    async def _crawl_hotlist(self):
        """定时热榜爬取→增量检测→存储"""
        logger.info("SignalScheduler: 开始热榜爬取")
        try:
            results = await self.fetcher.fetch_all()
            total = sum(len(v) for v in results.values())
            logger.info("SignalScheduler: 热榜爬取完成，共 %d 条信号", total)

            # 增量检测
            db: Session = SessionLocal()
            try:
                detector = IncrementalDetector(db)
                incremental = await detector.detect(results)
                new_count = len(incremental.get("new", []))
                changed_count = len(incremental.get("changed", []))
                logger.info(
                    "SignalScheduler: 增量检测完成 - 新上榜 %d, 排名变化 %d",
                    new_count, changed_count,
                )
            except Exception as e:
                logger.error("SignalScheduler: 增量检测失败 %s", e)
            finally:
                db.close()

        except Exception as e:
            logger.error("SignalScheduler: 热榜爬取失败 %s", e)

    async def _crawl_rss(self):
        """定时RSS爬取"""
        logger.info("SignalScheduler: 开始RSS爬取")
        try:
            feeds = self.config.get("signal", {}).get("rss", {}).get("feeds", [])
            if not feeds:
                logger.info("SignalScheduler: 无RSS源配置")
                return

            results = await self.rss_fetcher.fetch_all(feeds)
            total = sum(len(v) for v in results.values())
            logger.info("SignalScheduler: RSS爬取完成，共 %d 条信号", total)

            # 增量检测
            db: Session = SessionLocal()
            try:
                detector = IncrementalDetector(db)
                await detector.detect(results)
            except Exception as e:
                logger.error("SignalScheduler: RSS增量检测失败 %s", e)
            finally:
                db.close()

        except Exception as e:
            logger.error("SignalScheduler: RSS爬取失败 %s", e)

    async def _detect_events(self):
        """定时事件检测→深度爬取触发"""
        logger.info("SignalScheduler: 开始事件检测")
        try:
            db: Session = SessionLocal()
            try:
                # 获取最近的信号
                cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=2)
                recent_signals = (
                    db.query(SignalRecord)
                    .filter(SignalRecord.last_seen >= cutoff)
                    .all()
                )

                if not recent_signals:
                    logger.info("SignalScheduler: 无近期信号，跳过事件检测")
                    return

                # 转换为Signal对象
                signals = self._records_to_signals(recent_signals)

                # 事件检测
                events = await self.event_detector.detect_events(signals)
                logger.info("SignalScheduler: 检测到 %d 个事件", len(events))

                # 深度爬取触发
                preset = SCHEDULE_PRESETS.get(self.current_mode, SCHEDULE_PRESETS["standard"])
                threshold = preset.get("deep_crawl_threshold", 0.7)

                for event in events:
                    # 保存种子事件
                    self._save_seed_event(db, event)

                    # 信号强度达标触发深度爬取
                    if event.signal_strength >= threshold:
                        logger.info(
                            "SignalScheduler: 事件 '%s' 信号强度 %.2f >= %.2f，触发深度爬取",
                            event.title, event.signal_strength, threshold,
                        )
                        await self._trigger_deep_crawl(event, db)

                db.commit()

            finally:
                db.close()

        except Exception as e:
            logger.error("SignalScheduler: 事件检测失败 %s", e)

    async def _trigger_deep_crawl(self, event: SeedEvent, db: Session):
        """触发深度爬取"""
        try:
            # LLM关键词提取
            keywords = await self.keyword_extractor.extract(
                event.title, event.description
            )

            # 逐个关键词爬取
            for kw in keywords[:3]:  # 限制最多3个关键词
                comments = await self.deep_crawler.crawl_comments(kw)
                event.comments.extend(comments)
                logger.info(
                    "SignalScheduler: 关键词 '%s' 爬取到 %d 条评论",
                    kw.keyword, len(comments),
                )

            # 更新种子事件记录
            event_record = (
                db.query(SeedEventRecord)
                .filter(SeedEventRecord.event_id == event.event_id)
                .first()
            )
            if event_record:
                event_record.comments_json = json.dumps([
                    {
                        "comment_id": c.comment_id,
                        "platform": c.platform,
                        "content": c.content[:200],
                        "sentiment": c.sentiment,
                        "sentiment_score": c.sentiment_score,
                        "confidence": c.confidence,
                    }
                    for c in event.comments
                ], ensure_ascii=False)
                event_record.crawl_depth = "deep"

        except Exception as e:
            logger.error("SignalScheduler: 深度爬取失败 %s", e)

    def _save_seed_event(self, db: Session, event: SeedEvent):
        """保存种子事件到数据库"""
        existing = (
            db.query(SeedEventRecord)
            .filter(SeedEventRecord.title == event.title)
            .first()
        )
        if existing:
            # 更新
            existing.signal_strength = max(existing.signal_strength, event.signal_strength)
            existing.updated_at = datetime.now(timezone.utc)
            existing.source_platforms = json.dumps(
                list(set(s.source_platform for s in event.sources))
            )
            if event.crawl_depth.value > existing.crawl_depth:
                existing.crawl_depth = event.crawl_depth.value
            return existing

        record = SeedEventRecord(
            event_id=event.event_id,
            title=event.title,
            description=event.description,
            category=event.category.value if event.category else "society",
            signal_strength=event.signal_strength,
            source_platforms=json.dumps(
                list(set(s.source_platform for s in event.sources))
            ),
            source_urls=json.dumps(
                [s.url for s in event.sources if s.url]
            ),
            comments_json="[]",
            related_events=json.dumps(event.related_events),
            causal_parents=json.dumps(event.causal_parents),
            causal_children=json.dumps(event.causal_children),
            crawl_depth=event.crawl_depth.value,
        )
        db.add(record)
        return record

    @staticmethod
    def _records_to_signals(records) -> list:
        """将SQLAlchemy记录转换为Signal对象"""
        signals = []
        for r in records:
            s = Signal(
                signal_id=r.signal_id,
                source_platform=r.source_platform,
                title=r.title,
                url=r.url,
                rank=r.rank,
                first_seen=r.first_seen,
                last_seen=r.last_seen,
                appearance_count=r.appearance_count,
                is_new=r.is_new,
                signal_type=r.signal_type,
            )
            if r.category:
                try:
                    s.category = EventCategory(r.category)
                except ValueError:
                    pass
            signals.append(s)
        return signals
