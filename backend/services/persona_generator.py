"""7层人格生成器 — 基于原型模板+LLM生成差异化Agent人格

核心能力：
1. 基于原型模板生成具体人格（LLM增加变异）
2. 变体种子注入（同一原型生成不同变体）
3. 一致性校验与自动修复（QualityValidator）
4. 图谱知识注入（GraphInjector）
5. 持久化存储（AgentRecord）
6. 批量并行生成（Semaphore并发控制）
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json
from backend.services.persona_archetypes import (
    PersonaArchetype,
    get_archetypes_for_platform,
    get_random_archetypes,
    archetype_to_dict,
    _get_variation_seeds,
)
from backend.services.persona.quality_validator import QualityValidator
from backend.services.persona.graph_injector import GraphInjector

logger = logging.getLogger(__name__)


async def generate_persona(
    archetype: PersonaArchetype,
    variation_seed: Optional[str] = None,
    graph_injector: Optional[GraphInjector] = None,
    validate: bool = True,
) -> Optional[dict]:
    """基于原型模板生成一个完整的7层人格

    Args:
        archetype: 人格原型
        variation_seed: 变体种子，让同一原型生成不同变体
        graph_injector: 图谱注入器实例
        validate: 是否执行质量校验

    Returns:
        完整的7层人格dict，或None（生成失败时）
    """
    prompt_template = load_prompt("persona_generation.txt")
    archetype_dict = archetype_to_dict(archetype)

    # 注入变体种子到prompt
    if variation_seed:
        archetype_dict["variation_direction"] = variation_seed

    archetype_json = json.dumps(archetype_dict, ensure_ascii=False, indent=2)
    prompt = prompt_template.replace("{archetype_json}", archetype_json)

    try:
        response = await call_llm(prompt, task_type="persona_generation")
        result = parse_llm_json(response, fallback=None)

        if not result or "L1_basic" not in result:
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

        # 图谱注入
        if graph_injector:
            result = graph_injector.inject(result)

        # 质量校验与修复
        if validate:
            validator = QualityValidator()
            result, quality_score = await validator.validate_and_fix(result)
            result["quality_score"] = quality_score
        else:
            result["quality_score"] = 0.5

        return result

    except Exception as e:
        logger.error("人格生成失败，原型 %s: %s", archetype.archetype_id, e)
        return None


async def generate_personas_batch(
    platform: str,
    count: int = 5,
    graph_injector: Optional[GraphInjector] = None,
    persist: bool = False,
    max_concurrent: int = 5,
) -> List[dict]:
    """批量并行生成指定平台的Agent人格

    Args:
        platform: 平台标识
        count: 生成数量
        graph_injector: 图谱注入器
        persist: 是否持久化到数据库
        max_concurrent: 最大并发数

    Returns:
        成功生成的人格列表
    """
    archetypes = get_random_archetypes(platform, count, with_variation=True)

    if not archetypes:
        logger.warning("平台 %s 没有可用的人格原型", platform)
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _generate_with_semaphore(arch):
        async with semaphore:
            # 选择随机变体种子
            seeds = arch.variation_seeds or _get_variation_seeds(arch)
            import random
            seed = random.choice(seeds) if seeds else None
            return await generate_persona(arch, variation_seed=seed, graph_injector=graph_injector)

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

    # 持久化
    if persist and personas:
        _persist_personas(personas)

    return personas


async def generate_agents_cross_platform(
    platforms: Optional[List[str]] = None,
    count_per_platform: int = 5,
    graph_injector: Optional[GraphInjector] = None,
    persist: bool = False,
) -> Dict[str, List[dict]]:
    """跨平台批量生成Agent

    Args:
        platforms: 平台列表，None则使用全部4平台
        count_per_platform: 每平台生成数量
        graph_injector: 图谱注入器
        persist: 是否持久化

    Returns:
        {platform: [persona_list]}
    """
    if platforms is None:
        platforms = ["bilibili", "xiaohongshu", "zhihu", "douyin"]

    result = {}
    for platform in platforms:
        result[platform] = await generate_personas_batch(
            platform=platform,
            count=count_per_platform,
            graph_injector=graph_injector,
            persist=persist,
        )

    return result


def _persist_personas(personas: List[dict]):
    """将生成的人格持久化到数据库"""
    from datetime import datetime, timezone
    from backend.database import SessionLocal
    from backend.models import AgentRecord

    db = SessionLocal()
    try:
        for persona in personas:
            record = AgentRecord(
                agent_id=persona.get("persona_id", str(uuid.uuid4())),
                platform=persona.get("platform", "unknown"),
                archetype_base=persona.get("archetype_base", ""),
                persona_json=json.dumps(persona, ensure_ascii=False),
                quality_score=persona.get("quality_score", 0.0),
                status="active",
                version=1,
            )
            db.merge(record)
        db.commit()
        logger.info(f"持久化 {len(personas)} 个Agent到数据库")
    except Exception as e:
        logger.error(f"持久化Agent失败: {e}")
        db.rollback()
    finally:
        db.close()


# ── 兼容旧接口 ──────────────────────────────────────

def _validate_consistency(persona: dict) -> list[str]:
    """兼容旧调用：使用QualityValidator进行校验"""
    validator = QualityValidator()
    _, issues = validator.validate(persona)
    return issues
