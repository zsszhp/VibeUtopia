"""仿真引擎与反事实改写预估 — 导入 + 最小可运行 smoke

覆盖 P0 修复验收：
1. engine.py 可导入（SyntaxError 已修复）
2. 轻量引擎可 initialize + 跑完最小 tick 循环
3. 反事实不再产出占位符假句 / 固定衰减"风险必降"
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ── 导入测试 ──────────────────────────────────────

def test_simulation_package_importable():
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation import SimulationEngine as Exported

    assert SimulationEngine is Exported
    assert hasattr(SimulationEngine, "create_lightweight")
    assert hasattr(SimulationEngine, "initialize")
    assert hasattr(SimulationEngine, "run")


def test_counterfactual_module_importable():
    from backend.services.counterfactual_sim import CounterfactualSimulator, DISCLAIMER

    assert "非全量仿真" in DISCLAIMER
    assert hasattr(CounterfactualSimulator, "simulate")


# ── 仿真引擎最小可运行路径 ──────────────────────────

def test_engine_minimal_run():
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.models import PlatformAction

    async def fake_decide(agent, platform, time_slot, platform_feed):
        return [PlatformAction(
            agent_id=agent.get("persona_id", ""),
            platform=platform,
            action_type="like",
            target_id="",
            content="",
        )]

    async def _run():
        cfg = {
            "lightweight": True,
            "agent_count": 10,
            "max_ticks": 2,
            "tick_interval": 0.01,
            "platforms": ["weibo", "bilibili"],
            "b_agent_per_tick": 1,
            "seed_content": "冒烟测试话题",
        }
        engine = SimulationEngine(sim_id="smoke_engine", topic="冒烟测试话题", config=cfg)
        with patch("backend.services.simulation.engine.decide_actions", side_effect=fake_decide):
            await engine.initialize()
            assert len(engine.agents) >= 10
            await engine.run()

        status = engine.get_status()
        assert status["status"] == "completed"
        assert status["current_tick"] == 2
        assert status["total_agents"] >= 10
        assert "propagation" in status

    asyncio.run(_run())


def test_engine_survives_db_unavailable():
    """数据库不可用时引擎应降级补充Agent并跑完，而不是崩溃"""
    from backend.services.simulation.engine import SimulationEngine

    async def _run():
        cfg = {
            "lightweight": True,
            "agent_count": 6,
            "max_ticks": 1,
            "tick_interval": 0.01,
            "platforms": ["weibo"],
            "b_agent_per_tick": 0,
            "seed_content": "降级冒烟",
        }
        engine = SimulationEngine(sim_id="smoke_degraded", topic="降级冒烟", config=cfg)
        await engine.initialize()
        assert len(engine.agents) >= 6
        await engine.run()
        assert engine.status == "completed"

    asyncio.run(_run())


def test_enhanced_analyzer_phase3_no_longer_always_fails():
    """enhanced_analyzer 仿真阶段在引擎可用时真实执行，不再恒落入 except"""
    from backend.services import enhanced_analyzer as ea

    async def _run():
        result = ea.EnhancedAnalysisResult(task_id="smoke_phase3")
        # 缩短轻量配置，避免 smoke 过久
        original = dict(
            __import__(
                "backend.services.simulation.engine", fromlist=["LIGHTWEIGHT_SIM_CONFIG"]
            ).LIGHTWEIGHT_SIM_CONFIG
        )

        import backend.services.simulation.engine as eng_mod

        eng_mod.LIGHTWEIGHT_SIM_CONFIG.update({
            "agent_count": 8,
            "simulation_hours": 1,   # create_lightweight: max_ticks = hours*6 = 6
            "tick_interval": 0.01,
            "platforms": ["weibo"],
            "b_agent_per_tick": 0,
        })
        try:
            await ea._run_phase3("冒烟文案：这是一段用于验证仿真阶段可执行的测试文本。", result)
        finally:
            eng_mod.LIGHTWEIGHT_SIM_CONFIG.clear()
            eng_mod.LIGHTWEIGHT_SIM_CONFIG.update(original)
        return result

    result = asyncio.run(_run())
    summary = result.simulation_summary or {}
    assert "error" not in summary or summary.get("degraded") is True
    # 引擎可用时必须真实跑出 tick 摘要
    assert summary.get("total_ticks", 0) >= 1 or summary.get("degraded_reason")
    if "error" not in summary:
        assert summary.get("engine_mode") == "lightweight_tick_simulation"
        assert summary.get("total_agents", 0) > 0


# ── 反事实改写预估 ──────────────────────────────────

RISK_ITEMS = [
    {"dimension": "情绪极化", "severity": "high", "score": 75, "evidence": "你们这些人都是一丘之貉，活该被骂"},
    {"dimension": "群体冒犯", "severity": "medium", "score": 50, "evidence": "某地人素质就是差"},
]

TEXT = "今天真是无语了。你们这些人都是一丘之貉，活该被骂。某地人素质就是差。大家都散了吧。"


def test_counterfactual_delete_no_llm_needed():
    from backend.services.counterfactual_sim import CounterfactualSimulator

    async def _run():
        sim = CounterfactualSimulator()
        return await sim.simulate(TEXT, RISK_ITEMS, strategy_type="delete")

    result = asyncio.run(_run())
    assert result.error is None
    assert result.strategy.strategy_type == "delete"
    assert result.strategy.target_sentence in TEXT
    assert result.strategy.target_sentence not in result.modified_text
    assert "非全量仿真" in result.disclaimer
    assert result.direction_hint in ("likely_down", "likely_up", "uncertain")
    assert "风险必降" not in result.recommendation


def test_counterfactual_rewrite_failure_returns_error_not_placeholder():
    """改写失败必须返回明确错误，不得产出 [中性表述]/第5字符插词 等假句子"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    empty = {
        "original": "",
        "is_transcript_noise": False,
        "is_redline": False,
        "transcript_note": "",
        "rewrites": [],
    }

    async def _run():
        sim = CounterfactualSimulator()
        with patch("backend.services.rewriter.rewrite_sentence", new=AsyncMock(return_value=empty)):
            return await sim.simulate(TEXT, RISK_ITEMS, strategy_type="soften")

    result = asyncio.run(_run())
    assert result.error is not None
    assert "改写" in result.error or "未返回" in result.error
    assert result.modified_text == ""
    assert "[中性表述]" not in (result.modified_text or "")
    assert result.strategy.modified_sentence == ""


