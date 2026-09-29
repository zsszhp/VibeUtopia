"""事件级视频理解单元测试（合成帧序列，离线可跑）

验证项：
1. EventSegmenter：帧差尖峰/话题切换能切出事件；kind/anchors 合理
2. AnchorSelector：事件边界/差异尖峰强制选帧；reason 字段齐全；覆盖度约束
3. NarrativeConflictDetector：肯定→否定反转、OCR 与口播不一致可检出
4. Pipeline：事件摘要与 selected_frame_reasons 可供 UI 下钻；空输入降级
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
    AnchorSelector,
    EventSegmenter,
    FrameObservation,
    NarrativeConflictDetector,
    TranscriptSegment,
    VideoEventUnderstandingPipeline,
    run_event_understanding,
)


# ─── 合成数据 ─────────────────────────────────────────────────


def make_frames() -> list:
    """60s 合成帧序列：0-15s 静态口播、15s 处帧差尖峰（场景切换）、
    15-30s 展示画面（OCR 出现 GitHub）、30s 处再次尖峰、30-60s 平稳。"""
    frames = []
    # 段 1: 平稳（diff≈0.02）
    for i in range(0, 15):
        frames.append(FrameObservation(
            timestamp=float(i),
            frame_id=f"f{i:03d}",
            image_path=f"/tmp/f{i:03d}.jpg",
            description="主讲人面对镜头口播",
            ocr_text="",
            diff_score=0.02,
        ))
    # 15s: 场景切换尖峰
    frames.append(FrameObservation(
        timestamp=15.0, frame_id="f015", image_path="/tmp/f015.jpg",
        description="切到电脑屏幕演示", ocr_text="项目文件夹",
        diff_score=0.92,
    ))
    # 段 2: 演示画面，OCR 有开源托管信息
    for i in range(16, 30):
        frames.append(FrameObservation(
            timestamp=float(i),
            frame_id=f"f{i:03d}",
            image_path=f"/tmp/f{i:03d}.jpg",
            description="屏幕展示项目目录",
            ocr_text="GitHub / ByteTrack / open source",
            diff_score=0.08,
        ))
    # 30s: 又一次尖峰（短暂画面）
    frames.append(FrameObservation(
        timestamp=30.0, frame_id="f030", image_path="/tmp/f030.jpg",
        description="闪过一张完整地图", ocr_text="中国地图",
        diff_score=0.88,
    ))
    # 段 3: 回到口播
    for i in range(31, 60):
        frames.append(FrameObservation(
            timestamp=float(i),
            frame_id=f"f{i:03d}",
            image_path=f"/tmp/f{i:03d}.jpg",
            description="主讲人总结",
            ocr_text="",
            diff_score=0.03,
        ))
    return frames


def make_transcript() -> list:
    """与帧序列配套的转写：前段肯定自研，中段画面暴露开源，后段否定澄清。"""
    return [
        TranscriptSegment(0.0, 8.0, "这是我们完全自主研发的系统"),
        TranscriptSegment(8.0, 14.0, "整个底层都是我们自己写的代码"),
        TranscriptSegment(16.0, 24.0, "大家看这个项目目录结构"),
        TranscriptSegment(24.0, 29.0, "这里放的是核心模块文件"),
        TranscriptSegment(32.0, 40.0, "其实之前说自研并不准确"),
        TranscriptSegment(40.0, 50.0, "有部分是基于开源组件做的"),
        TranscriptSegment(50.0, 58.0, "感谢大家观看"),
    ]


# ─── EventSegmenter ──────────────────────────────────────────


def test_event_segmenter_basic():
    seg = EventSegmenter()
    events = seg.segment(make_frames(), make_transcript())
    assert events, "应至少切出一个事件"
    # 时间轴完整覆盖（末帧即时间轴终点）
    assert events[0].start == 0.0
    assert abs(events[-1].end - make_frames()[-1].timestamp) < 1e-6
    # 相邻事件无缝衔接
    for a, b in zip(events, events[1:]):
        assert abs(a.end - b.start) < 1e-6, f"事件不连续: {a} -> {b}"
    # 每个事件字段完整
    for ev in events:
        assert ev.event_id
        assert ev.end > ev.start
        assert 0.0 <= ev.score <= 1.0
        assert ev.kind in ("scene", "action", "claim", "display", "speech_act")
        assert ev.anchors, "事件应有锚点"
    print(f"  ✓ 事件切分: {len(events)} 个事件, kinds={[e.kind for e in events]}")


def test_event_segmenter_detects_scene_boundary():
    """15s/30s 帧差尖峰应产生边界，事件数应多于 1"""
    seg = EventSegmenter()
    events = seg.segment(make_frames(), make_transcript())
    assert len(events) >= 2, f"场景尖峰应切出多事件，实际 {len(events)}"
    # 15s 尖峰附近应有某个事件边界
    boundaries = [e.start for e in events] + [e.end for e in events]
    assert any(abs(b - 15.0) < 2.0 for b in boundaries), f"15s 尖峰未形成边界: {boundaries}"
    print(f"  ✓ 场景边界: 边界点={sorted(set(round(b,1) for b in boundaries))}")


def test_event_segmenter_kind_and_modalities():
    seg = EventSegmenter()
    events = seg.segment(make_frames(), make_transcript())
    # 含“自研”主张的事件应为 claim
    claim_events = [e for e in events if e.kind == "claim"]
    assert claim_events, f"应有 claim 事件, 实际 kinds={[e.kind for e in events]}"
    # 含口播的事件应带 asr 模态
    asr_events = [e for e in events if "asr" in e.modalities]
    assert asr_events
    print(f"  ✓ 事件分类: claim={len(claim_events)}, asr={len(asr_events)}")


def test_event_segmenter_empty_input():
    seg = EventSegmenter()
    assert seg.segment([], []) == []
    print("  ✓ 空输入返回空事件列表")


def test_event_segmenter_transcript_only():
    """无帧仅转写时也能切分（离线降级路径）"""
    seg = EventSegmenter()
    events = seg.segment([], make_transcript())
    assert events, "纯转写应能切出事件"
    print(f"  ✓ 纯转写切分: {len(events)} 事件")


# ─── AnchorSelector ──────────────────────────────────────────


def test_anchor_selector_reasons_and_boundaries():
    frames = make_frames()
    events = EventSegmenter().segment(frames, make_transcript())
    selector = AnchorSelector({"budget": 20})
    selected = selector.select(frames, events, budget=20)

    assert selected, "应选中帧"
    assert len(selected) <= len(frames)
    # reason 字段齐全且合法
    valid_reasons = {"event_boundary", "high_density", "diff_spike", "coverage", "budget_fill"}
    for s in selected:
        assert s.reason, "每帧必须有 reason"
        for token in s.reason.split("+"):
            assert token in valid_reasons, f"非法 reason: {token}"
        assert s.frame_id
    # 时间升序
    times = [s.timestamp for s in selected]
    assert times == sorted(times)
    print(f"  ✓ 选帧 reason: {len(selected)} 帧, reasons={sorted(set(s.reason for s in selected))}")


def test_anchor_selector_forces_boundary_and_spike():
    frames = make_frames()
    events = EventSegmenter().segment(frames, make_transcript())
    selected = AnchorSelector().select(frames, events, budget=10)
    reasons = [s.reason for s in selected]
    assert any("event_boundary" in r for r in reasons), "事件边界帧必须强制选中"
    assert any("diff_spike" in r for r in reasons), "帧差尖峰（15s/30s）必须强制选中"
    # 尖峰帧 f015 / f030 必须在选中集合
    ids = {s.frame_id for s in selected}
    assert "f015" in ids, "15s 场景切换帧必须选中"
    assert "f030" in ids, "30s 短暂画面帧必须选中"
    print(f"  ✓ 强制锚点: f015/f030 均被选中, ids 命中={sorted(ids)[:8]}...")


def test_anchor_selector_budget_respected():
    frames = make_frames()
    events = EventSegmenter().segment(frames, make_transcript())
    for budget in (5, 12, 30):
        selected = AnchorSelector().select(frames, events, budget=budget)
        # 强制锚点可以超过纯 budget，但不应超过帧总数
        assert 0 < len(selected) <= len(frames)
    print("  ✓ 预算参数可调且不越界")


def test_anchor_selector_coverage_constraint():
    """覆盖度约束：任意 30s 窗内至少 1 帧"""
    frames = make_frames()
    events = EventSegmenter().segment(frames, make_transcript())
    selector = AnchorSelector({"coverage_gap_seconds": 30.0})
    # 极小预算仍要触发覆盖补帧
    selected = selector.select(frames, events, budget=3)
    times = [s.timestamp for s in selected]
    t0, t1 = frames[0].timestamp, frames[-1].timestamp
    t = t0
    while t < t1 - 1e-6:
        window_end = min(t + 30.0, t1 + 1e-6)
        hit = any(t - 1e-6 <= x < window_end - 1e-6 for x in times)
        assert hit, f"覆盖度缺口: [{t}, {window_end})"
        t = window_end
    print(f"  ✓ 覆盖度约束: 30s 窗全覆盖, 选中={len(selected)} 帧")


def test_anchor_selector_empty_frames():
    assert AnchorSelector().select([], [], budget=10) == []
    print("  ✓ 空帧输入返回空列表")


# ─── NarrativeConflictDetector ───────────────────────────────


def test_conflict_polarity_reversal():
    transcript = [
        TranscriptSegment(0.0, 5.0, "这个产品绝对没有问题，质量非常好"),
        TranscriptSegment(5.5, 10.0, "其实之前说没有问题并不准确，产品存在缺陷"),
    ]
    detector = NarrativeConflictDetector()
    conflicts = asyncio.run(detector.detect(transcript, []))
    kinds = [c.kind for c in conflicts]
    assert "polarity_reversal" in kinds, f"应检出肯定→否定反转, 实际 {kinds}"
    rev = next(c for c in conflicts if c.kind == "polarity_reversal")
    assert rev.end > rev.start
    assert rev.evidence and len(rev.evidence) == 2
    assert 0 < rev.confidence <= 1
    print(f"  ✓ 极性反转检出: score={rev.score}, conf={rev.confidence}")


def test_conflict_ocr_asr_mismatch():
    """口播称自研、画面 OCR 出现 GitHub → 应检出不一致"""
    transcript = [
        TranscriptSegment(10.0, 18.0, "这是我们完全自主研发的系统"),
    ]
    frames = [
        FrameObservation(timestamp=14.0, frame_id="f014", ocr_text="GitHub repository"),
    ]
    detector = NarrativeConflictDetector()
    conflicts = asyncio.run(detector.detect(transcript, frames))
    kinds = [c.kind for c in conflicts]
    assert "ocr_asr_mismatch" in kinds, f"应检出口播/画面不一致, 实际 {kinds}"
    m = next(c for c in conflicts if c.kind == "ocr_asr_mismatch")
    mods = {e["modality"] for e in m.evidence}
    assert "asr" in mods and "ocr" in mods
    print(f"  ✓ OCR/口播不一致检出: score={m.score}")


def test_conflict_claim_contradiction():
    """主张句 + 同窗否定句 → claim_contradiction"""
    transcript = [
        TranscriptSegment(0.0, 5.0, "我们保证全程自研没有任何外部代码"),
        TranscriptSegment(6.0, 11.0, "实际上并不是自研，借鉴了很多外部代码"),
    ]
    detector = NarrativeConflictDetector()
    conflicts = asyncio.run(detector.detect(transcript, []))
    kinds = [c.kind for c in conflicts]
    assert "claim_contradiction" in kinds or "polarity_reversal" in kinds, f"应检出主张矛盾, 实际 {kinds}"
    print(f"  ✓ 主张矛盾检出: kinds={kinds}")


def test_conflict_no_false_positive_on_consistent():
    transcript = [
        TranscriptSegment(0.0, 5.0, "今天天气不错适合出门"),
        TranscriptSegment(5.0, 10.0, "我们去公园散步吧"),
        TranscriptSegment(10.0, 15.0, "路上买了一杯咖啡"),
    ]
    frames = [
        FrameObservation(timestamp=2.0, frame_id="f002", ocr_text="公园入口"),
        FrameObservation(timestamp=12.0, frame_id="f012", ocr_text="咖啡店"),
    ]
    detector = NarrativeConflictDetector()
    conflicts = asyncio.run(detector.detect(transcript, frames))
    assert conflicts == [], f"一致内容不应误报, 实际 {conflicts}"
    print("  ✓ 一致内容零误报")


def test_conflict_llm_failure_degrades():
    """LLM 增强开启但调用失败时，必须降级回规则结果而不是抛错"""
    transcript = [
        TranscriptSegment(0.0, 5.0, "这个产品绝对没有问题"),
        TranscriptSegment(5.5, 10.0, "其实产品存在严重问题"),
    ]
    detector = NarrativeConflictDetector({"enable_llm": True})

    async def _run():
        # 强制 LLM 失败：monkeypatch call_llm
        import backend.services.llm_client as lc
        orig = lc.call_llm

        async def boom(*args, **kwargs):
            raise RuntimeError("offline")

        lc.call_llm = boom
        try:
            return await detector.detect(transcript, [])
        finally:
            lc.call_llm = orig

    conflicts = asyncio.run(_run())
    assert any(c.kind == "polarity_reversal" for c in conflicts), "降级后规则结果必须保留"
    print("  ✓ LLM 失败降级为规则结果")


# ─── Pipeline 集成 ───────────────────────────────────────────


def test_pipeline_output_for_ui_drilldown():
    result = asyncio.run(run_event_understanding(make_frames(), make_transcript()))
    assert not result.degraded, f"正常输入不应降级: {result.degrade_reason}"
    assert result.events_summary, "events_summary 必须产出"
    assert result.selected_frame_reasons, "selected_frame_reasons 必须产出"

    # events_summary 字段可下钻
    for ev in result.events_summary:
        for key in ("event_id", "start", "end", "kind", "score", "anchors", "summary"):
            assert key in ev, f"events_summary 缺字段 {key}"

    # selected_frame_reasons 字段可下钻
    for fr in result.selected_frame_reasons:
        for key in ("frame_id", "timestamp", "reason", "score"):
            assert key in fr, f"selected_frame_reasons 缺字段 {key}"
        assert fr["reason"]

    out = result.to_output_dict()
    assert "events_summary" in out
    assert "selected_frame_reasons" in out
    assert "narrative_conflicts" in out
    assert "event_understanding" in out
    print(
        f"  ✓ 管线输出: events={len(result.events_summary)}, "
        f"frames={len(result.selected_frame_reasons)}, "
        f"conflicts={len(result.conflicts)}"
    )


def test_pipeline_empty_input_degrades_gracefully():
    result = asyncio.run(run_event_understanding([], ""))
    assert result.degraded
    assert result.degrade_reason == "empty_input"
    assert result.events_summary == []
    assert result.selected_frame_reasons == []
    print("  ✓ 空输入优雅降级")


def test_pipeline_accepts_dict_frames():
    """dict 形态帧输入（主流程适配层会传 dict）"""
    frames = [
        {"timestamp": 0.0, "frame_id": "a", "diff_score": 0.01},
        {"timestamp": 1.0, "frame_id": "b", "diff_score": 0.9, "ocr_text": "github"},
    ]
    result = asyncio.run(run_event_understanding(frames, "这是自研系统"))
    assert not result.degraded or result.degrade_reason == "empty_input"
    assert result.events_summary or result.degraded
    print("  ✓ dict 帧输入可用")


def test_pipeline_api_compatible_fields():
    """新增字段只增不删：to_output_dict 必须包含老接口兼容键"""
    result = asyncio.run(run_event_understanding(make_frames(), make_transcript()))
    out = result.to_output_dict()
    # 兼容性：新键必须存在（即便为空列表）
    for key in ("events_summary", "selected_frame_reasons", "narrative_conflicts", "event_understanding"):
        assert key in out
    print("  ✓ API 字段兼容（只增不删）")


def test_frames_from_delta_adapter():
    """DeltaFrame → FrameObservation 适配器"""
    from types import SimpleNamespace
    from backend.services.video_understanding.pipeline import frames_from_delta_frames

    fake = [
        SimpleNamespace(timestamp=1.5, index=3, file_path="/x/3.jpg", delta_score=0.4),
        SimpleNamespace(timestamp=2.5, index=4, file_path="/x/4.jpg", delta_score=0.1),
    ]
    obs = frames_from_delta_frames(fake)
    assert len(obs) == 2
    assert obs[0].timestamp == 1.5
    assert obs[0].diff_score == 0.4
    assert obs[0].image_path == "/x/3.jpg"
    assert frames_from_delta_frames(None) == []
    print("  ✓ DeltaFrame 适配器正确")


def test_event_understanding_result_summary_fields():
    """VideoEventUnderstandingPipeline 的输出结构稳定性"""
    pipeline = VideoEventUnderstandingPipeline()
    result = asyncio.run(pipeline.run(make_frames(), make_transcript(), frame_budget=15))
    assert result.method_used.startswith("heuristic")
    assert isinstance(result.events, list)
    assert isinstance(result.selected_frames, list)
    assert isinstance(result.conflicts, list)
    # 选帧总数应不大于帧总数，且 budget=15 时强制锚点可略超但有上界
    assert len(result.selected_frames) <= len(make_frames())
    print(f"  ✓ 结果结构稳定: method={result.method_used}")


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
    sys.exit(1 if failed else 0)
