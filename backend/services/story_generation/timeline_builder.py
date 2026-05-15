"""T7.1 人生时间线构建服务

基于完整人格画像（32 原型 + 5 平台人格 + 价值观体系），自动生成个体的人生关键节点故事。

功能：
- 根据 MBTI 类型和 Enneagram 类型推导关键人生决策模式
- 结合 Big Five 特质推导职业发展路径
- 结合依恋类型推导重要关系节点
- 生成包含 5 个人生阶段的时间线，每个阶段包含≥3 个关键事件
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


class LifeStage(Enum):
    """人生阶段枚举"""
    CHILDHOOD = "童年期 (0-12 岁)"
    ADOLESCENCE = "青少年期 (13-18 岁)"
    EARLY_ADULTHOOD = "成年早期 (19-35 岁)"
    MIDDLE_ADULTHOOD = "成年中期 (36-55 岁)"
    LATE_ADULTHOOD = "成年晚期 (56 岁+)"


class EventType(Enum):
    """关键事件类型"""
    TURNING_POINT = "转折点"  # 重大决策时刻
    CHALLENGE = "挑战期"  # 困难与突破
    HIGHLIGHT = "高光时刻"  # 成就与认可
    RELATIONSHIP = "关系节点"  # 重要他人相遇/分离
    MIGRATION = "迁徙"  # 地理/环境变化
    CAREER_CHANGE = "职业转换"  # 职业道路变化


@dataclass
class LifeEvent:
    """人生关键事件"""
    stage: LifeStage
    event_type: EventType
    age: int
    title: str
    description: str
    impact: str  # 对人格/价值观的影响
    involved_traits: Dict[str, Any]  # 涉及的人格特质
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class LifeTimeline:
    """人生时间线"""
    user_id: str
    persona_id: str
    stages: Dict[LifeStage, List[LifeEvent]]
    total_events: int
    narrative_arc: str  # 叙事弧线类型
    generated_at: datetime = field(default_factory=datetime.now)


class TimelineBuilder:
    """人生时间线构建器"""

    # MBTI 职业倾向映射
    MBTI_CAREER_PATHS = {
        "INTJ": ["科学研究", "战略规划", "技术开发", "金融分析"],
        "INTP": ["学术研究", "软件开发", "数据分析", "哲学"],
        "ENTJ": ["企业管理", "创业", "政治", "投资银行"],
        "ENTP": ["创业", "市场营销", "咨询", "媒体"],
        "INFJ": ["心理咨询", "教育", "写作", "社会工作"],
        "INFP": ["艺术创作", "写作", "心理学", "非营利组织"],
        "ENFJ": ["教育培训", "人力资源", "公关", "政治"],
        "ENFP": ["媒体", "市场营销", "创业", "咨询"],
        "ISTJ": ["会计", "法律", "医疗", "公务员"],
        "ISFJ": ["护理", "教育", "行政", "社会工作"],
        "ESTJ": ["管理", "执法", "军事", "金融"],
        "ESFJ": ["销售", "客服", "医疗", "教育"],
        "ISTP": ["工程", "技术", "体育", "手工艺"],
        "ISFP": ["艺术", "设计", "音乐", "兽医"],
        "ESTP": ["销售", "创业", "体育", "紧急救援"],
        "ESFP": ["表演", "销售", "旅游", "娱乐"],
    }

    # Enneagram 核心动机
    ENNEAGRAM_MOTIVATIONS = {
        1: "追求完美与正直",
        2: "渴望被爱与被需要",
        3: "追求成就与认可",
        4: "寻找独特的自我",
        5: "追求知识与理解",
        6: "寻求安全与归属",
        7: "追求快乐与新鲜体验",
        8: "追求掌控与自主",
        9: "追求和谐与平静",
    }

    # 依恋类型与关系模式
    ATTACHMENT_RELATIONSHIPS = {
        "secure": {
            "pattern": "容易建立亲密关系，信任他人",
            "challenges": ["平衡独立与依赖"],
            "strengths": ["情感稳定", "沟通良好"],
        },
        "anxious": {
            "pattern": "渴望亲密但害怕被抛弃",
            "challenges": ["过度依赖", "嫉妒心强"],
            "strengths": ["情感丰富", "同理心强"],
        },
        "avoidant": {
            "pattern": "回避亲密，强调独立",
            "challenges": ["难以信任他人", "情感疏离"],
            "strengths": ["自立自强", "边界清晰"],
        },
        "disorganized": {
            "pattern": "矛盾的关系模式",
            "challenges": ["情绪不稳定", "信任问题"],
            "strengths": ["适应力强", "警觉性高"],
        },
    }

    def __init__(self, model_name: str = "Qwen3.6-Plus"):
        self.model_name = model_name

    async def build_timeline(
        self,
        persona_data: Dict[str, Any],
        user_id: str = "default",
    ) -> LifeTimeline:
        """
        基于人格画像构建人生时间线

        Args:
            persona_data: 完整人格画像，包含：
                - mbti_type: MBTI 类型 (16 种)
                - enneagram_type: 九型人格 (1-9)
                - big_five: Big Five 特质 (openness, conscientiousness, extraversion, agreeableness, neuroticism)
                - attachment_style: 依恋类型 (secure/anxious/avoidant/disorganized)
                - values: 价值观体系
                - platform_personas: 5 个平台人格
                - archetype: 32 个原型之一
            user_id: 用户 ID

        Returns:
            LifeTimeline: 包含 5 个人生阶段的时间线
        """
        logger.info("开始构建人生时间线，用户：%s, 人格：%s", user_id, persona_data.get("archetype", "unknown"))

        stages = {}
        total_events = 0

        for stage in LifeStage:
            events = await self._generate_stage_events(stage, persona_data)
            stages[stage] = events
            total_events += len(events)

        narrative_arc = self._determine_narrative_arc(persona_data)

        timeline = LifeTimeline(
            user_id=user_id,
            persona_id=persona_data.get("id", "unknown"),
            stages=stages,
            total_events=total_events,
            narrative_arc=narrative_arc,
        )

        logger.info(
            "人生时间线构建完成，用户：%s, 阶段数：%d, 总事件数：%d, 叙事弧线：%s",
            user_id,
            len(stages),
            total_events,
            narrative_arc,
        )

        return timeline

    async def _generate_stage_events(
        self,
        stage: LifeStage,
        persona_data: Dict[str, Any],
    ) -> List[LifeEvent]:
        """生成某个人生阶段的关键事件（至少 3 个）"""
        logger.debug("生成%s的关键事件", stage.value)

        age_range = self._get_age_range(stage)
        base_prompt = self._build_stage_prompt(stage, persona_data, age_range)

        try:
            response = await parse_llm_json(
                prompt=base_prompt,
                system="你是一位专业的心理传记作家，擅长基于人格特质推导人生经历。请生成真实、具体、有细节的人生事件。",
                task_type="story_generation",
                model=self.model_name,
            )

            events = []
            for event_data in response.get("events", []):
                event = self._parse_event(event_data, stage, persona_data)
                if event:
                    events.append(event)

            if len(events) < 3:
                events.extend(await self._generate_fallback_events(stage, persona_data, 3 - len(events)))

            return events

        except Exception as e:
            logger.warning("LLM 生成%s事件失败：%s，使用规则生成 fallback", stage.value, e)
            return await self._generate_fallback_events(stage, persona_data, 3)

    def _get_age_range(self, stage: LifeStage) -> tuple[int, int]:
        """获取人生阶段的年龄范围"""
        age_ranges = {
            LifeStage.CHILDHOOD: (0, 12),
            LifeStage.ADOLESCENCE: (13, 18),
            LifeStage.EARLY_ADULTHOOD: (19, 35),
            LifeStage.MIDDLE_ADULTHOOD: (36, 55),
            LifeStage.LATE_ADULTHOOD: (56, 80),
        }
        return age_ranges.get(stage, (0, 100))

    def _build_stage_prompt(
        self,
        stage: LifeStage,
        persona_data: Dict[str, Any],
        age_range: tuple[int, int],
    ) -> str:
        """构建某个人生阶段的事件生成 Prompt"""
        mbti = persona_data.get("mbti_type", "INTJ")
        enneagram = persona_data.get("enneagram_type", 5)
        big_five = persona_data.get("big_five", {})
        attachment = persona_data.get("attachment_style", "secure")
        archetype = persona_data.get("archetype", "探索者")
        values = persona_data.get("values", {})

        career_paths = self.MBTI_CAREER_PATHS.get(mbti, ["通用职业"])
        enneagram_motivation = self.ENNEAGRAM_MOTIVATIONS.get(enneagram, "追求个人目标")
        attachment_info = self.ATTACHMENT_RELATIONSHIPS.get(attachment, {})

        prompt = f"""请为以下人格画像生成{stage.value}的关键人生事件。

