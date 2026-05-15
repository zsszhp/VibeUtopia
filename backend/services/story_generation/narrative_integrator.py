"""T7.3 人生叙事整合服务

将人生时间线和场景故事整合成完整的人生叙事。

功能：
- 叙事弧线：英雄之旅 / 成长弧线 / 悲剧弧线
- 主题提炼：从人生故事中提取核心主题
- 输出格式：完整人生故事、精简版传记、主题解读
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm

from .scene_generator import ScenePackage
from .timeline_builder import LifeTimeline

logger = logging.getLogger(__name__)


@dataclass
class LifeNarrative:
    """完整人生叙事"""
    user_id: str
    persona_id: str
    full_story: str  # 完整人生故事
    summary: str  # 精简版传记（500 字）
    themes: List[str]  # 核心主题
    narrative_arc: str  # 叙事弧线
    psychological_analysis: str  # 心理分析视角
    generated_at: datetime = field(default_factory=datetime.now)


class NarrativeIntegrator:
    """人生叙事整合器"""

    # 叙事弧线模板
    NARRATIVE_ARCS = {
        "英雄之旅": {
            "structure": [
                "平凡世界",
                "冒险召唤",
                "拒绝召唤",
                "遇见导师",
                "跨越门槛",
                "考验与盟友",
                "核心挑战",
                "获得宝藏",
                "回归",
            ],
            "tone": "积极向上，强调成长与突破",
        },
        "成长弧线": {
            "structure": [
                "初始状态",
                "触发事件",
                "挣扎与学习",
                "顿悟时刻",
                "应用新知",
                "新的平衡",
            ],
            "tone": "温和渐进，强调内在变化",
        },
        "悲剧弧线": {
            "structure": [
                "高峰状态",
                "致命缺陷",
                "错误选择",
                "局势恶化",
                "最后挣扎",
                "不可避免结局",
            ],
            "tone": "沉重压抑，强调命运与局限",
        },
        "平凡之旅": {
            "structure": [
                "出生与童年",
                "求学经历",
                "职业发展",
                "家庭建立",
                "中年反思",
                "晚年回顾",
            ],
            "tone": "平实叙述，强调日常生活的意义",
        },
    }

    # 主题类型
    THEME_CATEGORIES = {
        "身份认同": ["寻找自我", "身份危机", "归属感", "独特性"],
        "关系连接": ["爱与被爱", "孤独", "友谊", "家庭纽带"],
        "成就追求": ["成功渴望", "证明价值", "超越自我", "留下遗产"],
        "意义探索": ["生命意义", "存在价值", "精神追求", "哲学思考"],
        "创伤愈合": ["克服创伤", "原谅与和解", "重新出发", "心理成长"],
        "自由与责任": ["追求自由", "承担责任", "选择与后果", "自律"],
    }

    def __init__(self, model_name: str = "Qwen3.6-Plus"):
        self.model_name = model_name

    async def integrate_narrative(
        self,
        timeline: LifeTimeline,
        scene_package: ScenePackage,
        persona_data: Dict[str, Any],
    ) -> LifeNarrative:
        """
        整合人生叙事

        Args:
            timeline: 人生时间线
            scene_package: 场景故事包
            persona_data: 完整人格画像

        Returns:
            LifeNarrative: 完整的人生叙事
        """
        logger.info("开始整合人生叙事，用户：%s", timeline.user_id)

        narrative_arc = timeline.narrative_arc or self._determine_arc(persona_data)

        full_story = await self._generate_full_story(
            timeline,
            scene_package,
            persona_data,
            narrative_arc,
        )

        summary = await self._generate_summary(full_story, persona_data)
        themes = self._extract_themes(full_story, persona_data)
        psychological_analysis = await self._generate_psychological_analysis(
            full_story,
            persona_data,
        )

        narrative = LifeNarrative(
            user_id=timeline.user_id,
            persona_id=timeline.persona_id,
            full_story=full_story,
            summary=summary,
            themes=themes,
            narrative_arc=narrative_arc,
            psychological_analysis=psychological_analysis,
        )

        logger.info(
            "人生叙事整合完成，完整故事字数：%d, 主题数：%d",
            len(full_story),
            len(themes),
        )

        return narrative

    def _determine_arc(self, persona_data: Dict[str, Any]) -> str:
        """根据人格特质确定叙事弧线"""
        big_five = persona_data.get("big_five", {})
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)
        openness = big_five.get("openness", 0.5)

        if neuroticism > 0.7:
            return "悲剧弧线"
        elif extraversion > 0.6 and openness > 0.6:
            return "英雄之旅"
        elif big_five.get("agreeableness", 0.5) > 0.6:
            return "成长弧线"
        else:
            return "平凡之旅"

    async def _generate_full_story(
        self,
        timeline: LifeTimeline,
        scene_package: ScenePackage,
        persona_data: Dict[str, Any],
        narrative_arc: str,
    ) -> str:
        """生成完整人生故事"""
        logger.info("生成完整人生故事，叙事弧线：%s", narrative_arc)

        arc_info = self.NARRATIVE_ARCS.get(narrative_arc, self.NARRATIVE_ARCS["平凡之旅"])

        timeline_summary = self._summarize_timeline(timeline)
        scenes_summary = self._summarize_scenes(scene_package)

        prompt = f"""
