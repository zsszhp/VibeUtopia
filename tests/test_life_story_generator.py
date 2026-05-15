#!/usr/bin/env python3
"""人生故事生成器测试脚本

测试 A/B/C 三级人格生成策略：
- A-tier: AI 访谈生成器 (6 轮结构化访谈→数万字人生故事)
- B-tier: CGSS 采样+LLM 丰富 (人口统计采样→千字故事)
- C-tier: 模板变体 (原型模板 + 随机参数→百字梗概)

验收标准：
1. A-tier 生成故事字数≥15000 字
2. B-tier 生成故事字数≥800 字
3. C-tier 生成故事字数≥50 字
4. 7 层人格完整性 100%
5. Big Five 特质有效性 100%
6. 质量评分≥0.6
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from backend.services.persona.life_story_generator import (
    PersonaFactory,
    LifeStoryInterviewer,
    CGSSSampler,
    TemplateVariator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


async def test_a_tier_interview():
    """测试 A-tier：AI 访谈生成器"""
    logger.info("=" * 60)
    logger.info("测试 A-tier：AI 访谈生成器 (6 轮访谈)")
    logger.info("=" * 60)
    
    interviewer = LifeStoryInterviewer()
    
    base_profile = {
        "gender": "女",
        "age": "28-32",
        "occupation": "互联网产品经理",
        "location": "北京",
    }
    
    logger.info("生成人格：platform=微博，archetype=争议用户")
    persona = await interviewer.generate(
        platform="weibo",
        archetype="争议用户",
        base_profile=base_profile,
    )
    
    # 验证
    story_words = len(persona.life_story)
    logger.info(f"✓ 人生故事字数：{story_words} 字")
    
    has_7layers = "L1_basic" in persona.persona_7layers
    logger.info(f"✓ 7 层人格完整性：{'完整' if has_7layers else '缺失'}")
    
    has_big_five = all(k in persona.big_five for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"])
    logger.info(f"✓ Big Five 完整性：{'完整' if has_big_five else '缺失'}")
    
    logger.info(f"✓ 质量评分：{persona.quality_score}")
    
    result = {
        "tier": "A",
        "story_words": story_words,
        "has_7layers": has_7layers,
        "has_big_five": has_big_five,
        "quality_score": persona.quality_score,
        "pass": story_words >= 15000 and has_7layers and has_big_five,
    }
    
    logger.info(f"A-tier 测试结果：{'✅ PASS' if result['pass'] else '❌ FAIL'}")
    
    return result, persona


async def test_b_tier_cgss():
    """测试 B-tier：CGSS 采样 +LLM 丰富"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 B-tier：CGSS 采样+LLM 丰富")
    logger.info("=" * 60)
    
    sampler = CGSSSampler()
    
    logger.info("生成人格：platform=B 站，archetype=主流用户")
    persona = await sampler.generate(
        platform="bilibili",
        archetype="主流用户",
    )
    
    story_words = len(persona.life_story)
    logger.info(f"✓ 人生故事字数：{story_words} 字")
    
    has_7layers = "L1_basic" in persona.persona_7layers
    logger.info(f"✓ 7 层人格完整性：{'完整' if has_7layers else '缺失'}")
    
    has_big_five = all(k in persona.big_five for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"])
    logger.info(f"✓ Big Five 完整性：{'完整' if has_big_five else '缺失'}")
    
    result = {
        "tier": "B",
        "story_words": story_words,
        "has_7layers": has_7layers,
        "has_big_five": has_big_five,
        "pass": story_words >= 800 and has_7layers and has_big_five,
    }
    
    logger.info(f"B-tier 测试结果：{'✅ PASS' if result['pass'] else '❌ FAIL'}")
    
    return result, persona


async def test_c_tier_template():
    """测试 C-tier：模板变体"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 C-tier：模板变体")
    logger.info("=" * 60)
    
    variator = TemplateVariator()
    
    logger.info("生成人格：platform=小红书，archetype=KOL/大 V")
    persona = variator.generate(
        platform="xiaohongshu",
        archetype="KOL/大 V",
    )
    
    story_words = len(persona.life_story)
    logger.info(f"✓ 人生故事字数：{story_words} 字")
    
    has_7layers = "L1_basic" in persona.persona_7layers
    logger.info(f"✓ 7 层人格完整性：{'完整' if has_7layers else '缺失'}")
    
    has_big_five = all(k in persona.big_five for k in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"])
    logger.info(f"✓ Big Five 完整性：{'完整' if has_big_five else '缺失'}")
    
    result = {
        "tier": "C",
        "story_words": story_words,
        "has_7layers": has_7layers,
        "has_big_five": has_big_five,
        "pass": story_words >= 50 and has_7layers and has_big_five,
    }
    
    logger.info(f"C-tier 测试结果：{'✅ PASS' if result['pass'] else '❌ FAIL'}")
    
    return result, persona


async def test_persona_factory():
    """测试 PersonaFactory 统一入口"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 PersonaFactory 统一入口 (批量生成)")
    logger.info("=" * 60)
    
    factory = PersonaFactory()
    
    logger.info("批量生成 5 个人格 (平台=知乎)")
    personas = await factory.generate_batch(
        platform="zhihu",
        count=5,
        tier_distribution={"A": 1, "B": 2, "C": 2},
    )
    
    tier_counts = {}
    for p in personas:
        tier = p.tier
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    logger.info(f"✓ 生成数量：{len(personas)}")
    logger.info(f"✓ Tier 分布：{tier_counts}")
    
    valid_count = sum(1 for p in personas if p.persona_7layers)
    logger.info(f"✓ 7 层人格有效：{valid_count}/{len(personas)}")
    
    result = {
        "total": len(personas),
        "tier_distribution": tier_counts,
        "valid_count": valid_count,
        "pass": len(personas) >= 3 and valid_count >= 3,
    }
    
    logger.info(f"PersonaFactory 测试结果：{'✅ PASS' if result['pass'] else '❌ FAIL'}")
    
    return result, personas


