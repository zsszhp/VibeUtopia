"""R2 可信与度量专项测试：计量写入 / 红线抬升 / 置信度收敛 / 评测脚本离线 demo"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# 计量 Meter
# ---------------------------------------------------------------------------

def test_meter_writes_jsonl_and_summarizes(tmp_path):
    from backend.services.llm_meter import LLMMeter

    path = tmp_path / "llm_usage.jsonl"
    meter = LLMMeter(path)

    meter.record(model="m1", latency_ms=120.0, success=True, provider="p1",
                 prompt_tokens=100, completion_tokens=50, total_tokens=150,
                 analysis_id="task-1")
    meter.record(model="m1", latency_ms=300.0, success=True, provider="p1",
                 prompt_tokens=80, completion_tokens=40, analysis_id="task-1")
    meter.record(model="m2", latency_ms=500.0, success=False, error_type="http_429",
                 analysis_id="task-2")

    assert path.exists(), "计量文件应已创建"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 3
    row = json.loads(lines[0])
    assert row["model"] == "m1"
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 50
    assert row["latency_ms"] == 120.0
    assert row["success"] is True
    assert row["analysis_id"] == "task-1"

    summary = meter.summarize(n=10)
    assert summary["available"] is True
    assert summary["calls"] == 3
    assert summary["failures"] == 1
    assert abs(summary["failure_rate"] - 1 / 3) < 1e-3
    assert summary["latency_ms"]["p50"] > 0
    assert summary["latency_ms"]["p90"] >= summary["latency_ms"]["p50"]
    assert summary["tokens"]["prompt"] == 180
    assert summary["tokens"]["completion"] == 90
    assert summary["by_model"]["m1"]["calls"] == 2
    assert summary["analyses"]["count"] == 2


def test_meter_empty_summary_is_blank():
    from backend.services.llm_meter import LLMMeter

    meter = LLMMeter(Path(__file__).parent / "__no_such_metrics__.jsonl")
    summary = meter.summarize(n=5)
    assert summary["available"] is False
    assert summary["calls"] == 0
    assert summary["failure_rate"] is None
    assert summary["latency_ms"] is None


def test_meter_analysis_id_context():
    from backend.services.llm_meter import LLMMeter, reset_analysis_id, set_analysis_id

    path = Path(__file__).parent / "__meter_ctx_test__.jsonl"
    if path.exists():
        path.unlink()
    meter = LLMMeter(path)
    try:
        token = set_analysis_id("ctx-task")
        meter.record(model="m", latency_ms=1.0, success=True)
        reset_analysis_id(token)
    finally:
        if path.exists():
            rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
            path.unlink()
    assert rows and rows[0]["analysis_id"] == "ctx-task"


# ---------------------------------------------------------------------------
# 红线 76+ 强制
# ---------------------------------------------------------------------------

def test_redline_forces_overall_to_76():
    """任一红线维度 red/high → overall 至少 76（红线代码化，与 Prompt 标定一致）"""
    from backend.services.analyzer import calculate_overall_score

    # 红线维度（政治敏感）被判 red，但 LLM 只给了低分
    dims = [
        {"name": "政治敏感", "score": 30, "severity": "red", "dimension_weight": 1.5},
        {"name": "道德伦理", "score": 10, "severity": "green", "dimension_weight": 1.0},
    ]
    overall, _w, _c = calculate_overall_score(dims)
    assert overall >= 76, f"红线 red 应强制 overall>=76，实际 {overall}"

    # 旧词表 high 同样触发
    dims_legacy = [
        {"name": "法律合规", "score": 40, "severity": "high", "dimension_weight": 1.5},
    ]
    overall2, _w2, _c2 = calculate_overall_score(dims_legacy)
    assert overall2 >= 76, f"红线 high 应强制 overall>=76，实际 {overall2}"


def test_redline_dim_score_lifted():
    """红线维度 red → 维度分强制抬到 76+，severity 与分数区间自洽"""
    from backend.services.analyzer import calculate_overall_score

    dims = [
        {"name": "民族宗教", "score": 20, "severity": "red", "dimension_weight": 1.3},
        {"name": "性别议题", "score": 15, "severity": "green", "dimension_weight": 1.0},
    ]
    overall, _w, _c = calculate_overall_score(dims)
    assert dims[0]["score"] >= 76, f"红线维度分数应被抬升，实际 {dims[0]['score']}"
    assert dims[1]["score"] == 15, "非红线维度不应被改分"
    assert overall >= 76


def test_non_redline_red_keeps_floor_50():
    """非红线维度 red 只触发保底 50，不强制 76"""
    from backend.services.analyzer import calculate_overall_score

    dims = [
        {"name": "性别议题", "score": 10, "severity": "red", "dimension_weight": 1.0},
        {"name": "道德伦理", "score": 5, "severity": "green", "dimension_weight": 1.0},
    ]
    overall, _w, _c = calculate_overall_score(dims)
    assert 50 <= overall < 76, f"非红线 red 应为 50 保底而非 76，实际 {overall}"


def test_green_not_lifted():
    from backend.services.analyzer import calculate_overall_score

    dims = [
        {"name": "政治敏感", "score": 5, "severity": "green", "dimension_weight": 1.5},
    ]
    overall, _w, _c = calculate_overall_score(dims)
    assert overall < 50


# ---------------------------------------------------------------------------
# 置信度收敛
# ---------------------------------------------------------------------------

def test_confidence_level_and_reason_labels():
    from backend.services.confidence_calculator import ConfidenceCalculator, confidence_level

    assert confidence_level(0.9) == "very_high"
    assert confidence_level(0.75) == "high"
    assert confidence_level(0.55) == "medium"
    assert confidence_level(0.3) == "low"

    calc = ConfidenceCalculator()
    dimensions = [{"name": f"d{i}", "score": 10} for i in range(11)]
    risk_sentences = [{"text": "句子" * 50} for _ in range(5)]
    evidence_chains = [
        {"confidence": 0.9, "cross_validation": [{"dimension": "d0"}]},
        {"confidence": 0.8, "cross_validation": []},
    ]
    result = calc.calculate(
        dimensions=dimensions,
        risk_sentences=risk_sentences,
        evidence_chains=evidence_chains,
    )
    assert result["confidence_level"] in ("low", "medium", "high", "very_high")
    assert "cross_validation" in result["reason_labels"]
    assert "consistency" in result["reason_labels"]
    assert "full_coverage" in result["reason_labels"]
    assert 0.0 <= result["overall_confidence"] <= 1.0


def test_enhanced_analyzer_uses_shared_calculator():
    """enhanced_analyzer 必须走 ConfidenceCalculator，而非旧模块计数公式"""
    from backend.services.enhanced_analyzer import EnhancedAnalysisResult, _compile_final_report

    result = EnhancedAnalysisResult(task_id="t1")
    result.mvp_dimensions = {"性别议题": 20, "道德伦理": 10}
    result.v2_dimensions = {"性别议题": 20, "道德伦理": 10}
    result.mvp_risk_sentences = [{"sentence": "测试句子", "dimension": "性别议题", "severity": "green"}]
    result.mvp_platform_reactions = []
    _compile_final_report(result)

    assert result.confidence_sources.get("formula") == "confidence_calculator"
    assert "confidence_level" in result.confidence_sources
    assert isinstance(result.confidence_sources.get("reason_labels"), list)
    # 旧公式：仅开仿真+音频会给 0.5+0.15+0.1=0.75；新公式不得由模块数决定
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# 评测脚本离线 demo
# ---------------------------------------------------------------------------

def test_eval_regression_offline_demo(tmp_path):
    out_dir = tmp_path / "eval"
    cmd = [
        sys.executable,
        str(ROOT / "tests" / "run_eval_regression.py"),
        "--mode", "mock",
        "--limit", "4",
        "--out-dir", str(out_dir),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"},
        timeout=120,
    )
    assert proc.returncode == 0, f"eval 脚本应成功退出: {proc.stdout}\n{proc.stderr}"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"
    assert latest_json.exists() and latest_md.exists()
    report = json.loads(latest_json.read_text(encoding="utf-8"))
    assert report["mode"] == "mock"
    assert report["total_cases"] == 4
    assert report["valid_ratio"] == 1.0  # mock 无 API 失败
    assert report["valid_accuracy"] is not None
    assert "valid_accuracy" in latest_md.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# metrics 汇总 API
# ---------------------------------------------------------------------------

def test_metrics_summary_endpoint(tmp_path, monkeypatch):
    from backend.services import llm_meter as lm
    from backend.services.llm_meter import LLMMeter

    test_path = tmp_path / "api_metrics.jsonl"
    meter = LLMMeter(test_path)
    meter.record(model="m1", latency_ms=100.0, success=True, analysis_id="a1")
    monkeypatch.setattr(lm, "meter", meter)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import backend.routes as routes

    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1")
    client = TestClient(app)
    resp = client.get("/api/v1/metrics/summary?n=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["calls"] == 1

    empty_meter = LLMMeter(tmp_path / "none.jsonl")
    monkeypatch.setattr(lm, "meter", empty_meter)
    resp2 = client.get("/api/v1/metrics/summary")
    assert resp2.status_code == 200
    assert resp2.json()["available"] is False
