"""平台仿真器 - 阶段2: 平台深度打磨

模拟5大核心平台(P0)的用户反应差异，生成平台特有的舆论预测。
每个平台有独特的传播特征、用户画像、情绪基线和风险敏感度。

核心能力：
1. 平台反应模拟 - 预测各平台用户对内容的典型反应
2. 情绪分布预测 - 基于平台基线和内容特征预测情绪分布
3. 风险放大计算 - 根据平台传播特征计算风险放大效应
4. 平台差异化建议 - 针对不同平台给出改写建议
"""
import json
import logging
from typing import Any, Dict, List, Optional

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.platform_weights import (
    PlatformProfile,
    get_platform_profile,
    get_p0_platforms,
    get_platform_risk_sensitivity,
    get_platform_emotion_bias,
    get_propagation_params,
    adjust_risk_by_platform,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# 平台反应数据结构
# ===========================================================================

class PlatformReaction:
    """单平台反应预测"""

    def __init__(
        self,
        platform_id: str,
        platform_name: str,
        emotion_distribution: Dict[str, float],
        risk_score: float,
        risk_level: str,
        typical_reactions: List[Dict[str, str]],
        key_concerns: List[str],
        amplification_risk: float,
        platform_specific_advice: List[str],
    ):
        self.platform_id = platform_id
        self.platform_name = platform_name
        self.emotion_distribution = emotion_distribution
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.typical_reactions = typical_reactions
        self.key_concerns = key_concerns
        self.amplification_risk = amplification_risk
        self.platform_specific_advice = platform_specific_advice

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "emotion_distribution": self.emotion_distribution,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "typical_reactions": self.typical_reactions,
            "key_concerns": self.key_concerns,
            "amplification_risk": round(self.amplification_risk, 1),
            "platform_specific_advice": self.platform_specific_advice,
        }


# ===========================================================================
# 平台仿真器主类
# ===========================================================================