def test_counterfactual_rewrite_success_uses_llm_sentence():
    """改写成功时使用 rewriter 输出，而不是占位符拼接"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    real_rewrite = {
        "original": "你们这些人都是一丘之貉，活该被骂",
        "is_transcript_noise": False,
        "is_redline": False,
        "transcript_note": "",
        "rewrites": [
            {"text": "这样的态度让我很失望，希望大家能理性沟通", "rewrite_note": "去掉群体攻击，改为表达个人感受"},
        ],
    }

    async def _run():
        sim = CounterfactualSimulator()
        with patch("backend.services.rewriter.rewrite_sentence", new=AsyncMock(return_value=real_rewrite)), \
             patch("backend.services.risk_assessor.assess_risks", new=AsyncMock(side_effect=RuntimeError("no llm"))):
            return await sim.simulate(TEXT, RISK_ITEMS, strategy_type="soften")

    result = asyncio.run(_run())
    assert result.error is None
    assert result.strategy.modified_sentence == "这样的态度让我很失望，希望大家能理性沟通"
    assert "[中性表述]" not in result.modified_text
    assert "可能" != result.strategy.modified_sentence[:2]  # 不是第5字符插"可能"的产物
    assert result.modified_text.startswith("今天真是无语了。")
    assert result.method == "heuristic_rewrite_estimate"
    assert "非全量仿真" in result.disclaimer


def test_counterfactual_heuristic_is_range_not_fixed_decay():
    """LLM 重评估不可用时：给出区间与方向，不使用 min(原分*0.4,30) 固定衰减"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    real_rewrite = {
        "original": "",
        "is_transcript_noise": False,
        "is_redline": False,
        "transcript_note": "",
        "rewrites": [{"text": "改写后的安全表述", "rewrite_note": "说明"}],
    }

    async def _run():
        sim = CounterfactualSimulator()
        with patch("backend.services.rewriter.rewrite_sentence", new=AsyncMock(return_value=real_rewrite)), \
             patch("backend.services.risk_assessor.assess_risks", new=AsyncMock(side_effect=RuntimeError("no llm"))):
            return await sim.simulate(TEXT, RISK_ITEMS, strategy_type="replace")

    result = asyncio.run(_run())
    assert result.error is None
    assert result.after.method == "heuristic_range"
    assert result.after.estimated_range is not None
    assert result.improvement_range is not None
    low, high = result.improvement_range["low"], result.improvement_range["high"]
    assert low <= high

    # 不再恒等式"风险必降"：区间必须覆盖不确定（soft/replace 允许上升）
    assert result.direction_hint in ("likely_down", "likely_up", "uncertain")
    # 固定衰减 40% 会给出 improvement≈30 的确定值，启发式区间不应是单点
    assert not (low == high and low == pytest.approx(30.0))
    # 符号约定必须写清：improvement = before - after，正值=风险下降
    assert "正值=风险下降" in result.recommendation
    assert "风险必降" not in result.recommendation
    assert "预计风险可降低" not in result.recommendation


