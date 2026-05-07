"""7层人格生成器 — 基于原型模板+LLM生成差异化Agent人格

核心能力：
1. 基于原型模板生成具体人格（LLM增加变异）
2. 一致性校验（L1-L7逻辑自洽）
3. 批量并行生成
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json
from backend.services.persona_archetypes import (
    PersonaArchetype,
    get_archetypes_for_platform,
    get_random_archetypes,
    archetype_to_dict,
)

logger = logging.getLogger(__name__)


async def generate_persona(archetype: PersonaArchetype) -> Optional[dict]:
    """基于原型模板生成一个完整的7层人格

    Args:
        archetype: 人格原型

    Returns:
        完整的7层人格dict，或None（生成失败时）
    """
    prompt_template = load_prompt("persona_generation.txt")
    archetype_json = json.dumps(archetype_to_dict(archetype), ensure_ascii=False, indent=2)
    prompt = prompt_template.replace("{archetype_json}", archetype_json)

    try:
        response = await call_llm(prompt, task_type="persona_generation")
        result = parse_llm_json(response, fallback=None)

        if not result or "L1_basic" not in result:
            # 重试一次
            logger.warning("人格生成结果缺少必要字段，重试中，原型: %s", archetype.archetype_id)
            response = await call_llm(prompt, task_type="persona_generation")
            result = parse_llm_json(response, fallback=None)
            if not result or "L1_basic" not in result:
                logger.warning("人格生成重试仍失败，原型: %s", archetype.archetype_id)
                return None

        # 确保persona_id存在
        if "persona_id" not in result:
            result["persona_id"] = f"{archetype.archetype_id}_{uuid.uuid4().hex[:6]}"

        result["archetype_base"] = archetype.archetype_id
        result["platform"] = archetype.platform

        # 一致性校验
        issues = _validate_consistency(result)
        if issues:
            logger.info("人格 %s 一致性问题: %s（已接受，LLM生成的人格允许适度偏差）",
                        result["persona_id"], issues)

        return result

    except Exception as e:
        logger.error("人格生成失败，原型 %s: %s", archetype.archetype_id, e)
        return None


async def generate_personas_batch(platform: str, count: int = 3) -> list[dict]:
    """批量并行生成指定平台的Agent人格

    Args:
        platform: 平台标识
        count: 生成数量

    Returns:
        成功生成的人格列表
    """
    archetypes = get_random_archetypes(platform, count)

    if not archetypes:
        logger.warning("平台 %s 没有可用的人格原型", platform)
        return []

    # 并行生成，2个并发（避免API速率限制）
    semaphore = asyncio.Semaphore(2)

    async def _generate_with_semaphore(arch):
        async with semaphore:
            return await generate_persona(arch)

    tasks = [_generate_with_semaphore(a) for a in archetypes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    personas = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("批量生成中的异常: %s", r)
            continue
        if r is not None:
            personas.append(r)

    logger.info("平台 %s: 请求生成 %d 个人格，成功 %d 个", platform, count, len(personas))
    return personas


def _validate_consistency(persona: dict) -> list[str]:
    """校验7层人格的一致性

    Returns:
        一致性问题列表（空列表表示完全一致）
    """
    issues = []

    l1 = persona.get("L1_basic", {})
    l2 = persona.get("L2_values", {})
    l3 = persona.get("L3_knowledge", {})
    l4 = persona.get("L4_behavior", {})
    l5 = persona.get("L5_correction", {})
    l7 = persona.get("L7_evolution", {})

    # 检查1：教育程度与认知水平匹配
    education = l1.get("education", "")
    cognitive = l3.get("cognitive_level", "中等")
    if "博士" in education or "硕士" in education:
        if cognitive == "初级":
            issues.append("高学历但认知水平为初级，不一致")

    # 检查2：收入与消费观匹配
    income = l1.get("income", "")
    consumerism = l2.get("consumerism", 5.0)
    if "低" in str(income) and consumerism > 7.0:
        issues.append("低收入但高消费主义倾向，可能不一致")

    # 检查3：表达风格与互动偏好匹配
    expression = l4.get("expression_style", "")
    interaction = l4.get("interaction_preference", "")
    if "激进" in expression and "潜水" in interaction:
        issues.append("激进表达风格但潜水偏好，不一致")

    # 检查4：自我审查与禁忌触发匹配
    self_censorship = l5.get("self_censorship", "中等")
    triggers = l5.get("sensitive_triggers", [])
    if self_censorship == "高" and len(triggers) == 0:
        issues.append("高自我审查但没有敏感触发点，可能不一致")

    # 检查5：情绪基线与近期经历匹配
    baseline = l7.get("emotional_baseline", "平稳")
    recent = l7.get("recent_experiences", [])
    if baseline in ("积极", "亢奋") and any(
        any(w in str(e) for w in ["失败", "失业", "崩溃", "悲剧"])
        for e in recent
    ):
        issues.append("积极情绪基线但有负面近期经历，可能不一致")

    return issues
