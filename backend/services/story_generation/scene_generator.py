"""T7.2 关键场景故事生成服务

基于人生时间线中的关键事件，生成详细的场景故事（800-1500 字）。

功能：
- 场景类型：转折点、挑战期、高光时刻、关系节点
- 融入认知扭曲模式和防御机制
- 体现价值观冲突与选择
- 字数控制在 800-1500 字
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm

from .timeline_builder import LifeEvent, LifeStage, LifeTimeline

logger = logging.getLogger(__name__)


@dataclass
class SceneStory:
    """场景故事"""
    event: LifeEvent
    title: str
    content: str
    word_count: int
    cognitive_distortions: List[str]  # 涉及的认知扭曲
    defense_mechanisms: List[str]  # 涉及的防御机制
    value_conflicts: List[str]  # 体现的价值观冲突
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ScenePackage:
    """场景故事包（多个场景的集合）"""
    user_id: str
    persona_id: str
    scenes: List[SceneStory]
    total_word_count: int
    generated_at: datetime = field(default_factory=datetime.now)


class SceneGenerator:
    """关键场景故事生成器"""

    # 认知扭曲类型
    COGNITIVE_DISTORTIONS = [
        "非黑即白思维",
        "过度概括",
        "心理过滤",
        "否定正面思考",
        "跳跃式结论",
        "灾难化",
        "情绪化推理",
        "应该陈述",
        "贴标签",
        "个人化",
    ]

    # 防御机制类型
    DEFENSE_MECHANISMS = [
        "压抑",
        "否认",
        "投射",
        "合理化",
        "反向形成",
        "退行",
        "升华",
        "转移",
        "分裂",
        "理智化",
    ]

    # 场景类型 Prompt 模板
    SCENE_PROMPTS = {
        "转折点": """
【场景类型】转折点 - 重大决策时刻

【事件】{event_title}
【年龄】{age}岁
【事件描述】{event_description}
【人格特质】{persona_traits}

请生成一个 800-1500 字的详细场景故事，描述这个人生转折点。

要求：
1. 使用第三人称叙述，聚焦于主人公的内心世界
2. 详细描写决策过程中的内心挣扎：
   - 面临的选择有哪些？
   - 每个选择的利弊是什么？
   - 最终如何做出决定？
3. 融入适当的认知扭曲（如：非黑即白思维、灾难化等）
4. 体现防御机制（如：合理化、投射等）
5. 展示价值观冲突（如：安全 vs 自由、成就 vs 关系等）
6. 包含具体的对话、动作、环境细节
7. 结尾点明这个决定对后续人生的影响

故事结构：
- 开场：决策背景（200 字）
- 发展：内心挣扎与权衡（400-600 字）
- 高潮：做出决定的时刻（300-400 字）
- 结尾：影响与反思（200 字）
""",
        "挑战期": """
【场景类型】挑战期 - 困难与突破

【事件】{event_title}
【年龄】{age}岁
【事件描述】{event_description}
【人格特质】{persona_traits}

请生成一个 800-1500 字的详细场景故事，描述主人公面对挑战并突破的过程。

要求：
1. 使用第三人称叙述，突出情感起伏
2. 详细描写：
   - 挑战的具体表现和严重程度
   - 主人公的初始反应（恐惧、焦虑、逃避等）
   - 转折点：是什么促使主人公改变态度？
   - 突破过程：采取了什么行动？遇到了什么阻碍？
   - 最终结果：成功/失败/部分成功
3. 融入适当的认知扭曲（如：灾难化、过度概括等）
4. 体现防御机制（如：否认、压抑、升华等）
5. 展现性格成长：从挑战中学到了什么？
6. 包含具体的感官细节（看到的、听到的、感受到的）

故事结构：
- 开场：挑战来临（200 字）
- 发展：挣扎与逃避（300-400 字）
- 转折：觉醒时刻（200 字）
- 高潮：突破行动（300-400 字）
- 结尾：成长与收获（200 字）
""",
        "高光时刻": """
【场景类型】高光时刻 - 成就与认可

【事件】{event_title}
【年龄】{age}岁
【事件描述】{event_description}
【人格特质】{persona_traits}

