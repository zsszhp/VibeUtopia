"""API 鉴权（最小可用 + JWT 多租户雏形）

- 配置 settings.API_KEY 后，/api/** 与 /ws/** 必须携带 X-API-Key 或 Authorization: Bearer <key>
- 配置 settings.JWT_SECRET 后启用 JWT：POST /api/v1/auth/token 用用户名+密码换 token；
  Authorization: Bearer <jwt> 优先按 JWT 校验，通过后视为已认证（可不带 API Key）
- 未配置时本地开发放行，由响应头标注「生产必须配置」
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field

from backend.config import settings

try:  # PyJWT 未安装时降级为纯 API Key 模式（JWT_SECRET 配置了也会被忽略）
    import jwt as pyjwt
except ImportError:  # pragma: no cover
    pyjwt = None  # type: ignore[assignment]


@dataclass(frozen=True)
class AuthIdentity:
    """请求身份：JWT 用户优先，其次 API Key，未鉴权时匿名"""

    subject: Optional[str] = None
    auth_type: str = "anonymous"  # jwt / api-key / anonymous

    @property
    def owner_id(self) -> Optional[str]:
        """任务归属标识（JWT sub）；匿名/API Key 时为 None"""
        return self.subject


def is_jwt_enabled() -> bool:
    """是否启用 JWT（需同时具备 PyJWT 与 JWT_SECRET）"""
    return pyjwt is not None and bool((getattr(settings, "JWT_SECRET", "") or "").strip())


def is_auth_enabled() -> bool:
    """是否启用 API Key 鉴权（未配置则本地开发放行）"""
    return bool((getattr(settings, "API_KEY", "") or "").strip())


def _extract_bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def extract_api_key(request: Request) -> Optional[str]:
    """从请求头提取 API Key：X-API-Key 优先，其次 Authorization: Bearer"""
    key = request.headers.get("X-API-Key")
    if key and key.strip():
        return key.strip()
    return _extract_bearer(request)


def verify_api_key(provided: Optional[str]) -> bool:
    """常量时间比较；未配置预期 Key 时视为放行"""
    expected = (getattr(settings, "API_KEY", "") or "").strip()
    if not expected:
        return True
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


def create_access_token(subject: str) -> tuple[str, int]:
    """签发 HS256 JWT，返回 (token, expires_in_seconds)"""
    if not is_jwt_enabled():
        raise RuntimeError("JWT 未启用：请先配置 JWT_SECRET")
    expires_minutes = max(1, int(getattr(settings, "JWT_EXPIRE_MINUTES", 720) or 720))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "iss": "vibeutopia",
        "typ": "access",
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token, expires_minutes * 60


def decode_access_token(token: Optional[str]) -> Optional[dict[str, Any]]:
    """校验并解码 JWT；无效/过期/未启用一律返回 None（由调用方决定是否降级）"""
    if not token or not is_jwt_enabled():
        return None
    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def resolve_identity(request: Request) -> AuthIdentity:
    """解析请求身份：Authorization Bearer 中的 JWT 优先，其次 API Key"""
    bearer = _extract_bearer(request)

    if bearer and is_jwt_enabled():
        payload = decode_access_token(bearer)
        if payload is not None:
            sub = str(payload.get("sub") or "").strip()
            return AuthIdentity(subject=sub or None, auth_type="jwt")

    provided = extract_api_key(request)
    if is_auth_enabled() and provided and verify_api_key(provided):
        return AuthIdentity(subject=None, auth_type="api-key")
    return AuthIdentity(subject=None, auth_type="anonymous")


async def get_identity(request: Request) -> AuthIdentity:
    """FastAPI 依赖：取当前请求身份（不强制鉴权，由业务端点自行决策）"""
    return resolve_identity(request)


async def require_api_key(request: Request) -> None:
    """FastAPI 依赖：校验鉴权

    JWT Bearer 有效 → 直接放行（JWT 优先）；
    未配置 API_KEY 时放行（本地开发体验不变）；
    已配置时拒绝缺失/错误的 Key（401）。
    """
    identity = resolve_identity(request)
    if identity.auth_type == "jwt":
        return
    if not is_auth_enabled():
        return
    if identity.auth_type == "api-key":
        return
    raise HTTPException(
        status_code=401,
        detail="缺少或无效的凭证，请携带 X-API-Key、API Key Bearer 或 JWT Bearer",
    )


async def check_ws_api_key(websocket: WebSocket) -> bool:
    """WebSocket 握手前校验（JWT Bearer 优先，其次 API Key）；未配置时放行"""
    auth = websocket.headers.get("Authorization", "") or ""
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None

    if bearer and is_jwt_enabled() and decode_access_token(bearer) is not None:
        return True

    if not is_auth_enabled():
        return True

    key = websocket.headers.get("X-API-Key")
    if key and key.strip():
        return verify_api_key(key.strip())
    if bearer:
        return verify_api_key(bearer)
    return False


# ─── JWT 签发端点（登录换 token，不校验 API Key，否则无法登录） ─────────

class TokenRequest(BaseModel):
    """用户名+密码换 token（本地单用户占位）"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


auth_router = APIRouter(tags=["auth"])


def _constant_time_eq(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 密码哈希（不存明文）"""
    import hashlib
    salt = settings.JWT_SECRET[:16] if settings.JWT_SECRET else "vibe-local-salt"
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return dk.hex()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return secrets.compare_digest(hash_password(password), password_hash or "")
    except Exception:
        return False


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


@auth_router.post("/auth/register", response_model=TokenResponse)
async def register_user(req: RegisterRequest):
    """注册本地用户并直接签发 JWT（R5 多租户账号）"""
    if not is_jwt_enabled():
        raise HTTPException(status_code=503, detail="JWT 未启用：请配置环境变量 JWT_SECRET")
    username = req.username.strip()
    if not username.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="用户名仅允许字母数字下划线")

    from backend.database import SessionLocal
    from backend.models import User

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=409, detail="用户名已存在")
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(req.password),
            role="member",
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    token, expires_in = create_access_token(username)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        username=username,
    )


@auth_router.post("/auth/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest):
    """用用户名+密码换取 JWT

    优先校验 users 表；无匹配时回退 admin/settings.ADMIN_PASSWORD。
    - JWT_SECRET 未配置 → 503（未启用）
    - 凭证错误 → 401（不区分用户/密码错误，避免枚举）
    """
    if not is_jwt_enabled():
        raise HTTPException(status_code=503, detail="JWT 未启用：请配置环境变量 JWT_SECRET")
    username = req.username.strip()

    # 1) users 表
    try:
        from backend.database import SessionLocal
        from backend.models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username, User.is_active == True).first()  # noqa: E712
            if user and verify_password(req.password, user.password_hash):
                token, expires_in = create_access_token(user.username)
                return TokenResponse(
                    access_token=token,
                    token_type="bearer",
                    expires_in=expires_in,
                    username=user.username,
                )
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception:
        pass  # 表不存在时回退 admin

    # 2) 本地 admin 占位
    expected_user = (getattr(settings, "ADMIN_USERNAME", "") or "admin").strip() or "admin"
    expected_pass = getattr(settings, "ADMIN_PASSWORD", "") or ""
    if not expected_pass:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD 未配置且用户不存在，禁止空口令签发令牌")

    user_ok = _constant_time_eq(username, expected_user)
    pass_ok = _constant_time_eq(req.password, expected_pass)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token, expires_in = create_access_token(expected_user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        username=expected_user,
    )