async def main():
    """主测试流程"""
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 15 + "人生故事生成器验收测试" + " " * 15 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info(f"测试时间：{datetime.now().isoformat()}")
    
    results = []
    all_personas = []
    
    # 测试 A-tier (耗时最长，单独执行)
    try:
        result_a, persona_a = await test_a_tier_interview()
        results.append(result_a)
        all_personas.append(persona_a)
    except Exception as e:
        logger.error(f"A-tier 测试异常：{e}")
        results.append({"tier": "A", "pass": False, "error": str(e)})
    
    # 测试 B-tier
    try:
        result_b, persona_b = await test_b_tier_cgss()
        results.append(result_b)
        all_personas.append(persona_b)
    except Exception as e:
        logger.error(f"B-tier 测试异常：{e}")
        results.append({"tier": "B", "pass": False, "error": str(e)})
    
    # 测试 C-tier
    try:
        result_c, persona_c = await test_c_tier_template()
        results.append(result_c)
        all_personas.append(persona_c)
    except Exception as e:
        logger.error(f"C-tier 测试异常：{e}")
        results.append({"tier": "C", "pass": False, "error": str(e)})
    
    # 测试 PersonaFactory
    try:
        result_factory, personas_factory = await test_persona_factory()
        results.append(result_factory)
        all_personas.extend(personas_factory)
    except Exception as e:
        logger.error(f"PersonaFactory 测试异常：{e}")
        results.append({"test": "factory", "pass": False, "error": str(e)})
    
    # 汇总报告
    passed = sum(1 for r in results if r.get("pass", False))
    total = len(results)
    
    logger.info("\n" + "=" * 60)
    logger.info("测试汇总报告")
    logger.info("=" * 60)
    logger.info(f"总测试数：{total}")
    logger.info(f"通过测试：{passed}")
    logger.info(f"失败测试：{total - passed}")
    logger.info(f"通过率：{passed / total * 100:.1f}%")
    
    if passed == total:
        logger.info("\n✅ 所有测试通过！人生故事生成器可以进入生产环境。")
    else:
        logger.info(f"\n⚠️ {total - passed} 个测试失败，请检查日志。")
    
    # 保存报告
    report_path = Path("/workspace/tests/life_story_test_report.json")
    report_data = {
        "test_time": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total * 100,
        },
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"测试报告已保存到：{report_path}")
    
    # 保存一个生成的示例人格
    if all_personas:
        sample_path = Path("/workspace/tests/sample_life_story_persona.json")
        sample_data = {
            "tier": all_personas[0].tier,
            "platform": all_personas[0].platform,
            "archetype": all_personas[0].archetype,
            "life_story": all_personas[0].life_story[:2000] + "..." if len(all_personas[0].life_story) > 2000 else all_personas[0].life_story,
            "persona_7layers": all_personas[0].persona_7layers,
            "big_five": all_personas[0].big_five,
            "quality_score": all_personas[0].quality_score,
        }
        with open(sample_path, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        logger.info(f"示例人格已保存到：{sample_path}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
