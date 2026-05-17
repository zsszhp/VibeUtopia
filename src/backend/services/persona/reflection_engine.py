"""Reflection 机制 — Stanford Generative Agents 论文核心能力

当 Agent 累积的观察记忆重要性之和超过阈值时，触发 Reflection——
Agent 回顾最近的记忆，生成更高层次的洞察（反思记忆）。

反射记忆特点:
- 记忆类型：reflection
- 重要性：较高 (0.7-1.0)
- 来源：对 observation 记忆的反思总结
- 作用：指导未来行为，形成长期认知
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.persona.memory_stream import MemoryStreamStore

logger = logging.getLogger(__name__)


class ReflectionTrigger:
    """Reflection 触发机制"""

    IMPORTANCE_THRESHOLD = 10.0  # 累积重要性阈值

    def __init__(self, memory_store: MemoryStreamStore):
        self.memory_store = memory_store

    def should_reflect(self, agent_id: str, window_hours: int = 24) -> bool:
        """判断是否触发 Reflection

        Args:
            agent_id: Agent ID
            window_hours: 检查时间窗口（小时）

        Returns:
            True 如果应该触发 Reflection
        """
        recent_memories = self.memory_store.get_recent(agent_id, limit=50)
        if not recent_memories:
            return False

        # 过滤未反射过的 observation 记忆
        now = datetime.now(timezone.utc)
        cumulative_importance = 0.0
        unreflected_count = 0

        for mem in recent_memories:
            # 只统计 observation 类型
            if mem.get("memory_type") != "observation":
                continue

            # 检查时间窗口
            try:
                created_at = datetime.fromisoformat(mem.get("created_at", ""))
                hours_elapsed = (now - created_at).total_seconds() / 3600
                if hours_elapsed > window_hours:
                    continue
            except (ValueError, TypeError):
                continue

            # 检查是否已经被反射过（通过 tags 判断）
            tags = mem.get("tags", [])
            if "reflected" in tags:
                continue

            cumulative_importance += mem.get("importance", 0.5)
            unreflected_count += 1

        # 记录调试信息
        logger.debug(
            "Agent %s Reflection 检查：累积重要性=%.2f, 未反射记忆数=%d, 阈值=%.2f",
            agent_id, cumulative_importance, unreflected_count, self.IMPORTANCE_THRESHOLD
        )

        return cumulative_importance >= self.IMPORTANCE_THRESHOLD

    def get_unreflected_memories(self, agent_id: str, window_hours: int = 24) -> List[Dict]:
        """获取未反射过的 observation 记忆"""
        recent_memories = self.memory_store.get_recent(agent_id, limit=50)
        if not recent_memories:
            return []

        now = datetime.now(timezone.utc)
        unreflected = []

        for mem in recent_memories:
            if mem.get("memory_type") != "observation":
                continue

            try:
                created_at = datetime.fromisoformat(mem.get("created_at", ""))
                hours_elapsed = (now - created_at).total_seconds() / 3600
                if hours_elapsed > window_hours:
                    continue
            except (ValueError, TypeError):
                continue

            tags = mem.get("tags", [])
            if "reflected" in tags:
                continue

            unreflected.append(mem)

        return unreflected


class ReflectionEngine:
    """Reflection 执行引擎"""

    def __init__(self, memory_store: MemoryStreamStore):
        self.memory_store = memory_store
        self.trigger = ReflectionTrigger(memory_store)
        # 统计信息
        self.total_reflections_triggered = 0
        self.total_reflections_generated = 0

    async def execute_reflection(self, agent_id: str) -> List[Dict[str, Any]]:
        """执行 Reflection，生成新的反思记忆

        Args:
            agent_id: Agent ID

        Returns:
            生成的 reflection 记忆列表
        """
        self.total_reflections_triggered += 1

        # 1. 获取触发 Reflection 的记忆集合
        recent_memories = self.trigger.get_unreflected_memories(agent_id)
        if not recent_memories:
            logger.warning("Agent %s 没有未反射的记忆", agent_id)
            return []

        logger.info(
            "Agent %s 开始 Reflection，累积了 %d 条未反射记忆",
            agent_id, len(recent_memories)
        )

        # 2. LLM 生成反思问题
        questions = await self._generate_reflection_questions(agent_id, recent_memories)
        if not questions:
            logger.warning("Agent %s Reflection 问题生成失败", agent_id)
            return []

        logger.debug("Agent %s 生成 %d 个反思问题", agent_id, len(questions))

        # 3. 对每个问题，检索相关记忆并生成反思
        reflections = []
        for question in questions:
            # 检索与该问题最相关的记忆
            related_memories = await self.memory_store.retrieve(
                agent_id, question, top_k=5
            )
            if not related_memories:
                continue

            # 生成反思
            reflection_text = await self._generate_reflection(
                agent_id, question, related_memories
            )
            if not reflection_text:
                continue

            # 评估反思的重要性
            importance = await self._assess_reflection_importance(reflection_text)

            # 创建 reflection 记忆条目
            reflection_entry = {
                "type": "reflection",
                "content": reflection_text,
                "importance": importance,
                "tags": ["reflection", question[:20]],
            }
            reflections.append(reflection_entry)

            # 标记原始记忆为已反射
            await self._mark_memories_reflected(related_memories)

        # 4. 批量存储 reflection 记忆
        if reflections:
            self.memory_store.store_batch(agent_id, reflections)
            self.total_reflections_generated += len(reflections)
            logger.info(
                "Agent %s Reflection 完成，生成 %d 条反思记忆 (总计触发=%d, 生成=%d)",
                agent_id, len(reflections),
                self.total_reflections_triggered,
                self.total_reflections_generated
            )

        return reflections

    def get_statistics(self) -> Dict[str, Any]:
        """获取 Reflection 统计信息"""
        return {
            "total_triggered": self.total_reflections_triggered,
            "total_generated": self.total_reflections_generated,
            "avg_per_trigger": (
                self.total_reflections_generated / self.total_reflections_triggered
                if self.total_reflections_triggered > 0 else 0.0
            ),
        }

    async def _generate_reflection_questions(
        self, agent_id: str, memories: List[Dict]
    ) -> List[str]:
        """基于最近记忆生成反思问题"""
        memory_texts = [m.get("content", "") for m in memories[:10]]
        memories_text = "\n".join(f"- {txt}" for txt in memory_texts)

        prompt = f"""你是一个思考者，正在反思最近经历的事情。