请生成一个 800-1500 字的详细场景故事，描述主人公的高光时刻。

要求：
1. 使用第三人称叙述，营造情感高潮
2. 详细描写：
   - 成就的背景：为之付出了什么努力？
   - 成就时刻的具体场景（颁奖台、庆功宴、收到通知等）
   - 周围人的反应（祝贺、羡慕、认可）
   - 主人公的内心感受（喜悦、自豪、如释重负等）
   - 这个成就对后续人生的意义
3. 体现主人公的核心价值观
4. 展现 Big Five 特质（如：尽责性带来成功、外向性享受认可等）
5. 包含具体的场景细节和对话
6. 避免过度炫耀，保持真实感

故事结构：
- 开场：成就背景与铺垫（200 字）
- 发展：努力过程回顾（300 字）
- 高潮：成就时刻（400-500 字）
- 结尾：意义与反思（200 字）
""",
        "关系节点": """
【场景类型】关系节点 - 重要他人相遇/分离

【事件】{event_title}
【年龄】{age}岁
【事件描述】{event_description}
【人格特质】{persona_traits}
【依恋类型】{attachment_style}

请生成一个 800-1500 字的详细场景故事，描述主人公与重要他人的相遇或分离。

要求：
1. 使用第三人称叙述，突出情感流动
2. 详细描写：
   - 相遇/分离的场景（时间、地点、情境）
   - 第一印象/最后印象
   - 双方的互动细节（对话、动作、表情）
   - 主人公的内心感受
   - 这段关系对主人公的影响
3. 体现依恋类型的特征：
   - 安全型：自然、信任、平衡
   - 焦虑型：渴望、不安、过度投入
   - 回避型：疏离、独立、情感保留
   - 混乱型：矛盾、反复、不确定
4. 融入适当的认知扭曲（如：个人化、贴标签等）
5. 包含具体的感官细节

故事结构：
- 开场：场景设定（200 字）
- 发展：互动过程（400-500 字）
- 高潮：关键对话/动作（300 字）
- 结尾：关系影响与后续（200 字）
""",
    }

    def __init__(self, model_name: str = "Qwen3.6-Plus"):
        self.model_name = model_name

    async def generate_scene(
        self,
        event: LifeEvent,
        persona_data: Dict[str, Any],
    ) -> SceneStory:
        """
        基于单个事件生成场景故事

        Args:
            event: 人生关键事件
            persona_data: 完整人格画像

        Returns:
            SceneStory: 生成的场景故事
        """
        logger.info(
            "生成场景故事：%s, 年龄：%d, 类型：%s",
            event.title,
            event.age,
            event.event_type.value,
        )

        prompt = self._build_scene_prompt(event, persona_data)

        try:
            content = await call_llm(
                prompt,
                system="你是一位擅长心理描写的作家，请生成真实、细腻、有深度的场景故事。",
                task_type="story_generation",
                model=self.model_name,
            )

            word_count = len(content.split())
            if word_count < 800:
                content = await self._expand_scene(content, event, persona_data)
                word_count = len(content.split())
            elif word_count > 1500:
                content = content[:1500]
                word_count = 1500

            cognitive_distortions = self._detect_cognitive_distortions(content)
            defense_mechanisms = self._detect_defense_mechanisms(content)
            value_conflicts = self._detect_value_conflicts(content, persona_data)

            scene = SceneStory(
                event=event,
                title=event.title,
                content=content,
                word_count=word_count,
                cognitive_distortions=cognitive_distortions,
                defense_mechanisms=defense_mechanisms,
                value_conflicts=value_conflicts,
            )

            logger.info(
                "场景故事生成完成，字数：%d, 认知扭曲：%d 个，防御机制：%d 个",
                word_count,
                len(cognitive_distortions),
                len(defense_mechanisms),
            )

            return scene

        except Exception as e:
            logger.error("场景故事生成失败：%s", e)
            return self._generate_fallback_scene(event, persona_data)

    def _build_scene_prompt(
        self,
        event: LifeEvent,
        persona_data: Dict[str, Any],
    ) -> str:
        """构建场景生成 Prompt"""
        big_five = persona_data.get("big_five", {})
        attachment_style = persona_data.get("attachment_style", "secure")
        enneagram = persona_data.get("enneagram_type", 5)
        mbti = persona_data.get("mbti_type", "INTJ")

        persona_traits = (
            f"MBTI: {mbti}, "
            f"九型人格：{enneagram}, "
            f"开放性：{big_five.get('openness', 0.5):.2f}, "
            f"尽责性：{big_five.get('conscientiousness', 0.5):.2f}, "
            f"外向性：{big_five.get('extraversion', 0.5):.2f}, "
            f"宜人性：{big_five.get('agreeableness', 0.5):.2f}, "
            f"神经质：{big_five.get('neuroticism', 0.5):.2f}"
        )

        prompt_template = self.SCENE_PROMPTS.get(
            event.event_type.value,
            self.SCENE_PROMPTS["转折点"],
        )

        return prompt_template.format(
            event_title=event.title,
            age=event.age,
            event_description=event.description,
            persona_traits=persona_traits,
            attachment_style=attachment_style,
        )

    async def _expand_scene(
        self,
        content: str,
        event: LifeEvent,
        persona_data: Dict[str, Any],
    ) -> str:
        """扩展字数不足的场景"""
        logger.debug("场景字数不足，进行扩展")

        expand_prompt = f"""
