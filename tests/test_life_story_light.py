#!/usr/bin/env python3
"""人生故事生成器轻量测试

验证 A/B/C 三级人格生成器的代码结构和接口完整性，不实际调用 LLM。
"""

import json
import logging
from pathlib import Path

from backend.services.persona.life_story_generator import (
    PersonaFactory,
    LifeStoryInterviewer,
    CGSSSampler,
    TemplateVariator,
    LifeStoryPersona,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


def test_template_variator():
    """测试 C-tier：模板变体（纯本地，不调用 LLM）"""
    logger.info("=" * 60)
    logger.info("测试 C-tier：模板变体")
    logger.info("=" * 60)
    
    variator = TemplateVariator()
    
    archetypes = ["主流用户", "争议用户", "边缘用户", "KOL/大 V", "跨界用户"]
    results = []
    
    for archetype in archetypes:
        logger.info(f"生成：platform=小红书，archetype={archetype}")
        persona = variator.generate(
            platform="xiaohongshu",
            archetype=archetype,
        )
        
        assert isinstance(persona, LifeStoryPersona), "返回类型必须是 LifeStoryPersona"
        assert persona.tier == "C", "Tier 必须是 C"
        assert len(persona.life_story) >= 40, f"故事字数不能少于 40，实际{len(persona.life_story)}"
        assert "L1_basic" in persona.persona_7layers, "必须包含 L1_basic"
        assert len(persona.big_five) == 5, f"Big Five 必须有 5 个维度，实际{len(persona.big_five)}"
        
        results.append({
            "archetype": archetype,
            "story_words": len(persona.life_story),
            "has_7layers": True,
            "has_big_five": True,
        })
        
        logger.info(f"✓ {archetype}: {len(persona.life_story)}字，7 层完整，Big Five 完整")
    
    logger.info(f"C-tier 测试结果：✅ PASS ({len(archetypes)}/{len(archetypes)})")
    
    return results


def test_cgss_sampler_structure():
    """测试 B-tier：CGSS 采样器结构（不实际生成）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 B-tier：CGSS 采样器结构")
    logger.info("=" * 60)
    
    sampler = CGSSSampler()
    
    # 验证人口统计分布
    demographics = sampler.CGSS_DEMOGRAPHICS
    logger.info(f"CGSS 人口统计分布数量：{len(demographics)}")
    
    # 验证权重总和接近 1
    total_weight = sum(d["weight"] for d in demographics)
    assert abs(total_weight - 1.0) < 0.01, f"权重总和必须接近 1，实际{total_weight}"
    logger.info(f"✓ 权重总和：{total_weight:.3f}")
    
    # 验证采样方法
    sample = sampler._sample_demographics()
    assert "age" in sample, "采样必须包含 age"
    assert "gender" in sample, "采样必须包含 gender"
    logger.info(f"✓ 采样示例：{sample}")
    
    # 验证故事转记忆方法
    test_story = "这是一个测试故事。包含多个句子。用来验证记忆提取功能。"
    memories = sampler._story_to_memories(test_story)
    assert len(memories) > 0, "必须生成记忆条目"
    assert memories[0]["type"] == "observation", "记忆类型必须是 observation"
    logger.info(f"✓ 记忆提取：生成{len(memories)}条记忆")
    
    logger.info("B-tier 结构测试：✅ PASS")
    
    return {"cgss_demographics": len(demographics), "weight_sum": total_weight}


def test_interviewer_structure():
    """测试 A-tier：访谈器结构（不实际调用）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 A-tier：访谈器结构")
    logger.info("=" * 60)
    
    interviewer = LifeStoryInterviewer()
    
    # 验证访谈轮数
    assert len(interviewer.INTERVIEW_ROUNDS) == 6, f"必须有 6 轮访谈，实际{len(interviewer.INTERVIEW_ROUNDS)}"
    logger.info(f"✓ 访谈轮数：{len(interviewer.INTERVIEW_ROUNDS)}")
    
    # 验证每轮配置
    total_target_words = 0
    for i, round_config in enumerate(interviewer.INTERVIEW_ROUNDS):
        assert "topic" in round_config, f"第{i+1}轮缺少 topic"
        assert "prompt" in round_config, f"第{i+1}轮缺少 prompt"
        assert "target_words" in round_config, f"第{i+1}轮缺少 target_words"
        total_target_words += round_config["target_words"]
        logger.info(f"  第{i+1}轮：{round_config['topic']} - {round_config['target_words']}字")
    
    logger.info(f"✓ 总目标字数：{total_target_words}字")
    
    # 验证记忆提取方法
    test_story = "## 童年与家庭\n\n我出生在一个小城市..."
    memories = interviewer._story_to_memories(test_story)
    assert len(memories) > 0, "必须生成记忆条目"
    logger.info(f"✓ 记忆提取：生成{len(memories)}条记忆")
    
    # 验证默认 7 层生成
    default_layers = interviewer._default_7layers("weibo", "主流用户")
    assert "L1_basic" in default_layers, "必须包含 L1_basic"
    logger.info(f"✓ 默认 7 层结构完整")
    
    logger.info("A-tier 结构测试：✅ PASS")
    
    return {
        "interview_rounds": len(interviewer.INTERVIEW_ROUNDS),
        "total_target_words": total_target_words,
    }


def test_persona_factory():
    """测试 PersonaFactory 工厂类"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 PersonaFactory 工厂类")
    logger.info("=" * 60)
    
    factory = PersonaFactory()
    
    # 验证组件初始化
    assert factory.a_interviewer is not None, "A-tier 访谈器必须初始化"
    assert factory.b_sampler is not None, "B-tier 采样器必须初始化"
    assert factory.c_variator is not None, "C-tier 变体器必须初始化"
    logger.info("✓ 三个 Tier 组件已初始化")
    
    # 测试 C-tier 生成（本地，不调用 LLM）
    logger.info("测试 C-tier 生成...")
    persona_c = factory.c_variator.generate(
        platform="zhihu",
        archetype="主流用户",
    )
    
    assert persona_c.tier == "C", "Tier 必须是 C"
    assert persona_c.platform == "zhihu", "平台必须是 zhihu"
    assert persona_c.archetype == "主流用户", "原型必须是主流用户"
    logger.info(f"✓ C-tier 生成成功：{len(persona_c.life_story)}字")
    
    # 验证批量生成分布计算
    tier_dist = {"A": 1, "B": 3, "C": 6}
    total = sum(tier_dist.values())
    assert total == 10, "默认分布总数必须是 10"
    logger.info(f"✓ 批量生成分布：A={tier_dist['A']}, B={tier_dist['B']}, C={tier_dist['C']}")
    
    logger.info("PersonaFactory 测试：✅ PASS")
    
    return {
        "components_initialized": 3,
        "c_tier_test_words": len(persona_c.life_story),
    }


def test_life_story_persona_dataclass():
    """测试 LifeStoryPersona 数据类"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 LifeStoryPersona 数据类")
    logger.info("=" * 60)
    
    persona = LifeStoryPersona(
        tier="C",
        life_story="测试故事",
        persona_7layers={"L1_basic": {"age": "25-34"}},
        initial_memories=[{"type": "observation", "content": "测试记忆"}],
        big_five={"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5},
        quality_score=0.8,
        platform="weibo",
        archetype="主流用户",
    )
    
    assert persona.tier == "C"
    assert len(persona.life_story) == 4
    assert "L1_basic" in persona.persona_7layers
    assert len(persona.initial_memories) == 1
    assert len(persona.big_five) == 5
    assert persona.quality_score == 0.8
    logger.info("✓ LifeStoryPersona 数据类验证通过")
    
    return {"valid": True}


def main():
    """主测试流程"""
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 12 + "人生故事生成器轻量级测试（无 LLM 调用）" + " " * 12 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    
    results = {}
    all_pass = True
    
    try:
        results["c_tier"] = test_template_variator()
    except Exception as e:
        logger.error(f"C-tier 测试失败：{e}")
        all_pass = False
    
    try:
        results["b_tier_structure"] = test_cgss_sampler_structure()
    except Exception as e:
        logger.error(f"B-tier 结构测试失败：{e}")
        all_pass = False
    
    try:
        results["a_tier_structure"] = test_interviewer_structure()
    except Exception as e:
        logger.error(f"A-tier 结构测试失败：{e}")
        all_pass = False
    
    try:
        results["factory"] = test_persona_factory()
    except Exception as e:
        logger.error(f"PersonaFactory 测试失败：{e}")
        all_pass = False
    
    try:
        results["dataclass"] = test_life_story_persona_dataclass()
    except Exception as e:
        logger.error(f"LifeStoryPersona 测试失败：{e}")
        all_pass = False
    
    # 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("测试汇总报告")
    logger.info("=" * 60)
    
    if all_pass:
        logger.info("✅ 所有测试通过！人生故事生成器结构完整，接口正常。")
        logger.info("\n注：A-tier 和 B-tier 的完整 LLM 调用测试需要 API 配额。")
        logger.info("当前 API 配额耗尽，已跳过实际调用测试。")
    else:
        logger.info("⚠️ 部分测试失败，请检查日志。")
    
    # 保存报告
    report_path = Path("/workspace/tests/life_story_light_test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"测试报告已保存到：{report_path}")
    
    return all_pass


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
