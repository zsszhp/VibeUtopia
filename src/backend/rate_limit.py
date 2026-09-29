"""API 限流（最小实现）

- 滑动窗口计数，单进程内存存储（多进程部署需换共享存储，本期不做）
- 配额：settings.RATE_LIMIT_PER_MIN（默认 60 次/分钟），按客户端 IP 计数
- 依赖注入：限流器实例可通过 set_limiter 替换（测试 / 部署定制）
- 覆盖范围：全部 /api/**（由 main._API_DEPS 挂载）；/health 等探活端点不限流
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from backend.config import settings


class SlidingWindowRateLimiter:
    """滑动窗口限流器：窗口内超过 max_requests 则拒绝，线程安全"""

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """记一次请求并判断是否放行。

        Returns:
            (是否放行, 剩余可用次数)
        """
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self.max_requests:
                return False, 0
            window.append(now)
            return True, self.max_requests - len(window)

    def remaining(self, key: str) -> int:
        """查询剩余可用次数（不计数）"""
        now = time.monotonic()
        with self._lock:
            window = self._hits.get(key)
            if not window:
                return self.max_requests
            cutoff = now - self.window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            return max(self.max_requests - len(window), 0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# 进程内共享实例；测试/部署通过 set_limiter 注入替换
_limiter: SlidingWindowRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_limiter() -> SlidingWindowRateLimiter:
    """取共享限流器；首次创建时读取 settings.RATE_LIMIT_PER_MIN"""
    global _limiter
    with _limiter_lock:
        if _limiter is None:
            _limiter = SlidingWindowRateLimiter(
                max_requests=int(settings.RATE_LIMIT_PER_MIN),
                window_seconds=60.0,
            )
        return _limiter


def set_limiter(limiter: SlidingWindowRateLimiter | None) -> None:
    """依赖注入：替换共享限流器实例（None 表示下次 get_limiter 重建）"""
    global _limiter
    with _limiter_lock:
        _limiter = limiter


def reset_limiter() -> None:
    """清空计数并释放实例（下次按 settings 重建）"""
    set_limiter(None)


def client_key(request: Request) -> str:
    """客户端标识：优先反代来源 IP，否则直连 IP"""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def rate_limit(request: Request) -> None:
    """FastAPI 依赖：超限返回 429 + detail

    RATE_LIMIT_PER_MIN <= 0 表示不限流（测试/特殊场景可关闭）。
    """
    limiter = get_limiter()
    if limiter.max_requests <= 0:
        return
    allowed, _remaining = limiter.check(client_key(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"请求过于频繁：每分钟最多 {limiter.max_requests} 次"
                f"（限流窗口 {int(limiter.window_seconds)} 秒），请稍后重试"
            ),
        )
