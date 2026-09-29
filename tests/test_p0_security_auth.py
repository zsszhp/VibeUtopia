"""P0 遗留项验证：API 鉴权 / 路径安全 / fail-open / 红线 76+

验证项：
1. 未配置 API_KEY：请求无头放行（本地开发体验不变），响应头标注生产必须配置
2. 已配置 API_KEY：无头请求 401；X-API-Key / Authorization: Bearer 正确放行；错误 Key 401
3. 危险端点（upload / set-model-override / resume delete / blogger index delete）受同一套鉴权保护
4. story user_id 路径遍历被拒绝
5. symbol_detector / code_tracer 解析失败 → unknown + needs_review（不得判 safe）
6. 红线维度高档 → overall ≥ 76

可直接 `python tests/test_p0_security_auth.py` 运行，也可被 pytest 收集。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TEST_KEY = "test-secret-key-p0-xyz"


@contextmanager
def _api_key(value: str):
    """临时设置 settings.API_KEY（不依赖 pytest monkeypatch，可独立运行）"""
    from backend.config import settings

    old = getattr(settings, "API_KEY", "")
    settings.API_KEY = value
    try:
        yield settings
    finally:
        settings.API_KEY = old


# ─── 鉴权：无 key 放行 ─────────────────────────────────────────────

def test_auth_disabled_allows_bare_requests():
    from backend import auth as auth_mod

    with _api_key(""):
        assert auth_mod.is_auth_enabled() is False

        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        r = client.get("/api/v1/health")
        assert r.status_code == 200, r.text
        assert r.headers.get("X-API-Auth") == "disabled"
        assert "Production" in r.headers.get("X-API-Auth-Warning", "")

        # 危险端点在未配置 Key 时同样放行（进入业务校验而非 401）
        r_upload = client.post("/api/v1/upload")
        assert r_upload.status_code != 401
        r_override = client.post("/api/v3/set-model-override")
        assert r_override.status_code != 401
    print("  ✓ 无 API_KEY：无头请求放行，响应头标注生产必须配置")


# ─── 鉴权：有 key 拒绝无头 / 放行正确头 ─────────────────────────────

def test_auth_enabled_rejects_bare_and_accepts_key():
    from backend import auth as auth_mod

    with _api_key(TEST_KEY):
        assert auth_mod.is_auth_enabled() is True

        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)

        # 无头请求 → 401
        for path in ("/api/v1/health", "/api/v1/models", "/api/v1/history"):
            r = client.get(path)
            assert r.status_code == 401, f"{path} 无头应 401，实际 {r.status_code}"
        r = client.post("/api/v1/upload")
        assert r.status_code == 401
        r = client.post("/api/v3/set-model-override", data={"provider": "x", "model": "y"})
        assert r.status_code == 401
        r = client.delete("/api/v1/resume/nonexistent")
        assert r.status_code == 401
        r = client.delete("/api/v1/blogger/nonexistent/index")
        assert r.status_code == 401
        print("  ✓ 有 API_KEY：无头请求 401（含 upload / set-model-override / resume delete / blogger delete）")

        # X-API-Key 正确 → 放行
        r = client.get("/api/v1/health", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        assert r.headers.get("X-API-Auth") == "api-key"

        # Authorization: Bearer 正确 → 放行
        r = client.get("/api/v1/health", headers={"Authorization": f"Bearer {TEST_KEY}"})
        assert r.status_code == 200

        # 错误 Key → 401
        r = client.get("/api/v1/health", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401
        r = client.get("/api/v1/health", headers={"Authorization": "Bearer wrong-key"})
        assert r.status_code == 401
        r = client.get("/api/v1/health", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401
        print("  ✓ X-API-Key / Bearer 正确放行，错误 Key 401")

    # 头部校验单元：extract_api_key / verify_api_key
    class _Req:
        def __init__(self, headers):
            self.headers = headers

    assert auth_mod.extract_api_key(_Req({"X-API-Key": " abc "})) == "abc"
    assert auth_mod.extract_api_key(_Req({"Authorization": "Bearer tok"})) == "tok"
    assert auth_mod.extract_api_key(_Req({})) is None

    with _api_key(TEST_KEY):
        assert auth_mod.verify_api_key(TEST_KEY) is True
        assert auth_mod.verify_api_key("nope") is False
        assert auth_mod.verify_api_key(None) is False
    with _api_key(""):
        assert auth_mod.verify_api_key(None) is True, "未配置 Key 时应放行"
    print("  ✓ 提取与比较逻辑正确")


def test_ws_auth_check():
    from backend import auth as auth_mod

    class _WS:
        def __init__(self, headers):
            self.headers = headers

    with _api_key(TEST_KEY):
        assert asyncio.run(auth_mod.check_ws_api_key(_WS({"X-API-Key": TEST_KEY}))) is True
        assert asyncio.run(auth_mod.check_ws_api_key(_WS({"Authorization": f"Bearer {TEST_KEY}"}))) is True
        assert asyncio.run(auth_mod.check_ws_api_key(_WS({}))) is False
        assert asyncio.run(auth_mod.check_ws_api_key(_WS({"X-API-Key": "bad"}))) is False

    with _api_key(""):
        assert asyncio.run(auth_mod.check_ws_api_key(_WS({}))) is True
    print("  ✓ WebSocket 鉴权：有 key 拒绝无头，无 key 放行")


# ─── 路径安全：story user_id ────────────────────────────────────────

def test_story_user_id_path_traversal_rejected():
    from fastapi import HTTPException
    from backend.routes_story import _safe_user_id, _user_dir

    assert _safe_user_id("user_001") == "user_001"
    assert _safe_user_id("用户abc-1") == "用户abc-1"

    for bad in (
        "../etc/passwd",
        "..\\windows\\system32",
        "a/b",
        "a\\b",
        "a\x00b",
        "",
        "   ",
        "." * 70,
        "a" * 65,
    ):
        with pytest.raises(HTTPException) as ei:
            _safe_user_id(bad)
        assert ei.value.status_code == 400, f"{bad!r} 应 400，实际 {ei.value.status_code}"

    # _user_dir 解析后仍位于存储根内
    d = _user_dir("user_001")
    assert d.name == "user_001"
    with pytest.raises(HTTPException):
        _user_dir("../outside")
    print("  ✓ story user_id 路径遍历被拒绝，目录解析限定在存储根内")


def test_video_path_validation_unchanged():
    import os

    from backend.routes import _validate_video_path, _sanitize_filename, _get_upload_dir

    # 目录外路径被拒
    assert _validate_video_path("C:\\Windows\\System32\\config\\SAM") is None
    assert _validate_video_path("../../etc/passwd") is None
    assert _validate_video_path("/etc/passwd") is None
    assert _validate_video_path("") is None
    assert _validate_video_path("a\x00b") is None

    # 上传目录内真实文件放行
    upload_dir = _get_upload_dir()
    probe = os.path.join(upload_dir, "p0_probe_video.mp4")
    with open(probe, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42")
    try:
        assert _validate_video_path(probe) == os.path.realpath(probe)
    finally:
        os.unlink(probe)

    # 文件名消毒：去路径分隔符
    assert "/" not in _sanitize_filename("../../evil.mp4")
    assert "\\" not in _sanitize_filename("..\\evil.mp4")
    assert _sanitize_filename("normal_name.mp4").endswith(".mp4")
    print("  ✓ video_files 仍被 _validate_video_path 约束；文件名消毒有效")


# ─── fail-open：symbol_detector / code_tracer ───────────────────────

def test_symbol_detector_fail_open():
    from backend.services.fine_grained.symbol_detector import (
        SensitiveSymbolDetector,
        SymbolRiskResult,
    )

    detector = SensitiveSymbolDetector()

    # 帧不存在 → unknown + needs_review，不得 safe
    r = asyncio.run(detector.detect_frame("no_such_frame.jpg", 1.0))
    assert isinstance(r, SymbolRiskResult)
    assert r.risk_level == "unknown", f"帧缺失不得判 safe: {r.risk_level}"
    assert r.needs_review is True

    # VLM 失败（无后端）→ unknown + needs_review
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"0" * 200)
        tmp = f.name
    try:
        r2 = asyncio.run(detector.detect_frame(tmp, 0.0))
        assert r2.risk_level == "unknown", f"VLM 失败不得判 safe: {r2.risk_level}"
        assert r2.needs_review is True
    finally:
        os.unlink(tmp)

    # 聚合：失败帧 → VideoSymbolResult.needs_review=True，不计入 has_symbol_risk
    agg = asyncio.run(detector.detect_video_frames(["no_such_1.jpg", "no_such_2.jpg"], [0.0, 1.0]))
    assert agg.needs_review is True
    assert agg.has_symbol_risk is False, "未知结果不得直接判为符号风险"
    print("  ✓ symbol_detector 解析/VLM 失败 → unknown + needs_review，聚合不误判安全")


def test_code_tracer_fail_open():
    from backend.services.fine_grained.code_tracer import CodeOriginTracer, CodeTraceResult

    tracer = CodeOriginTracer()

    r = asyncio.run(tracer.trace_frame("no_such_frame.jpg", 1.0))
    assert isinstance(r, CodeTraceResult)
    assert r.risk_level == "unknown", f"帧缺失不得判 safe: {r.risk_level}"
    assert r.needs_review is True

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff" + b"0" * 200)
        tmp = f.name
    try:
        r2 = asyncio.run(tracer.trace_frame(tmp, 0.0))
        assert r2.risk_level == "unknown", f"VLM 失败不得判 safe: {r2.risk_level}"
        assert r2.needs_review is True
    finally:
        os.unlink(tmp)

    agg = asyncio.run(tracer.trace_video_frames(["no_such_1.jpg", "no_such_2.jpg"], [0.0, 1.0]))
    assert agg.needs_review is True
    assert agg.has_opensource_risk is False
    print("  ✓ code_tracer 解析/VLM 失败 → unknown + needs_review，聚合不误判安全")


# ─── 红线 76+ ──────────────────────────────────────────────────────

def test_redline_dimension_forces_overall_76():
    from backend.services.analyzer import calculate_overall_score

    # 单个红线维度高档（红线 5 维之一）→ overall ≥ 76
    for name in ("政治敏感", "法律合规", "民族宗教", "事实错误", "平台禁区"):
        dims = [
            {"name": name, "score": 30, "severity": "red", "dimension_weight": 1.3},
            {"name": "道德伦理", "score": 5, "severity": "green", "dimension_weight": 1.0},
        ]
        overall, _, _ = calculate_overall_score(dims)
        assert overall >= 76, f"红线维度「{name}」高档应强制 overall≥76，实际 {overall}"
    print("  ✓ 任一红线维度高档 → overall≥76（5 个红线维度逐一验证）")

    # 红线维度 + 旧词表 high 也生效
    dims_legacy = [{"name": "政治敏感", "score": 20, "severity": "high", "dimension_weight": 1.5}]
    overall2, _, _ = calculate_overall_score(dims_legacy)
    assert overall2 >= 76, f"旧词表 high 的红线维度也应 ≥76，实际 {overall2}"

    # severity 错标但 score≥76 的红线维度 → is_high_severity 兜底 → ≥76
    dims_mislabeled = [{"name": "法律合规", "score": 80, "severity": "green", "dimension_weight": 1.5}]
    overall3, _, _ = calculate_overall_score(dims_mislabeled)
    assert overall3 >= 76
    print("  ✓ 旧词表 / severity 错标兜底均生效")

    # 非红线维度高档只触发保底 50（不误抬到 76）
    dims_non_redline = [
        {"name": "性别议题", "score": 10, "severity": "red", "dimension_weight": 1.0},
    ]
    overall4, _, _ = calculate_overall_score(dims_non_redline)
    assert 50 <= overall4 < 76, f"非红线维度高档应只保底 50，实际 {overall4}"
    print(f"  ✓ 非红线维度高档只保底 50（overall={overall4}）")

    # 双红线维度高档：保底 76 + 交叉叠加
    dims_two = [
        {"name": "政治敏感", "score": 30, "severity": "red", "dimension_weight": 1.5},
        {"name": "民族宗教", "score": 30, "severity": "red", "dimension_weight": 1.3},
    ]
    overall5, _, cross5 = calculate_overall_score(dims_two)
    assert overall5 >= 76
    assert len(cross5) >= 1
    print(f"  ✓ 双红线维度：overall={overall5}（≥76），cross_effects={len(cross5)}")

    # 全绿不触发
    dims_green = [{"name": "道德伦理", "score": 5, "severity": "green", "dimension_weight": 1.0}]
    overall6, _, _ = calculate_overall_score(dims_green)
    assert overall6 < 50
    print("  ✓ 全绿不触发红线规则")


def main():
    import traceback

    tests = [
        ("鉴权-无key放行", test_auth_disabled_allows_bare_requests),
        ("鉴权-有key拒绝/正确头放行", test_auth_enabled_rejects_bare_and_accepts_key),
        ("鉴权-WebSocket", test_ws_auth_check),
        ("路径-story user_id", test_story_user_id_path_traversal_rejected),
        ("路径-video_path", test_video_path_validation_unchanged),
        ("fail-open-symbol_detector", test_symbol_detector_fail_open),
        ("fail-open-code_tracer", test_code_tracer_fail_open),
        ("红线76+", test_redline_dimension_forces_overall_76),
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