【人格画像】
- MBTI 类型：{mbti}
- 九型人格：{enneagram} ({enneagram_motivation})
- Big Five 特质：
  * 开放性：{big_five.get('openness', 0.5):.2f}
  * 尽责性：{big_five.get('conscientiousness', 0.5):.2f}
  * 外向性：{big_five.get('extraversion', 0.5):.2f}
  * 宜人性：{big_five.get('agreeableness', 0.5):.2f}
  * 神经质：{big_five.get('neuroticism', 0.5):.2f}
- 依恋类型：{attachment} ({attachment_info.get('pattern', '未知')})
- 人格原型：{archetype}
- 核心价值观：{json.dumps(values, ensure_ascii=False)}
- 可能职业路径：{', '.join(career_paths)}

【要求】
1. 生成 3-5 个关键事件，覆盖以下类型：
   - 转折点（重大决策时刻）
   - 挑战期（困难与突破）
   - 高光时刻（成就与认可）
   - 关系节点（重要他人相遇/分离）

2. 每个事件必须包含：
   - age: 具体年龄 ({age_range[0]}-{age_range[1]}岁之间)
   - event_type: 事件类型 (从上述 4 类中选择)
   - title: 简短标题 (10 字以内)
   - description: 详细描述 (100-200 字)
   - impact: 对人格/价值观的影响 (50-100 字)

