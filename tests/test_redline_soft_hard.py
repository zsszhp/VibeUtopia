"""红线软硬分级测试：硬红线触及 vs 软红线阈值

验证：
1. 硬红线（民族宗教）score=55 → 触及，维度分与 overall 抬升到 76+
2. 软红线（法律合规）score=55 → 不触及，保持原分
3. 软红线（事实错误）score=72 → 触及
4. 非红线维度不参与触及判定
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.severity import (  # noqa: E402
    enforce_redline_dim_score,
    redline_touch_threshold,
    redline_triggers_floor,
)


def test_hard_redline_touch_at_50():
    assert redline_touch_threshold("民族宗教") == 50
    score, lifted = enforce_redline_dim_score("民族宗教", 55, "orange")
    assert score >= 76
    assert lifted is True
    assert redline_triggers_floor([{"name": "民族宗教", "score": 55, "severity": "orange"}])


def test_soft_redline_not_touch_at_55():
    assert redline_touch_threshold("法律合规") == 70
    score, lifted = enforce_redline_dim_score("法律合规", 55, "orange")
    assert score == 55
    assert lifted is False
    assert not redline_triggers_floor([{"name": "法律合规", "score": 55, "severity": "orange"}])


def test_soft_redline_touch_at_72():
    score, lifted = enforce_redline_dim_score("事实错误", 72, "orange")
    assert score >= 76
    assert redline_triggers_floor([{"name": "事实错误", "score": 72, "severity": "orange"}])


def test_non_redline_ignored():
    score, lifted = enforce_redline_dim_score("情绪极化", 90, "red")
    assert score == 90
    assert lifted is False
    assert not redline_triggers_floor([{"name": "情绪极化", "score": 90, "severity": "red"}])


def test_hard_redline_high_severity_still_lifts():
    score, lifted = enforce_redline_dim_score("政治敏感", 40, "red")
    assert score >= 76
    assert lifted is True
