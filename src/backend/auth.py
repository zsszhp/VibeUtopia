"""API 鉴权（最小可用）

- 配置 settings.API_KEY 后，/api/** 与 /ws/** 必须携带 X-API-Key 或 Authorization: Bearer <key>
- 未配置时本地开发放行，由响应头标注「生产必须配置」
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import HTTPException, Request, WebSocket

from backend.config import settings


def is_auth_enabled() -> bool:
    """是否启用 API Key 鉴权（未配置则本地开发放行）"""
    return bool((getattr(settings, "API_KEY", "") or "").strip())


def extract_api_key(request: Request) -> Optional[str]:
    """从请求头提取 API Key：X-API-Key 优先，其次 Authorization: Bearer"""
    key = request.headers.get("X-API-Key")
    if key and key.strip():
        return key.strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def verify_api_key(provided: Optional[str]) -> bool:
    """常量时间比较；未配置预期 Key 时视为放行"""
    expected = (getattr(settings, "API_KEY", "") or "").strip()
    if not expected:
        return True
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


async def require_api_key(request: Request) -> None:
    """FastAPI 依赖：校验 API Key

    未配置 API_KEY 时放行（本地开发体验不变）；
    已配置时拒绝缺失/错误的 Key（401）。
    """
    if not is_auth_enabled():
        return
    if not verify_api_key(extract_api_key(request)):
        raise HTTPException(
            status_code=401,
            detail="缺少或无效的 API Key，请携带 X-API-Key 或 Authorization: Bearer <key>",
        )


async def check_ws_api_key(websocket: WebSocket) -> bool:
    """WebSocket 握手前校验 API Key；未配置时放行"""
    if not is_auth_enabled():
        return True
    key = websocket.headers.get("X-API-Key")
    if key and key.strip():
        return verify_api_key(key.strip())
    auth = websocket.headers.get("Authorization", "") or ""
    if auth.lower().startswith("bearer "):
        return verify_api_key(auth[7:].strip())
    return False