class PlatformSimulator:
    """平台仿真器 - 模拟各平台用户反应

    使用LLM+平台画像配置，预测内容在不同平台的用户反应。
    """

    async def simulate_platform_reaction(
        self,
        text: str,
        platform_id: str,
        base_risk_scores: Optional[Dict[str, float]] = None,
    ) -> Optional[PlatformReaction]:
        """模拟单平台用户反应

        Args:
            text: 待评估文案
            platform_id: 平台标识
            base_risk_scores: 基础风险分数(可选，用于校准)

        Returns:
            PlatformReaction或None(失败时)
        """
        profile = get_platform_profile(platform_id)
        if not profile:
            logger.warning("未知平台 %s，跳过仿真", platform_id)
            return None

        # 构建平台仿真Prompt
        prompt = self._build_simulation_prompt(text, profile, base_risk_scores)

        try:
            response = await call_llm(
                prompt,
                system=f"你是一个{profile.name}平台的舆论分析专家，擅长预测该平台用户对新内容的反应。",
                task_type="platform_simulation",
            )

            result = parse_llm_json(response, fallback=None)
            if not result:
                logger.warning("平台 %s 仿真LLM返回无法解析", platform_id)
                return self._fallback_reaction(profile)

            return self._parse_reaction(result, profile, base_risk_scores)

        except Exception as e:
            logger.error("平台 %s 仿真失败: %s", platform_id, e)
            return self._fallback_reaction(profile)

    async def simulate_all_platforms(
        self,
        text: str,
        platforms: Optional[List[str]] = None,
        base_risk_scores: Optional[Dict[str, float]] = None,
        max_concurrent: int = 3,
    ) -> Dict[str, PlatformReaction]:
        """并行仿真多个平台

        Args:
            text: 待评估文案
            platforms: 平台列表，None则使用P0核心平台
            base_risk_scores: 基础风险分数
            max_concurrent: 最大并发数

        Returns:
            {platform_id: PlatformReaction}
        """
        if platforms is None:
            platforms = get_p0_platforms()

        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _simulate(platform_id: str):
            async with semaphore:
                return platform_id, await self.simulate_platform_reaction(
                    text, platform_id, base_risk_scores
                )

        tasks = [_simulate(pid) for pid in platforms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reactions = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error("平台仿真中的异常: %s", result)
                continue
            platform_id, reaction = result
            if reaction:
                reactions[platform_id] = reaction

        return reactions

    # ===========================================================================
    # Prompt 构建
    # ===========================================================================

    def _build_simulation_prompt(
        self,
        text: str,
        profile: PlatformProfile,
        base_risk_scores: Optional[Dict[str, float]] = None,
    ) -> str:
        """构建平台仿真Prompt"""
        risk_sensitivity = profile.risk_sensitivity
        top_sensitive = sorted(risk_sensitivity.items(), key=lambda x: x[1], reverse=True)[:3]

        prompt = f"""你是一名{profile.name}平台的资深用户和舆论观察员。请分析以下文案在{profile.name}平台可能引发的用户反应。

## 平台特征
- 用户画像：{profile.user_base_size}，主要年龄{profile.active_age_range[0]}-{profile.active_age_range[1]}岁，女性占比{int(profile.gender_ratio*100)}%
- 内容格式：{profile.content_format}，平均{profile.avg_content_length}
- 传播特征：传播速度{profile.propagation_speed}，放大系数{profile.amplification_factor}x
- 信息茧房强度：{profile.echo_chamber_strength}，极化倾向：{profile.polarization_tendency}
- 情绪基线：正面{int(profile.emotion_baseline.get('positive',0.35)*100)}%，中性{int(profile.emotion_baseline.get('neutral',0.35)*100)}%，负面{int(profile.emotion_baseline.get('negative',0.30)*100)}%

## 平台高风险维度
该用户对以下风险维度特别敏感：
{', '.join([f"{name}({score})" for name, score in top_sensitive])}

## 平台文化禁忌
{', '.join(profile.cultural_taboos)}

## 典型行为模式
{', '.join(profile.behavior_patterns)}

## 待评估文案
{text[:3000]}

{self._add_base_risk_hint(base_risk_scores)}

请以JSON格式返回分析结果：
{{
  "emotion_distribution": {{
    "positive": 0.0-1.0,
    "neutral": 0.0-1.0,
    "negative": 0.0-1.0
  }},
  "risk_score": 0-100,
  "risk_level": "safe|caution|warning|danger",
  "typical_reactions": [
    {{
      "reaction_type": "正面|中性|负面",
      "example_comment": "典型的用户评论示例（1-2句）",
      "reasoning": "为什么会产生这种反应"
    }}
  ],
  "key_concerns": ["用户可能关注的争议点1", "用户可能关注的争议点2"],
  "amplification_risk": 0.0-1.0,
  "platform_specific_advice": ["针对该平台的改写建议1", "建议2"]
}}

注意：
1. 情绪分布三项之和必须等于1.0
2. risk_level对应：safe(<30), caution(30-50), warning(50-70), danger(>70)
3. typical_reactions至少包含3条，覆盖正/中/负面
4. amplification_risk表示内容在该平台被放大的可能性
5. 建议要具体可操作，不要泛泛而谈"""
        return prompt

    def _add_base_risk_hint(self, base_risk_scores: Optional[Dict[str, float]]) -> str:
        """添加基础风险提示"""
        if not base_risk_scores:
            return ""

        high_risks = [
            (name, score) for name, score in base_risk_scores.items()
            if score >= 50
        ]
        if not high_risks:
            return "\n【参考信息】该文案整体风险较低，各维度分数均在50分以下。\n"

        hints = "【参考信息】该文案在以下维度存在中高风险：\n"
        for name, score in sorted(high_risks, key=lambda x: x[1], reverse=True):
            hints += f"- {name}: {score}分\n"
        return hints + "请结合平台特征判断这些风险在目标平台的影响。\n"

    # ===========================================================================
    # 结果解析
    # ===========================================================================

    def _parse_reaction(
        self,
        result: Dict[str, Any],
        profile: PlatformProfile,
        base_risk_scores: Optional[Dict[str, float]],
    ) -> PlatformReaction:
        """解析LLM返回的反应数据"""
        # 情绪分布校验
        emotion = result.get("emotion_distribution", {})
        total = emotion.get("positive", 0) + emotion.get("neutral", 0) + emotion.get("negative", 0)
        if total > 0 and abs(total - 1.0) > 0.01:
            # 归一化
            emotion["positive"] /= total
            emotion["neutral"] /= total
            emotion["negative"] /= total

        # 风险分数校准
        risk_score = result.get("risk_score", 50)
        if base_risk_scores:
            # 用平台敏感度调整风险分数
            avg_base = sum(base_risk_scores.values()) / len(base_risk_scores) if base_risk_scores else 0
            risk_score = (risk_score + avg_base) / 2

        # 风险等级映射
        risk_level = result.get("risk_level", "caution")
        if risk_level not in ("safe", "caution", "warning", "danger"):
            if risk_score >= 70:
                risk_level = "danger"
            elif risk_score >= 50:
                risk_level = "warning"
            elif risk_score >= 30:
                risk_level = "caution"
            else:
                risk_level = "safe"

        return PlatformReaction(
            platform_id=profile.platform_id,
            platform_name=profile.name,
            emotion_distribution=emotion,
            risk_score=risk_score,
            risk_level=risk_level,
            typical_reactions=result.get("typical_reactions", []),
            key_concerns=result.get("key_concerns", []),
            amplification_risk=result.get("amplification_risk", 0.5),
            platform_specific_advice=result.get("platform_specific_advice", []),
        )

    def _fallback_reaction(self, profile: PlatformProfile) -> PlatformReaction:
        """LLM失败时的降级反应"""
        emotion = profile.emotion_baseline.copy()
        # 确保和为1
        total = sum(emotion.values())
        if total > 0:
            emotion = {k: v / total for k, v in emotion.items()}

        return PlatformReaction(
            platform_id=profile.platform_id,
            platform_name=profile.name,
            emotion_distribution=emotion,
            risk_score=50.0,
            risk_level="caution",
            typical_reactions=[
                {
                    "reaction_type": "中性",
                    "example_comment": "（仿真降级：使用平台基线）",
                    "reasoning": "LLM调用失败，使用平台情绪基线",
                }
            ],
            key_concerns=[],
            amplification_risk=0.5,
            platform_specific_advice=[],
        )


# ===========================================================================
# 风险放大计算器
# ===========================================================================

def calculate_amplification_risk(
    base_score: float,
    platform_id: str,
    dimension: str = "overall",
) -> float:
    """计算内容在特定平台的风险放大分数

    Args:
        base_score: 基础风险分数
        platform_id: 平台标识
        dimension: 风险维度

    Returns:
        放大后的风险分数
    """
    profile = get_platform_profile(platform_id)
    if not profile:
        return base_score

    # 传播放大效应
    amp_factor = profile.amplification_factor
    # 放大效应主要影响高风险内容
    if base_score >= 60:
        amplification = min(100, base_score * (1 + (amp_factor - 1) * 0.3))
    elif base_score >= 40:
        amplification = min(100, base_score * (1 + (amp_factor - 1) * 0.15))
    else:
        amplification = base_score

    # 极化倾向加成
    pol_factor = profile.polarization_tendency
    if base_score >= 50:
        amplification = min(100, amplification * (1 + pol_factor * 0.1))

    return round(amplification, 1)


def get_platform_risk_summary(
    reactions: Dict[str, PlatformReaction],
) -> Dict[str, Any]:
    """汇总各平台风险预测

    Args:
        reactions: {platform_id: PlatformReaction}

    Returns:
        汇总报告
    """
    if not reactions:
        return {"platforms": [], "overall_risk": 0, "highest_risk_platform": None}

    platform_reports = []
    max_risk = 0
    highest_platform = None

    for platform_id, reaction in reactions.items():
        risk_dict = reaction.to_dict()
        platform_reports.append(risk_dict)

        if reaction.risk_score > max_risk:
            max_risk = reaction.risk_score
            highest_platform = reaction.platform_name

    # 平台加权风险分
    from backend.services.platform_weights import calculate_platform_weighted_score
    platform_scores = {pid: r.risk_score for pid, r in reactions.items()}
    overall_risk = calculate_platform_weighted_score(platform_scores)

    return {
        "platforms": platform_reports,
        "overall_risk": round(overall_risk, 1),
        "highest_risk_platform": highest_platform,
        "highest_risk_score": max_risk,
        "platform_count": len(reactions),
    }
