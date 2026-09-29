"""R5 最小闭环测试：JWT 多租户雏形 / 审核工作流 / 报告导出

验证项：
1. JWT 未配置（JWT_SECRET 为空）：/auth/token 返回 503，原有 API_KEY 与无鉴权行为不变
2. JWT 已配置：用户名+密码换 token 成功；错误凭证 401；空口令 503（禁止空口令放行）
3. JWT 优先：已配置 API_KEY 时，Bearer JWT 放行（可不带 API Key）；API Key 路径不回归
4. owner_id 归属：带 JWT 提交审核任务时写入 owner_id；无 token 时 owner_id 为空（兼容）
5. 工作流：draft → pending_review → approved 流转留痕；非法状态/非法流转 400
6. 归属校验雏形：他人 JWT 操作带归属任务 403；无 token 放行（兼容）
7. 导出：format=md 含 Verdict/分数/Top 风险/改写/免责；format=json 结构完整
8. 无密钥入库：工作流历史与导出内容不含 JWT_SECRET / ADMIN_PASSWORD / API_KEY

可直接 `python tests/test_r5_tenant_workflow.py` 运行，也可被 pytest 收集。
"""

from __future__ import annotations

import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

JWT_SECRET = "test-jwt-secret-r5-do-not-commit"
ADMIN_USER = "admin"
ADMIN_PASS = "test-admin-pass-r5-xyz"
API_KEY_VAL = "test-api-key-r5-xyz"


@contextmanager
def _settings(**overrides):
    """临时覆盖 settings 字段，结束后恢复（不依赖 monkeypatch，可独立运行）"""
    from backend.config import settings

    old: dict = {}
    for k, v in overrides.items():
        old[k] = getattr(settings, k, None)
        setattr(settings, k, v)
    try:
        yield settings
    finally:
        for k, v in old.items():
            setattr(settings, k, v)


def _client():
    from fastapi.testclient import TestClient
    from backend.main import app

    return TestClient(app)


def _make_task(db, **kwargs):
    """直接落库构造审核任务（避开 LLM 后台分析）"""
    from backend.models import Task

    task_id = kwargs.pop("id", None) or str(uuid.uuid4())
    task = Task(
        id=task_id,
        text=kwargs.pop("text", "这是用于 R5 测试的样例内容，长度超过十个字符。"),
        status=kwargs.pop("status", "completed"),
        mode="text",
        depth="standard",
        owner_id=kwargs.pop("owner_id", None),
        workflow_status=kwargs.pop("workflow_status", "draft"),
    )
    db.add(task)
    db.commit()
    return task


def _make_summary(db, task_id: str, **kwargs):
    """落库构造分析摘要（供导出使用）"""
    from backend.models import AnalysisSummary, RiskItem

    dimensions = kwargs.pop("dimensions", {
        "政治安全": {"score": 82, "severity": "red", "evidence": "涉及敏感政治人物评价", "suggestion": "删除相关内容"},
        "性别对立": {"score": 40, "severity": "yellow", "evidence": "存在群体标签化表述", "suggestion": "中性化改写"},
    })
    rewrites = kwargs.pop("rewrites", [
        {
            "original": "这个政策真是一刀切",
            "dimension": "政治安全",
            "rewrites": [{"text": "这项政策的适用范围或许可以更精细化", "rewrite_note": "去除情绪化措辞"}],
            "is_redline": False,
        },
        {
            "original": "某某群体都不讲理",
            "dimension": "性别对立",
            "is_redline": True,
            "redline_note": "该内容触及红线维度，建议不予发布",
        },
    ])
    summary = AnalysisSummary(
        task_id=task_id,
        overall_score=kwargs.pop("overall_score", 68),
        suggestion=kwargs.pop("suggestion", "不建议发"),
        dimensions_json=json.dumps(dimensions, ensure_ascii=False),
        rewrites_json=json.dumps(rewrites, ensure_ascii=False),
        confidence_json=json.dumps({"overall_confidence": 0.77}, ensure_ascii=False),
    )
    db.add(summary)

    risks = kwargs.pop("risks", [
        ("涉及敏感政治人物评价", "政治安全", "red", "原文第2句", 82.0),
        ("群体标签化表述", "性别对立", "yellow", "原文第5句", 40.0),
    ])
    for sentence, dimension, severity, evidence, score in risks:
        db.add(RiskItem(
            task_id=task_id,
            sentence=sentence,
            dimension=dimension,
            severity=severity,
            evidence=evidence,
            risk_score=score,
        ))
    db.commit()
    return summary


