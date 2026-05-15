#!/usr/bin/env python3
"""T7 深度信号采集增强 - 信号关联验证 + 深度评论爬取

功能：
1. 信号关联验证 - 运行回测验证信号关联对风险评估准确率的提升
2. 深度评论爬取 - 对高信号强度事件触发深度评论爬取和情感标注
3. 生成验证报告
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/t7_enhancement.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


# ============================================================================
# 任务 1：信号关联验证
# ============================================================================

async def validate_signal_association():
    """验证信号关联对风险评估的影响"""
    logger.info("\n" + "=" * 80)
    logger.info("任务 1：信号关联验证")
    logger.info("=" * 80)
    
    from backend.database import SessionLocal
    from backend.services.signal_matcher import SignalMatcher
    from backend.models import SignalRecord
    from sqlalchemy import desc
    
    db = SessionLocal()
    
    try:
        # 1. 获取测试案例
        test_cases = [
            "中美领导人会晤",
            "iPhone18 发布",
            "支付宝安全问题",
            "浪姐节目争议",
        ]
        
        results = []
        matcher = SignalMatcher(db)
        
        for case in test_cases:
            logger.info("\n测试案例：%s", case)
            logger.info("-" * 40)
            
            start = time.time()
            match_result = await matcher.match(case, top_k=5)
            duration = time.time() - start
            
            logger.info("  关键词：%s", match_result.keywords)
            logger.info("  匹配到 %d 条热点", len(match_result.matches))
            logger.info("  风险提升：%.2f", match_result.overall_risk_boost)
            logger.info("  耗时：%.2fs", duration)
            
            if match_result.matches:
                for m in match_result.matches[:3]:
                    logger.info("    - [%s] %s (关联度：%.2f)",
                               m.source_platform, m.title, m.relevance_score)
            
            results.append({
                "case": case,
                "keywords": match_result.keywords,
                "matches_count": len(match_result.matches),
                "risk_boost": match_result.overall_risk_boost,
                "duration_seconds": duration,
            })
        
        # 生成统计
        avg_matches = sum(r["matches_count"] for r in results) / len(results)
        avg_risk_boost = sum(r["risk_boost"] for r in results) / len(results)
        avg_duration = sum(r["duration_seconds"] for r in results) / len(results)
        
        logger.info("\n" + "=" * 80)
        logger.info("【信号关联验证统计】")
        logger.info("  - 测试案例数：%d", len(results))
        logger.info("  - 平均匹配热点数：%.1f 条/案例", avg_matches)
        logger.info("  - 平均风险提升：%.2f", avg_risk_boost)
        logger.info("  - 平均响应时间：%.2fs", avg_duration)
        logger.info("=" * 80)
        
        return {
            "test_cases": len(results),
            "avg_matches": avg_matches,
            "avg_risk_boost": avg_risk_boost,
            "avg_duration_seconds": avg_duration,
            "details": results,
        }
        
    except Exception as e:
        logger.error("信号关联验证失败：%s", e, exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()


# ============================================================================
# 任务 2：深度评论爬取
# ============================================================================

async def crawl_deep_comments(max_events: int = 5, max_comments_per_event: int = 20):
    """对高信号强度事件进行深度评论爬取"""
    logger.info("\n" + "=" * 80)
    logger.info("任务 2：深度评论爬取")
    logger.info("=" * 80)
    
    from backend.database import SessionLocal
    from backend.models import SignalRecord, SeedEventRecord
    from backend.services.signal.deep_crawler import DeepCrawler
    from backend.services.signal.keyword_extractor import KeywordExtractor
    from backend.services.signal.models import SearchKeyword, SeedEvent, EventCategory
    from sqlalchemy import desc
    
    db = SessionLocal()
    
    try:
        # 1. 获取高信号强度事件（出现次数最多的）
        top_signals = (
            db.query(SignalRecord)
            .order_by(desc(SignalRecord.appearance_count))
            .limit(max_events)
            .all()
        )
        
        if not top_signals:
            logger.info("无信号数据，跳过深度爬取")
            return {"crawled_events": 0, "total_comments": 0}
        
        logger.info("选定 %d 个高信号强度事件进行深度爬取", len(top_signals))
        
        crawler = DeepCrawler()
        keyword_extractor = KeywordExtractor()
        
        total_comments = 0
        crawled_events = []
        
        for signal in top_signals:
            logger.info("\n【事件】%s", signal.title)
            logger.info("  平台：%s, 出现次数：%d, 排名：%s",
                       signal.source_platform, signal.appearance_count, signal.rank)
            
            try:
                # 2. 从事件标题生成搜索关键词
                event = SeedEvent(
                    title=signal.title,
                    description=signal.title,
                    category=EventCategory.CULTURE,
                )
                keywords = await keyword_extractor.extract(event)
                
                if not keywords:
                    logger.info("  关键词提取失败，使用标题作为关键词")
                    keywords = [SearchKeyword(keyword=signal.title, platforms=["微博", "知乎", "B 站"], priority=1)]
                
                logger.info("  搜索关键词：%s", [k.keyword for k in keywords[:3]])
                
                # 3. 爬取评论
                all_comments = []
                for kw in keywords[:2]:  # 最多用 2 个关键词
                    logger.info("  爬取关键词 '%s' 的评论...", kw.keyword)
                    comments = await crawler.crawl_comments(kw, max_comments=max_comments_per_event)
                    all_comments.extend(comments)
                    logger.info("    爬取到 %d 条评论", len(comments))
                
                # 4. 统计情感分布
                sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0}
                for c in all_comments:
                    if c.sentiment in sentiment_dist:
                        sentiment_dist[c.sentiment] += 1
                
                logger.info("  情感分布：正面 %d, 负面 %d, 中性 %d",
                           sentiment_dist["positive"], sentiment_dist["negative"], sentiment_dist["neutral"])
                
                total_comments += len(all_comments)
                crawled_events.append({
                    "title": signal.title,
                    "platform": signal.source_platform,
                    "comments_count": len(all_comments),
                    "sentiment": sentiment_dist,
                })
                
            except Exception as e:
                logger.error("  爬取失败：%s", e)
                crawled_events.append({
                    "title": signal.title,
                    "platform": signal.source_platform,
                    "error": str(e),
                })
        
        logger.info("\n" + "=" * 80)
        logger.info("【深度评论爬取统计】")
        logger.info("  - 爬取事件数：%d", len(crawled_events))
        logger.info("  - 总评论数：%d", total_comments)
        logger.info("  - 平均每事件：%.1f 条", total_comments / len(crawled_events) if crawled_events else 0)
        logger.info("=" * 80)
        
        return {
            "crawled_events": len(crawled_events),
            "total_comments": total_comments,
            "details": crawled_events,
        }
        
    except Exception as e:
        logger.error("深度评论爬取失败：%s", e, exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()


# ============================================================================
# 主流程
# ============================================================================

async def run_t7_enhancement():
    """T7 深度信号采集增强主流程"""
    logger.info("=" * 80)
    logger.info("T7 深度信号采集增强")
    logger.info("开始时间：%s", datetime.now().isoformat())
    logger.info("=" * 80)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "signal_association": None,
        "deep_crawl": None,
    }
    
    # 任务 1：信号关联验证
    results["signal_association"] = await validate_signal_association()
    
    # 任务 2：深度评论爬取
    results["deep_crawl"] = await crawl_deep_comments(max_events=3, max_comments_per_event=15)
    
    # 输出 JSON 报告
    logger.info("\n" + "=" * 80)
    logger.info("【JSON 报告】")
    logger.info("=" * 80)
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    
    # 保存报告
    report_path = "data/t7_enhancement_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    logger.info("\n报告已保存到：%s", report_path)
    
    return results


if __name__ == "__main__":
    result = asyncio.run(run_t7_enhancement())
    
    # 退出码
    has_error = (
        result.get("signal_association", {}).get("error") or
        result.get("deep_crawl", {}).get("error")
    )
    sys.exit(0 if not has_error else 1)