请基于以下人生时间线和场景故事，整合成一篇完整的人生叙事。

【叙事弧线】{narrative_arc}
【结构】{" → ".join(arc_info['structure'])}
【基调】{arc_info['tone']}

【人生时间线摘要】
{timeline_summary}

【场景故事摘要】
{scenes_summary}

【人格特质】
- MBTI: {persona_data.get('mbti_type', '未知')}
- 九型人格：{persona_data.get('enneagram_type', '未知')}
- Big Five: 开放性{persona_data.get('big_five', {}).get('openness', 0.5):.2f}, 
           尽责性{persona_data.get('big_five', {}).get('conscientiousness', 0.5):.2f}, 
           外向性{persona_data.get('big_five', {}).get('extraversion', 0.5):.2f}, 
           宜人性{persona_data.get('big_five', {}).get('agreeableness', 0.5):.2f}, 
           神经质{persona_data.get('big_five', {}).get('neuroticism', 0.5):.2f}

要求：
1. 使用第三人称叙述
2. 按照{arc_info['structure']}的结构组织故事
3. 将场景故事自然融入时间线
4. 突出{arc_info['tone']}的基调
5. 体现人格特质对人生选择的影响
6. 字数 3000-5000 字
7. 注重故事的连贯性和情感流动
8. 在关键转折点加入心理描写

请生成完整的人生故事：
"""

        try:
            story = await call_llm(
                prompt,
                system="你是一位传记作家，请创作一篇真实、感人、有深度的人生故事。",
                task_type="story_generation",
                model=self.model_name,
            )
            return story
        except Exception as e:
            logger.error("生成完整故事失败：%s", e)
            return self._generate_fallback_story(timeline, scene_package)

    def _summarize_timeline(self, timeline: LifeTimeline) -> str:
        """将时间线转换为文本摘要"""
        summary_parts = []

        for stage, events in timeline.stages.items():
            stage_summary = f"{stage.value}:\n"
            for event in events[:3]:
                stage_summary += f"- {event.age}岁：{event.title}（{event.event_type.value}）\n"
            summary_parts.append(stage_summary)

        return "\n".join(summary_parts)

    def _summarize_scenes(self, scene_package: ScenePackage) -> str:
        """将场景故事包转换为文本摘要"""
        summary_parts = []

        for scene in scene_package.scenes[:5]:
            summary = scene.content[:200] + "..." if len(scene.content) > 200 else scene.content
            summary_parts.append(f"{scene.title}: {summary}")

        return "\n\n".join(summary_parts)

    async def _generate_summary(
        self,
        full_story: str,
        persona_data: Dict[str, Any],
    ) -> str:
        """生成精简版传记（500 字）"""
        logger.info("生成精简版传记")

        prompt = f"""
请将以下人生故事压缩成 500 字以内的精简版传记。

要求：
1. 保留关键的人生节点和转折点
2. 突出核心主题和成就
3. 语言简洁有力
4. 适合用于展示和介绍