@contextmanager
def _db_session():
    from backend.database import SessionLocal, engine, Base
    from backend import models  # noqa: F401 确保模型注册

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. JWT 未配置：行为兼容
# ---------------------------------------------------------------------------

def test_jwt_disabled_token_endpoint_503():
    """JWT_SECRET 未配置 → /auth/token 503，不签发任何令牌"""
    with _settings(JWT_SECRET="", ADMIN_PASSWORD=ADMIN_PASS):
        from backend import auth as auth_mod

        assert auth_mod.is_jwt_enabled() is False

        client = _client()
        r = client.post("/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert r.status_code == 503, r.text
        assert "JWT" in r.json().get("detail", "")
    print("  ✓ JWT 未配置：/auth/token 503")


def test_jwt_disabled_api_key_and_open_mode_unchanged():
    """未配置 JWT 时 API_KEY 机制与本地放行行为不回归"""
    from backend import auth as auth_mod

    with _settings(JWT_SECRET="", API_KEY=""):
        assert auth_mod.is_auth_enabled() is False
        client = _client()
        r = client.get("/api/v1/health")
        assert r.status_code == 200, r.text
        assert r.headers.get("X-API-Auth") == "disabled"

    with _settings(JWT_SECRET="", API_KEY=API_KEY_VAL):
        client = _client()
        assert client.get("/api/v1/health").status_code == 401
        r = client.get("/api/v1/health", headers={"X-API-Key": API_KEY_VAL})
        assert r.status_code == 200
        r = client.get("/api/v1/health", headers={"Authorization": f"Bearer {API_KEY_VAL}"})
        assert r.status_code == 200
    print("  ✓ JWT 未配置：API_KEY / 本地放行行为不变")


# ---------------------------------------------------------------------------
# 2. JWT 签发
# ---------------------------------------------------------------------------

def test_token_exchange_success_and_failure():
    """用户名+密码换 token；错误凭证 401；空口令配置 503"""
    with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=ADMIN_PASS, ADMIN_USERNAME=ADMIN_USER):
        client = _client()

        ok = client.post("/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["token_type"] == "bearer"
        assert body["username"] == ADMIN_USER
        assert body["expires_in"] > 0
        assert body["access_token"], "应返回 access_token"
        # 令牌本身不含明文口令
        assert ADMIN_PASS not in body["access_token"]

        bad = client.post("/api/v1/auth/token", json={"username": ADMIN_USER, "password": "wrong-pass"})
        assert bad.status_code == 401
        bad2 = client.post("/api/v1/auth/token", json={"username": "ghost", "password": ADMIN_PASS})
        assert bad2.status_code == 401

    with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=""):
        client = _client()
        r = client.post("/api/v1/auth/token", json={"username": ADMIN_USER, "password": "any"})
        assert r.status_code == 503, "空口令必须拒绝签发"
    print("  ✓ token 签发：成功/错误凭证/空口令行为正确")


