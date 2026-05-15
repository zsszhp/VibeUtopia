"""人格演化器 - 基于触发事件的动态人格调整

基于 T7 触发事件库，实现 Big Five 人格特质的动态演化。
支持事件组合效应、依恋类型响应、MBTI 倾向性调整。
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PersonalityState:
    """人格状态"""
    big_five: Dict[str, float] = field(default_factory=lambda: {
        "openness": 0.5,
        "conscientiousness": 0.5,
        "extraversion": 0.5,
        "agreeableness": 0.5,
        "neuroticism": 0.5,
    })
    mbti_type: str = "ENFP"
    attachment_style: str = "secure"
    enneagram_type: int = 1
    archetype: str = "探索者"


@dataclass
class TraitChange:
    """特质变化"""
    trait: str
    delta: float
    source_event: str
    cumulative_value: float


@dataclass
class EvolutionResult:
    """演化结果"""
    initial_state: PersonalityState
    evolved_state: PersonalityState
    trait_changes: List[TraitChange]
    key_turning_points: List[str]
    event_sequence: List[str]
    cumulative_impact: Dict[str, float]
    psychological_notes: List[str]


class PersonalityEvolver:
    """人格演化器"""
    
    def __init__(self, events_db_path: Optional[str] = None):
        """初始化人格演化器
        
        Args:
            events_db_path: 触发事件库路径，默认使用 data/events/trigger_events_db.json
        """
        if events_db_path is None:
            # 使用相对路径：从 backend/services/story_generation/ 到 data/events/
            events_db_path = str(Path(__file__).parent.parent.parent.parent / "data" / "events" / "trigger_events_db.json")
        
        self.events_db_path = events_db_path
        self.events_db = self._load_events_db()
        logger.info("人格演化器初始化完成，加载了 %d 个触发事件", len(self.events_db.get("trigger_events", [])))
    
    def _load_events_db(self) -> Dict[str, Any]:
        """加载触发事件库"""
        try:
            with open(self.events_db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("触发事件库不存在：%s", self.events_db_path)
            return {"trigger_events": [], "event_combinations": []}
        except json.JSONDecodeError as e:
            logger.error("触发事件库解析失败：%s", e)
            return {"trigger_events": [], "event_combinations": []}
    
    def evolve(
        self,
        initial_persona: Dict[str, Any],
        event_ids: List[str],
        simulate_years: int = 10,
    ) -> EvolutionResult:
        """执行人格演化模拟
        
        Args:
            initial_persona: 初始人格数据，包含 big_five, mbti_type, attachment_style 等
            event_ids: 触发事件 ID 列表
            simulate_years: 模拟年数（用于时间跨度计算）
        
        Returns:
            EvolutionResult: 演化结果，包含初始状态、演化后状态、特质变化等
        """
        initial_state = self._parse_persona(initial_persona)
        trait_changes: List[TraitChange] = []
        cumulative_impact = {
            "openness": 0.0,
            "conscientiousness": 0.0,
            "extraversion": 0.0,
            "agreeableness": 0.0,
            "neuroticism": 0.0,
        }
        key_turning_points: List[str] = []
        psychological_notes: List[str] = []
        
        events_map = {evt["id"]: evt for evt in self.events_db.get("trigger_events", [])}
        selected_events = []
        
        for event_id in event_ids:
            if event_id not in events_map:
                logger.warning("事件 ID %s 不存在，跳过", event_id)
                continue
            selected_events.append(events_map[event_id])
        
        current_big_five = initial_state.big_five.copy()
        
        for idx, event in enumerate(selected_events):
            event_name = event.get("name", "未知事件")
            event_category = event.get("category", "")
            
            impact_matrix = event.get("impact_matrix", {})
            for trait, delta in impact_matrix.items():
                if trait in cumulative_impact:
                    cumulative_impact[trait] += delta
                    
                    old_value = current_big_five.get(trait, 0.5)
                    new_value = self._clamp_trait(old_value + delta)
                    current_big_five[trait] = new_value
                    
                    trait_changes.append(TraitChange(
                        trait=trait,
                        delta=delta,
                        source_event=event_name,
                        cumulative_value=new_value,
                    ))
            
            event_turning_point = f"{event_category}: {event_name}"
            key_turning_points.append(event_turning_point)
            
            psychological_note = self._generate_psychological_note(
                event, initial_state, len(selected_events), idx
            )
            if psychological_note:
                psychological_notes.append(psychological_note)
        
        event_sequence = [evt.get("name", "未知事件") for evt in selected_events]
        
        evolved_state = PersonalityState(
            big_five=current_big_five,
            mbti_type=self._adjust_mbti(initial_state.mbti_type, cumulative_impact),
            attachment_style=self._adjust_attachment_style(
                initial_state.attachment_style, cumulative_impact, selected_events
            ),
            enneagram_type=initial_state.enneagram_type,
            archetype=initial_state.archetype,
        )
        
        return EvolutionResult(
            initial_state=initial_state,
            evolved_state=evolved_state,
            trait_changes=trait_changes,
            key_turning_points=key_turning_points,
            event_sequence=event_sequence,
            cumulative_impact=cumulative_impact,
            psychological_notes=psychological_notes,
        )
    
    def _parse_persona(self, persona_data: Dict[str, Any]) -> PersonalityState:
        """解析人格数据"""
        big_five_data = persona_data.get("big_five", {})
        
        return PersonalityState(
            big_five={
                "openness": big_five_data.get("openness", 0.5),
                "conscientiousness": big_five_data.get("conscientiousness", 0.5),
                "extraversion": big_five_data.get("extraversion", 0.5),
                "agreeableness": big_five_data.get("agreeableness", 0.5),
                "neuroticism": big_five_data.get("neuroticism", 0.5),
            },
            mbti_type=persona_data.get("mbti_type", "ENFP"),
            attachment_style=persona_data.get("attachment_style", "secure"),
            enneagram_type=persona_data.get("enneagram_type", 1),
            archetype=persona_data.get("archetype", "探索者"),
        )
    
    def _clamp_trait(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """限制特质值在有效范围内"""
        return max(min_val, min(max_val, value))
    
    def _generate_psychological_note(
        self,
        event: Dict[str, Any],
        state: PersonalityState,
        total_events: int,
        event_index: int,
    ) -> str:
        """生成心理学注释"""
        event_type = event.get("type", "")
        event_name = event.get("name", "")
        
        if event_type == "正向事件":
            if state.big_five.get("neuroticism", 0.5) < 0.4:
                return f"{event_name}后，情绪稳定性进一步提升，心理韧性增强"
            elif state.big_five.get("extraversion", 0.5) > 0.6:
                return f"{event_name}增强了社交信心，更愿意表达自我"
            else:
                return f"{event_name}带来积极的心理暗示，自我效能感提升"
        
        elif event_type == "负向事件":
            if state.big_five.get("neuroticism", 0.5) > 0.7:
                return f"{event_name}后，情绪波动加剧，需要更多心理支持"
            elif state.big_five.get("extraversion", 0.5) < 0.4:
                return f"{event_name}可能导致社交退缩，需要重建信任"
            else:
                return f"{event_name}带来短期心理冲击，但具备恢复潜力"
        
        elif event_type == "中性事件":
            if state.big_five.get("openness", 0.5) > 0.6:
                return f"{event_name}带来新的体验和成长机会"
            else:
                return f"{event_name}是生活的重要转折点，需要适应期"
        
        return ""
    
    def _adjust_mbti(self, mbti_type: str, cumulative_impact: Dict[str, float]) -> str:
        """根据特质变化调整 MBTI 类型（简化版本）
        
        MBTI 四个维度：
        - E/I: Extraversion 相关
        - S/N: Sensing/iNtuition，与 Openness 部分相关
        - T/F: Thinking/Feeling，与 Agreeableness 部分相关
        - J/P: Judging/Perceiving，与 Conscientiousness 相关
        """
        e_threshold = 0.55
        n_threshold = 0.55
        f_threshold = 0.55
        j_threshold = 0.55
        
        e_or_i = "E" if cumulative_impact.get("extraversion", 0) > 0 else "I"
        s_or_n = "N" if cumulative_impact.get("openness", 0) > 0.05 else "S"
        t_or_f = "F" if cumulative_impact.get("agreeableness", 0) > 0.05 else "T"
        j_or_p = "J" if cumulative_impact.get("conscientiousness", 0) > 0.05 else "P"
        
        new_mbti = f"{e_or_i}{s_or_n}{t_or_f}{j_or_p}"
        
        if new_mbti != mbti_type:
            logger.info("MBTI 类型从 %s 调整为 %s", mbti_type, new_mbti)
        
        return new_mbti
    
    def _adjust_attachment_style(
        self,
        attachment_style: str,
        cumulative_impact: Dict[str, float],
        events: List[Dict[str, Any]],
    ) -> str:
        """根据事件影响调整依恋类型（简化版本）
        
        依恋类型转换逻辑：
        - secure: 基线，高开放性 + 低神经质
        - anxious: 高神经质 + 低外向
        - avoidant: 低开放性 + 低外向
        - disorganized: 极高神经质
        """
        neuroticism = cumulative_impact.get("neuroticism", 0)
        extraversion = cumulative_impact.get("extraversion", 0)
        openness = cumulative_impact.get("openness", 0)
        
        if neuroticism > 0.5:
            return "disorganized"
        elif neuroticism > 0.2 and extraversion < -0.1:
            return "anxious"
        elif openness < -0.1 and extraversion < 0:
            return "avoidant"
        else:
            return attachment_style
    
    def to_response_dict(self, result: EvolutionResult) -> Dict[str, Any]:
        """将演化结果转换为 API 响应格式"""
        return {
            "user_id": "",
            "initial_persona": {
                "big_five": result.initial_state.big_five,
                "mbti_type": result.initial_state.mbti_type,
                "attachment_style": result.initial_state.attachment_style,
                "enneagram_type": result.initial_state.enneagram_type,
                "archetype": result.initial_state.archetype,
            },
            "evolved_persona": {
                "big_five": result.evolved_state.big_five,
                "mbti_type": result.evolved_state.mbti_type,
                "attachment_style": result.evolved_state.attachment_style,
                "enneagram_type": result.evolved_state.enneagram_type,
                "archetype": result.evolved_state.archetype,
            },
            "trait_changes": [
                {
                    "trait": change.trait,
                    "delta": change.delta,
                    "source_event": change.source_event,
                    "cumulative_value": change.cumulative_value,
                }
                for change in result.trait_changes
            ],
            "key_turning_points": result.key_turning_points,
            "event_sequence": result.event_sequence,
            "cumulative_impact": result.cumulative_impact,
            "psychological_notes": result.psychological_notes,
            "simulate_years": 0,
        }