原文：
{full_story[:3000]}...
"""

        try:
            summary = await call_llm(
                prompt,
                system="你是一位编辑，请将长文压缩成简洁有力的传记。",
                task_type="story_generation",
                model=self.model_name,
            )
            if len(summary) > 500:
                summary = summary[:500] + "..."
            return summary
        except Exception:
            return full_story[:500] + "..."

    def _extract_themes(
        self,
        full_story: str,
        persona_data: Dict[str, Any],
    ) -> List[str]:
        """从故事中提取核心主题"""
        logger.info("提取核心主题")

        detected_themes = []

        for category, subthemes in self.THEME_CATEGORIES.items():
            for subtheme in subthemes:
                if subtheme in full_story:
                    detected_themes.append(f"{category}: {subtheme}")
                    break

        if not detected_themes:
            detected_themes = [
                "个人成长",
                "自我实现",
                "关系建立",
            ]

        return detected_themes[:5]

    async def _generate_psychological_analysis(
        self,
        full_story: str,
        persona_data: Dict[str, Any],
    ) -> str:
        """生成心理分析视角的解读"""
        logger.info("生成心理分析视角")

        mbti = persona_data.get("mbti_type", "未知")
        enneagram = persona_data.get("enneagram_type", "未知")
        attachment = persona_data.get("attachment_style", "未知")

        prompt = f"""
请从心理学角度分析以下人生故事。

【人格画像】
- MBTI: {mbti}
- 九型人格：{enneagram}
- 依恋类型：{attachment}

【人生故事】
{full_story[:3000]}...

分析维度：
1. 人格特质如何影响人生选择？
2. 依恋类型在关系中的表现
3. 防御机制的使用模式
4. 心理成长的关键节点
5. 未解决的心理冲突

请生成 500-800 字的心理分析：
"""

        try:
            analysis = await call_llm(
                prompt,
                system="你是一位心理咨询师，请提供专业、深入的心理分析。",
                task_type="story_generation",
                model=self.model_name,
            )
            return analysis
        except Exception:
            return f"【心理分析】基于{mbti}、{enneagram}等人格特质，此人的人生选择体现了其核心价值观和行为模式。"

    def _generate_fallback_story(
        self,
        timeline: LifeTimeline,
        scene_package: ScenePackage,
    ) -> str:
        """当 LLM 失败时生成 fallback 故事"""
        logger.warning("生成完整故事失败，使用 fallback")

        story_parts = ["# 人生故事\n\n"]

        for stage, events in timeline.stages.items():
            story_parts.append(f"## {stage.value}\n\n")
            for event in events:
                story_parts.append(f"### {event.title}（{event.age}岁）\n\n")
                story_parts.append(f"{event.description}\n\n")
                story_parts.append(f"**影响**: {event.impact}\n\n")

        return "\n".join(story_parts)

    def narrative_to_dict(self, narrative: LifeNarrative) -> Dict[str, Any]:
        """将 LifeNarrative 转换为字典格式"""
        return {
            "user_id": narrative.user_id,
            "persona_id": narrative.persona_id,
            "full_story": narrative.full_story,
            "summary": narrative.summary,
            "themes": narrative.themes,
            "narrative_arc": narrative.narrative_arc,
            "psychological_analysis": narrative.psychological_analysis,
            "generated_at": narrative.generated_at.isoformat(),
        }

    def save_narrative(self, narrative: LifeNarrative, output_dir: str) -> Dict[str, str]:
        """
        保存人生叙事到多个文件

        Returns:
            保存的文件路径字典
        """
        os.makedirs(output_dir, exist_ok=True)

        paths = {}

        full_story_path = os.path.join(output_dir, f"{narrative.user_id}_life_story.md")
        with open(full_story_path, "w", encoding="utf-8") as f:
            f.write(f"# {narrative.user_id}的人生故事\n\n")
            f.write(f"**叙事弧线**: {narrative.narrative_arc}\n\n")
            f.write(f"**核心主题**: {', '.join(narrative.themes)}\n\n")
            f.write("---\n\n")
            f.write(narrative.full_story)
        paths["full_story"] = full_story_path

        summary_path = os.path.join(output_dir, f"{narrative.user_id}_summary.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"# 人生传记摘要\n\n")
            f.write(narrative.summary)
            f.write("\n\n---\n\n")
            f.write(f"## 心理分析\n\n{narrative.psychological_analysis}\n")
        paths["summary"] = summary_path

        json_path = os.path.join(output_dir, f"{narrative.user_id}_narrative.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.narrative_to_dict(narrative), f, ensure_ascii=False, indent=2)
        paths["json"] = json_path

        logger.info("人生叙事已保存到：%s 等文件", full_story_path)
        return paths