def test_jwt_bearer_accepted_and_prioritized_over_api_key():
    """已配置 API_KEY 时，Bearer JWT 优先放行（可不带 API Key）"""
    with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=ADMIN_PASS, API_KEY=API_KEY_VAL):
        client = _client()

        token = client.post(
            "/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS}
        ).json()["access_token"]

        # JWT Bearer 放行，无需 API Key
        r = client.get("/api/v1/health", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text

        # 无凭证 → 401（API_KEY 已配置）
        assert client.get("/api/v1/health").status_code == 401

        # 伪造/过期 JWT → 401（不能降级成匿名放行）
        r = client.get("/api/v1/health", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

        # API Key 路径不回归
        r = client.get("/api/v1/health", headers={"X-API-Key": API_KEY_VAL})
        assert r.status_code == 200

        # JWT 开启响应头标注
        assert r.headers.get("X-API-Auth-JWT") == "enabled"
    print("  ✓ JWT Bearer 优先校验，API Key 路径不回归")


# ---------------------------------------------------------------------------
# 3. owner_id 归属
# ---------------------------------------------------------------------------

def test_owner_id_assigned_with_jwt_and_compatible_without():
    """带 JWT 提交审核任务写入 owner_id；无 token 时为 NULL"""
    created: list[str] = []

    async def _noop_analysis(task_id, *args, **kwargs):
        return {"task_id": task_id, "status": "completed"}

    try:
        import backend.routes as routes_mod

        old_run = routes_mod.run_analysis
        routes_mod.run_analysis = _noop_analysis
        try:
            with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=ADMIN_PASS, API_KEY=""):
                client = _client()
                token = client.post(
                    "/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS}
                ).json()["access_token"]

                r = client.post(
                    "/api/v1/review",
                    json={"mode": "text", "texts": [{"type": "text", "content": "R5 归属测试内容，超过十个字符。"}]},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200, r.text
                task_id = r.json()["task_id"]
                created.append(task_id)

                with _db_session() as db:
                    from backend.models import Task

                    t = db.query(Task).filter(Task.id == task_id).first()
                    assert t is not None
                    assert t.owner_id == ADMIN_USER
                    assert (t.workflow_status or "draft") == "draft"

                # 无 token 提交 → owner_id 为空（兼容）
                r2 = client.post(
                    "/api/v1/review",
                    json={"mode": "text", "texts": [{"type": "text", "content": "R5 无鉴权兼容测试内容。"}]},
                )
                assert r2.status_code == 200, r2.text
                created.append(r2.json()["task_id"])
                with _db_session() as db:
                    from backend.models import Task

                    t2 = db.query(Task).filter(Task.id == r2.json()["task_id"]).first()
                    assert t2 is not None
                    assert t2.owner_id is None

                # 结果接口暴露归属与工作流状态
                r3 = client.get(f"/api/v1/review/{task_id}")
                assert r3.status_code == 200
                body = r3.json()
                assert body.get("owner_id") == ADMIN_USER
                assert body.get("workflow_status") == "draft"
                assert body.get("workflow_history") == []
        finally:
            routes_mod.run_analysis = old_run
    finally:
        with _db_session() as db:
            from backend.models import AnalysisSummary, RiskItem, Task

            for tid in created:
                db.query(RiskItem).filter(RiskItem.task_id == tid).delete()
                db.query(AnalysisSummary).filter(AnalysisSummary.task_id == tid).delete()
                db.query(Task).filter(Task.id == tid).delete()
            db.commit()
    print("  ✓ owner_id：JWT 归属写入 / 无 token 兼容 / 结果接口暴露")


# ---------------------------------------------------------------------------
# 4. 审核工作流
# ---------------------------------------------------------------------------

def test_workflow_transitions_and_history():
    """draft → pending_review → approved 留痕完整；非法状态与非法流转 400"""
    with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=ADMIN_PASS, API_KEY=""):
        client = _client()
        token = client.post(
            "/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with _db_session() as db:
            task = _make_task(db, owner_id=ADMIN_USER, workflow_status="draft")
            task_id = task.id

        try:
            # draft → pending_review
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "pending_review", "note": "提交人工复核"},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "pending_review"
            assert body["previous_status"] == "draft"
            assert len(body["workflow_history"]) == 1
            assert body["workflow_history"][0]["from"] == "draft"
            assert body["workflow_history"][0]["to"] == "pending_review"
            assert body["workflow_history"][0]["note"] == "提交人工复核"
            assert body["workflow_history"][0]["actor"] == ADMIN_USER

            # pending_review → approved
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "approved", "note": "复核通过"},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            hist = r.json()["workflow_history"]
            assert len(hist) == 2
            assert hist[-1]["to"] == "approved"

            # approved → rejected 非法流转
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "rejected"},
                headers=headers,
            )
            assert r.status_code == 400, r.text

            # 非法状态值
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "hacked"},
                headers=headers,
            )
            assert r.status_code == 400, r.text

            # 同状态提交仅追加备注
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "approved", "note": "补充备注"},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            hist = r.json()["workflow_history"]
            assert len(hist) == 3
            assert hist[-1]["from"] == "approved" and hist[-1]["to"] == "approved"

            # 不存在任务 404
            r = client.patch(
                f"/api/v1/review/{str(uuid.uuid4())}/workflow",
                json={"status": "approved"},
                headers=headers,
            )
            assert r.status_code == 404

            # 422：缺 status 字段
            r = client.patch(f"/api/v1/review/{task_id}/workflow", json={"note": "x"}, headers=headers)
            assert r.status_code == 422
        finally:
            with _db_session() as db:
                from backend.models import Task

                db.query(Task).filter(Task.id == task_id).delete()
                db.commit()
    print("  ✓ 工作流：流转留痕 / 非法状态与流转 400 / 404 / 422")


