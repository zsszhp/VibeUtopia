"""API 限流验证：滑动窗口计数 / 429 + detail / /health 豁免 / 依赖注入

验证项：
1. SlidingWindowRateLimiter：窗口内放行、超限拒绝、窗口滑动后恢复
2. settings.RATE_LIMIT_PER_MIN 默认 60，get_limiter 按配置创建
3. set_limiter 依赖注入可替换共享实例
4. /api/** 超限返回 429 且响应体 {"detail": ...}；未超限正常
5. /health 探活端点不受限流（配额耗尽后仍可访问，不返回 429）
6. RATE_LIMIT_PER_MIN <= 0 表示不限流

可直接 `python tests/test_rate_limit.py` 运行，也可被 pytest 收集。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _make_limiter(max_requests: int, window_seconds: float = 60.0):
    from backend.rate_limit import SlidingWindowRateLimiter

    return SlidingWindowRateLimiter(max_requests=max_requests, window_seconds=window_seconds)


# ─── 滑动窗口单元行为 ─────────────────────────────────────────────

def test_sliding_window_allows_then_denies():
    limiter = _make_limiter(max_requests=3)

    for i in range(3):
        allowed, remaining = limiter.check("ip-a")
        assert allowed, f"第{i + 1}次应放行"
        assert remaining == 2 - i

    allowed, remaining = limiter.check("ip-a")
    assert not allowed, "超出配额应拒绝"
    assert remaining == 0

    # 不同 key 独立计数
    allowed_b, _ = limiter.check("ip-b")
    assert allowed_b, "不同客户端计数应独立"
    print("  ✓ 窗口内 3 次放行、第 4 次拒绝；key 间独立计数")


def test_sliding_window_slides_and_recovers():
    limiter = _make_limiter(max_requests=2, window_seconds=0.2)

    assert limiter.check("ip-c")[0] is True
    assert limiter.check("ip-c")[0] is True
    assert limiter.check("ip-c")[0] is False, "窗口内超限应拒绝"

    time.sleep(0.25)  # 窗口滑出
    allowed, remaining = limiter.check("ip-c")
    assert allowed, "窗口滑动后应恢复放行"
    assert remaining == 1
    print("  ✓ 窗口滑动后计数清零、恢复放行")


def test_limiter_reset_and_remaining():
    limiter = _make_limiter(max_requests=5)
    limiter.check("ip-d")
    limiter.check("ip-d")
    assert limiter.remaining("ip-d") == 3

    limiter.reset()
    assert limiter.remaining("ip-d") == 5
    print("  ✓ remaining 查询与 reset 清空计数")


# ─── 配置与依赖注入 ───────────────────────────────────────────────

def test_settings_default_and_get_limiter():
    from backend.config import settings
    from backend import rate_limit as rl

    assert settings.RATE_LIMIT_PER_MIN == 60, f"默认配额应为 60，实际 {settings.RATE_LIMIT_PER_MIN}"

    rl.reset_limiter()
    try:
        limiter = rl.get_limiter()
        assert limiter.max_requests == 60
        # 同一进程共享单例
        assert rl.get_limiter() is limiter
    finally:
        rl.reset_limiter()
    print("  ✓ settings.RATE_LIMIT_PER_MIN 默认 60，get_limiter 共享单例")


def test_set_limiter_dependency_injection():
    from backend import rate_limit as rl

    injected = _make_limiter(max_requests=7)
    rl.set_limiter(injected)
    try:
        assert rl.get_limiter() is injected, "set_limiter 注入的实例应被使用"
    finally:
        rl.reset_limiter()
    print("  ✓ set_limiter 依赖注入生效")


# ─── HTTP 层：429 + detail / /health 豁免 ─────────────────────────

def test_api_rate_limit_returns_429_with_detail():
    from backend import rate_limit as rl
    from fastapi.testclient import TestClient
    from backend.main import app

    rl.set_limiter(_make_limiter(max_requests=3))
    client = TestClient(app)

    # 配额内正常（/api/v1/health 受鉴权但未配置 Key 时放行）
    for i in range(3):
        r = client.get("/api/v1/health")
        assert r.status_code == 200, f"第{i + 1}次应 200，实际 {r.status_code}: {r.text}"

    # 超限 → 429 + detail
    r4 = client.get("/api/v1/health")
    assert r4.status_code == 429, f"超限应 429，实际 {r4.status_code}: {r4.text}"
    body = r4.json()
    assert "detail" in body, f"429 响应必须带 detail: {body}"
    assert isinstance(body["detail"], str) and body["detail"], "detail 应为非空字符串"
    assert "429" != body["detail"], "detail 需为可读消息"
    print(f"  ✓ /api/** 超限 429，detail={body['detail'][:40]}...")

    # 其他 /api/** 同样受限
    r5 = client.get("/api/v1/models")
    assert r5.status_code == 429, f"其他 /api/** 也应 429，实际 {r5.status_code}"
    print("  ✓ 限流覆盖全部 /api/**（含 /api/v1/models）")


def test_health_exempt_from_rate_limit():
    from backend import rate_limit as rl
    from fastapi.testclient import TestClient
    from backend.main import app

    rl.set_limiter(_make_limiter(max_requests=1))
    client = TestClient(app)

    r = client.get("/api/v1/health")
    assert r.status_code == 200
    r2 = client.get("/api/v1/health")
    assert r2.status_code == 429, "API 配额应已耗尽"

    # 探活端点不受限流影响（/ready 可能因数据库未就绪返回 503，但不得 429）
    for path in ("/health", "/healthz", "/ready"):
        rh = client.get(path)
        assert rh.status_code != 429, f"{path} 应豁免限流，实际 {rh.status_code}"
    rh_ok = client.get("/health")
    assert rh_ok.status_code == 200
    print("  ✓ /health、/healthz、/ready 豁免限流（配额耗尽后不返回 429）")


def test_non_positive_limit_disables_rate_limit():
    from backend import rate_limit as rl
    from fastapi.testclient import TestClient
    from backend.main import app

    rl.set_limiter(_make_limiter(max_requests=0))
    client = TestClient(app)

    for _ in range(5):
        r = client.get("/api/v1/health")
        assert r.status_code == 200, "RATE_LIMIT_PER_MIN<=0 应不限流"
    print("  ✓ 配额 <=0 时不限流")


def test_client_key_prefers_forwarded_for():
    from backend.rate_limit import client_key

    class _Req:
        def __init__(self, headers, client=None):
            self.headers = headers
            self.client = client

    class _Client:
        host = "10.0.0.1"

    assert client_key(_Req({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}, _Client())) == "203.0.113.7"
    assert client_key(_Req({}, _Client())) == "10.0.0.1"
    assert client_key(_Req({}, None)) == "unknown"
    print("  ✓ client_key：X-Forwarded-For 优先，其次直连 IP")


def main():
    import traceback

    tests = [
        ("滑动窗口-放行与拒绝", test_sliding_window_allows_then_denies),
        ("滑动窗口-窗口滑动恢复", test_sliding_window_slides_and_recovers),
        ("滑动窗口-remaining/reset", test_limiter_reset_and_remaining),
        ("配置-默认60与单例", test_settings_default_and_get_limiter),
        ("依赖注入-set_limiter", test_set_limiter_dependency_injection),
        ("HTTP-429与detail", test_api_rate_limit_returns_429_with_detail),
        ("HTTP-health豁免", test_health_exempt_from_rate_limit),
        ("HTTP-配额<=0不限流", test_non_positive_limit_disables_rate_limit),
        ("client_key", test_client_key_prefers_forwarded_for),
    ]
    failed = []
    for name, fn in tests:
        print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
        try:
            fn()
            print(f"[PASS] {name}")
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed.append(name)
        except Exception:
            traceback.print_exc()
            failed.append(name)

    print(f"\n{'=' * 60}")
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} -> {failed}")
        sys.exit(1)
    print(f"ALL PASSED: {len(tests)}/{len(tests)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
