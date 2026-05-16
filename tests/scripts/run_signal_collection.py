#!/usr/bin/env python3
"""T7 深度信号采集 - 手动运行一次采集流程"""

import asyncio
import logging
import sys
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/signal_collection.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


async def run_signal_collection():
    """手动运行一次信号采集"""
    logger.info("=" * 60)
    logger.info("T7 深度信号采集 - 手动运行")
    logger.info("开始时间：%s", datetime.now().isoformat())
    logger.info("=" * 60)
    
    from backend.database import SessionLocal
    from backend.services.signal.fetcher import HotlistFetcher
    from backend.services.signal.rss_fetcher import RssFetcher
    from backend.services.signal.incremental import IncrementalDetector
    from backend.services.signal.event_detector import EventDetector
    from backend.services.signal.models import Signal
    from backend.models import SignalRecord
    
    db = SessionLocal()
    fetcher = HotlistFetcher()
    
    try:
        # Step 1: 热榜采集
        logger.info("\n【Step 1】开始热榜采集...")
        hotlist_results = await fetcher.fetch_all()
        hotlist_signals = []
        for platform_signals in hotlist_results.values():
            hotlist_signals.extend(platform_signals)
        logger.info("热榜采集完成：共 %d 条信号", len(hotlist_signals))
        
        # Step 2: RSS 采集
        logger.info("\n【Step 2】开始 RSS 采集...")
        rss_config = [
            {"id": "hacker-news", "name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "tech"},
            {"id": "yahoo-finance", "name": "雅虎财经", "url": "https://finance.yahoo.com/news/rssindex", "category": "finance"},
        ]
        rss_fetcher = RssFetcher()
        rss_results = await rss_fetcher.fetch_all(rss_config)
        rss_signals = []
        for feed_signals in rss_results.values():
            rss_signals.extend(feed_signals)
        logger.info("RSS 采集完成：共 %d 条信号", len(rss_signals))
        
        # Step 3: 增量检测
        logger.info("\n【Step 3】开始增量检测...")
        detector = IncrementalDetector(db)
        
        # 转换为 fetch_all 返回的 dict 格式
        signal_dict = {}
        for signal in hotlist_signals:
            platform = signal.source_platform
            if platform not in signal_dict:
                signal_dict[platform] = []
            signal_dict[platform].append(signal)
        
        incremental_result = await detector.detect(signal_dict)
        new_count = len(incremental_result.get("new", []))
        changed_count = len(incremental_result.get("changed", []))
        logger.info("增量检测完成：新上榜 %d 条，排名变化 %d 条", new_count, changed_count)
        
        # Step 4: 事件检测与聚类
        logger.info("\n【Step 4】开始事件检测...")
        event_detector = EventDetector()
        
        # 从数据库获取近期信号
        from sqlalchemy import desc
        recent_records = (
            db.query(SignalRecord)
            .order_by(desc(SignalRecord.last_seen))
            .limit(200)
            .all()
        )
        
        events = []
        if recent_records:
            # 转换为 Signal 对象
            from backend.services.signal.fetcher import HotlistFetcher
            signals = []
            for record in recent_records:
                signal = Signal(
                    signal_id=record.signal_id,
                    source_platform=record.source_platform,
                    title=record.title,
                    url=record.url,
                    rank=record.rank,
                    rank_timeline=record.rank_timeline or [],
                    first_seen=record.first_seen,
                    last_seen=record.last_seen,
                    appearance_count=record.appearance_count,
                    is_new=record.is_new,
                    signal_type=record.signal_type or "hotlist",
                )
                signals.append(signal)
            
        events = event_detector.cluster_events(signals)
        logger.info("事件检测完成：检测到 %d 个事件簇", len(events))
        
        # 打印事件摘要（合并为 SeedEvent）
        for i, cluster in enumerate(events[:5], 1):
            if cluster:
                event = event_detector._merge_cluster(cluster)
                logger.info("  事件%d: %s (强度：%.2f, 平台数：%d)",
                           i, event.title, event.signal_strength, len(event.sources))
        else:
            logger.info("无近期信号，跳过事件检测")
        
        # Step 5: 统计摘要
        logger.info("\n" + "=" * 60)
        logger.info("【采集统计摘要】")
        logger.info("  - 热榜信号：%d 条", len(hotlist_signals))
        logger.info("  - RSS 信号：%d 条", len(rss_signals))
        logger.info("  - 增量信号：新上榜 %d 条，排名变化 %d 条", new_count, changed_count)
        logger.info("  - 事件簇数：%d 个", len(events))
        logger.info("结束时间：%s", datetime.now().isoformat())
        logger.info("=" * 60)
        
        # 返回采集结果
        return {
            "hotlist_count": len(hotlist_signals),
            "rss_count": len(rss_signals),
            "new_signals": new_count,
            "changed_signals": changed_count,
            "event_count": len(events),
            "success": True
        }
        
    except Exception as e:
        logger.error("信号采集失败：%s", e, exc_info=True)
        return {
            "hotlist_count": 0,
            "rss_count": 0,
            "incremental_count": 0,
            "event_count": 0,
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


if __name__ == "__main__":
    result = asyncio.run(run_signal_collection())
    
    # 输出 JSON 结果供后续处理
    import json
    print("\n采集结果 JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 退出码
    sys.exit(0 if result.get("success") else 1)