3. 事件应该：
   - 符合 MBTI 类型的典型发展路径
   - 体现九型人格的核心动机
   - 与 Big Five 特质一致（如高开放性更可能经历多样事件）
   - 反映依恋类型对关系的影响
   - 符合{archetype}原型的成长轨迹

4. 事件之间应该有逻辑连贯性，形成一条清晰的成长线

请以 JSON 格式输出：
{{
    "events": [
        {{
            "age": 15,
            "event_type": "转折点",
            "title": "选择理科方向",
            "description": "...",
            "impact": "..."
        }}
    ]
}}
"""
        return prompt

    def _parse_event(
        self,
        event_data: Dict[str, Any],
        stage: LifeStage,
        persona_data: Dict[str, Any],
    ) -> Optional[LifeEvent]:
        """解析事件数据为 LifeEvent 对象"""
        try:
            event_type_str = event_data.get("event_type", "转折点")
            event_type = EventType(event_type_str)
        except ValueError:
            event_type = EventType.TURNING_POINT

        age = event_data.get("age", 10)
        age_range = self._get_age_range(stage)
        if not (age_range[0] <= age <= age_range[1]):
            age = (age_range[0] + age_range[1]) // 2

        involved_traits = {
            "mbti": persona_data.get("mbti_type"),
            "enneagram": persona_data.get("enneagram_type"),
            "big_five": persona_data.get("big_five", {}),
            "attachment": persona_data.get("attachment_style"),
        }

        return LifeEvent(
            stage=stage,
            event_type=event_type,
            age=age,
            title=event_data.get("title", "未命名事件"),
            description=event_data.get("description", ""),
            impact=event_data.get("impact", ""),
            involved_traits=involved_traits,
        )

    async def _generate_fallback_events(
        self,
        stage: LifeStage,
        persona_data: Dict[str, Any],
        count: int,
    ) -> List[LifeEvent]:
        """当 LLM 失败时使用规则生成 fallback 事件"""
        logger.debug("使用规则生成 fallback 事件，阶段：%s, 数量：%d", stage.value, count)

        mbti = persona_data.get("mbti_type", "INTJ")
        archetype = persona_data.get("archetype", "探索者")
        age_range = self._get_age_range(stage)

        fallback_templates = self._get_fallback_templates(stage, mbti, archetype)
        events = []

        for i in range(count):
            template = fallback_templates[i % len(fallback_templates)]
            age = age_range[0] + (i * ((age_range[1] - age_range[0]) // count))

            event = LifeEvent(
                stage=stage,
                event_type=template["type"],
                age=age,
                title=template["title"],
                description=template["description"],
                impact=template["impact"],
                involved_traits={
                    "mbti": mbti,
                    "archetype": archetype,
                },
            )
            events.append(event)

        return events

    def _get_fallback_templates(
        self,
        stage: LifeStage,
        mbti: str,
        archetype: str,
    ) -> List[Dict[str, Any]]:
        """获取 fallback 事件模板"""
        templates = {
            LifeStage.CHILDHOOD: [
                {
                    "type": EventType.RELATIONSHIP,
                    "title": "结识童年好友",
                    "description": "在小学/幼儿园结识了一位重要的朋友，两人一起度过了许多快乐时光。",
                    "impact": "培养了社交能力和信任感。",
                },
                {
                    "type": EventType.CHALLENGE,
                    "title": "面对学习困难",
                    "description": "在某门学科上遇到了困难，通过努力或他人帮助最终克服。",
                    "impact": "建立了面对挑战的信心和毅力。",
                },
                {
                    "type": EventType.HIGHLIGHT,
                    "title": "获得首次认可",
                    "description": "在某项活动或比赛中获得了奖励或表扬，感受到了成就感。",
                    "impact": "增强了自信心，明确了兴趣方向。",
                },
            ],
            LifeStage.ADOLESCENCE: [
                {
                    "type": EventType.TURNING_POINT,
                    "title": "文理分科选择",
                    "description": "在高中面临文理科选择，根据自己的兴趣和优势做出了决定。",
                    "impact": "开始形成自我认知，明确发展方向。",
                },
                {
                    "type": EventType.RELATIONSHIP,
                    "title": "初恋经历",
                    "description": "经历了青春期的情感萌动，体验了喜欢与被喜欢的感觉。",
                    "impact": "学习处理亲密关系，形成依恋模式的雏形。",
                },
                {
                    "type": EventType.CHALLENGE,
                    "title": "学业压力考验",
                    "description": "面对高考/升学的巨大压力，经历了焦虑、迷茫到坚持的过程。",
                    "impact": "锻炼了抗压能力，学会自我调节。",
                },
            ],
            LifeStage.EARLY_ADULTHOOD: [
                {
                    "type": EventType.TURNING_POINT,
                    "title": "职业道路选择",
                    "description": f"基于{mbti}类型的特质，选择了适合自己的职业方向。",
                    "impact": "确立了职业生涯的起点，开始积累专业能力。",
                },
                {
                    "type": EventType.HIGHLIGHT,
                    "title": "职场首次晋升/认可",
                    "description": "在工作中表现出色，获得了上司或同事的认可，迎来首次晋升或重要项目。",
                    "impact": "验证了职业选择，增强了职业自信。",
                },
                {
                    "type": EventType.RELATIONSHIP,
                    "title": "建立重要伴侣关系",
                    "description": "遇到了人生中的重要伴侣，建立了长期稳定的亲密关系。",
                    "impact": "学习经营长期关系，形成家庭观念。",
                },
            ],
            LifeStage.MIDDLE_ADULTHOOD: [
                {
                    "type": EventType.CAREER_CHANGE,
                    "title": "职业转型/晋升",
                    "description": "职业生涯达到新高度，或选择转型追求新的方向。",
                    "impact": "重新审视人生目标，调整优先级。",
                },
                {
                    "type": EventType.CHALLENGE,
                    "title": "中年危机考验",
                    "description": "面临事业、家庭、健康等多重压力，经历自我怀疑和调整。",
                    "impact": "学会平衡多方需求，重新定义成功。",
                },
                {
                    "type": EventType.HIGHLIGHT,
                    "title": "专业成就/社会认可",
                    "description": "在专业领域取得显著成就，获得行业或社会的认可。",
                    "impact": "实现自我价值，获得成就感。",
                },
            ],
            LifeStage.LATE_ADULTHOOD: [
                {
                    "type": EventType.TURNING_POINT,
                    "title": "退休生活规划",
                    "description": "从工作岗位退休，开始规划新的生活方式。",
                    "impact": "从追求成就转向追求意义和传承。",
                },
                {
                    "type": EventType.RELATIONSHIP,
                    "title": "三代同堂/家庭团聚",
                    "description": "享受与子女、孙辈的家庭时光，体验天伦之乐。",
                    "impact": "感受家族延续，思考生命意义。",
                },
                {
                    "type": EventType.HIGHLIGHT,
                    "title": "人生回顾与整合",
                    "description": "回顾一生的经历，整合成完整的人生叙事，获得内心的平静与满足。",
                    "impact": "达成自我和解，形成完整的人生智慧。",
                },
            ],
        }

        return templates.get(stage, templates[LifeStage.EARLY_ADULTHOOD])

    def _determine_narrative_arc(self, persona_data: Dict[str, Any]) -> str:
        """根据人格特质确定叙事弧线类型"""
        neuroticism = persona_data.get("big_five", {}).get("neuroticism", 0.5)
        extraversion = persona_data.get("big_five", {}).get("extraversion", 0.5)
        openness = persona_data.get("big_five", {}).get("openness", 0.5)

        if neuroticism > 0.7:
            return "悲剧弧线"
        elif extraversion > 0.6 and openness > 0.6:
            return "英雄之旅"
        elif persona_data.get("big_five", {}).get("agreeableness", 0.5) > 0.6:
            return "成长弧线"
        else:
            return "平凡之旅"

    def timeline_to_dict(self, timeline: LifeTimeline) -> Dict[str, Any]:
        """将 LifeTimeline 转换为字典格式（用于 JSON 序列化）"""
        return {
            "user_id": timeline.user_id,
            "persona_id": timeline.persona_id,
            "stages": {
                stage.value: [
                    {
                        "age": event.age,
                        "event_type": event.event_type.value,
                        "title": event.title,
                        "description": event.description,
                        "impact": event.impact,
                        "involved_traits": event.involved_traits,
                    }
                    for event in events
                ]
                for stage, events in timeline.stages.items()
            },
            "total_events": timeline.total_events,
            "narrative_arc": timeline.narrative_arc,
            "generated_at": timeline.generated_at.isoformat(),
        }

    def save_timeline(self, timeline: LifeTimeline, output_dir: str) -> str:
        """保存时间线到 JSON 文件"""
        import os

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{timeline.user_id}_timeline.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.timeline_to_dict(timeline), f, ensure_ascii=False, indent=2)

        logger.info("时间线已保存到：%s", output_path)
        return output_path