以下场景故事字数不足 800 字，请扩展细节，使其达到 800-1500 字：

原文：
{content}

扩展要求：
1. 增加更多内心独白和心理描写
2. 补充环境细节和感官细节
3. 增加对话内容
4. 深化情感描写

请在原文基础上扩展，不要改变原有情节。
"""

        try:
            expanded = await call_llm(
                expand_prompt,
                system="你是一位擅长细节描写的作家，请丰富场景故事的细节。",
                task_type="story_generation",
                model=self.model_name,
            )
            return expanded
        except Exception:
            return content

    def _detect_cognitive_distortions(self, content: str) -> List[str]:
        """检测故事中涉及的认知扭曲"""
        detected = []

        distortion_keywords = {
            "非黑即白思维": ["要么", "或者", "绝对", "完全", "总是"],
            "过度概括": ["所有", "每个", "永远", "从不", "每次"],
            "灾难化": ["完蛋了", "彻底失败", "灾难", "毁灭性"],
            "情绪化推理": ["我感觉", "我觉得", "直觉告诉我"],
            "应该陈述": ["应该", "必须", "一定要", "理应"],
            "个人化": ["都是因为", "是我的错", "我导致的"],
        }

        for distortion, keywords in distortion_keywords.items():
            if any(keyword in content for keyword in keywords):
                detected.append(distortion)

        return detected[:3]  # 最多返回 3 个

    def _detect_defense_mechanisms(self, content: str) -> List[str]:
        """检测故事中涉及的防御机制"""
        detected = []

        mechanism_keywords = {
            "合理化": ["其实", "换句话说", "也就是说", "原因是"],
            "否认": ["不相信", "拒绝承认", "不可能", "没有这回事"],
            "投射": ["他觉得", "她认为", "别人都"],
            "转移": ["转而", "把情绪发泄", "迁怒"],
            "升华": ["转化为", "投入到", "专注于"],
            "退行": ["像个孩子", "回到过去", "逃避"],
        }

        for mechanism, keywords in mechanism_keywords.items():
            if any(keyword in content for keyword in keywords):
                detected.append(mechanism)

        return detected[:3]

    def _detect_value_conflicts(
        self,
        content: str,
        persona_data: Dict[str, Any],
    ) -> List[str]:
        """检测故事中体现的价值观冲突"""
        detected = []

        conflicts = [
            "安全 vs 自由",
            "成就 vs 关系",
            "个人 vs 集体",
            "传统 vs 创新",
            "理想 vs 现实",
            "公平 vs 效率",
        ]

        if any(word in content for word in ["稳定", "安全", "风险"]):
            conflicts = [c for c in conflicts if "安全" in c]
        if any(word in content for word in ["成功", "认可", "陪伴"]):
            conflicts = [c for c in conflicts if "成就" in c or "关系" in c]

        return conflicts[:2]

    def _generate_fallback_scene(
        self,
        event: LifeEvent,
        persona_data: Dict[str, Any],
    ) -> SceneStory:
        """当 LLM 失败时生成 fallback 场景"""
        logger.warning("场景故事生成失败，使用 fallback")

        fallback_content = f"""
{event.title}（{event.age}岁）

