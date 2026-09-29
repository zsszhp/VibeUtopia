from __future__ import annotations

"""叙事语用启发（L6 轻量）—— 带节奏 / 狗哨影射 / setup-payoff

基于转写 + OCR 的规则与词表离线检测：
  1. provocation：对立主体并置 + 煽动框架词（带节奏）
  2. dog_whistle / insinuation：狗哨隐射关键词与影射句式
  3. setup_payoff：先立靶（树靶子/树权威主张）后打（反转/清算）

只产出线索与置信，不自动定罪。可选 LLM 增强失败即降级回规则结果。
"""

import logging
import re
from typing import Iterable, Optional

from backend.services.video_understanding.event_segmenter import (
    CLAIM_MARKERS,
    NEGATION_MARKERS,
    _overlap,
    _tokenize,
)
from backend.services.video_understanding.models import (
    FrameObservation,
    PragmaticRisk,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "window_seconds": 12.0,             # 对立主体并置的时间窗
    "setup_payoff_min_gap": 4.0,        # 立靶与清算的最小间隔
    "setup_payoff_max_gap": 180.0,      # 超过该间隔不再认为是同一叙事结构
    "min_shared_tokens": 1,             # setup-payoff 句对最少共享词数
    "confidence_rule": 0.55,            # 规则命中的默认置信（不过度承诺）
    "enable_llm": False,                # LLM 增强默认关闭，离线可跑
    "llm_timeout_seconds": 8.0,
}

# 对立主体并置（带节奏）：双方同时出现在短窗内 + 框架词 → 挑动对立线索
OPPOSING_PAIRS = [
    (("我们", "咱们", "自己人", "国人", "我们这边"), ("他们", "有些人", "某些人", "对岸", "海外", "他们那边")),
    (("男人", "男性", "男的"), ("女人", "女性", "女的")),
    (("本地人", "本地的"), ("外地人", "外地的")),
    (("粉丝", "支持者", "铁粉"), ("黑子", "喷子", "水军", "反对者", "杠精")),
    (("打工人", "员工", "打螺丝"), ("老板", "资本", "资本家", "管理层")),
    (("老玩家", "老用户", "元老"), ("萌新", "新人", "小白", "新用户")),
    (("正版", "原创"), ("盗版", "山寨", "抄袭", "剽窃")),
]

PROVOCATION_MARKERS = (
    "竟然", "居然", "凭什么", "双标", "歧视", "欺负", "挑衅", "叫板",
    "又来", "又在", "不是说", "难道", "怎么好意思", "真敢", "故意", "欺负人",
)

# 狗哨/隐射关键词：对外不明说、对内群体秒懂
DOG_WHISTLE_MARKERS = (
    "懂得都懂", "懂的都懂", "dddd", "细思极恐", "细思恐极",
    "自己品", "细品", "品一品", "我不说", "不敢说", "不能说",
    "某人", "某公司", "某平台", "某地", "某些人", "相关人士",
    "我就笑笑", "笑死我了", "呵呵", "yygq", "阴阳怪气",
    "猜猜是谁", "不会吧不会吧", "不会真有人",
)

INSINUATION_PATTERNS = re.compile(
    r"(有人(?:说|问|觉得|认为|爆料)|听说|据说|不知道(?:是谁|是哪个|是谁家)"
    r"|我(?:就)?不(?:点名|多说|展开)了|有个(?:人|公司|平台|群体))"
)

# setup-payoff：立靶（树靶子/树主张）与清算（反转/打脸）
SETUP_MARKERS = (
    "有人说", "总有人", "他们说", "经常有人", "有人黑", "有人质疑",
    "有人造谣", "先说清楚", "我要证明", "今天我就", "他们说我", "黑我的",
) + CLAIM_MARKERS

PAYOFF_MARKERS = (
    "其实", "实际上", "翻车", "打脸", "露馅", "被扒", "尴尬", "翻船",
    "并不", "并不是", "根本没", "从未有过", "假的", "谣言", "造谣", "抹黑",
    "清算", "反击", "澄清", "打假",
)

AUDIENCE_BY_TYPE = {
    "provocation": ["对立群体", "围观群众"],
    "dog_whistle": ["圈内知情群体", "被暗示群体"],
    "insinuation": ["被影射对象相关群体", "围观群众"],
    "setup_payoff": ["质疑方", "支持方"],
}


