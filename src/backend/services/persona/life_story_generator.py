"""Life Story 驱动人格系统 — A/B/C 三级人格生成

A-tier: AI访谈生成器 — 6轮结构化访谈 → 数万字人生故事
B-tier: CGSS采样+LLM丰富 — 人口统计采样 → LLM推理L2-L7 → 千字故事
C-tier: 模板变体 — 原型模板+随机参数变体 → 百字梗概
"""

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class LifeStoryPersona:
    """Life Story 生成的人格"""
    tier: str  # A/B/C
    life_story: str
    persona_7layers: Dict[str, Any]
    initial_memories: List[Dict[str, Any]] = field(default_factory=list)
    big_five: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    platform: str = ""
    archetype: str = ""


class LifeStoryInterviewer:
    """A-tier: AI访谈生成器 — 6轮结构化访谈生成数万字人生故事"""

    INTERVIEW_ROUNDS = [
        {
            "topic": "童年与家庭",
            "prompt": "请详细描述你的童年生活。你是在哪里长大的？家庭环境如何？父母是什么样的人？你和他们关系如何？有没有什么童年经历对你影响特别大？",
            "target_words": 3000,
        },
        {
            "topic": "教育与成长",
            "prompt": "请谈谈你的求学经历。你在学校表现如何？最喜欢的科目是什么？有没有对你影响深远的老师或同学？你如何看待教育？",
            "target_words": 3000,
        },
        {
            "topic": "职业与事业",
            "prompt": "请描述你的职业经历。你是如何选择现在的工作的？工作中最大的挑战和成就是什么？你对当前职业的满意度如何？未来有什么职业规划？",
            "target_words": 3000,
        },
        {
            "topic": "社交与关系",
            "prompt": "请谈谈你的社交生活。你有哪些重要的朋友？你如何维持社交关系？在社交场合你通常是怎样的？你对亲密关系有什么看法？",
            "target_words": 2500,
        },
        {
            "topic": "价值观与信仰",
            "prompt": "请分享你的核心价值观。什么对你来说最重要？你对社会热点问题（如性别平等、贫富差距、环境保护）有什么看法？你的政治立场倾向是什么？",
            "target_words": 2500,
        },
        {
            "topic": "网络行为与态度",
            "prompt": "请描述你在互联网上的行为习惯。你主要使用哪些平台？在每个平台上你通常做什么？你对网络上的争议话题通常持什么态度？你会公开发表评论吗？什么话题会让你忍不住发言？",
            "target_words": 2500,
        },
    ]

    async def generate(self, platform: str, archetype: str, base_profile: Dict[str, Any]) -> LifeStoryPersona:
        """通过6轮AI访谈生成完整人生故事"""
        story_parts = []
        current_context = f"你是一个{archetype}类型的{platform}用户。"

        if base_profile:
            current_context += f"基本信息：{json.dumps(base_profile, ensure_ascii=False)}"

        for i, round_config in enumerate(self.INTERVIEW_ROUNDS):
            prompt = f"""{current_context}

作为这个人物，请回答以下问题。请以第一人称详细叙述，就像在回忆自己的人生。

问题：{round_config['prompt']}

请写至少{round_config['target_words']}字的详细回答。要具体、真实、有细节，不要泛泛而谈。"""

            try:
                response = await call_llm(
                    prompt,
                    system="你正在扮演一个真实的人物，请以第一人称详细回忆自己的人生经历。回答要具体、真实、有细节。",
                    task_type="life_story_generation",
                )
                story_parts.append(f"## {round_config['topic']}\n\n{response}")
                current_context += f"\n\n{round_config['topic']}：{response[:500]}..."
            except Exception as e:
                logger.warning("A-tier访谈第%d轮失败: %s", i + 1, e)
                story_parts.append(f"## {round_config['topic']}\n\n（访谈记录缺失）")

        full_story = "\n\n".join(story_parts)

        persona_7layers = await self._story_to_7layers(full_story, platform, archetype)
        initial_memories = self._story_to_memories(full_story)
        big_five = await self._story_to_big_five(full_story)

        return LifeStoryPersona(
            tier="A",
            life_story=full_story,
            persona_7layers=persona_7layers,
            initial_memories=initial_memories,
            big_five=big_five,
            platform=platform,
            archetype=archetype,
        )

    async def _story_to_7layers(self, story: str, platform: str, archetype: str) -> Dict[str, Any]:
        """从人生故事提取7层人格"""
        prompt = f"""请从以下人生故事中提取7层人格信息，输出JSON格式。

人生故事：
{story[:6000]}

请输出以下JSON格式：
{{
    "L1_basic": {{
        "age": "年龄段",
        "gender": "性别",
        "education": "学历",
        "occupation": "职业",
        "income": "收入水平",
        "location": "居住地",
        "marital_status": "婚姻状态"
    }},
    "L2_values": {{
        "political_stance": "政治立场(左倾/中立/右倾)",
        "consumerism": 5.0,
        "nationalism": 5.0,
        "egalitarianism": 5.0,
        "environmentalism": 5.0,
        "traditionalism": 5.0
    }},
    "L3_knowledge": {{
        "professional_fields": ["领域1"],
        "hobbies": ["爱好1"],
        "cognitive_level": "初级/中等/高级",
        "media_preferences": ["偏好媒体类型"]
    }},
    "L4_behavior": {{
        "expression_style": "含蓄/温和/直接/激进",
        "interaction_preference": "潜水/偶尔评论/活跃评论/主动发帖",
        "conflict_style": "回避/妥协/对抗/理性讨论",
        "humor_style": "无/冷幽默/自嘲/讽刺"
    }},
    "L5_correction": {{
        "self_censorship": "低/中/高",
        "sensitive_triggers": ["触发词1"],
        "taboo_topics": ["禁忌话题1"],
        "correction_tendency": "从不/偶尔/经常"
    }},
    "L6_social": {{
        "influence_level": 5.0,
        "group_identity": ["群体1"],
        "conformity": 5.0,
        "leadership": 5.0
    }},
    "L7_evolution": {{
        "emotional_baseline": "消极/平稳/积极",
        "recent_experiences": ["经历1"],
        "personality_trend": "稳定/成长/波动",
        "resilience": 5.0
    }}
}}

注意：数值字段范围1-10，5为中等。所有字段都必须填写。"""

        try:
            resp = await call_llm(prompt, task_type="life_story_generation")
            data = parse_llm_json(resp)
            if data and "L1_basic" in data:
                return data
        except Exception as e:
            logger.warning("Story→7层提取失败: %s", e)
        return self._default_7layers(platform, archetype)

    def _story_to_memories(self, story: str) -> List[Dict[str, Any]]:
        """从人生故事提取初始记忆条目"""
        memories = []
        sections = story.split("## ")
        for section in sections[1:]:
            lines = section.strip().split("\n")
            topic = lines[0].strip() if lines else ""
            content = "\n".join(lines[1:]).strip()[:500]
            if content:
                memories.append({
                    "type": "observation",
                    "content": f"[{topic}] {content}",
                    "importance": random.uniform(0.5, 0.9),
                    "tags": [topic],
                })
        return memories[:20]

    async def _story_to_big_five(self, story: str) -> Dict[str, float]:
        """从人生故事推断Big Five人格特质"""
        prompt = f"""请根据以下人生故事，评估这个人的Big Five人格特质，输出JSON。

人生故事摘要：
{story[:3000]}

输出格式：
{{
    "openness": 0.0-1.0,
    "conscientiousness": 0.0-1.0,
    "extraversion": 0.0-1.0,
    "agreeableness": 0.0-1.0,
    "neuroticism": 0.0-1.0
}}"""

        try:
            resp = await call_llm(prompt, task_type="life_story_generation")
            data = parse_llm_json(resp)
            if data:
                return {k: max(0.0, min(1.0, float(v))) for k, v in data.items() if k in (
                    "openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"
                )}
        except Exception as e:
            logger.warning("Story→Big Five推断失败: %s", e)
        return {"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5}

    def _default_7layers(self, platform: str, archetype: str) -> Dict[str, Any]:
        return {
            "L1_basic": {"age": "25-34", "gender": "未知", "education": "本科", "occupation": "未知"},
            "L2_values": {"political_stance": "中立", "consumerism": 5.0, "nationalism": 5.0},
            "L3_knowledge": {"cognitive_level": "中等"},
            "L4_behavior": {"expression_style": "温和", "interaction_preference": "偶尔评论"},
            "L5_correction": {"self_censorship": "中"},
            "L6_social": {"influence_level": 5.0},
            "L7_evolution": {"emotional_baseline": "平稳"},
        }


class CGSSSampler:
    """B-tier: CGSS采样+LLM丰富 — 人口统计采样 → LLM推理L2-L7 → 千字故事"""

    CGSS_DEMOGRAPHICS = [
        {"age": "18-24", "gender": "男", "education": "高中", "income": "低", "location": "三线城市", "weight": 0.08},
        {"age": "18-24", "gender": "女", "education": "本科", "income": "中低", "location": "二线城市", "weight": 0.07},
        {"age": "25-34", "gender": "男", "education": "本科", "income": "中等", "location": "一线城市", "weight": 0.12},
        {"age": "25-34", "gender": "女", "education": "本科", "income": "中等", "location": "新一线城市", "weight": 0.10},
        {"age": "25-34", "gender": "男", "education": "硕士", "income": "中高", "location": "一线城市", "weight": 0.08},
        {"age": "35-44", "gender": "男", "education": "本科", "income": "中等", "location": "二线城市", "weight": 0.09},
        {"age": "35-44", "gender": "女", "education": "大专", "income": "中低", "location": "三线城市", "weight": 0.07},
        {"age": "45-54", "gender": "男", "education": "高中", "income": "中等", "location": "三线城市", "weight": 0.06},
        {"age": "45-54", "gender": "女", "education": "初中", "income": "低", "location": "农村", "weight": 0.05},
        {"age": "25-34", "gender": "男", "education": "大专", "income": "中低", "location": "三线城市", "weight": 0.08},
        {"age": "18-24", "gender": "男", "education": "本科", "income": "低", "location": "新一线城市", "weight": 0.06},
        {"age": "35-44", "gender": "女", "education": "本科", "income": "中等", "location": "一线城市", "weight": 0.07},
        {"age": "25-34", "gender": "女", "education": "硕士", "income": "中高", "location": "一线城市", "weight": 0.07},
    ]

    async def generate(self, platform: str, archetype: str) -> LifeStoryPersona:
        """CGSS采样+LLM丰富"""
        demo = self._sample_demographics()

        prompt = f"""请根据以下人口统计信息，推理出一个完整的人物形象，并写出约1000字的人生故事。

人口统计：
- 年龄段：{demo['age']}
- 性别：{demo['gender']}
- 学历：{demo['education']}
- 收入水平：{demo['income']}
- 居住地：{demo['location']}
- 平台：{platform}
- 用户类型：{archetype}

请输出JSON格式：
{{
    "life_story": "约1000字的人生故事",
    "L1_basic": {{...}},
    "L2_values": {{...}},
    "L3_knowledge": {{...}},
    "L4_behavior": {{...}},
    "L5_correction": {{...}},
    "L6_social": {{...}},
    "L7_evolution": {{...}},
    "big_five": {{
        "openness": 0.0-1.0,
        "conscientiousness": 0.0-1.0,
        "extraversion": 0.0-1.0,
        "agreeableness": 0.0-1.0,
        "neuroticism": 0.0-1.0
    }}
}}

L1-L7的格式要求同A-tier。数值字段范围1-10。故事要真实、有细节、符合人口统计特征。"""

        try:
            resp = await call_llm(prompt, task_type="persona_generation")
            data = parse_llm_json(resp)
            if data:
                story = data.pop("life_story", "")
                big_five = data.pop("big_five", {})
                memories = self._story_to_memories(story)
                return LifeStoryPersona(
                    tier="B",
                    life_story=story,
                    persona_7layers=data,
                    initial_memories=memories,
                    big_five=big_five,
                    platform=platform,
                    archetype=archetype,
                )
        except Exception as e:
            logger.warning("B-tier生成失败: %s", e)

        return LifeStoryPersona(
            tier="B",
            life_story="",
            persona_7layers=self._default_7layers(),
            platform=platform,
            archetype=archetype,
        )

    def _sample_demographics(self) -> Dict[str, str]:
        """按权重采样人口统计"""
        weights = [d["weight"] for d in self.CGSS_DEMOGRAPHICS]
        total = sum(weights)
        weights = [w / total for w in weights]
        chosen = random.choices(self.CGSS_DEMOGRAPHICS, weights=weights, k=1)[0]
        return {k: v for k, v in chosen.items() if k != "weight"}

    def _story_to_memories(self, story: str) -> List[Dict[str, Any]]:
        if not story:
            return []
        sentences = story.replace("。", "。\n").split("\n")
        memories = []
        for s in sentences:
            s = s.strip()
            if len(s) > 10:
                memories.append({
                    "type": "observation",
                    "content": s[:200],
                    "importance": random.uniform(0.3, 0.7),
                    "tags": [],
                })
        return memories[:10]

    def _default_7layers(self) -> Dict[str, Any]:
        return {
            "L1_basic": {"age": "25-34", "gender": "未知"},
            "L2_values": {},
            "L3_knowledge": {},
            "L4_behavior": {},
            "L5_correction": {},
            "L6_social": {},
            "L7_evolution": {},
        }


class TemplateVariator:
    """C-tier: 模板变体 — 原型模板+随机参数变体 → 百字梗概"""

    ARCHETYPE_TEMPLATES = {
        "主流用户": {
            "L1_basic": {"age": "25-34", "education": "本科", "income": "中等"},
            "L2_values": {"political_stance": "中立", "consumerism": 5.0},
            "L4_behavior": {"expression_style": "温和", "interaction_preference": "偶尔评论"},
        },
        "争议用户": {
            "L1_basic": {"age": "18-24", "education": "高中", "income": "低"},
            "L2_values": {"political_stance": "右倾", "consumerism": 3.0},
            "L4_behavior": {"expression_style": "激进", "interaction_preference": "活跃评论"},
        },
        "边缘用户": {
            "L1_basic": {"age": "35-44", "education": "初中", "income": "低"},
            "L2_values": {"political_stance": "左倾", "consumerism": 2.0},
            "L4_behavior": {"expression_style": "含蓄", "interaction_preference": "潜水"},
        },
        "KOL/大V": {
            "L1_basic": {"age": "25-34", "education": "硕士", "income": "高"},
            "L2_values": {"political_stance": "中立", "consumerism": 6.0},
            "L4_behavior": {"expression_style": "直接", "interaction_preference": "主动发帖"},
            "L6_social": {"influence_level": 8.0},
        },
        "跨界用户": {
            "L1_basic": {"age": "25-34", "education": "本科", "income": "中高"},
            "L2_values": {"political_stance": "左倾", "consumerism": 4.0},
            "L4_behavior": {"expression_style": "温和", "interaction_preference": "活跃评论"},
            "L3_knowledge": {"professional_fields": ["科技", "文化"]},
        },
    }

    def generate(self, platform: str, archetype: str) -> LifeStoryPersona:
        """模板变体生成"""
        template = self.ARCHETYPE_TEMPLATES.get(archetype, self.ARCHETYPE_TEMPLATES["主流用户"])
        persona = self._apply_variations(template)
        story = self._generate_sketch(persona, platform, archetype)

        return LifeStoryPersona(
            tier="C",
            life_story=story,
            persona_7layers=persona,
            initial_memories=[],
            big_five=self._infer_big_five(persona),
            platform=platform,
            archetype=archetype,
        )

    def _apply_variations(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """在模板基础上添加随机变体"""
        import copy
        persona = copy.deepcopy(template)

        for layer_name, layer_data in persona.items():
            if isinstance(layer_data, dict):
                for key, value in layer_data.items():
                    if isinstance(value, float):
                        layer_data[key] = max(1.0, min(10.0, value + random.uniform(-1.5, 1.5)))

        if "L2_values" not in persona:
            persona["L2_values"] = {}
        persona["L2_values"]["nationalism"] = max(1.0, min(10.0, 5.0 + random.uniform(-2, 2)))
        persona["L2_values"]["egalitarianism"] = max(1.0, min(10.0, 5.0 + random.uniform(-2, 2)))

        if "L5_correction" not in persona:
            persona["L5_correction"] = {}
        persona["L5_correction"]["self_censorship"] = random.choice(["低", "中", "高"])

        if "L7_evolution" not in persona:
            persona["L7_evolution"] = {}
        persona["L7_evolution"]["emotional_baseline"] = random.choice(["消极", "平稳", "积极"])

        return persona

    def _generate_sketch(self, persona: Dict[str, Any], platform: str, archetype: str) -> str:
        """生成百字梗概"""
        l1 = persona.get("L1_basic", {})
        l4 = persona.get("L4_behavior", {})
        return (
            f"一个{l1.get('age', '未知')}岁的{l1.get('education', '未知')}学历"
            f"{archetype}，在{platform}上{l4.get('interaction_preference', '偶尔评论')}。"
            f"表达风格{l4.get('expression_style', '温和')}，"
            f"自我审查{l4.get('self_censorship', '中')}。"
        )

    def _infer_big_five(self, persona: Dict[str, Any]) -> Dict[str, float]:
        """从人格属性推断Big Five"""
        l4 = persona.get("L4_behavior", {})
        l2 = persona.get("L2_values", {})

        extraversion = 0.3
        if l4.get("interaction_preference") in ("活跃评论", "主动发帖"):
            extraversion = 0.7
        elif l4.get("interaction_preference") == "潜水":
            extraversion = 0.2

        agreeableness = 0.5
        if l4.get("expression_style") == "激进":
            agreeableness = 0.3
        elif l4.get("expression_style") == "含蓄":
            agreeableness = 0.7

        openness = 0.5
        if l2.get("political_stance") in ("左倾", "右倾"):
            openness = 0.6

        return {
            "openness": openness,
            "conscientiousness": 0.5,
            "extraversion": extraversion,
            "agreeableness": agreeableness,
            "neuroticism": 0.5,
        }


class PersonaFactory:
    """人格工厂 — 统一入口，根据tier选择生成策略"""

    def __init__(self):
        self.a_interviewer = LifeStoryInterviewer()
        self.b_sampler = CGSSSampler()
        self.c_variator = TemplateVariator()

    async def generate(
        self,
        platform: str,
        archetype: str,
        tier: str = "C",
        base_profile: Optional[Dict[str, Any]] = None,
    ) -> LifeStoryPersona:
        """生成人格

        Args:
            platform: 平台名
            archetype: 原型类型(主流用户/争议用户/边缘用户/KOL/跨界用户)
            tier: 生成层级 A/B/C
            base_profile: 可选的基础人口统计信息
        """
        if tier == "A":
            persona = await self.a_interviewer.generate(platform, archetype, base_profile or {})
        elif tier == "B":
            persona = await self.b_sampler.generate(platform, archetype)
        else:
            persona = self.c_variator.generate(platform, archetype)

        # 质量校验
        from backend.services.persona.quality_validator import QualityValidator
        validator = QualityValidator()
        if persona.persona_7layers:
            fixed, score = await validator.validate_and_fix(persona.persona_7layers)
            persona.persona_7layers = fixed
            persona.quality_score = score

        return persona

    async def generate_batch(
        self,
        platform: str,
        count: int = 10,
        tier_distribution: Optional[Dict[str, int]] = None,
    ) -> List[LifeStoryPersona]:
        """批量生成人格

        Args:
            platform: 平台名
            count: 生成数量
            tier_distribution: 各层级数量 {"A": 1, "B": 3, "C": 6}
        """
        if tier_distribution is None:
            a_count = max(1, count // 10)
            b_count = max(1, count // 3)
            c_count = count - a_count - b_count
            tier_distribution = {"A": a_count, "B": b_count, "C": c_count}

        archetypes = list(TemplateVariator.ARCHETYPE_TEMPLATES.keys())
        personas = []

        for tier_name, tier_count in tier_distribution.items():
            for _ in range(tier_count):
                archetype = random.choice(archetypes)
                try:
                    persona = await self.generate(platform, archetype, tier_name)
                    personas.append(persona)
                except Exception as e:
                    logger.warning("人格生成失败(tier=%s, archetype=%s): %s", tier_name, archetype, e)

        return personas