这是一个{event.event_type.value}的时刻。{event.description}

在这个关键时刻，主人公根据自己的性格特质做出了选择。这个决定对其后续人生产生了深远的影响：{event.impact}

尽管面临挑战，主人公还是凭借自己的能力和勇气度过了这个重要时刻。这段经历成为了其人生故事中的重要一章。
"""

        return SceneStory(
            event=event,
            title=event.title,
            content=fallback_content,
            word_count=len(fallback_content.split()),
            cognitive_distortions=[],
            defense_mechanisms=[],
            value_conflicts=[],
        )

    async def generate_all_scenes(
        self,
        timeline: LifeTimeline,
        persona_data: Dict[str, Any],
    ) -> ScenePackage:
        """
        为时间线中的所有事件生成场景故事

        Args:
            timeline: 人生时间线
            persona_data: 完整人格画像

        Returns:
            ScenePackage: 场景故事包
        """
        logger.info("开始为时间线生成所有场景故事，总事件数：%d", timeline.total_events)

        scenes = []
        total_word_count = 0

        all_events = []
        for stage_events in timeline.stages.values():
            all_events.extend(stage_events)

        for i, event in enumerate(all_events):
            logger.debug("生成第%d个场景故事", i + 1)
            scene = await self.generate_scene(event, persona_data)
            scenes.append(scene)
            total_word_count += scene.word_count

        scene_package = ScenePackage(
            user_id=timeline.user_id,
            persona_id=timeline.persona_id,
            scenes=scenes,
            total_word_count=total_word_count,
        )

        logger.info(
            "场景故事包生成完成，场景数：%d, 总字数：%d",
            len(scenes),
            total_word_count,
        )

        return scene_package

    def scene_to_dict(self, scene: SceneStory) -> Dict[str, Any]:
        """将 SceneStory 转换为字典格式"""
        return {
            "event": {
                "stage": scene.event.stage.value,
                "age": scene.event.age,
                "event_type": scene.event.event_type.value,
                "title": scene.event.title,
            },
            "title": scene.title,
            "content": scene.content,
            "word_count": scene.word_count,
            "cognitive_distortions": scene.cognitive_distortions,
            "defense_mechanisms": scene.defense_mechanisms,
            "value_conflicts": scene.value_conflicts,
            "generated_at": scene.generated_at.isoformat(),
        }

    def save_scene(self, scene: SceneStory, output_dir: str) -> str:
        """保存单个场景故事到 Markdown 文件"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"scene_{scene.event.stage.name}_{scene.event.age}_{scene.title[:20]}.md",
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {scene.title}\n\n")
            f.write(f"**年龄**: {scene.event.age}岁  ")
            f.write(f"**阶段**: {scene.event.stage.value}  ")
            f.write(f"**类型**: {scene.event.event_type.value}  \n\n")
            f.write(f"**字数**: {scene.word_count}  \n\n")
            if scene.cognitive_distortions:
                f.write(f"**认知扭曲**: {', '.join(scene.cognitive_distortions)}  \n")
            if scene.defense_mechanisms:
                f.write(f"**防御机制**: {', '.join(scene.defense_mechanisms)}  \n")
            if scene.value_conflicts:
                f.write(f"**价值观冲突**: {', '.join(scene.value_conflicts)}  \n")
            f.write(f"\n---\n\n{scene.content}\n")

        logger.info("场景故事已保存到：%s", output_path)
        return output_path

    def save_scene_package(self, package: ScenePackage, output_dir: str) -> str:
        """保存场景故事包"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{package.user_id}_scenes.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "user_id": package.user_id,
                    "persona_id": package.persona_id,
                    "scenes": [self.scene_to_dict(scene) for scene in package.scenes],
                    "total_word_count": package.total_word_count,
                    "generated_at": package.generated_at.isoformat(),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("场景故事包已保存到：%s", output_path)
        return output_path
