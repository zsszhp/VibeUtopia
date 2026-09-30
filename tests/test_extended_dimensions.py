"""扩展维度（12-14）测试：未成年人/隐私/知识产权"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.irony_detector import apply_extended_dim_floor  # noqa: E402
from backend.services.analyzer import calculate_overall_score  # noqa: E402


def test_minor_floor():
    dims = apply_extended_dim_floor([], "带娃直播过度曝光让孩子出镜赚钱")
    names = {d["name"]: d for d in dims}
    assert "未成年人保护" in names
    assert names["未成年人保护"]["score"] >= 55


def test_privacy_double_hit_red():
    dims = apply_extended_dim_floor([], "有人把住址人肉出来还偷拍私密照片")
    names = {d["name"]: d for d in dims}
    assert names["隐私侵犯"]["score"] >= 70
    assert names["隐私侵犯"]["severity"] == "red"


def test_ip_floor():
    dims = apply_extended_dim_floor([], "文案抄袭洗稿搬运假冒品牌")
    names = {d["name"]: d for d in dims}
    assert "知识产权" in names


def test_extended_red_overall_floor():
    dims = [{"name": "知识产权", "score": 70, "severity": "red"}]
    overall, _, _ = calculate_overall_score(dims, context_text="抄袭洗稿")
    assert overall >= 76


def test_normal_text_no_extended():
    dims = apply_extended_dim_floor([], "今天天气不错适合出门散步")
    assert not any(d.get("name") in ("未成年人保护", "隐私侵犯", "知识产权") for d in dims)
