"""仿真时间模型 — 8时段 + Agent个性化时间表 + 时间加速"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 8时段定义
TIME_SLOTS = [
    {"name": "深夜(0-6)", "start": 0, "end": 6, "activity": 0.1},
    {"name": "早晨(6-8)", "start": 6, "end": 8, "activity": 0.3},
    {"name": "上午(8-12)", "start": 8, "end": 12, "activity": 0.5},
    {"name": "午间(12-14)", "start": 12, "end": 14, "activity": 0.6},
    {"name": "下午(14-18)", "start": 14, "end": 18, "activity": 0.5},
    {"name": "傍晚(18-20)", "start": 18, "end": 20, "activity": 0.7},
    {"name": "晚间(20-23)", "start": 20, "end": 23, "activity": 0.9},
    {"name": "深夜(23-24)", "start": 23, "end": 24, "activity": 0.3},
]

# 活跃时段映射
ACTIVE_HOURS_MAP = {
    "早间": [(6, 9)],
    "午间": [(11, 14)],
    "晚间": [(19, 23)],
    "深夜": [(22, 2)],
    "全天": [(6, 23)],
    "上午": [(8, 12)],
    "下午": [(13, 18)],
}


@dataclass
class SimTime:
    """仿真时间"""
    hour: int = 8
    minute: int = 0
    day: int = 1

    @property
    def total_minutes(self) -> int:
        return (self.day - 1) * 1440 + self.hour * 60 + self.minute

    @property
    def time_str(self) -> str:
        return f"Day{self.day} {self.hour:02d}:{self.minute:02d}"

    @property
    def current_slot(self) -> str:
        for slot in TIME_SLOTS:
            if slot["start"] <= self.hour < slot["end"]:
                return slot["name"]
        return "深夜(0-6)"

    @property
    def activity_level(self) -> float:
        for slot in TIME_SLOTS:
            if slot["start"] <= self.hour < slot["end"]:
                return slot["activity"]
        return 0.1


class TimeModel:
    """仿真时间模型"""

    def __init__(self, start_hour: int = 8, time_acceleration: int = 60):
        """
        Args:
            start_hour: 仿真起始小时
            time_acceleration: 时间加速比（1 tick = 多少仿真分钟）
        """
        self.acceleration = time_acceleration
        self.sim_time = SimTime(hour=start_hour)
        self.tick_count = 0
        # Agent活跃时间表 {agent_id: [(start_hour, end_hour), ...]}
        self._agent_schedules: Dict[str, List[tuple]] = {}

    def advance(self) -> SimTime:
        """推进一个tick"""
        self.tick_count += 1
        total = self.sim_time.total_minutes + self.acceleration
        self.sim_time.day = total // 1440 + 1
        remaining = total % 1440
        self.sim_time.hour = remaining // 60
        self.sim_time.minute = remaining % 60
        return self.sim_time

    def is_agent_active(self, agent_id: str, active_hours: str = "晚间") -> bool:
        """判断Agent在当前仿真时间是否活跃"""
        schedule = self._agent_schedules.get(agent_id)
        if schedule is None:
            schedule = ACTIVE_HOURS_MAP.get(active_hours, [(19, 23)])
            self._agent_schedules[agent_id] = schedule

        current_hour = self.sim_time.hour
        for start, end in schedule:
            if start <= end:
                if start <= current_hour < end:
                    return True
            else:  # 跨午夜
                if current_hour >= start or current_hour < end:
                    return True
        return False

    def set_agent_schedule(self, agent_id: str, active_hours: str):
        """设置Agent活跃时间表"""
        schedule = ACTIVE_HOURS_MAP.get(active_hours, [(19, 23)])
        self._agent_schedules[agent_id] = schedule

    @property
    def current_activity(self) -> float:
        """当前时段全局活跃度"""
        return self.sim_time.activity_level

    @property
    def time_str(self) -> str:
        return self.sim_time.time_str

    @property
    def current_slot(self) -> str:
        return self.sim_time.current_slot