class NarrativePragmaticsAnalyzer:
    """叙事语用启发：规则 + 词表离线可跑；LLM 增强失败降级"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def analyze(
        self,
        transcript: Iterable[TranscriptSegment],
        frames: Iterable[FrameObservation] = (),
        events: Iterable = (),
    ) -> list:
        """返回 PragmaticRisk 列表；任何内部失败都降级为空/规则结果。"""
        transcript = sorted(list(transcript or []), key=lambda s: s.start)
        frames = sorted(list(frames or []), key=lambda f: f.timestamp)
        events = list(events or [])

        risks: list = []
        try:
            risks.extend(self._provocation(transcript, frames))
            risks.extend(self._dog_whistle(transcript, frames))
            risks.extend(self._insinuation(transcript, frames))
            risks.extend(self._setup_payoff(transcript, frames))
        except Exception as e:
            logger.warning("叙事语用规则检测失败(降级): %s", e)
            return []

        if self.config.get("enable_llm"):
            try:
                risks = await self._llm_enhance(risks, transcript, frames)
            except Exception as e:
                logger.warning("叙事语用 LLM 增强失败(降级回规则结果): %s", e)

        risks = self._dedup(risks)
        self._attach_events(risks, events)
        return risks

    # ─── 规则 1: 带节奏（对立主体并置） ──────────────────────

    def _provocation(self, transcript: list, frames: list) -> list:
        out = []
        win = self.config["window_seconds"]
        units = self._text_units(transcript, frames)
        for i in range(len(units)):
            for j in range(i, len(units)):
                a, b = units[i], units[j]
                if b["start"] - a["end"] > win:
                    break
                blob = a["text"] + " " + b["text"]
                for left, right in OPPOSING_PAIRS:
                    left_hit = any(h in blob for h in left)
                    right_hit = any(h in blob for h in right)
                    if not (left_hit and right_hit):
                        continue
                    if not any(m in blob for m in PROVOCATION_MARKERS):
                        continue
                    out.append(PragmaticRisk(
                        risk_type="provocation",
                        explanation=(
                            "对立主体在同一时序窗内并置，且出现煽动/不公框架词，存在带节奏线索"
                        ),
                        audience_segments=list(AUDIENCE_BY_TYPE["provocation"]),
                        confidence=self.config["confidence_rule"],
                        start=min(a["start"], b["start"]),
                        end=max(a["end"], b["end"]),
                        score=0.65,
                        evidence=[
                            {"modality": a["modality"], "span": [a["start"], a["end"]], "text": a["text"][:120]},
                            {"modality": b["modality"], "span": [b["start"], b["end"]], "text": b["text"][:120]},
                        ],
                    ))
                    break
        return out

    # ─── 规则 2: 狗哨关键词 ──────────────────────────────────

    def _dog_whistle(self, transcript: list, frames: list) -> list:
        out = []
        for unit in self._text_units(transcript, frames):
            hits = [m for m in DOG_WHISTLE_MARKERS if m in unit["text"].lower()]
            if not hits:
                continue
            out.append(PragmaticRisk(
                risk_type="dog_whistle",
                explanation=f"出现狗哨/隐射类关键词（{'、'.join(hits[:4])}），面向特定群体暗示",
                audience_segments=list(AUDIENCE_BY_TYPE["dog_whistle"]),
                confidence=min(0.85, self.config["confidence_rule"] + 0.05 * len(hits)),
                start=unit["start"],
                end=unit["end"],
                score=min(0.9, 0.5 + 0.1 * len(hits)),
                evidence=[{
                    "modality": unit["modality"],
                    "span": [unit["start"], unit["end"]],
                    "text": unit["text"][:120],
                    "hits": hits[:6],
                }],
            ))
        return out

    # ─── 规则 3: 影射句式 ────────────────────────────────────

    def _insinuation(self, transcript: list, frames: list) -> list:
        out = []
        for unit in self._text_units(transcript, frames):
            m = INSINUATION_PATTERNS.search(unit["text"])
            if not m:
                continue
            # 影射需带贬义/指控语境，纯转述不报
            if not any(t in unit["text"] for t in NEGATION_MARKERS + PAYOFF_MARKERS):
                if not any(w in unit["text"] for w in ("黑", "脏", "烂", "骗", "坑", "假", "抄")):
                    continue
            out.append(PragmaticRisk(
                risk_type="insinuation",
                explanation=f"出现不点名影射句式（{m.group(0)[:20]}），指向性不明但带指控语境",
                audience_segments=list(AUDIENCE_BY_TYPE["insinuation"]),
                confidence=self.config["confidence_rule"],
                start=unit["start"],
                end=unit["end"],
                score=0.55,
                evidence=[{
                    "modality": unit["modality"],
                    "span": [unit["start"], unit["end"]],
                    "text": unit["text"][:120],
                }],
            ))
        return out

    # ─── 规则 4: setup-payoff（先立靶后打） ──────────────────

    def _setup_payoff(self, transcript: list, frames: list) -> list:
        out = []
        min_gap = self.config["setup_payoff_min_gap"]
        max_gap = self.config["setup_payoff_max_gap"]
        for i, setup in enumerate(transcript):
            if not any(m in setup.text for m in SETUP_MARKERS):
                continue
            for payoff in transcript[i + 1:]:
                gap = payoff.start - setup.end
                if gap < min_gap:
                    continue
                if gap > max_gap:
                    break
                if not (
                    any(m in payoff.text for m in PAYOFF_MARKERS)
                    or any(m in payoff.text for m in NEGATION_MARKERS)
                ):
                    continue
                shared = _tokenize(setup.text) & _tokenize(payoff.text)
                if len(shared) < self.config["min_shared_tokens"]:
                    continue
                out.append(PragmaticRisk(
                    risk_type="setup_payoff",
                    explanation="前段立靶（树主张/树靶子）后段清算反转，构成 setup-payoff 叙事结构",
                    audience_segments=list(AUDIENCE_BY_TYPE["setup_payoff"]),
                    confidence=self.config["confidence_rule"] + 0.1,
                    start=setup.start,
                    end=payoff.end,
                    score=0.7,
                    evidence=[
                        {"modality": "asr", "span": [setup.start, setup.end], "text": setup.text[:120], "role": "setup"},
                        {"modality": "asr", "span": [payoff.start, payoff.end], "text": payoff.text[:120], "role": "payoff"},
                    ],
                ))
                break
        return out

    # ─── 辅助 ────────────────────────────────────────────────

    @staticmethod
    def _text_units(transcript: list, frames: list) -> list:
        """把转写与 OCR 统一成带时序的文本单元，便于跨模态并置检测。"""
        units = []
        for seg in transcript:
            if seg.text.strip():
                units.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "modality": "asr",
                })
        for f in frames:
            if f.ocr_text.strip() or f.description.strip():
                units.append({
                    "start": f.timestamp,
                    "end": f.timestamp,
                    "text": (f.ocr_text + " " + f.description).strip(),
                    "modality": "ocr" if f.ocr_text.strip() else "visual",
                })
        units.sort(key=lambda u: (u["start"], u["end"]))
        return units

    @staticmethod
    def _attach_events(risks: list, events: list) -> None:
        """把语用线索挂到时间覆盖的事件 id，供证据下钻。"""
        if not events:
            return
        for risk in risks:
            ids = []
            for ev in events:
                if ev.end < risk.start or ev.start > risk.end:
                    continue
                if getattr(ev, "event_id", ""):
                    ids.append(ev.event_id)
            risk.trigger_events = ids

    @staticmethod
    def _dedup(risks: list) -> list:
        seen = set()
        out = []
        for r in risks:
            key = (r.risk_type, round(r.start, 1), round(r.end, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        out.sort(key=lambda r: (r.start, r.end, r.risk_type))
        return out

    # ─── LLM 增强（可选，失败降级）──────────────────────────

    async def _llm_enhance(self, risks: list, transcript: list, frames: list) -> list:
        if not transcript and not frames:
            return risks
        from backend.services.llm_client import call_llm, parse_llm_json

        asr_blob = "\n".join(f"[{t.start:.1f}-{t.end:.1f}] {t.text[:80]}" for t in transcript[:30])
        ocr_blob = "\n".join(f"[{f.timestamp:.1f}] {f.ocr_text[:60]}" for f in frames if f.ocr_text)[:1200]
        rule_hint = "\n".join(f"- {r.risk_type}: {r.explanation}" for r in risks[:8])
        prompt = (
            "以下是视频口播转写与画面OCR的时序片段。请识别叙事语用风险，仅输出JSON：\n"
            '{"pragmatics": [{"risk_type": "provocation|dog_whistle|insinuation|setup_payoff",'
            ' "start": 秒, "end": 秒, "score": 0-1, "explanation": "一句话",'
            ' "audience_segments": ["群体"]}]}\n'
            f"口播:\n{asr_blob}\n\nOCR:\n{ocr_blob}\n\n规则已发现线索:\n{rule_hint}\n"
            "若无风险输出 {\"pragmatics\": []}。不要臆造证据。"
        )
        resp = await call_llm(prompt, system="你是内容审核分析器，只输出JSON。", task_type="risk_analysis")
        data = parse_llm_json(resp, fallback={})
        llm_risks = []
        for item in (data.get("pragmatics") or [])[:10]:
            if not isinstance(item, dict):
                continue
            try:
                llm_risks.append(PragmaticRisk(
                    risk_type=str(item.get("risk_type", "insinuation")),
                    explanation=str(item.get("explanation", ""))[:200],
                    audience_segments=[str(a) for a in (item.get("audience_segments") or [])][:6],
                    confidence=0.5,  # LLM 单通道不过度承诺（反伪精确）
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", 0.0)),
                    score=max(0.0, min(1.0, float(item.get("score", 0.5)))),
                    evidence=[{"modality": "llm", "text": str(item.get("explanation", ""))[:120]}],
                ))
            except (TypeError, ValueError):
                continue
        return risks + llm_risks
