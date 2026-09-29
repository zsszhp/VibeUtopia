"""L6 叙事语用 + L7 风险涌现 单元测试（合成转写/事件，离线可跑）

验证项：
1. NarrativePragmaticsAnalyzer：狗哨关键词、影射句式、带节奏（对立主体并置）、
   setup-payoff（先立靶后打）可检出；LLM 失败降级回规则结果
2. RiskEmergence：涌现分单调性（冲突↑则 emergent↑）、base/emergent 分解、
   区间 + 置信分解（反伪精确）、短闪现原子
3. Pipeline：narrative_pragmatics / emergence_summary 输出与旧字段兼容
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.video_understanding import (  # noqa: E402
    FrameObservation,
    NarrativeConflict,
    NarrativePragmaticsAnalyzer,
    PragmaticRisk,
    RiskEmergenceScorer,
    TranscriptSegment,
    VideoEventUnderstandingPipeline,
    build_risk_atoms,
    run_event_understanding,
    short_flash_indicators,
)


# ─── 合成数据 ─────────────────────────────────────────────────


def make_dog_whistle_transcript() -> list:
    """狗哨/隐射样本"""
    return [
        TranscriptSegment(0.0, 6.0, "有些事情懂得都懂，我就不点名了"),
        TranscriptSegment(6.0, 12.0, "大家自己品一品这里面的门道"),
        TranscriptSegment(12.0, 18.0, "感谢大家观看本期视频"),
    ]


def make_provocation_transcript() -> list:
    """带节奏样本：对立主体并置 + 煽动框架词"""
    return [
        TranscriptSegment(0.0, 6.0, "我们打工人天天加班到半夜"),
        TranscriptSegment(6.0, 12.0, "老板们凭什么还觉得我们不够努力"),
        TranscriptSegment(12.0, 18.0, "这就是赤裸裸的双标"),
    ]


def make_setup_payoff_transcript() -> list:
    """setup-payoff 样本：先立靶后打"""
    return [
        TranscriptSegment(0.0, 8.0, "总有人说我们抄袭别人的方案"),
        TranscriptSegment(8.0, 16.0, "今天我就把这些造谣的人扒干净"),
        TranscriptSegment(20.0, 28.0, "其实那些指控根本没有任何证据"),
        TranscriptSegment(28.0, 36.0, "谢谢大家的支持"),
    ]


def make_neutral_transcript() -> list:
    """负样本：正常科普口播，不应命中语用风险"""
    return [
        TranscriptSegment(0.0, 8.0, "今天我们来讲解一下机器学习的基本概念"),
        TranscriptSegment(8.0, 16.0, "首先看什么是监督学习和无监督学习"),
        TranscriptSegment(16.0, 24.0, "接下来演示一个简单的训练流程"),
        TranscriptSegment(24.0, 32.0, "本期内容就到这里，下期再见"),
    ]


def make_conflict(score: float, start: float = 10.0, end: float = 16.0) -> NarrativeConflict:
    return NarrativeConflict(
        kind="ocr_asr_mismatch",
        start=start,
        end=end,
        score=score,
        evidence=[
            {"modality": "asr", "span": [start, end], "text": "口播称完全自研"},
            {"modality": "ocr", "span": [start, start], "text": "GitHub"},
        ],
        explanation="口播主张与画面文字信号指向相反",
        confidence=0.6,
    )


def make_frames_with_flash() -> list:
    """平稳背景 + 单帧孤立尖峰（短闪现）"""
    frames = []
    for i in range(0, 20):
        frames.append(FrameObservation(
            timestamp=float(i), frame_id=f"f{i:03d}",
            description="主讲人口播", diff_score=0.03,
        ))
    frames.append(FrameObservation(
        timestamp=10.0, frame_id="f_flash",
        description="一闪而过的画面", ocr_text="内部文件",
        diff_score=0.95,
    ))
    frames.sort(key=lambda f: f.timestamp)
    return frames


def make_atoms(severity: float = 0.7, confidence: float = 0.6) -> list:
    """固定风险原子，供涌现单调性测试控制变量"""
    return build_risk_atoms(
        events=[],
        conflicts=[],
        pragmatics=[
            PragmaticRisk(
                risk_type="dog_whistle", start=0.0, end=6.0,
                score=severity, confidence=confidence,
                explanation="固定语用原子", evidence=[{"modality": "asr", "text": "x"}],
            )
        ],
        frames=[],
    )


# ─── L6: 叙事语用 ────────────────────────────────────────────


def test_dog_whistle_detected():
    analyzer = NarrativePragmaticsAnalyzer()
    risks = asyncio.run(analyzer.analyze(make_dog_whistle_transcript(), []))
    kinds = {r.risk_type for r in risks}
    assert "dog_whistle" in kinds, f"狗哨关键词应检出: {kinds}"
    hit = next(r for r in risks if r.risk_type == "dog_whistle")
    assert hit.confidence > 0.0
    assert 0.0 <= hit.score <= 1.0
    assert hit.audience_segments, "语用风险应标注可能被引爆的受众"
    assert hit.evidence, "语用风险必须带证据片段"
    print(f"  ✓ 狗哨检出: {hit.explanation[:40]}")


def test_insinuation_detected():
    analyzer = NarrativePragmaticsAnalyzer()
    segs = [
        TranscriptSegment(0.0, 8.0, "听说某个平台的数据都是刷出来的，假得很"),
        TranscriptSegment(8.0, 16.0, "我就不多说了，大家心里有数"),
    ]
    risks = asyncio.run(analyzer.analyze(segs, []))
    kinds = {r.risk_type for r in risks}
    assert "insinuation" in kinds or "dog_whistle" in kinds, f"影射/狗哨应检出: {kinds}"
    print(f"  ✓ 影射检出: {kinds}")


def test_provocation_detected():
    analyzer = NarrativePragmaticsAnalyzer()
    risks = asyncio.run(analyzer.analyze(make_provocation_transcript(), []))
    kinds = {r.risk_type for r in risks}
    assert "provocation" in kinds, f"对立主体并置应检出带节奏: {kinds}"
    hit = next(r for r in risks if r.risk_type == "provocation")
    assert hit.start < hit.end or hit.start == hit.end
    print(f"  ✓ 带节奏检出: span=[{hit.start},{hit.end}]")


def test_setup_payoff_detected():
    analyzer = NarrativePragmaticsAnalyzer()
    risks = asyncio.run(analyzer.analyze(make_setup_payoff_transcript(), []))
    kinds = {r.risk_type for r in risks}
    assert "setup_payoff" in kinds, f"先立靶后打应检出: {kinds}"
    hit = next(r for r in risks if r.risk_type == "setup_payoff")
    roles = {e.get("role") for e in hit.evidence if isinstance(e, dict)}
    assert "setup" in roles and "payoff" in roles, f"setup/payoff 证据角色应齐全: {roles}"
    assert hit.end - hit.start >= 4.0
    print(f"  ✓ setup-payoff 检出: span=[{hit.start:.0f},{hit.end:.0f}]")


def test_neutral_transcript_no_pragmatic_risk():
    analyzer = NarrativePragmaticsAnalyzer()
    risks = asyncio.run(analyzer.analyze(make_neutral_transcript(), []))
    assert risks == [], f"正常口播不应报语用风险: {[(r.risk_type, r.explanation) for r in risks]}"
    print("  ✓ 负样本无误报")


def test_pragmatics_llm_failure_degrades_to_rules():
    from backend.services import llm_client as lc

    analyzer = NarrativePragmaticsAnalyzer({"enable_llm": True})
    orig = lc.call_llm

    async def boom(*args, **kwargs):
        raise RuntimeError("offline")

    lc.call_llm = boom
    try:
        risks = asyncio.run(analyzer.analyze(make_dog_whistle_transcript(), []))
    finally:
        lc.call_llm = orig
    assert any(r.risk_type == "dog_whistle" for r in risks), "降级后规则结果必须保留"
    print("  ✓ LLM 失败降级为规则结果")


# ─── L7: 风险涌现 ────────────────────────────────────────────


def test_emergence_monotonic_in_conflict():
    """冲突强度上升 → emergent 单调上升（其余输入固定）"""
    atoms = make_atoms()
    scorer = RiskEmergenceScorer()
    prev_emergent = -1.0
    prev_score = -1.0
    for c_score in (0.2, 0.4, 0.6, 0.8, 0.95):
        summary = scorer.aggregate(
            atoms,
            conflicts=[make_conflict(c_score)],
            pragmatics=[],
            frames=[],
        )
        assert summary["emergent_score"] >= prev_emergent, (
            f"emergent 应随冲突单调不减: {c_score} → {summary['emergent_score']} < {prev_emergent}"
        )
        assert summary["risk_score"] >= prev_score, (
            f"总分应随冲突单调不减: {c_score} → {summary['risk_score']} < {prev_score}"
        )
        if prev_emergent >= 0 and summary["emergent_score"] == prev_emergent:
            pass
        prev_emergent = summary["emergent_score"]
        prev_score = summary["risk_score"]
    assert prev_emergent > 0.0, "强冲突下 emergent 必须为正"
    # 严格性：强冲突 emergent 应显著高于弱冲突
    weak = scorer.aggregate(atoms, conflicts=[make_conflict(0.2)], pragmatics=[], frames=[])
    strong = scorer.aggregate(atoms, conflicts=[make_conflict(0.9)], pragmatics=[], frames=[])
    assert strong["emergent_score"] > weak["emergent_score"]
    assert strong["risk_score"] > weak["risk_score"]
    print(f"  ✓ 涌现分单调: weak_e={weak['emergent_score']}, strong_e={strong['emergent_score']}")


def test_emergence_decomposition():
    atoms = make_atoms()
    conflicts = [make_conflict(0.8)]
    pragmatics = [PragmaticRisk(
        risk_type="dog_whistle", start=0.0, end=5.0, score=0.8, confidence=0.6,
        explanation="x", evidence=[{"modality": "asr", "text": "x"}],
    )]
    frames = make_frames_with_flash()
    scorer = RiskEmergenceScorer()
    summary = scorer.aggregate(atoms, conflicts=conflicts, pragmatics=pragmatics, frames=frames)

    assert 0.0 <= summary["risk_score"] <= 100.0
    assert 0.0 <= summary["base_score"] <= 100.0
    assert 0.0 <= summary["emergent_score"] <= 100.0
    assert summary["risk_score"] == min(100.0, max(0.0, summary["base_score"] + summary["emergent_score"]))

    comps = summary["components"]
    for key in ("conflict_amplify", "narrative_pragmatic", "short_flash"):
        assert key in comps, f"emergent 分量缺 {key}"
        assert comps[key] >= 0.0
    assert comps["conflict_amplify"] > 0.0, "强冲突应产生冲突放大项"
    assert comps["narrative_pragmatic"] > 0.0
    assert comps["short_flash"] > 0.0, "孤立尖峰帧应产生短闪现项"
    print(
        f"  ✓ 涌现分解: base={summary['base_score']}, emergent={summary['emergent_score']}, "
        f"comps={comps}"
    )


def test_emergence_anti_pseudo_precision():
    """反伪精确：区间 + 置信分解，低置信只给线索级别"""
    scorer = RiskEmergenceScorer()
    atoms = make_atoms(confidence=0.4)
    summary = scorer.aggregate(atoms, conflicts=[make_conflict(0.5)], pragmatics=[], frames=[])

    assert "risk_interval" in summary
    lo, hi = summary["risk_interval"]
    assert 0.0 <= lo <= summary["risk_score"] <= hi <= 100.0
    assert hi - lo > 0.0, "区间必须给出宽度，不给单点伪精确"

    conf = summary["confidence"]
    for key in ("conf_detect", "conf_confirm", "conf_context", "conf_provenance", "conf_total"):
        assert key in conf, f"置信分解缺 {key}"
        assert 0.0 <= conf[key] <= 1.0
    assert abs(conf["conf_total"] - (
        conf["conf_detect"] * conf["conf_confirm"] * conf["conf_context"] * conf["conf_provenance"]
    )) < 0.02
    assert summary["confidence_label"] in ("高置信结论", "疑似，建议人工复核", "线索")

    # 无原子 → 空结果仍带结构（不崩、不装高置信）
    empty = scorer.aggregate([], conflicts=[], pragmatics=[], frames=[])
    assert empty["risk_score"] == 0.0
    assert empty["confidence"]["conf_total"] < 0.75
    assert empty["confidence_label"] != "高置信结论"
    print(
        f"  ✓ 反伪精确: interval=[{lo:.1f},{hi:.1f}], "
        f"conf_total={conf['conf_total']}, label={summary['confidence_label']}"
    )


def test_short_flash_indicators():
    frames = make_frames_with_flash()
    flashes = short_flash_indicators(frames)
    assert flashes, "孤立帧差尖峰应检出短闪现"
    assert any(abs(f["start"] - 10.0) < 1e-6 for f in flashes)
    assert all(0.0 < f["intensity"] <= 1.0 for f in flashes)

    # 平稳帧序列不应误报
    calm = [
        FrameObservation(timestamp=float(i), frame_id=f"c{i}", diff_score=0.03)
        for i in range(10)
    ]
    assert short_flash_indicators(calm) == []
    print(f"  ✓ 短闪现检出: {len(flashes)} 个")


def test_build_risk_atoms_traceable():
    conflicts = [make_conflict(0.7)]
    pragmatics = [PragmaticRisk(
        risk_type="setup_payoff", start=0.0, end=20.0, score=0.7, confidence=0.6,
        explanation="x", trigger_events=["E2"],
        evidence=[{"modality": "asr", "text": "x"}],
    )]
    atoms = build_risk_atoms([], conflicts, pragmatics, make_frames_with_flash())
    assert atoms, "应产出风险原子"
    types = {a.atom_type for a in atoms}
    assert "modality_conflict" in types
    assert "narrative_pragmatic" in types
    assert "short_flash" in types
    for a in atoms:
        assert a.atom_id
        assert 0.0 <= a.severity <= 1.0
        assert 0.0 <= a.confidence <= 1.0
        assert a.explanation
    # 语用原子应携带 trigger_events
    pra = next(a for a in atoms if a.atom_type == "narrative_pragmatic")
    assert pra.event_id == "E2"
    print(f"  ✓ 风险原子可回溯: {len(atoms)} 个, types={types}")


# ─── Pipeline 集成 ───────────────────────────────────────────


def test_pipeline_outputs_pragmatics_and_emergence():
    frames = make_frames_with_flash()
    transcript = make_setup_payoff_transcript() + [
        TranscriptSegment(36.0, 42.0, "懂得都懂，我不说太细了"),
    ]
    result = asyncio.run(run_event_understanding(frames, transcript))
    assert not result.degraded, f"正常输入不应降级: {result.degrade_reason}"

    out = result.to_output_dict()
    # 新字段只增不删
    for key in (
        "events_summary", "selected_frame_reasons", "narrative_conflicts",
        "narrative_pragmatics", "emergence_summary", "event_understanding",
    ):
        assert key in out, f"输出缺字段 {key}"

    assert isinstance(out["narrative_pragmatics"], list)
    kinds = {p["risk_type"] for p in out["narrative_pragmatics"]}
    assert kinds, "合成样本应至少产出一条语用线索"
    for p in out["narrative_pragmatics"]:
        for key in ("risk_type", "explanation", "confidence", "audience_segments", "evidence"):
            assert key in p, f"narrative_pragmatics 缺字段 {key}"

    em = out["emergence_summary"]
    for key in (
        "risk_score", "risk_interval", "base_score", "emergent_score",
        "components", "confidence", "confidence_label", "risk_level", "risk_atoms",
    ):
        assert key in em, f"emergence_summary 缺字段 {key}"
    assert 0.0 <= em["risk_score"] <= 100.0
    assert em["risk_level"] in ("green", "yellow", "orange", "red")
    assert em["risk_atoms"], "应有事件级风险原子"

    meta = out["event_understanding"]
    assert "pragmatic_count" in meta
    print(
        f"  ✓ 管线输出: pragmatics={len(out['narrative_pragmatics'])}, "
        f"risk_score={em['risk_score']}, level={em['risk_level']}"
    )


def test_pipeline_empty_input_still_safe():
    result = asyncio.run(run_event_understanding([], ""))
    assert result.degraded
    out = result.to_output_dict()
    assert out["narrative_pragmatics"] == []
    assert out["emergence_summary"] == {}
    print("  ✓ 空输入降级且新字段安全")


def test_pipeline_config_overrides():
    pipeline = VideoEventUnderstandingPipeline({
        "emergence": {"lambda_conflict": 0.5, "lambda_flash": 0.1},
        "pragmatics": {"confidence_rule": 0.4},
    })
    result = asyncio.run(pipeline.run(make_frames_with_flash(), make_dog_whistle_transcript()))
    assert not result.degraded
    em = result.emergence_summary
    assert em["weights"]["lambda_conflict"] == 0.5
    assert em["weights"]["lambda_flash"] == 0.1
    if result.narrative_pragmatics:
        assert all(p.confidence <= 0.9 for p in result.narrative_pragmatics)
    print("  ✓ 配置覆盖生效")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
