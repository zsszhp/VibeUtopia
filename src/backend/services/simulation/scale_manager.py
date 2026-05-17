"""Agent 规模递进管理 — 4个规模级别的仿真配置与 GroupAgent 自动启用

规模级别：
- 轻量（100 Agent，1-2分钟）
- 标准（500 Agent，3-5分钟）
- 深度（2000 Agent，10-15分钟）
- 大规模（10000 Agent，20-40分钟）
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.services.simulation.models import AgentTier

logger = logging.getLogger(__name__)


class ScaleLevel(str, Enum):
    """仿真规模级别"""
    LIGHTWEIGHT = "lightweight"
    STANDARD = "standard"
    DEEP = "deep"
    MASSIVE = "massive"


SCALE_LABELS = {
    ScaleLevel.LIGHTWEIGHT: "轻量",
    ScaleLevel.STANDARD: "标准",
    ScaleLevel.DEEP: "深度",
    ScaleLevel.MASSIVE: "大规模",
}


@dataclass
class TierAllocation:
    """Agent 层级分配策略"""
    a_count: int = 0
    b_count: int = 0
    c_count: int = 0
    group_count: int = 0
    group_size_per: int = 50  # 每个 GroupAgent 包含的个体数

    @property
    def equivalent_individuals(self) -> int:
        """等效个体总数（含 GroupAgent 等效）"""
        return self.a_count + self.b_count + self.c_count + self.group_count * self.group_size_per

    @property
    def llm_calling_agents(self) -> int:
        """需要 LLM 调用的 Agent 数（A + B 层）"""
        return self.a_count + self.b_count


@dataclass
class ScaleConfig:
    """规模配置"""
    level: ScaleLevel = ScaleLevel.LIGHTWEIGHT
    total_agents: int = 100
    tier_allocation: TierAllocation = field(default_factory=TierAllocation)
    simulation_hours: int = 6
    time_acceleration: int = 6
    tick_interval: float = 0.2
    max_llm_calls: int = 200
    enable_group_agent: bool = False
    enable_director: bool = False
    enable_watcher: bool = False
    enable_guardian: bool = False
    b_agent_per_tick: int = 5
    estimated_duration_minutes: Tuple[float, float] = (1.0, 2.0)
    estimated_cost_cny: Tuple[float, float] = (0.5, 1.0)


# 预定义规模配置
SCALE_CONFIGS: Dict[ScaleLevel, ScaleConfig] = {
    ScaleLevel.LIGHTWEIGHT: ScaleConfig(
        level=ScaleLevel.LIGHTWEIGHT,
        total_agents=100,
        tier_allocation=TierAllocation(
            a_count=2,
            b_count=20,
            c_count=78,
            group_count=0,
            group_size_per=0,
        ),
        simulation_hours=6,
        time_acceleration=6,
        tick_interval=0.2,
        max_llm_calls=200,
        enable_group_agent=False,
        enable_director=False,
        enable_watcher=False,
        enable_guardian=False,
        b_agent_per_tick=3,
        estimated_duration_minutes=(1.0, 2.0),
        estimated_cost_cny=(0.5, 1.0),
    ),
    ScaleLevel.STANDARD: ScaleConfig(
        level=ScaleLevel.STANDARD,
        total_agents=500,
        tier_allocation=TierAllocation(
            a_count=3,
            b_count=50,
            c_count=447,
            group_count=0,
            group_size_per=0,
        ),
        simulation_hours=12,
        time_acceleration=12,
        tick_interval=0.3,
        max_llm_calls=600,
        enable_group_agent=False,
        enable_director=True,
        enable_watcher=True,
        enable_guardian=False,
        b_agent_per_tick=5,
        estimated_duration_minutes=(3.0, 5.0),
        estimated_cost_cny=(2.0, 5.0),
    ),
    ScaleLevel.DEEP: ScaleConfig(
        level=ScaleLevel.DEEP,
        total_agents=2000,
        tier_allocation=TierAllocation(
            a_count=3,
            b_count=80,
            c_count=917,
            group_count=20,
            group_size_per=50,
        ),
        simulation_hours=24,
        time_acceleration=24,
        tick_interval=0.4,
        max_llm_calls=1500,
        enable_group_agent=True,
        enable_director=True,
        enable_watcher=True,
        enable_guardian=True,
        b_agent_per_tick=8,
        estimated_duration_minutes=(10.0, 15.0),
        estimated_cost_cny=(8.0, 15.0),
    ),
    ScaleLevel.MASSIVE: ScaleConfig(
        level=ScaleLevel.MASSIVE,
        total_agents=10000,
        tier_allocation=TierAllocation(
            a_count=5,
            b_count=100,
            c_count=1895,
            group_count=160,
            group_size_per=50,
        ),
        simulation_hours=48,
        time_acceleration=48,
        tick_interval=0.5,
        max_llm_calls=3000,
        enable_group_agent=True,
        enable_director=True,
        enable_watcher=True,
        enable_guardian=True,
        b_agent_per_tick=10,
        estimated_duration_minutes=(20.0, 40.0),
        estimated_cost_cny=(20.0, 50.0),
    ),
}


class ScaleManager:
    """Agent 规模递进管理器

    管理不同规模的仿真配置，自动在大规模仿真时启用 GroupAgent 机制，
    估算 LLM 调用次数和费用。
    """

    def __init__(self):
        self._current_level: ScaleLevel = ScaleLevel.LIGHTWEIGHT
        self._custom_configs: Dict[ScaleLevel, ScaleConfig] = {}

    def get_config(self, level: Optional[ScaleLevel] = None) -> ScaleConfig:
        """获取指定规模的配置"""
        level = level or self._current_level
        # 优先使用自定义配置
        if level in self._custom_configs:
            return self._custom_configs[level]
        return SCALE_CONFIGS.get(level, SCALE_CONFIGS[ScaleLevel.LIGHTWEIGHT])

    def set_level(self, level: ScaleLevel):
        """设置当前规模级别"""
        self._current_level = level
        config = self.get_config(level)
        logger.info(
            "ScaleManager: 切换到 %s 规模, 总Agent=%d, 等效个体=%d, GroupAgent=%s",
            SCALE_LABELS.get(level, ""),
            config.total_agents,
            config.tier_allocation.equivalent_individuals,
            "启用" if config.enable_group_agent else "禁用",
        )

    @property
    def current_level(self) -> ScaleLevel:
        return self._current_level

    def customize_config(self, level: ScaleLevel, overrides: Dict[str, Any]) -> ScaleConfig:
        """自定义规模配置（降级机制：参数校验后覆盖）"""
        base = self.get_config(level)
        config_dict = {
            "level": base.level,
            "total_agents": base.total_agents,
            "simulation_hours": base.simulation_hours,
            "time_acceleration": base.time_acceleration,
            "tick_interval": base.tick_interval,
            "max_llm_calls": base.max_llm_calls,
            "enable_group_agent": base.enable_group_agent,
            "enable_director": base.enable_director,
            "enable_watcher": base.enable_watcher,
            "enable_guardian": base.enable_guardian,
            "b_agent_per_tick": base.b_agent_per_tick,
        }

        for key, value in overrides.items():
            if key in config_dict:
                config_dict[key] = value

        # 自动启用 GroupAgent（当 total_agents > 1000 时）
        if config_dict["total_agents"] > 1000:
            config_dict["enable_group_agent"] = True

        # 重新计算层级分配
        allocation = self._compute_allocation(
            config_dict["total_agents"],
            config_dict["enable_group_agent"],
        )

        new_config = ScaleConfig(
            level=level,
            total_agents=config_dict["total_agents"],
            tier_allocation=allocation,
            simulation_hours=config_dict["simulation_hours"],
            time_acceleration=config_dict["time_acceleration"],
            tick_interval=config_dict["tick_interval"],
            max_llm_calls=config_dict["max_llm_calls"],
            enable_group_agent=config_dict["enable_group_agent"],
            enable_director=config_dict["enable_director"],
            enable_watcher=config_dict["enable_watcher"],
            enable_guardian=config_dict["enable_guardian"],
            b_agent_per_tick=config_dict["b_agent_per_tick"],
            estimated_duration_minutes=self._estimate_duration(config_dict),
            estimated_cost_cny=self._estimate_cost(config_dict, allocation),
        )

        self._custom_configs[level] = new_config
        return new_config

    def _compute_allocation(self, total_agents: int, use_group: bool) -> TierAllocation:
        """计算 Agent 层级分配策略"""
        # A 层：管理 Agent（2-5个）
        a_count = min(5, max(2, total_agents // 200))

        # B 层：LLM 驱动市民 Agent（10-20%）
        b_count = max(10, min(100, int(total_agents * 0.1)))

        if use_group:
            # C 层 + GroupAgent 混合
            # C 层保留一部分（30%）
            c_count = int(total_agents * 0.3)
            # 剩余用 GroupAgent 覆盖
            remaining = total_agents - a_count - b_count - c_count
            group_size_per = 50
            group_count = max(0, remaining // group_size_per)
        else:
            c_count = total_agents - a_count - b_count
            group_count = 0
            group_size_per = 0

        return TierAllocation(
            a_count=a_count,
            b_count=b_count,
            c_count=c_count,
            group_count=group_count,
            group_size_per=group_size_per,
        )

    def _estimate_duration(self, config_dict: Dict[str, Any]) -> Tuple[float, float]:
        """估算仿真时长（分钟）"""
        total = config_dict["total_agents"]
        tick_interval = config_dict["tick_interval"]
        sim_hours = config_dict["simulation_hours"]
        time_accel = config_dict["time_acceleration"]

        # tick 总数 ≈ sim_hours * 6 (每小时6个tick)
        total_ticks = sim_hours * 6
        # 真实时间 ≈ total_ticks * tick_interval / 60
        base_minutes = total_ticks * tick_interval / 60

        # Agent 数量增加会带来额外开销
        scale_factor = 1.0 + (total / 1000) * 0.5

        min_est = base_minutes * scale_factor * 0.8
        max_est = base_minutes * scale_factor * 1.2

        return (round(min_est, 1), round(max_est, 1))

    def _estimate_cost(self, config_dict: Dict[str, Any], allocation: TierAllocation) -> Tuple[float, float]:
        """估算 LLM 调用费用（人民币）

        假设：
        - B 层每次 LLM 调用约 0.01-0.03 元
        - A 层每次 LLM 调用约 0.02-0.05 元
        """
        b_calls = config_dict.get("max_llm_calls", 200)
        a_calls = b_calls // 5  # A 层调用约为 B 层的 1/5

        # B 层费用
        b_cost_min = b_calls * 0.01
        b_cost_max = b_calls * 0.03

        # A 层费用
        a_cost_min = a_calls * 0.02
        a_cost_max = a_calls * 0.05

        return (
            round(b_cost_min + a_cost_min, 2),
            round(b_cost_max + a_cost_max, 2),
        )

    def build_engine_config(self, level: Optional[ScaleLevel] = None) -> Dict[str, Any]:
        """构建 SimulationEngine 所需的配置字典"""
        config = self.get_config(level)
        alloc = config.tier_allocation

        engine_config = {
            "agent_count": config.total_agents,
            "simulation_hours": config.simulation_hours,
            "time_acceleration": config.time_acceleration,
            "max_ticks": config.simulation_hours * 6,
            "tick_interval": config.tick_interval,
            "max_llm_calls": config.max_llm_calls,
            "b_agent_per_tick": config.b_agent_per_tick,
            "platforms": ["weibo", "bilibili", "xiaohongshu", "zhihu", "douyin"],
            "llm_tier": "tier2" if config.level in (ScaleLevel.LIGHTWEIGHT, ScaleLevel.STANDARD) else "tier1",
            "seed_injection": True,
            # 规模相关
            "scale_level": config.level.value,
            "enable_group_agent": config.enable_group_agent,
            "enable_director": config.enable_director,
            "enable_watcher": config.enable_watcher,
            "enable_guardian": config.enable_guardian,
            # 层级分配
            "a_count": alloc.a_count,
            "b_count": alloc.b_count,
            "c_count": alloc.c_count,
            "group_count": alloc.group_count,
            "group_size_per": alloc.group_size_per,
            "equivalent_individuals": alloc.equivalent_individuals,
        }

        # 轻量模式标记
        if config.level == ScaleLevel.LIGHTWEIGHT:
            engine_config["lightweight"] = True
            engine_config["skip_coordinators"] = True

        return engine_config

    def get_cost_estimate(self, level: Optional[ScaleLevel] = None) -> Dict[str, Any]:
        """获取成本估算详情"""
        config = self.get_config(level)
        alloc = config.tier_allocation

        return {
            "level": config.level.value,
            "level_label": SCALE_LABELS.get(config.level, ""),
            "total_agents": config.total_agents,
            "equivalent_individuals": alloc.equivalent_individuals,
            "llm_calling_agents": alloc.llm_calling_agents,
            "max_llm_calls": config.max_llm_calls,
            "estimated_duration_min": config.estimated_duration_minutes[0],
            "estimated_duration_max": config.estimated_duration_minutes[1],
            "estimated_cost_min": config.estimated_cost_cny[0],
            "estimated_cost_max": config.estimated_cost_cny[1],
            "group_agent_enabled": config.enable_group_agent,
            "tier_breakdown": {
                "A": alloc.a_count,
                "B": alloc.b_count,
                "C": alloc.c_count,
                "Group": alloc.group_count,
                "Group_equivalent": alloc.group_count * alloc.group_size_per if alloc.group_count > 0 else 0,
            },
        }

    def get_all_levels(self) -> List[Dict[str, Any]]:
        """获取所有规模级别信息"""
        return [self.get_cost_estimate(level) for level in ScaleLevel]

    def validate_feasibility(self, level: ScaleLevel) -> Dict[str, Any]:
        """验证指定规模是否可行（降级机制：资源不足时建议降级）"""
        config = self.get_config(level)
        issues = []
        suggestions = []

        # LLM 调用量检查
        if config.max_llm_calls > 5000:
            issues.append("LLM 调用量可能过高，建议减少 B 层 Agent 或降低 b_agent_per_tick")
            suggestions.append("考虑使用深度模式替代大规模模式")

        # 时长检查
        if config.estimated_duration_minutes[1] > 60:
            issues.append(f"预估时长可能超过60分钟（{config.estimated_duration_minutes[1]}分钟）")
            suggestions.append("考虑减少 simulation_hours 或增加 time_acceleration")

        # GroupAgent 可行性
        if config.enable_group_agent and config.tier_allocation.group_count > 200:
            issues.append("GroupAgent 数量较多，内存占用可能较高")
            suggestions.append("考虑增大 group_size_per 以减少 GroupAgent 数量")

        feasible = len(issues) == 0
        recommended_level = level

        if not feasible:
            # 降级建议
            level_order = [ScaleLevel.LIGHTWEIGHT, ScaleLevel.STANDARD, ScaleLevel.DEEP, ScaleLevel.MASSIVE]
            idx = level_order.index(level)
            if idx > 0:
                recommended_level = level_order[idx - 1]

        return {
            "level": level.value,
            "feasible": feasible,
            "issues": issues,
            "suggestions": suggestions,
            "recommended_level": recommended_level.value if not feasible else level.value,
        }
