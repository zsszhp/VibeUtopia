"""Memory Stream 初始化 — Life Story → 记忆转换

将人生故事分解为 Memory Stream 初始条目，使 Agent 在仿真开始时已拥有"过去的记忆"
"""

import json
import logging
from typing import Any, Dict, List

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.persona.memory_stream import MemoryStreamStore

logger = logging.getLogger(__name__)


class StoryToMemoryConverter:
    """将 Life Story 转换为 Memory Stream 初始条目"""

    def __init__(self, memory_store: MemoryStreamStore):
        self.memory_store = memory_store

    async def convert(self, agent_id: str, life_story: str) -> List[Dict[str, Any]]:
        """将人生故事拆解为记忆条目

        Args:
            agent_id: Agent ID
            life_story: 完整人生故事

        Returns:
            记忆条目列表
        """
        memories = []

        # 1. 从人生故事中提取关键事件（observation 记忆）
        key_events = await self._extract_key_events(life_story)
        for event in key_events:
            memory_id = self.memory_store.store(
                agent_id=agent_id,
                content=event["description"],
                memory_type="observation",
                importance=event.get("importance", 0.5),
                tags=event.get("tags", []),
            )
            memories.append({
                "memory_id": memory_id,
                "type": "observation",
                "content": event["description"],
                "importance": event.get("importance", 0.5),
            })

        # 2. 从价值观描述中生成 reflection 记忆
        reflections = await self._extract_reflections(life_story)
        for reflection in reflections:
            memory_id = self.memory_store.store(
                agent_id=agent_id,
                content=reflection["content"],
                memory_type="reflection",
                importance=reflection.get("importance", 0.7),
                tags=reflection.get("tags", []),
            )
            memories.append({
                "memory_id": memory_id,
                "type": "reflection",
                "content": reflection["content"],
                "importance": reflection.get("importance", 0.7),
            })

        # 3. 从日常描述中生成 plan 记忆
        plans = await self._extract_routine_plans(life_story)
        for plan in plans:
            memory_id = self.memory_store.store(
                agent_id=agent_id,
                content=plan["content"],
                memory_type="plan",
                importance=plan.get("importance", 0.3),
                tags=plan.get("tags", []),
            )
            memories.append({
                "memory_id": memory_id,
                "type": "plan",
                "content": plan["content"],
                "importance": plan.get("importance", 0.3),
            })

        logger.info("✅ Agent %s Memory Stream 初始化完成，共%d条记忆", agent_id, len(memories))
        return memories

    async def _extract_key_events(self, life_story: str) -> List[Dict[str, Any]]:
        """从人生故事中提取关键事件（observation 记忆）"""

        prompt = f"""请从以下人生故事中提取关键事件，输出JSON列表。

人生故事：
{life_story[:5000]}

提取要求：
1. 选择对人格塑造有重要影响的事件（如童年经历、教育转折、职业变化、重大挫折等）
2. 每个事件包含具体描述和重要性评分
3. 事件数量：5-15 个

输出格式：
[
    {{
        "description": "事件详细描述（100-300 字）",
        "importance": 0.0-1.0（重要性评分），
        "tags": ["标签 1", "标签 2"]
    }}
]

示例：
[
    {{
        "description": "高中时因家境贫寒被同学嘲笑，从此对贫富差距话题格外敏感",
        "importance": 0.8,
        "tags": ["童年", "自尊", "贫富差距"]
    }}
]
"""

        try:
            response = await call_llm(prompt, task_type="memory_extraction")
            events = parse_llm_json(response)
            if isinstance(events, list):
                # 验证和清理
                cleaned = []
                for event in events:
                    if isinstance(event, dict) and "description" in event:
                        cleaned.append({
                            "description": event.get("description", "")[:500],
                            "importance": max(0.1, min(1.0, float(event.get("importance", 0.5)))),
                            "tags": event.get("tags", [])[:5],
                        })
                return cleaned[:15]  # 限制最多 15 个
        except Exception as e:
            logger.warning("关键事件提取失败：%s", e)

        # 降级：简单分割
        return self._simple_split(life_story)

    async def _extract_reflections(self, life_story: str) -> List[Dict[str, Any]]:
        """从人生故事中提取反思总结（reflection 记忆）"""

        prompt = f"""请从以下人生故事中提取价值观反思和人生洞察，输出JSON列表。

人生故事：
{life_story[:5000]}

提取要求：
1. 识别人物的核心价值观和人生哲学
2. 提取对重大问题的反思（如对社会、人际关系、职业发展的看法）
3. 数量：3-8 个

输出格式：
[
    {{
        "content": "反思内容（100-300 字）",
        "importance": 0.7-1.0（反思类记忆重要性较高）,
        "tags": ["价值观", "主题"]
    }}
]

示例：
[
    {{
        "content": "经过多年职场沉浮，我意识到成功不在于赚多少钱，而在于能否坚持做自己喜欢的事",
        "importance": 0.9,
        "tags": ["价值观", "职业观"]
    }}
]
"""

        try:
            response = await call_llm(prompt, task_type="memory_extraction")
            reflections = parse_llm_json(response)
            if isinstance(reflections, list):
                cleaned = []
                for ref in reflections:
                    if isinstance(ref, dict) and "content" in ref:
                        cleaned.append({
                            "content": ref.get("content", "")[:500],
                            "importance": max(0.7, min(1.0, float(ref.get("importance", 0.8)))),
                            "tags": ref.get("tags", ["反思"])[:5],
                        })
                return cleaned[:8]
        except Exception as e:
            logger.warning("反思提取失败：%s", e)

        return []

    async def _extract_routine_plans(self, life_story: str) -> List[Dict[str, Any]]:
        """从人生故事中提取日常习惯和计划（plan 记忆）"""

        prompt = f"""请从以下人生故事中提取日常习惯和行为计划，输出 JSON 列表。

人生故事：
{life_story[:5000]}

提取要求：
1. 识别人物的日常行为习惯（如阅读、运动、社交频率）
2. 提取短期计划或意图（如"打算学习新技能"、"计划换工作"）
3. 数量：3-6 个

输出格式：
[
    {{
        "content": "习惯或计划描述（50-200 字）",
        "importance": 0.2-0.5（日常计划重要性较低）,
        "tags": ["习惯", "计划"]
    }}
]

示例：
[
    {{
        "content": "每天晚上睡前阅读 30 分钟，主要看历史和社会学书籍",
        "importance": 0.3,
        "tags": ["习惯", "阅读"]
    }}
]
"""

        try:
            response = await call_llm(prompt, task_type="memory_extraction")
            plans = parse_llm_json(response)
            if isinstance(plans, list):
                cleaned = []
                for plan in plans:
                    if isinstance(plan, dict) and "content" in plan:
                        cleaned.append({
                            "content": plan.get("content", "")[:300],
                            "importance": max(0.2, min(0.6, float(plan.get("importance", 0.3)))),
                            "tags": plan.get("tags", ["计划"])[:5],
                        })
                return cleaned[:6]
        except Exception as e:
            logger.warning("计划提取失败：%s", e)

        return []

    def _simple_split(self, life_story: str) -> List[Dict[str, Any]]:
        """降级方案：简单分割故事为记忆片段"""

        if not life_story:
            return []

        # 按段落分割
        paragraphs = life_story.split("\n\n")
        memories = []

        for para in paragraphs[:10]:  # 最多 10 段
            para = para.strip()
            if len(para) > 50:
                memories.append({
                    "description": para[:300],
                    "importance": 0.5,
                    "tags": ["人生故事"],
                })

        return memories


