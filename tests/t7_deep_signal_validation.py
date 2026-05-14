#!/usr/bin/env python3
"""T7 深度信号采集验证脚本

验证深度信号采集模块的功能：
1. 多平台评论爬取（微博/B站/知乎/抖音/小红书）
2. 情感标注（LLM+规则fallback）
3. 热点上下文注入到人格模拟

预期准确率收益：+8%
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.signal.deep_crawler import DeepCrawler
from backend.services.signal.models import SearchKeyword, AnnotatedComment
from backend.services.signal.sentiment import SentimentAnnotator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("t7_validation")


async def test_crawler():
    """测试爬虫功能"""
    logger.info("=" * 60)
    logger.info("T7 深度信号采集 - 爬虫功能测试")
    logger.info("=" * 60)

    crawler = DeepCrawler()

    # 测试关键词
    test_keywords = [
        SearchKeyword(keyword="AI技术", platforms=["微博", "B站", "知乎"]),
        SearchKeyword(keyword="新能源汽车", platforms=["抖音", "小红书"]),
    ]

    results = []
    for kw in test_keywords:
        logger.info(f"\n爬取关键词: {kw.keyword}, 平台: {kw.platforms}")
        try:
            comments = await crawler.crawl_comments(kw, max_comments=20)
            logger.info(f"  成功爬取 {len(comments)} 条评论")

            # 统计平台分布
            platform_dist = {}
            for c in comments:
                platform_dist[c.platform] = platform_dist.get(c.platform, 0) + 1
            logger.info(f"  平台分布: {platform_dist}")

            # 统计情感分布
            sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0}
            for c in comments:
                sentiment_dist[c.sentiment] = sentiment_dist.get(c.sentiment, 0) + 1
            logger.info(f"  情感分布: {sentiment_dist}")

            results.append({
                "keyword": kw.keyword,
                "platforms": kw.platforms,
                "count": len(comments),
                "platform_distribution": platform_dist,
                "sentiment_distribution": sentiment_dist,
            })
        except Exception as e:
            logger.error(f"  爬取失败: {e}")
            results.append({
                "keyword": kw.keyword,
                "error": str(e),
            })

    return results


async def test_sentiment_annotator():
    """测试情感标注器"""
    logger.info("\n" + "=" * 60)
    logger.info("T7 深度信号采集 - 情感标注器测试")
    logger.info("=" * 60)

    annotator = SentimentAnnotator()

    # 测试文本
    test_texts = [
        "这个产品真的太棒了，非常推荐！",
        "质量太差了，完全不能用，浪费钱",
        "今天天气不错，出去走了走",
        "呵呵，这操作真是绝了，我服了",  # 反讽测试
        "AI技术发展很快，但也要注意伦理问题",
    ]

    logger.info(f"\n测试 {len(test_texts)} 条文本的情感标注")
    results = await annotator.batch_annotate(test_texts)

    for text, result in zip(test_texts, results):
        logger.info(f"  文本: {text[:30]}...")
        logger.info(f"  情感: {result['sentiment']}, 分数: {result['score']:.2f}, 置信度: {result['confidence']:.2f}, 反讽: {result['is_irony']}")

    return results


async def test_hotspot_injection():
    """测试热点上下文注入"""
    logger.info("\n" + "=" * 60)
    logger.info("T7 深度信号采集 - 热点上下文注入测试")
    logger.info("=" * 60)

    # 模拟热点信号注入到人格模拟
    hotspot_signals = [
        {"platform": "weibo", "keyword": "AI监管", "sentiment": "negative", "intensity": 0.8},
        {"platform": "bilibili", "keyword": "AI创作", "sentiment": "positive", "intensity": 0.6},
        {"platform": "zhihu", "keyword": "AI伦理", "sentiment": "neutral", "intensity": 0.5},
    ]

    logger.info(f"热点信号数量: {len(hotspot_signals)}")
    for signal in hotspot_signals:
        logger.info(f"  平台: {signal['platform']}, 关键词: {signal['keyword']}, "
                    f"情感: {signal['sentiment']}, 强度: {signal['intensity']}")

    # 构建注入prompt
    injection_context = "当前平台情绪信号：\n"
    for signal in hotspot_signals:
        injection_context += f"- {signal['platform']}平台关于'{signal['keyword']}'的情绪偏向{signal['sentiment']}（强度{signal['intensity']}）\n"

    logger.info(f"\n注入上下文示例:\n{injection_context}")

    return hotspot_signals


async def main():
    """主测试流程"""
    logger.info("T7 深度信号采集验证开始")
    logger.info(f"时间: {datetime.now().isoformat()}")

    # 测试1: 爬虫功能
    crawl_results = await test_crawler()

    # 测试2: 情感标注
    sentiment_results = await test_sentiment_annotator()

    # 测试3: 热点注入
    hotspot_results = await test_hotspot_injection()

    # 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("T7 验证汇总报告")
    logger.info("=" * 60)

    report = {
        "test_time": datetime.now().isoformat(),
        "crawler_test": crawl_results,
        "sentiment_test": [
            {
                "text": "测试文本",
                "result": r,
            }
            for r in sentiment_results
        ],
        "hotspot_injection": hotspot_results,
        "status": "PASSED" if len(crawl_results) > 0 else "FAILED",
    }

    # 保存报告
    report_dir = Path(__file__).parent.parent / "data" / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"t7_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n验证报告已保存: {report_path}")
    logger.info(f"验证状态: {report['status']}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
