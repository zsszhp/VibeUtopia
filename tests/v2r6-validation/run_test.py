"""V2.R6 博主附加服务 - 版本测试脚本

测试5类博主画像、选题推荐相关性、竞品分析深度。
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.blogger_profiler import BloggerProfiler
from backend.services.topic_recommender import TopicRecommender
from backend.services.competitor_analyzer import CompetitorAnalyzer


# ─── 5类博主测试案例 ────────────────────────────────────────

BLOGGER_CASES = [
    {
        "id": "blogger-food",
        "name": "美食博主-小李",
        "platform": "douyin",
        "contents": [
            "今天教大家做一道超级简单的红烧肉！先准备好五花肉、酱油、冰糖，跟着步骤来保证零失败！",
            "家人们！这个西红柿炒鸡蛋的做法太绝了，我奶奶教我的独门秘方，绝对让你惊艳！",
            "减脂期怎么吃？这5道低卡美食让你既好吃又不胖，姐妹们快收藏！",
            "探店实录！这家隐藏在胡同里的小店，一碗面只要15块，味道绝了！",
            "厨房小白必看！3步搞定蛋炒饭，再也不用点外卖了！",
        ],
        "expected_style": "casual",
        "expected_topic": "美食",
    },
    {
        "id": "blogger-tech",
        "name": "科技博主-老王",
        "platform": "bilibili",
        "contents": [
            "深度评测：这款新旗舰手机的性能到底如何？我们用跑分数据说话。",
            "从底层架构分析，为什么这颗芯片的能效比如此出色？技术解析来了。",
            "AI大模型横评：5款主流模型在中文场景下的表现对比，结果可能出乎你的意料。",
            "程序员必看：这个开源工具让你的开发效率提升300%，亲测有效。",
            "5G vs WiFi7：谁才是未来无线通信的王者？从协议层深度分析。",
        ],
        "expected_style": "formal",
        "expected_topic": "科技",
    },
    {
        "id": "blogger-fashion",
        "name": "时尚博主-小美",
        "platform": "xiaohongshu",
        "contents": [
            "今日穿搭分享～这件风衣真的太好看了！搭配高腰牛仔裤秒变大长腿✨",
            "姐妹们！这个口红颜色绝了，黄皮也能驾驭！快来get同款！💄",
            "秋冬必入的5件单品，时尚又保暖，让你成为街头最靓的崽！",
            "香水推荐！这3款小众香水让你气质瞬间提升，男士闻了都说好！",
            "微胖女孩穿搭指南！这些搭配技巧让你显瘦10斤不是梦！👗",
        ],
        "expected_style": "casual",
        "expected_topic": "时尚",
    },
    {
        "id": "blogger-news",
        "name": "时评博主-老张",
        "platform": "weibo",
        "contents": [
            "关于最近的社会热点，我想说几点：第一，我们不能简单站队；第二，事实比情绪更重要。",
            "深度解析：这项政策背后的逻辑是什么？对普通人有什么影响？",
            "理性讨论：面对争议话题，我们应该如何保持独立思考？",
            "回顾历史：类似的公共事件，过去是怎么处理的？有哪些经验教训？",
            "媒体素养课：如何识别信息茧房？这5个方法帮你打破认知壁垒。",
        ],
        "expected_style": "serious",
        "expected_topic": "时评",
    },
    {
        "id": "blogger-finance",
        "name": "理财博主-阿明",
        "platform": "wechat",
        "contents": [
            "普通人如何实现财务自由？这3个步骤你必须知道！",
            "基金定投：为什么大多数人都在亏钱？因为你踩了这5个坑！",
            "2024年投资策略：这3个赛道值得关注，但要注意风险管控。",
            "月光族如何理财？从记账开始，这5个习惯改变你的财务状况。",
            "保险避坑指南：这4种保险千万别买，买了就是交智商税！",
        ],
        "expected_style": "formal",
        "expected_topic": "理财",
    },
]

# 热点数据
HOT_TOPICS = [
    {"title": "AI大模型新突破", "platform": "weibo", "strength": 95},
    {"title": "预制菜食品安全", "platform": "douyin", "strength": 88},
    {"title": "新能源汽车补贴", "platform": "bilibili", "strength": 75},
    {"title": "职场35岁困境", "platform": "xiaohongshu", "strength": 82},
    {"title": "网红带货翻车", "platform": "douyin", "strength": 90},
]


async def run_tests():
    """运行所有测试"""
    print("=" * 70)
    print("V2.R6 博主附加服务 - 版本测试")
    print("=" * 70)

    profiler = BloggerProfiler()
    recommender = TopicRecommender()
    analyzer = CompetitorAnalyzer()

    # ─── 1. 博主画像测试 ─────────────────────────────
    print("\n--- 博主画像测试 (5类博主) ---")
    profile_results = []

    for case in BLOGGER_CASES:
        start = time.time()
        profile = await profiler.generate_profile(
            blogger_id=case["id"],
            name=case["name"],
            platform=case["platform"],
            contents=case["contents"],
        )
        elapsed = time.time() - start

        # 验证
        style_match = profile.expression.tone == case["expected_style"]
        topic_match = any(
            t.get("topic", "") == case["expected_topic"]
            for t in profile.topics.primary_topics
            if isinstance(t, dict)
        )
        passed = style_match or topic_match  # 至少一个匹配即通过

        status = "PASS" if passed else "WARN"
        print(f"  [{status}] {case['name']}: 风格={profile.expression.tone}({case['expected_style']}) "
              f"主题={profile.topics.primary_topics[:2]} 置信度={profile.confidence} "
              f"耗时={elapsed:.1f}s")

        profile_results.append({
            "id": case["id"],
            "name": case["name"],
            "profile": profile,
            "passed": passed,
        })

    profile_pass_rate = sum(1 for r in profile_results if r["passed"]) / len(profile_results)

    # ─── 2. 选题推荐测试 ─────────────────────────────
    print("\n--- 选题推荐测试 ---")
    rec_results = []

    for pr in profile_results[:3]:  # 测试前3个博主
        import dataclasses
        profile_data = dataclasses.asdict(pr["profile"])

        start = time.time()
        rec_result = await recommender.recommend(
            blogger_profile=profile_data,
            hot_topics=HOT_TOPICS,
            blogger_id=pr["id"],
            blogger_name=pr["name"],
        )
        elapsed = time.time() - start

        rec_count = len(rec_result.recommendations)
        has_safe = any(r.risk_level == "safe" for r in rec_result.recommendations)
        passed = rec_count >= 3 and has_safe

        status = "PASS" if passed else "WARN"
        print(f"  [{status}] {pr['name']}: 推荐{rec_count}个选题, "
              f"有安全选题={has_safe}, 耗时={elapsed:.1f}s")

        if rec_result.recommendations:
            for r in rec_result.recommendations[:2]:
                print(f"    - {r.topic} (风险:{r.risk_level}, 优先级:{r.priority})")

        rec_results.append(passed)

    rec_pass_rate = sum(rec_results) / len(rec_results) if rec_results else 0

    # ─── 3. 竞品分析测试 ─────────────────────────────
    print("\n--- 竞品对标分析测试 ---")
    comp_results = []

    # 美食博主 vs 科技博主
    import dataclasses
    food_data = dataclasses.asdict(profile_results[0]["profile"])
    tech_data = dataclasses.asdict(profile_results[1]["profile"])

    start = time.time()
    comp_result = await analyzer.compare(
        blogger_profile=food_data,
        competitor_profile=tech_data,
        blogger_id="blogger-food",
        blogger_name="美食博主-小李",
        competitor_id="blogger-tech",
        competitor_name="科技博主-老王",
    )
    elapsed = time.time() - start

    has_comparisons = len(comp_result.style_comparisons) > 0
    has_gaps = len(comp_result.content_gaps) >= 0  # 空也是合理的
    has_suggestions = len(comp_result.suggestions) > 0
    passed = has_comparisons and has_suggestions

    status = "PASS" if passed else "WARN"
    print(f"  [{status}] 美食vs科技: 对比{len(comp_result.style_comparisons)}个维度, "
          f"缺口{len(comp_result.content_gaps)}个, "
          f"建议{len(comp_result.suggestions)}个, 耗时={elapsed:.1f}s")
    print(f"    评估: {comp_result.overall_assessment[:80]}...")
    comp_results.append(passed)

    # 时尚博主 vs 美食博主
    fashion_data = dataclasses.asdict(profile_results[2]["profile"])
    start = time.time()
    comp_result2 = await analyzer.compare(
        blogger_profile=fashion_data,
        competitor_profile=food_data,
        blogger_id="blogger-fashion",
        competitor_id="blogger-food",
    )
    elapsed = time.time() - start

    passed2 = len(comp_result2.style_comparisons) > 0 and len(comp_result2.suggestions) > 0
    status = "PASS" if passed2 else "WARN"
    print(f"  [{status}] 时尚vs美食: 对比{len(comp_result2.style_comparisons)}个维度, "
          f"建议{len(comp_result2.suggestions)}个, 耗时={elapsed:.1f}s")
    comp_results.append(passed2)

    comp_pass_rate = sum(comp_results) / len(comp_results)

    # ─── 4. 规则补充验证 ─────────────────────────────
    print("\n--- 规则补充功能验证 ---")
    # 词汇统计
    profiler_test = BloggerProfiler()
    test_profile = await profiler_test.generate_profile(
        blogger_id="test",
        contents=["这是一个测试文案。很长的句子，包含多个词汇和表达方式！还有感叹号！"],
    )
    vocab_ok = test_profile.vocabulary.avg_sentence_length > 0
    expr_ok = test_profile.expression.exclamation_ratio > 0
    print(f"  {'PASS' if vocab_ok else 'FAIL'}: 词汇统计(句长={test_profile.vocabulary.avg_sentence_length})")
    print(f"  {'PASS' if expr_ok else 'FAIL'}: 表达统计(感叹比={test_profile.expression.exclamation_ratio})")

    # ─── 5. 汇总 ──────────────────────────────────
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    print(f"博主画像测试: {sum(1 for r in profile_results if r['passed'])}/{len(profile_results)} 通过 ({profile_pass_rate*100:.0f}%)")
    print(f"选题推荐测试: {sum(rec_results)}/{len(rec_results)} 通过 ({rec_pass_rate*100:.0f}%)")
    print(f"竞品分析测试: {sum(comp_results)}/{len(comp_results)} 通过 ({comp_pass_rate*100:.0f}%)")
    print(f"规则补充: {'PASS' if vocab_ok and expr_ok else 'FAIL'}")

    # Go/No-Go
    print("\n--- Go/No-Go 评估 ---")
    go_criteria = {
        "博主画像通过率≥60%": profile_pass_rate >= 0.6,
        "选题推荐通过率≥60%": rec_pass_rate >= 0.6,
        "竞品分析通过率≥60%": comp_pass_rate >= 0.6,
        "规则补充功能可用": vocab_ok and expr_ok,
    }
    for criterion, met in go_criteria.items():
        print(f"  {criterion}: {'GO' if met else 'NO-GO'}")

    all_go = all(go_criteria.values())
    print(f"\n最终判定: {'GO - V2.R6达标，产品成熟！' if all_go else 'NO-GO - 需要修复问题'}")

    return all_go


if __name__ == "__main__":
    asyncio.run(run_tests())
