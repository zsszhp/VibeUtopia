"""人生故事→风险评估关联机制

将人生故事和人格特质映射到风险评估维度，提供个性化风险敏感度调整。

核心机制:
1. Big Five 特质→风险维度敏感度映射
2. 人生经历→风险权重调整
3. 记忆检索→上下文增强
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from backend.services.persona.memory_stream import MemoryStreamStore

logger = logging.getLogger(__name__)


@dataclass
class StoryRiskAssociation:
    """人生故事与风险的关联结果"""
    
    # 人格特质基础敏感度 (0-1)
    trait_sensitivities: Dict[str, float] = field(default_factory=dict)
    
    # 人生经历触发的风险调整
    experience_adjustments: Dict[str, float] = field(default_factory=dict)
    
    # 检索到的相关记忆
    retrieved_memories: List[Dict[str, Any]] = field(default_factory=list)
    
    # 最终的风险维度权重调整 (0.5-2.0)
    dimension_weights: Dict[str, float] = field(default_factory=dict)
    
    # 关联说明
    explanation: str = ""


class StoryRiskAssociator:
    """人生故事→风险评估关联器"""
    
    # Big Five 特质到风险维度的映射权重
    # 格式：{特质：{风险维度：敏感度}}
    TRAIT_RISK_MAPPING = {
        # 开放性 (Openness)
        "openness": {
            "政治敏感": 0.3,      # 开放性高的人更关注政治议题
            "价值观倾向": 0.4,    # 更愿意挑战传统价值观
            "时事踩雷": 0.2,      # 对新事物好奇，可能忽视风险
        },
        
        # 尽责性 (Conscientiousness)
        "conscientiousness": {
            "法律合规": 0.4,      # 尽责性高的人更重视规则
            "道德伦理": 0.3,      # 更强的道德约束
            "事实错误": 0.3,      # 更注重准确性
        },
        
        # 外向性 (Extraversion)
        "extraversion": {
            "群体冒犯": 0.2,      # 外向者可能忽视少数群体感受
            "性别议题": 0.1,      # 相对较低敏感度
            "平台禁区": 0.2,      # 可能更敢于突破边界
        },
        
        # 宜人性 (Agreeableness)
        "agreeableness": {
            "群体冒犯": -0.3,     # 宜人性高的人更敏感于冒犯
            "性别议题": -0.2,     # 更关注弱势群体
            "道德伦理": 0.2,      # 更强的同理心
        },
        
        # 神经质 (Neuroticism)
        "neuroticism": {
            "民族宗教": 0.3,      # 情绪不稳定者更易焦虑
            "时事踩雷": 0.3,      # 对负面事件更敏感
            "道德伦理": 0.2,      # 更易产生道德焦虑
        },
    }
    
    # 人生经历类型到风险维度的影响
    EXPERIENCE_RISK_MAPPING = {
        # 创伤类经历
        "童年创伤": {
            "未成年人保护": 0.4,
            "道德伦理": 0.3,
            "群体冒犯": 0.2,
        },
        "校园暴力": {
            "未成年人保护": 0.5,
            "群体冒犯": 0.3,
            "道德伦理": 0.2,
        },
        "关系背叛": {
            "性别议题": 0.3,
            "道德伦理": 0.2,
        },
        "家庭破裂": {
            "未成年人保护": 0.3,
            "价值观倾向": 0.2,
        },
        
        # 成就类经历
        "事业成功": {
            "法律合规": -0.1,     # 成功者更自信于合规
            "事实错误": -0.1,
        },
        "学术成就": {
            "事实错误": -0.2,
            "法律合规": -0.1,
        },
        
        # 负面经历
        "被欺骗": {
            "法律合规": 0.2,
            "事实错误": 0.2,
        },
        "被歧视": {
            "群体冒犯": 0.4,
            "性别议题": 0.3,
            "民族宗教": 0.2,
        },
        "贫困经历": {
            "价值观倾向": 0.3,
            "群体冒犯": 0.2,
        },
    }
    
    def __init__(self, memory_store: Optional[MemoryStreamStore] = None):
        """初始化关联器
        
        Args:
            memory_store: ChromaDB 记忆存储，用于检索相关记忆
        """
        self.memory_store = memory_store or MemoryStreamStore()
    
    def associate(
        self,
        persona: Dict[str, Any],
        life_story: Optional[Dict[str, Any]] = None,
        text: str = "",
        agent_id: Optional[str] = None,
    ) -> StoryRiskAssociation:
        """将人生故事关联到风险评估
        
        Args:
            persona: 人格画像 (包含 Big Five 等)
            life_story: 人生故事数据 (可选)
            text: 待评估的文案文本
            agent_id: Agent ID (用于记忆检索)
        
        Returns:
            StoryRiskAssociation: 关联结果
        """
        result = StoryRiskAssociation()
        
        # Step 1: 计算人格特质的基础敏感度
        result.trait_sensitivities = self._calc_trait_sensitivities(persona)
        
        # Step 2: 从人生经历提取风险调整
        if life_story:
            result.experience_adjustments = self._calc_experience_adjustments(life_story)
        
        # Step 3: 检索相关记忆 (如果有 agent_id 和文本)
        if agent_id and text and self.memory_store.is_chroma_available:
            result.retrieved_memories = self._retrieve_relevant_memories(
                agent_id, text, top_k=5
            )
        
        # Step 4: 综合计算最终的风险维度权重
        result.dimension_weights = self._calc_dimension_weights(
            result.trait_sensitivities,
            result.experience_adjustments,
        )
        
        # Step 5: 生成关联说明
        result.explanation = self._generate_explanation(result)
        
        return result
    
    def _calc_trait_sensitivities(
        self,
        persona: Dict[str, Any],
    ) -> Dict[str, float]:
        """计算人格特质的风险敏感度
        
        基于 Big Five 特质分数，计算对各个风险维度的基础敏感度。
        
        Args:
            persona: 人格画像，应包含 big_five 字段
        
        Returns:
            风险维度→敏感度分数的字典
        """
        sensitivities: Dict[str, float] = {}
        big_five = persona.get("big_five", {})
        
        if not big_five:
            logger.warning("人格画像缺少 Big Five 数据")
            return sensitivities
        
        # 遍历每个人格特质
        for trait_name, trait_score in big_five.items():
            if trait_name not in self.TRAIT_RISK_MAPPING:
                continue
            
            # trait_score 范围：0-1，0.5 为中性
            # 转换为影响因子：-0.5 到 +0.5
            trait_factor = (trait_score - 0.5) * 2  # -1 到 +1
            
            # 应用特质到风险维度的映射
            for risk_dim, sensitivity in self.TRAIT_RISK_MAPPING[trait_name].items():
                if risk_dim not in sensitivities:
                    sensitivities[risk_dim] = 0.0
                
                # 累加敏感度 (trait_factor 可正可负)
                sensitivities[risk_dim] += sensitivity * trait_factor
        
        return sensitivities
    
    def _calc_experience_adjustments(
        self,
        life_story: Dict[str, Any],
    ) -> Dict[str, float]:
        """计算人生经历的风险权重调整
        
        从人生故事的关键事件中提取风险相关经历，计算权重调整。
        
        Args:
            life_story: 人生故事数据，应包含 events 或 stages
        
        Returns:
            风险维度→调整分数的字典
        """
        adjustments: Dict[str, float] = {}
        
        # 从人生故事中提取关键事件
        events = []
        if "events" in life_story:
            events = life_story["events"]
        elif "stages" in life_story:
            # 从时间线阶段中提取事件
            for stage in life_story["stages"]:
                if "events" in stage:
                    events.extend(stage["events"])
        
        # 遍历事件，匹配已知的经历类型
        for event in events:
            event_desc = event.get("description", "").lower()
            event_type = event.get("type", "")
            
            # 检查是否匹配已知的经历类型
            for exp_type, risk_mapping in self.EXPERIENCE_RISK_MAPPING.items():
                if exp_type in event_type or exp_type in event_desc:
                    # 匹配成功，应用风险调整
                    for risk_dim, adjustment in risk_mapping.items():
                        if risk_dim not in adjustments:
                            adjustments[risk_dim] = 0.0
                        adjustments[risk_dim] += adjustment
        
        return adjustments
    
    def _retrieve_relevant_memories(
        self,
        agent_id: str,
        text: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """从 ChromaDB 检索相关记忆
        
        使用文案文本作为查询，检索与该 Agent 相关的历史记忆，
        为风险评估提供上下文。
        
        Args:
            agent_id: Agent ID
            text: 查询文本 (通常是待评估的文案)
            top_k: 返回的记忆数量
        
        Returns:
            记忆列表
        """
        try:
            memories = self.memory_store.retrieve(agent_id, text, top_k)
            logger.info(f"为 Agent {agent_id} 检索到 {len(memories)} 条相关记忆")
            return memories
        except Exception as e:
            logger.warning(f"记忆检索失败：{e}")
            return []
    
    def _calc_dimension_weights(
        self,
        trait_sensitivities: Dict[str, float],
        experience_adjustments: Dict[str, float],
    ) -> Dict[str, float]:
        """综合计算最终的风险维度权重
        
        权重范围：0.5 (降低敏感度) 到 2.0 (提升敏感度)
        1.0 为基准权重。
        
        Args:
            trait_sensitivities: 人格特质敏感度
            experience_adjustments: 人生经历调整
        
        Returns:
            风险维度→最终权重的字典
        """
        weights: Dict[str, float] = {}
        
        # 所有风险维度列表
        all_dimensions = set(trait_sensitivities.keys()) | set(experience_adjustments.keys())
        
        for dim in all_dimensions:
            # 基础权重为 1.0
            base_weight = 1.0
            
            # 人格特质敏感度贡献 (范围：-0.5 到 +0.5)
            trait_contrib = trait_sensitivities.get(dim, 0.0)
            
            # 人生经历调整贡献 (范围：-0.5 到 +0.5)
            exp_contrib = experience_adjustments.get(dim, 0.0)
            
            # 综合贡献
            total_contrib = trait_contrib + exp_contrib
            
            # 转换为权重 (0.5-2.0)
            # 贡献为 0 → 权重 1.0
            # 贡献为正 → 权重提升，最大 2.0
            # 贡献为负 → 权重降低，最小 0.5
            weight = base_weight + total_contrib
            
            # 限制范围
            weight = max(0.5, min(2.0, weight))
            
            weights[dim] = weight
        
        return weights
    
    def _generate_explanation(
        self,
        association: StoryRiskAssociation,
    ) -> str:
        """生成关联说明
        
        用自然语言解释人生故事如何影响风险评估。
        
        Args:
            association: 关联结果
        
        Returns:
            说明文本
        """
        explanations = []
        
        # 人格特质影响
        if association.trait_sensitivities:
            top_traits = sorted(
                association.trait_sensitivities.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:3]
            
            for dim, score in top_traits:
                if abs(score) > 0.1:  # 只显示显著影响
                    direction = "提升" if score > 0 else "降低"
                    explanations.append(
                        f"人格特质对「{dim}」风险敏感度{direction}{abs(score)*100:.0f}%"
                    )
        
        # 人生经历影响
        if association.experience_adjustments:
            top_exps = sorted(
                association.experience_adjustments.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:3]
            
            for dim, adj in top_exps:
                if abs(adj) > 0.1:
                    direction = "强化" if adj > 0 else "弱化"
                    explanations.append(
                        f"人生经历{direction}了「{dim}」风险的权重"
                    )
        
        # 记忆检索
        if association.retrieved_memories:
            explanations.append(
                f"从 ChromaDB 检索到{len(association.retrieved_memories)}条相关记忆"
            )
        
        if not explanations:
            explanations.append("未检测到显著的人生故事影响")
        
        return "；".join(explanations) + "。"
    
    def apply_to_risk_assessment(
        self,
        association: StoryRiskAssociation,
        base_scores: Dict[str, float],
    ) -> Dict[str, float]:
        """将关联结果应用到风险评分
        
        使用计算出的维度权重调整基础风险评分。
        
        Args:
            association: 关联结果
            base_scores: 基础风险评分 (各维度 0-100 分)
        
        Returns:
            调整后的风险评分
        """
        adjusted_scores = {}
        
        for dim, base_score in base_scores.items():
            weight = association.dimension_weights.get(dim, 1.0)
            
            # 应用权重调整
            # 权重 > 1.0 → 提升风险分
            # 权重 < 1.0 → 降低风险分
            adjusted_score = base_score * weight
            
            # 限制在 0-100 范围内
            adjusted_score = max(0, min(100, adjusted_score))
            
            adjusted_scores[dim] = adjusted_score
        
        return adjusted_scores


# 单例模式
_associator: Optional[StoryRiskAssociator] = None


def get_associator() -> StoryRiskAssociator:
    """获取关联器单例"""
    global _associator
    if _associator is None:
        _associator = StoryRiskAssociator()
    return _associator
