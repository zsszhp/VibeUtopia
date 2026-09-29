"""R4 博主闭环测试：风格画像 / 选题推荐 / 对标分析 / 决策映射

验证项：
1. 风格画像规则降级：输入历史文案 → 话题/语气/节奏/风险偏好/人设 五维齐全
2. 风格画像空输入：返回明确错误与 risk_impact
3. 选题推荐闭环：返回 ≤3 张卡，含切入点/预期效果/风险预估/安全分/理由/risk_impact
4. 对标分析闭环：结构差异 + 可模仿动作（选题角度/标题结构/发布节奏）+ 风险模式差异
5. 决策映射：选题与对标建议均带 risk_impact
6. API 层：/api/v1/blogger/style-profile 与 /api/v3/blogger/topics/recommend 可用
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SAMPLE_CONTENTS = [
    "姐妹们这个粉底液绝了！持妆一整天不暗沉，油皮亲妈！今天给大家测评三款热门粉底。",
    "哈哈这期有点翻车，不过过程很真实。大家想看什么测评留言告诉我～",
    "很多人问敏感肌能不能用，我专门做了成分分析，结论是这款含酒精，敏感肌慎入。",
    "这期聊聊美妆圈的性别刻板印象，为什么男生化妆就要被指指点点？",
    "日常vlog：周末去了新开的咖啡店，环境很出片，推荐给爱拍照的姐妹。",
]


# ---------------------------------------------------------------------------
# 风格画像
# ---------------------------------------------------------------------------

def test_style_profile_rule_based_dimensions():
    """规则降级下五维画像齐全，含决策映射"""
    from backend.services.blogger_style_profiler import BloggerStyleProfiler

    profiler = BloggerStyleProfiler()

    async def _run():
        return await profiler.analyze(
            contents=SAMPLE_CONTENTS,
            video_metadata=[{"title": "粉底液测评", "duration": 300, "platform": "bilibili"}],
            blogger_id="blogger-a",
            blogger_name="测试博主",
        )

    result = asyncio.run(_run())

    assert result.error is None
    # 话题
    assert result.topics.get("primary_topics"), "应识别出主要话题"
    # 语气 / 节奏
    assert result.expression.get("tone") in (
        "formal", "casual", "humorous", "serious", "inspiring",
    )
    assert result.expression.get("pacing") in ("快节奏", "慢叙事", "混合")
    # 风险偏好
    assert result.risk.get("risk_tolerance") in ("conservative", "moderate", "aggressive")
    # 人设
    assert result.persona.get("role")
    # 决策映射
    assert result.risk_impact
    assert result.style_summary
    assert isinstance(result.to_dict(), dict)
    print("  ✓ 风格画像五维齐全 + risk_impact")


def test_style_profile_empty_input():
    """空输入返回错误与决策提示，不抛异常"""
    from backend.services.blogger_style_profiler import BloggerStyleProfiler

    profiler = BloggerStyleProfiler()

    async def _run():
        return await profiler.analyze(contents=[], video_metadata=None)

    result = asyncio.run(_run())
    assert result.error is not None
    assert result.risk_impact
    print("  ✓ 空输入降级处理正确")


def test_style_profile_detects_risk_topics():
    """含敏感内容时风险偏好更保守，识别高危区"""
    from backend.services.blogger_style_profiler import BloggerStyleProfiler

    profiler = BloggerStyleProfiler()
    risky = [
        "这个政治话题太敏感了，体制内的人都在讨论领导人讲话。",
        "性别对立越来越严重，歧视和偏见无处不在。",
    ]

    async def _run():
        return await profiler.analyze(contents=risky)

    result = asyncio.run(_run())
    assert result.risk.get("risk_tolerance") == "conservative"
    assert result.risk.get("danger_zones"), "应识别出高危区"
    assert "回避" in result.risk_impact or "预审" in result.risk_impact
    print("  ✓ 敏感内容风险偏好识别正确")


# ---------------------------------------------------------------------------
# 选题推荐
# ---------------------------------------------------------------------------

def _sample_profile() -> dict:
    return {
        "topics": {"primary_topics": [{"topic": "美妆护肤", "weight": 0.5}]},
        "expression": {"tone": "humorous", "tone_label": "幽默", "pacing": "快节奏"},
        "risk": {"risk_tolerance": "moderate", "danger_zones": ["性别议题"]},
    }


def test_topic_recommend_returns_three_cards_with_fields():
    """选题推荐返回 ≤3 张卡，字段齐全"""
    from backend.services.topic_recommender import TopicRecommender

    recommender = TopicRecommender()
    hot_topics = [
        {"title": "春季新品粉底液盘点", "platform": "xiaohongshu", "strength": 80},
        {"title": "美妆博主翻车合集", "platform": "bilibili", "strength": 60},
        {"title": "敏感肌换季护肤指南", "platform": "douyin", "strength": 70},
        {"title": "化妆刷清洁教程", "platform": "xiaohongshu", "strength": 40},
    ]

    async def _run():
        return await recommender.recommend(
            blogger_profile=_sample_profile(),
            hot_topics=hot_topics,
            blogger_id="blogger-a",
            blogger_name="测试博主",
        )

    result = asyncio.run(_run())
    assert result.error is None
    assert 1 <= len(result.recommendations) <= 3, "应返回最多 3 张选题卡"

    for rec in result.recommendations:
        assert rec.topic
        assert rec.angle, "每张卡应有切入点"
        assert rec.reason, "每张卡应有推荐理由"
        assert rec.estimated_reach is not None
        assert rec.risk_level in ("safe", "low", "medium", "high", "critical")
        assert 0 < rec.safety_score <= 100, "应有安全分"
        assert rec.risk_impact, "应有决策映射"
        assert rec.brief, "应有可预审的简介草稿"
    print("  ✓ 选题卡字段齐全（切入点/效果/风险/安全分/理由/risk_impact）")


def test_topic_recommend_high_risk_low_safety():
    """高危选题安全分更低，risk_impact 指向不可直接发"""
    from backend.services.topic_recommender import TopicRecommender

    recommender = TopicRecommender()
    hot_topics = [{"title": "政治体制争议话题讨论", "platform": "weibo", "strength": 90}]

    async def _run():
        return await recommender.recommend(
            blogger_profile=_sample_profile(),
            hot_topics=hot_topics,
        )

    result = asyncio.run(_run())
    rec = result.recommendations[0]
    assert rec.risk_level in ("high", "medium", "critical")
    assert rec.safety_score < 70
    assert "发" in rec.risk_impact
    print("  ✓ 高危选题安全分与决策映射正确")


# ---------------------------------------------------------------------------
# 对标分析
# ---------------------------------------------------------------------------

def test_competitor_imitation_analysis():
    """对标输出结构差异、可模仿动作、风险模式差异"""
    from backend.services.competitor_comparator import CompetitorComparator

    comparator = CompetitorComparator()
    b_profile = {
        "topics": {"primary_topics": [{"topic": "美妆护肤"}]},
        "expression": {"tone": "humorous", "tone_label": "幽默", "pacing": "快节奏"},
        "risk": {
            "risk_tolerance": "moderate",
            "risk_tolerance_label": "中等",
            "danger_zones": ["性别议题"],
        },
    }
    c_profile = {
        "topics": {"primary_topics": [{"topic": "美妆护肤"}]},
        "expression": {"tone": "casual", "tone_label": "轻松", "pacing": "混合"},
        "risk": {
            "risk_tolerance": "conservative",
            "risk_tolerance_label": "保守",
            "danger_zones": ["广告法"],
        },
    }

    report = comparator.compare(
        blogger_id="blogger-a",
        competitor_ids=["competitor-b"],
        field_name="美妆",
        blogger_profile=b_profile,
        competitor_profiles=[c_profile],
    )

    # 结构差异
    assert report.structure_diff.get("主题结构")
    assert report.structure_diff.get("标题结构")
    assert report.structure_diff.get("内容节奏")

    # 可模仿动作：三类齐全
    categories = {a.category for a in report.imitable_actions}
    assert "选题角度" in categories
    assert "标题结构" in categories
    assert "发布节奏" in categories
    for a in report.imitable_actions:
        assert a.action
        assert a.reason
        assert a.risk_impact, "可模仿动作必须带决策映射"

    # 风险模式差异
    assert report.risk_pattern_diff.get("风险偏好差异")
    assert report.risk_pattern_diff.get("高危区差异")
    assert report.risk_pattern_diff.get("对发布决策的影响")
    print("  ✓ 对标分析：结构差异 + 三类可模仿动作 + 风险模式差异")


def test_competitor_without_profiles_still_works():
    """无风格画像时仍给出可读的对标结论（降级不中断）"""
    from backend.services.competitor_comparator import CompetitorComparator

    comparator = CompetitorComparator()
    report = comparator.compare(
        blogger_id="blogger-a",
        competitor_ids=["competitor-b"],
        field_name="",
    )

    assert report.structure_diff.get("主题结构")
    assert report.imitable_actions, "降级时仍应给出可模仿动作"
    assert report.risk_pattern_diff.get("对发布决策的影响")
    print("  ✓ 无画像降级路径可用")


# ---------------------------------------------------------------------------
# API 层
# ---------------------------------------------------------------------------

def test_api_style_profile_and_topics_recommend():
    """API 端点可用，响应含决策映射字段"""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    r = client.post(
        "/api/v1/blogger/style-profile",
        json={
            "blogger_id": "blogger-a",
            "blogger_name": "测试博主",
            "contents": SAMPLE_CONTENTS,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["topics"] is not None
    assert data["expression"]["tone"]
    assert data["risk"]["risk_tolerance"]
    assert data["persona"]["role"]
    assert data["risk_impact"]

    r2 = client.post(
        "/api/v3/blogger/topics/recommend",
        json={
            "blogger_profile": _sample_profile(),
            "hot_topics": [
                {"title": "春季新品粉底液盘点", "platform": "xiaohongshu", "strength": 80},
                {"title": "敏感肌换季护肤指南", "platform": "douyin", "strength": 70},
            ],
            "blogger_id": "blogger-a",
            "blogger_name": "测试博主",
        },
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert 1 <= len(body["recommendations"]) <= 3
    first = body["recommendations"][0]
    for key in ("topic", "angle", "reason", "estimated_reach", "risk_level",
                "safety_score", "brief", "risk_impact"):
        assert key in first, f"响应缺少字段 {key}"
    print("  ✓ 风格画像与选题推荐 API 可用")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"\n{name}")
            fn()
    print("\nR4 博主闭环测试：全部通过")