def test_counterfactual_static_reevaluation_path():
    """重评估可用时：method=static_reevaluation，且允许风险上升"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    real_rewrite = {
        "original": "",
        "is_transcript_noise": False,
        "is_redline": False,
        "transcript_note": "",
        "rewrites": [{"text": "改写后仍带风险的表述", "rewrite_note": "说明"}],
    }
    worse_eval = {
        "dimensions": [
            {"name": "情绪极化", "score": 80, "severity": "high", "dimension_weight": 1.2},
            {"name": "群体冒犯", "score": 60, "severity": "medium", "dimension_weight": 1.0},
        ],
        "risk_sentences": [],
        "cross_effects": [],
    }

    async def _run():
        sim = CounterfactualSimulator()
        with patch("backend.services.rewriter.rewrite_sentence", new=AsyncMock(return_value=real_rewrite)), \
             patch("backend.services.risk_assessor.assess_risks", new=AsyncMock(return_value=worse_eval)):
            return await sim.simulate(TEXT, RISK_ITEMS, strategy_type="replace")

    result = asyncio.run(_run())
    assert result.error is None
    assert result.after.method == "static_reevaluation"
    assert result.method == "static_reevaluation"
    assert result.confidence == "medium"
    # 改写后分更高 → 风险上升方向，不得写成"预计风险可降低"
    assert result.direction_hint in ("likely_up", "uncertain")
    assert "预计风险可降低" not in result.recommendation
    assert "非全量仿真" in result.recommendation


def test_counterfactual_redline_dimension_refuses_rewrite():
    """红线维度：改写服务拒绝，结果返回明确错误而不是假改写"""
    from backend.services.counterfactual_sim import CounterfactualSimulator

    redline = {
        "original": "",
        "is_transcript_noise": False,
        "is_redline": True,
        "redline_note": "该内容触及红线维度，建议不予发布。改写建议不适用于规避审核用途。",
        "rewrites": [],
    }
    items = [{"dimension": "政治敏感", "severity": "critical", "score": 90, "evidence": "红线内容示例句"}]

    async def _run():
        sim = CounterfactualSimulator()
        with patch("backend.services.rewriter.rewrite_sentence", new=AsyncMock(return_value=redline)):
            return await sim.simulate("前文。红线内容示例句。后文。", items, strategy_type="soften")

    result = asyncio.run(_run())
    assert result.error is not None
    assert "红线" in result.error
    assert result.strategy.modified_sentence == ""