def initialize_memory_stream_for_agent(
    agent_id: str,
    life_story: str,
    persist_dir: str = "./data/chroma_memories",
) -> List[Dict[str, Any]]:
    """同步版本：为 Agent 初始化 Memory Stream

    Args:
        agent_id: Agent ID
        life_story: 人生故事
        persist_dir: ChromaDB 持久化目录

    Returns:
        记忆条目列表
    """
    import asyncio

    memory_store = MemoryStreamStore(persist_dir=persist_dir)
    converter = StoryToMemoryConverter(memory_store)

    return asyncio.run(converter.convert(agent_id, life_story))


if __name__ == "__main__":
    # 测试用例
    logging.basicConfig(level=logging.INFO)

    test_story = """
    ## 童年与家庭

    我在北京的一个普通工薪家庭长大。父母都是工厂工人，虽然收入不高，但非常重视我的教育。小时候家里条件不好，经常要计算着花钱，这让我从小就对金钱比较敏感。

    小学时成绩中等，但初中时遇到了一位好老师，她发现我对历史特别感兴趣，经常借书给我看。这段经历让我相信教育可以改变命运。

    ## 教育与成长

    高考考上了北京的一所 211 大学，学习社会学专业。大学期间开始接触各种社会理论，对贫富差距、社会流动性等议题产生了浓厚兴趣。

    大二时参加了学校组织的农村调研活动，第一次亲眼看到城乡差距的震撼。那次经历后，我决定以后要做一些对社会有实际贡献的工作。

    ## 职业与事业

    毕业后进入一家互联网公司做用户研究。工作三年，从初级研究员做到了团队负责人。虽然收入比以前好了很多，但经常感到工作内容和社会理想有落差。

    最近在考虑是否要读研深造，或者转向公益行业。家人希望我稳定，但内心总觉得应该追求更有意义的事情。

    ## 价值观与信仰

    政治立场偏左，支持社会公平和再分配政策。认为贫富差距是中国面临的最大挑战之一。

    消费观比较理性，虽然收入提高了，但保持储蓄习惯。对奢侈品没什么兴趣，更愿意把钱花在旅行和学习上。

    ## 网络行为与态度

    主要使用知乎和微博。在知乎上会认真写长文回答，微博上 mostly 是转发和偶尔评论。

    遇到社会热点事件时，会先等一等，看多方信息再表态。不太喜欢网络上非黑即白的讨论氛围。
    """

    logger.info("🧪 开始 Memory Stream 初始化测试")

    memories = initialize_memory_stream_for_agent(
        agent_id="test_agent_memory_init",
        life_story=test_story,
    )

    logger.info("\n✅ 转换完成！生成的记忆:")
    for i, mem in enumerate(memories, 1):
        logger.info(f"{i}. [{mem['type']}] 重要性={mem['importance']:.2f}")
        logger.info(f"   内容：{mem['content'][:100]}...")

    logger.info("\n总计：%d 条记忆", len(memories))