def test_workflow_owner_isolation_prototype():
    """归属校验雏形：他人 JWT 403；无 token 放行（兼容）"""
    with _settings(JWT_SECRET=JWT_SECRET, ADMIN_PASSWORD=ADMIN_PASS, API_KEY=""):
        client = _client()
        token_a = client.post(
            "/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS}
        ).json()["access_token"]

        with _db_session() as db:
            task = _make_task(db, owner_id="other-user", workflow_status="draft")
            task_id = task.id

        try:
            # 归属为 other-user，admin JWT 操作 → 403
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "pending_review"},
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert r.status_code == 403, r.text

            # 无 token → 放行（兼容旧行为）
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "pending_review", "note": "匿名兼容"},
            )
            assert r.status_code == 200, r.text
        finally:
            with _db_session() as db:
                from backend.models import Task

                db.query(Task).filter(Task.id == task_id).delete()
                db.commit()
    print("  ✓ 归属校验雏形：他人 403 / 无 token 兼容放行")


# ---------------------------------------------------------------------------
# 5. 报告导出
# ---------------------------------------------------------------------------

def test_export_markdown_and_json():
    """format=md 含 Verdict/分数/Top 风险/改写/免责；format=json 结构完整"""
    with _settings(JWT_SECRET="", API_KEY=""):
        client = _client()
        with _db_session() as db:
            task = _make_task(db, workflow_status="pending_review")
            _make_summary(db, task.id)
            task_id = task.id

        try:
            # Markdown
            r = client.get(f"/api/v1/review/{task_id}/export?format=md")
            assert r.status_code == 200, r.text
            assert "text/markdown" in r.headers.get("content-type", "")
            md = r.text
            assert "结论（Verdict）" in md
            assert "68/100" in md
            assert "维度得分" in md
            assert "Top 风险" in md
            assert "改写建议" in md
            assert "免责声明" in md
            assert "政治安全" in md
            assert "红线说明" in md
            assert "这项政策的适用范围或许可以更精细化" in md

            # JSON
            r = client.get(f"/api/v1/review/{task_id}/export?format=json")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["task_id"] == task_id
            assert data["workflow_status"] == "pending_review"
            assert data["verdict"]["overall_score"] == 68
            assert data["verdict"]["risk_level"] in ("orange", "red", "yellow", "green")
            assert data["verdict"]["suggestion"] == "不建议发"
            assert isinstance(data["dimensions"], list) and len(data["dimensions"]) == 2
            assert isinstance(data["top_risks"], list) and data["top_risks"]
            assert data["top_risks"][0]["dimension"] == "政治安全"
            assert isinstance(data["rewrites"], list) and data["rewrites"]
            assert data["disclaimer"]

            # 非法 format
            r = client.get(f"/api/v1/review/{task_id}/export?format=pdf")
            assert r.status_code == 400

            # 404
            r = client.get(f"/api/v1/review/{str(uuid.uuid4())}/export?format=md")
            assert r.status_code == 404
        finally:
            with _db_session() as db:
                from backend.models import AnalysisSummary, RiskItem, Task

                db.query(RiskItem).filter(RiskItem.task_id == task_id).delete()
                db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).delete()
                db.query(Task).filter(Task.id == task_id).delete()
                db.commit()
    print("  ✓ 导出：md 五要素齐全 / json 结构完整 / 400 / 404")


