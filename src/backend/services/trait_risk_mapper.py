"""人格特质→风险维度权重映射表

将 Big Five 人格特质、人生经历映射到 7 维风险评估的权重调整。
用于 A/B 回测验证中实验组 (人生故事 Agent) 的风险评估增强。

映射规则:
1. Big Five 特质→基础敏感度 (0.5-2.0x)
2. 人生经历类型→触发式调整 (+/- 10-30 分)
3. 记忆检索→上下文相关增强
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TraitRiskMapping:
    """人格特质到风险维度的映射结果"""
    
    # 人格特质基础权重 (Big Five → 7 维风险)
    # 格式：{风险维度：权重因子}
    base_weights: Dict[str, float] = field(default_factory=dict)
    
    # 人生经历触发的额外调整
    # 格式：{风险维度：调整分数}
    experience_adjustments: Dict[str, float] = field(default_factory=dict)
    
    # 最终的风险维度权重 (0.5-2.0)
    # 格式：{风险维度：最终权重}
    final_weights: Dict[str, float] = field(default_factory=dict)
    
    # 人格画像摘要
    persona_summary: str = ""
    
    # 调整说明
    explanation: str = ""


class TraitRiskMapper:
    """人格特质→风险维度映射器"""
    
    # 风险维度列表 (7 维 + 4 维扩展)
    RISK_DIMENSIONS = [
        "政治敏感",
        "法律合规",
        "民族宗教",
        "性别议题",
        "道德伦理",
        "群体冒犯",
        "时事踩雷",
        # T4 扩展维度
        "事实错误",
        "平台禁区",
        "情绪极化",
        "价值观倾向",
    ]
    
    # Big Five 特质到风险维度的基础敏感度映射
    # 基于心理学研究：人格特质影响风险感知和判断
    BIG_FIVE_MAPPING = {
        # 开放性 (Openness): 对新经验、新思想的开放程度
        "openness": {
            "政治敏感": 0.15,
            "价值观倾向": 0.20,
            "时事踩雷": 0.10,
            "事实错误": -0.10,
        },
        
        # 尽责性 (Conscientiousness): 自律、组织性、目标导向
        "conscientiousness": {
            "法律合规": 0.20,
            "道德伦理": 0.15,
            "事实错误": 0.15,
            "平台禁区": 0.10,
        },
        
        # 外向性 (Extraversion): 社交活跃度、能量来源
        "extraversion": {
            "群体冒犯": -0.10,
            "性别议题": -0.05,
            "平台禁区": 0.10,
            "情绪极化": 0.10,
        },
        
        # 宜人性 (Agreeableness): 合作性、同理心、信任
        "agreeableness": {
            "群体冒犯": -0.20,
            "性别议题": -0.15,
            "道德伦理": 0.10,
            "情绪极化": -0.10,
        },
        
        # 神经质 (Neuroticism): 情绪稳定性、焦虑倾向
        "neuroticism": {
            "民族宗教": 0.15,
            "时事踩雷": 0.15,
            "道德伦理": 0.10,
            "群体冒犯": 0.10,
            "情绪极化": 0.15,
        },
    }
    
    # 人生经历类型到风险维度的影响映射
    EXPERIENCE_MAPPING = {
        "童年创伤": {"道德伦理": 0.15, "群体冒犯": 0.10, "情绪极化": 0.10},
        "校园暴力": {"群体冒犯": 0.20, "道德伦理": 0.15, "情绪极化": 0.15},
        "关系背叛": {"道德伦理": 0.15, "价值观倾向": 0.10},
        "家庭破裂": {"道德伦理": 0.10, "价值观倾向": 0.15, "情绪极化": 0.10},
        "被歧视": {"群体冒犯": 0.25, "性别议题": 0.20, "民族宗教": 0.15, "价值观倾向": 0.10},
        "贫困经历": {"价值观倾向": 0.20, "群体冒犯": 0.15, "道德伦理": 0.10},
        "事业成功": {"法律合规": -0.10, "事实错误": -0.10},
        "学术成就": {"事实错误": -0.15, "法律合规": -0.05},
        "被欺骗": {"法律合规": 0.15, "事实错误": 0.15, "道德伦理": 0.10},
        "网络暴力": {"群体冒犯": 0.20, "情绪极化": 0.20, "道德伦理": 0.10},
        "海外经历": {"民族宗教": -0.10, "价值观倾向": -0.10, "政治敏感": -0.05},
        "高等教育": {"事实错误": -0.10, "法律合规": -0.05, "价值观倾向": 0.10},
    }
    
    # 红线维度 (触碰即 HIGH 风险 76+)
    RED_LINE_DIMENSIONS = {"政治敏感", "法律合规", "民族宗教", "事实错误", "平台禁区"}
    
    def map_persona_to_risk_weights(self, persona: Dict[str, Any]) -> TraitRiskMapping:
        """将人格画像映射到风险维度权重"""
        result = TraitRiskMapping()
        result.base_weights = self._calc_base_weights(persona.get("big_five", {}))
        
        if "life_experiences" in persona or "events" in persona:
            result.experience_adjustments = self._calc_experience_adjustments(persona)
        
        result.final_weights = self._calc_final_weights(result.base_weights, result.experience_adjustments)
        result.persona_summary = self._generate_persona_summary(persona)
        result.explanation = self._generate_explanation(result)
        
        return result
    
    def _calc_base_weights(self, big_five: Dict[str, float]) -> Dict[str, float]:
        """计算 Big Five 基础权重"""
        weights = {dim: 1.0 for dim in self.RISK_DIMENSIONS}
        
        if not big_five:
            logger.warning("人格画像缺少 Big Five 数据，使用默认权重")
            return weights
        
        for trait_name, trait_score in big_five.items():
            if trait_name not in self.BIG_FIVE_MAPPING:
                continue
            
            trait_factor = (trait_score - 0.5) * 2
            
            for risk_dim, sensitivity in self.BIG_FIVE_MAPPING[trait_name].items():
                if risk_dim in weights:
                    weights[risk_dim] += sensitivity * trait_factor
        
        return weights
    
    def _calc_experience_adjustments(self, persona: Dict[str, Any]) -> Dict[str, float]:
        """计算人生经历的风险调整"""
        adjustments = {}
        experiences = persona.get("life_experiences", []) or persona.get("events", [])
        
        for exp in experiences:
            exp_type = exp.get("type", "")
            exp_desc = exp.get("description", "").lower()
            
            for known_type, risk_mapping in self.EXPERIENCE_MAPPING.items():
                if known_type in exp_type or known_type in exp_desc:
                    for risk_dim, adjustment in risk_mapping.items():
                        adjustments[risk_dim] = adjustments.get(risk_dim, 0.0) + adjustment
        
        return adjustments
    
    def _calc_final_weights(self, base_weights: Dict[str, float], experience_adjustments: Dict[str, float]) -> Dict[str, float]:
        """综合计算最终的风险维度权重"""
        final_weights = {}
        
        for dim in self.RISK_DIMENSIONS:
            base = base_weights.get(dim, 1.0)
            exp_adj = experience_adjustments.get(dim, 0.0)
            exp_factor = exp_adj / 100.0
            weight = base + exp_factor
            weight = max(0.5, min(2.0, weight))
            final_weights[dim] = round(weight, 3)
        
        return final_weights
    
    def _generate_persona_summary(self, persona: Dict[str, Any]) -> str:
        """生成人格画像摘要"""
        big_five = persona.get("big_five", {})
        if not big_five:
            return "未知人格画像"
        
        significant_traits = []
        for trait, score in big_five.items():
            deviation = abs(score - 0.5)
            if deviation > 0.15:
                direction = "偏高" if score > 0.5 else "偏低"
                trait_name_cn = {"openness": "开放性", "conscientiousness": "尽责性", "extraversion": "外向性", "agreeableness": "宜人性", "neuroticism": "神经质"}.get(trait, trait)
                significant_traits.append(f"{trait_name_cn}{direction}")
        
        return "人格特质：" + "、".join(significant_traits) if significant_traits else "人格特质：均衡型"
    
    def _generate_explanation(self, result: TraitRiskMapping) -> str:
        """生成权重调整说明"""
        significant_dims = [(dim, w) for dim, w in result.final_weights.items() if abs(w - 1.0) > 0.1]
        
        if not significant_dims:
            return "人格特质对风险评估无显著影响"
        
        significant_dims.sort(key=lambda x: abs(x[1] - 1.0), reverse=True)
        explanations = []
        
        for dim, weight in significant_dims[:3]:
            direction = "敏感度提升" if weight > 1.0 else "敏感度降低"
            change_pct = abs(weight - 1.0) * 100
            explanations.append(f"「{dim}」风险{direction}{change_pct:.0f}%")
        
        return "；".join(explanations) + "。"
    
    def apply_weights_to_scores(self, base_scores: Dict[str, float], weights: Dict[str, float]) -> Dict[str, float]:
        """将权重应用到基础风险评分"""
        adjusted_scores = {}
        
        for dim, base_score in base_scores.items():
            weight = weights.get(dim, 1.0)
            adjusted_score = base_score * weight
            adjusted_score = max(0, min(100, adjusted_score))
            adjusted_scores[dim] = round(adjusted_score, 1)
        
        return adjusted_scores
    
    def has_red_line_boost(self, weights: Dict[str, float], threshold: float = 1.15) -> bool:
        """检查是否有红线维度权重提升"""
        for dim in self.RED_LINE_DIMENSIONS:
            if weights.get(dim, 1.0) > threshold:
                return True
        return False


_mapper: Optional[TraitRiskMapper] = None


def get_mapper() -> TraitRiskMapper:
    """获取映射器单例"""
    global _mapper
    if _mapper is None:
        _mapper = TraitRiskMapper()
    return _mapper