最近经历的记忆：
{memories_text}

请生成 2-3 个深刻的反思问题，帮助理解这些经历背后的模式和意义。
问题应该关注：
1. 这些经历反映了什么趋势或模式？
2. 这些经历如何影响我的价值观或态度？
3. 我从这些经历中学到了什么？

输出 JSON 数组格式：["问题 1", "问题 2", "问题 3"]

只输出问题列表，不要其他内容。"""

        try:
            resp = await call_llm(prompt, task_type="reflection_questions")
            questions = parse_llm_json(resp)
            if isinstance(questions, list) and questions:
                return [str(q) for q in questions if q]
        except Exception as e:
            logger.warning("Reflection 问题生成失败：%s", e)

        # fallback 问题
        return [
            "这些经历反映了什么模式？",
            "我从中学到了什么？",
        ]

    async def _generate_reflection(
        self, agent_id: str, question: str, related_memories: List[Dict]
    ) -> str:
        """基于问题和相关记忆生成反思"""
        memory_texts = [m.get("content", "") for m in related_memories]
        memories_text = "\n".join(f"- {txt}" for txt in memory_texts)

        prompt = f"""请反思以下问题，基于提供的记忆。

反思问题：{question}

相关记忆：
{memories_text}

请以第一人称写一段深刻的反思（200-400 字），包括：
1. 对这些记忆的整体观察
2. 发现的模式或趋势
3. 形成的新认知或态度变化

用连贯的段落表达，像日记一样自然。"""

        try:
            resp = await call_llm(prompt, task_type="reflection_generation")
            if resp and len(resp.strip()) > 20:
                return resp.strip()
        except Exception as e:
            logger.warning("Reflection 生成失败：%s", e)

        return ""

    async def _assess_reflection_importance(self, reflection_text: str) -> float:
        """评估反思的重要性（0-1）"""
        prompt = f"""评估以下反思的重要性（0-1 之间的小数）：

反思内容：
{reflection_text[:500]}

评分标准：
- 0.9-1.0: 涉及核心价值观或重大态度转变
- 0.7-0.9: 重要的自我认知或行为模式发现
- 0.5-0.7: 一般性的观察总结
- 0.3-0.5: 琐碎的日常反思

只输出一个 0-1 之间的小数，不要其他内容。"""

        try:
            resp = await call_llm(prompt, task_type="reflection_importance")
            importance = float(resp.strip())
            return max(0.0, min(1.0, importance))
        except Exception as e:
            logger.warning("Reflection 重要性评估失败：%s", e)

        # 默认较高重要性（反思通常比观察更重要）
        return 0.7

    async def _mark_memories_reflected(self, memories: List[Dict]):
        """标记记忆为已反射（更新 tags）"""
        # 注：当前 MemoryStreamStore 不支持直接更新，这里只做日志记录
        # 未来可以添加 update_entry 方法
        memory_ids = [m.get("memory_id", "") for m in memories]
        logger.debug("标记记忆为已反射：%s", memory_ids[:5])


async def test_reflection_mechanism(agent_id: str = "test_agent"):
    """测试 Reflection 机制"""
    from backend.services.persona.memory_stream import MemoryStreamStore

    memory_store = MemoryStreamStore()

    # 添加一些测试 observation 记忆
    test_memories = [
        {"type": "observation", "content": "看到关于 AI 伦理的讨论，引发思考", "importance": 0.8},
        {"type": "observation", "content": "参与了一场激烈的网络辩论", "importance": 0.7},
        {"type": "observation", "content": "阅读了一篇关于技术偏见的论文", "importance": 0.9},
        {"type": "observation", "content": "听到了不同观点的碰撞", "importance": 0.6},
        {"type": "observation", "content": "反思自己的立场是否客观", "importance": 0.7},
        {"type": "observation", "content": "发现自己在某些问题上的盲点", "importance": 0.8},
    ]

    memory_store.store_batch(agent_id, test_memories)

    # 测试 Reflection
    reflection_engine = ReflectionEngine(memory_store)
    trigger = ReflectionTrigger(memory_store)

    should_reflect = trigger.should_reflect(agent_id)
    print(f"Should reflect: {should_reflect}")

    if should_reflect:
        reflections = await reflection_engine.execute_reflection(agent_id)
        print(f"Generated {len(reflections)} reflections:")
        for ref in reflections:
            print(f"  - {ref['content'][:100]}... (importance={ref['importance']})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_reflection_mechanism())