def test_export_no_summary_degrades():
    """未完成分析的任务导出不崩溃，仍含 Verdict 占位与免责"""
    with _settings(JWT_SECRET="", API_KEY=""):
        client = _client()
        with _db_session() as db:
            task = _make_task(db, status="processing")
            task_id = task.id

        try:
            r = client.get(f"/api/v1/review/{task_id}/export?format=md")
            assert r.status_code == 200, r.text
            md = r.text
            assert "结论（Verdict）" in md
            assert "免责声明" in md
            assert "N/A" in md

            r = client.get(f"/api/v1/review/{task_id}/export?format=json")
            assert r.status_code == 200
            data = r.json()
            assert data["verdict"]["overall_score"] is None
            assert data["dimensions"] == []
            assert data["disclaimer"]
        finally:
            with _db_session() as db:
                from backend.models import Task

                db.query(Task).filter(Task.id == task_id).delete()
                db.commit()
    print("  ✓ 无摘要导出降级正确")


# ---------------------------------------------------------------------------
# 6. 无密钥入库
# ---------------------------------------------------------------------------

def test_no_secrets_persisted_in_db_or_export():
    """工作流历史 / 任务行 / 导出内容均不落 JWT_SECRET、ADMIN_PASSWORD、API_KEY 明文"""
    with _settings(
        JWT_SECRET=JWT_SECRET,
        ADMIN_PASSWORD=ADMIN_PASS,
        ADMIN_USERNAME=ADMIN_USER,
        API_KEY=API_KEY_VAL,
    ):
        client = _client()
        token = client.post(
            "/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with _db_session() as db:
            task = _make_task(db, owner_id=ADMIN_USER)
            _make_summary(db, task.id)
            task_id = task.id

        try:
            r = client.patch(
                f"/api/v1/review/{task_id}/workflow",
                json={"status": "pending_review", "note": "密钥不落库校验"},
                headers=headers,
            )
            assert r.status_code == 200, r.text

            with _db_session() as db:
                from backend.models import Task

                t = db.query(Task).filter(Task.id == task_id).first()
                raw_rows = [
                    t.text or "",
                    t.owner_id or "",
                    t.workflow_status or "",
                    t.workflow_history_json or "",
                    t.model or "",
                    t.error or "",
                ]
                joined = "\n".join(raw_rows)
                for secret in (JWT_SECRET, ADMIN_PASS, API_KEY_VAL, token):
                    assert secret not in joined, f"数据库任务行泄露密钥/令牌: {secret[:8]}..."

            for fmt in ("md", "json"):
                r = client.get(f"/api/v1/review/{task_id}/export?format={fmt}", headers=headers)
                assert r.status_code == 200
                body = r.text
                for secret in (JWT_SECRET, ADMIN_PASS, API_KEY_VAL, token):
                    assert secret not in body, f"导出({fmt})泄露密钥/令牌: {secret[:8]}..."

            # token 接口响应不含口令
            r = client.post("/api/v1/auth/token", json={"username": ADMIN_USER, "password": ADMIN_PASS})
            assert ADMIN_PASS not in r.text
        finally:
            with _db_session() as db:
                from backend.models import AnalysisSummary, RiskItem, Task

                db.query(RiskItem).filter(RiskItem.task_id == task_id).delete()
                db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).delete()
                db.query(Task).filter(Task.id == task_id).delete()
                db.commit()
    print("  ✓ 无密钥入库：任务行/工作流历史/导出均不含密钥与令牌")


# ---------------------------------------------------------------------------
# 独立运行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {fn.__name__}: {e}")
    print(f"\nR5 tests: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
