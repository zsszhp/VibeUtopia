"""隐喻/反讽兜底测试（BT015 类场景）"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.irony_detector import apply_irony_floor, detect_irony_risk


def test_irony_with_target_flags():
    r = detect_irony_risk("好一个政策为人民服务，真是优秀，懂的都懂")
    assert r["has_irony_markers"]
    assert r["has_sensitive_targets"]
    assert r["suggested_min_score"] >= 55


def test_plain_text_no_floor():
    r = detect_irony_risk("今天天气不错，适合出门散步")
    assert r["suggested_min_score"] == 0
    dims = [{"name": "时事踩雷", "score": 10, "severity": "green"}]
    out = apply_irony_floor(dims, "今天天气不错，适合出门散步")
    assert out[0]["score"] == 10


def test_irony_floor_lifts_sensitive_dims():
    text = "所谓的英雄事迹都是编出来的，历史书都是胜利者写的，懂的都懂，好一个光辉历史"
    dims = [
        {"name": "时事踩雷", "score": 19, "severity": "green"},
        {"name": "群体冒犯", "score": 20, "severity": "green"},
        {"name": "法律合规", "score": 10, "severity": "green"},
    ]
    out = apply_irony_floor(dims, text)
    by = {d["name"]: d for d in out}
    assert by["时事踩雷"]["score"] >= 55
    assert by["时事踩雷"]["severity"] == "orange"
    assert by["群体冒犯"]["score"] >= 55
    assert by["法律合规"]["score"] == 10  # 非目标维度不动
