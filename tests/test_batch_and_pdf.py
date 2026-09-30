"""批量预审与 PDF 导出 smoke"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_vibeutopia.db")
os.environ.setdefault("MYSQL_HOST", "")


def test_batch_review_smoke():
    from fastapi.testclient import TestClient
    from backend.database import Base, engine
    from backend import models  # noqa: F401
    from backend.main import app

    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    r = client.post(
        "/api/v1/review/batch",
        json={
            "items": [
                {"client_id": "a", "text": "今天天气不错，适合出门散步心情好。"},
                {"client_id": "b", "text": "我有内部消息某只股票下周会暴涨，赶紧买入绝对赚钱。"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert data["ok"] >= 1
    levels = {x["client_id"]: x.get("risk_level") for x in data["results"]}
    assert levels.get("a") in ("green", "yellow")
    assert levels.get("b") in ("orange", "red", "yellow")


def test_pdf_export_helper():
    from backend.routes import _render_export_pdf

    pdf = _render_export_pdf(
        {
            "task_id": "t",
            "verdict": {"overall_score": 80, "risk_level": "red", "suggestion": "不建议发布"},
            "dimensions": [{"name": "政治敏感", "score": 82, "severity": "red", "evidence": "证据"}],
            "top_risks": [],
            "rewrites": [],
            "disclaimer": "免责",
        }
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500
