"""内存消息总线 — asyncio.Queue 5通道实现"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 5种通道
CHANNEL_PLATFORM_FEED = "platform_feed"       # 平台内容feed
CHANNEL_AGENT_ACTIONS = "agent_actions"        # Agent行为
CHANNEL_SYSTEM_EVENTS = "system_events"        # 系统事件
CHANNEL_MONITORING = "monitoring"              # 监控数据
CHANNEL_INTERVENTION = "intervention"          # 干预指令

ALL_CHANNELS = [
    CHANNEL_PLATFORM_FEED,
    CHANNEL_AGENT_ACTIONS,
    CHANNEL_SYSTEM_EVENTS,
    CHANNEL_MONITORING,
    CHANNEL_INTERVENTION,
]


class MessageBus:
    """内存消息总线"""

    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._history: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history = 1000

    def initialize(self):
        """初始化所有通道"""
        for channel in ALL_CHANNELS:
            self._queues[channel] = asyncio.Queue(maxsize=self.max_queue_size)

    async def publish(self, channel: str, message: Dict[str, Any]):
        """发布消息到通道"""
        if channel not in self._queues:
            logger.warning(f"未知通道: {channel}")
            return

        try:
            self._queues[channel].put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(f"通道 {channel} 已满，丢弃最早消息")
            try:
                self._queues[channel].get_nowait()
                self._queues[channel].put_nowait(message)
            except Exception:
                pass

        # 记录历史
        self._history[channel].append(message)
        if len(self._history[channel]) > self._max_history:
            self._history[channel] = self._history[channel][-self._max_history:]

        # 通知订阅者
        for sub_queue in self._subscribers[channel]:
            try:
                sub_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    async def consume(self, channel: str, timeout: float = 0.1) -> Optional[Dict]:
        """从通道消费一条消息"""
        if channel not in self._queues:
            return None
        try:
            return await asyncio.wait_for(self._queues[channel].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def subscribe(self, channel: str) -> asyncio.Queue:
        """订阅通道，返回专用队列"""
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers[channel].append(queue)
        return queue

    def get_history(self, channel: str, limit: int = 50) -> List[Dict]:
        """获取通道历史消息"""
        return self._history[channel][-limit:]

    def clear(self):
        """清空所有通道"""
        for channel in ALL_CHANNELS:
            if channel in self._queues:
                while not self._queues[channel].empty():
                    try:
                        self._queues[channel].get_nowait()
                    except Exception:
                        break
            self._history[channel].clear()
