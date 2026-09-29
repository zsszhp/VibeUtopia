from __future__ import annotations

"""叙事冲突检测（轻量启发式）

基于转写 + OCR 的时序窗口冲突/反转启发：
  1. polarity_reversal：前句肯定、后句否定（共享实体）
  2. ocr_asr_mismatch：画面字与口播关键词不一致
  3. claim_contradiction：声称类词汇与否定证据并置

不强制 LLM：规则路径永远可用；可选 LLM 增强失败即降级回规则结果。
"""

import logging
import re
from typing import Iterable, Optional

from backend.services.video_understanding.event_segmenter import (
    CLAIM_MARKERS,
    DISPLAY_MARKERS,
    NEGATION_MARKERS,
    _overlap,
    _tokenize,
)
from backend.services.video_understanding.models import (
    FrameObservation,
    NarrativeConflict,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "window_seconds": 8.0,          # 时序冲突窗
    "min_shared_tokens": 1,         # 冲突句对最少共享词数
    "confidence_rule": 0.55,        # 规则命中的默认置信（不过度承诺）
    "enable_llm": False,            # LLM 增强默认关闭，离线可跑
    "llm_timeout_seconds": 8.0,
}

# 肯定/否定短语（中文粗规则）
AFFIRM_PATTERNS = re.compile(
    r"(绝对是?|肯定是|一定是|就是|保证|完全(?:正确|没问题|真实)|没有(?:任何)?问题)"
)
NEGATE_PATTERNS = re.compile(
    r"(不是|并非|并不|否认|澄清|其实|实际上是|假的|错误的|不(?:是)?真的"
    r"|有(?:问题|风险|错误|缺陷)|存在[^，。]*(?:问题|缺陷|风险|错误))"
)

# OCR 与口播冲突的关键词对：口播侧 vs 画面字侧
MISMATCH_PAIRS = [
    (("自研", "原创", "自主研发", "我们开发"), ("github", "gitee", "fork", "开源", "open source", "clone")),
    (("国内", "国产", "中国"), ("海外", "国外", "abroad", "overseas")),
    (("免费", "不要钱", "零元"), ("收费", "付费", "会员", "订阅", "¥", "￥", "元/月")),
    (("官方", "正品", "授权"), ("破解", "盗版", "pj", "crack", "激活码")),
    (("没有广告", "无广告", "零广告"), ("广告", "sponsor", "推广", "带货")),
]


class NarrativeConflictDetector:
    """轻量叙事冲突检测：规则启发 + 可选 LLM 增强（失败降级）"""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def detect(
        self,
        transcript: Iterable[TranscriptSegment],
        frames: Iterable[FrameObservation] = (),
    ) -> list:
        """返回 NarrativeConflict 列表；任何内部失败都降级为空/规则结果。"""
        transcript = sorted(list(transcript or []), key=lambda s: s.start)
        frames = sorted(list(frames or []), key=lambda f: f.timestamp)

        conflicts: list = []
        try:
            conflicts.extend(self._polarity_reversal(transcript))
            conflicts.extend(self._ocr_asr_mismatch(transcript, frames))
            conflicts.extend(self._claim_contradiction(transcript, frames))
        except Exception as e:
            logger.warning("叙事冲突规则检测失败(降级): %s", e)
            return []

        if self.config.get("enable_llm"):
            try:
                conflicts = await self._llm_enhance(conflicts, transcript, frames)
            except Exception as e:
                logger.warning("叙事冲突 LLM 增强失败(降级回规则结果): %s", e)
        return self._dedup(conflicts)

    # ─── 规则 1: 前句肯定后句否定 ────────────────────────────

    def _polarity_reversal(self, transcript: list) -> list:
        out = []
        win = self.config["window_seconds"]
        for i in range(1, len(transcript)):
            prev, cur = transcript[i - 1], transcript[i]
            if cur.start - prev.end > win:
                continue
            prev_aff = bool(AFFIRM_PATTERNS.search(prev.text))
            cur_neg = bool(NEGATE_PATTERNS.search(cur.text))
            prev_neg = bool(NEGATE_PATTERNS.search(prev.text))
            cur_aff = bool(AFFIRM_PATTERNS.search(cur.text))
            if not ((prev_aff and cur_neg) or (prev_neg and cur_aff)):
                continue
            shared = _tokenize(prev.text) & _tokenize(cur.text)
            # 去掉纯单字虚词影响：要求至少 N 个实质共享 token
            if len(shared) < self.config["min_shared_tokens"]:
                continue
            out.append(NarrativeConflict(
                kind="polarity_reversal",
                start=prev.start,
                end=cur.end,
                score=0.6,
                evidence=[
                    {"modality": "asr", "span": [prev.start, prev.end], "text": prev.text[:120]},
                    {"modality": "asr", "span": [cur.start, cur.end], "text": cur.text[:120]},
                ],
                explanation="前后口播在共享主体上出现肯定→否定（或否定→肯定）反转",
                confidence=self.config["confidence_rule"],
            ))
        return out

    # ─── 规则 2: 画面字与口播不一致 ──────────────────────────

    def _ocr_asr_mismatch(self, transcript: list, frames: list) -> list:
        out = []
        if not transcript or not frames:
            return out
        win = self.config["window_seconds"]
        for f in frames:
            if not f.ocr_text.strip():
                continue
            ocr_tokens = _tokenize(f.ocr_text)
            for seg in transcript:
                if not (seg.start - win <= f.timestamp <= seg.end + win):
                    continue
                speech_tokens = _tokenize(seg.text)
                for speech_hits, ocr_hits in MISMATCH_PAIRS:
                    s_hit = any(h in seg.text.lower() for h in speech_hits)
                    o_hit = any(h in f.ocr_text.lower() for h in ocr_hits)
                    if s_hit and o_hit:
                        out.append(NarrativeConflict(
                            kind="ocr_asr_mismatch",
                            start=min(seg.start, f.timestamp),
                            end=max(seg.end, f.timestamp),
                            score=0.7,
                            evidence=[
                                {"modality": "asr", "span": [seg.start, seg.end], "text": seg.text[:120]},
                                {"modality": "ocr", "span": [f.timestamp, f.timestamp], "text": f.ocr_text[:120]},
                            ],
                            explanation="口播主张与画面文字信号指向相反（如口播称自研、画面出现开源托管字样）",
                            confidence=self.config["confidence_rule"] + 0.1,
                        ))
                        break
                _ = ocr_tokens, speech_tokens  # 保留分词结果供后续扩展
        return out

    # ─── 规则 3: 声称与否定证据并置 ──────────────────────────

    def _claim_contradiction(self, transcript: list, frames: list) -> list:
        out = []
        win = self.config["window_seconds"]
        # 声称句 + 同窗内否定词画面字/口播
        for seg in transcript:
            if not any(m in seg.text for m in CLAIM_MARKERS):
                continue
            # 同窗转写否定
            for other in transcript:
                if other is seg:
                    continue
                if abs(other.start - seg.start) > win:
                    continue
                if any(m in other.text for m in NEGATION_MARKERS) and _overlap(
                    _tokenize(seg.text), _tokenize(other.text)
                ) >= 0.15:
                    out.append(NarrativeConflict(
                        kind="claim_contradiction",
                        start=min(seg.start, other.start),
                        end=max(seg.end, other.end),
                        score=0.55,
                        evidence=[
                            {"modality": "asr", "span": [seg.start, seg.end], "text": seg.text[:120]},
                            {"modality": "asr", "span": [other.start, other.end], "text": other.text[:120]},
                        ],
                        explanation="主张类口播与同窗否定性口播共享主体，存在自我矛盾线索",
                        confidence=self.config["confidence_rule"],
                    ))
            # 同窗 OCR 否定/暴露证据
            for f in frames:
                if abs(f.timestamp - seg.start) > win:
                    continue
                blob = (f.ocr_text + " " + f.description).lower()
                if any(m in blob for m in DISPLAY_MARKERS) and any(m in blob for m in NEGATION_MARKERS):
                    out.append(NarrativeConflict(
                        kind="claim_contradiction",
                        start=min(seg.start, f.timestamp),
                        end=max(seg.end, f.timestamp),
                        score=0.6,
                        evidence=[
                            {"modality": "asr", "span": [seg.start, seg.end], "text": seg.text[:120]},
                            {"modality": "visual", "span": [f.timestamp, f.timestamp], "text": blob[:120]},
                        ],
                        explanation="主张类口播同窗出现否定/暴露型画面信息，存在欲盖弥彰线索",
                        confidence=self.config["confidence_rule"],
                    ))
        return out

    # ─── LLM 增强（可选，失败降级）──────────────────────────

    async def _llm_enhance(self, conflicts: list, transcript: list, frames: list) -> list:
        """用 LLM 复核/补充冲突；调用失败抛出，由上层降级回规则结果。"""
        if not conflicts and not transcript:
            return conflicts
        from backend.services.llm_client import call_llm, parse_llm_json

        asr_blob = "\n".join(f"[{t.start:.1f}-{t.end:.1f}] {t.text[:80]}" for t in transcript[:30])
        ocr_blob = "\n".join(f"[{f.timestamp:.1f}] {f.ocr_text[:60]}" for f in frames if f.ocr_text)[:1200]
        rule_hint = "\n".join(f"- {c.kind}: {c.explanation}" for c in conflicts[:8])
        prompt = (
            "以下是视频口播转写与画面OCR的时序片段。请仅输出JSON：\n"
            '{"conflicts": [{"kind": "polarity_reversal|ocr_asr_mismatch|claim_contradiction",'
            ' "start": 秒, "end": 秒, "score": 0-1, "explanation": "一句话"}]}\n'
            f"口播:\n{asr_blob}\n\nOCR:\n{ocr_blob}\n\n规则已发现线索:\n{rule_hint}\n"
            "若无冲突输出 {\"conflicts\": []}。不要臆造证据。"
        )
        resp = await call_llm(prompt, system="你是内容审核分析器，只输出JSON。", task_type="risk_analysis")
        data = parse_llm_json(resp, fallback={})
        llm_conflicts = []
        for item in (data.get("conflicts") or [])[:10]:
            if not isinstance(item, dict):
                continue
            try:
                llm_conflicts.append(NarrativeConflict(
                    kind=str(item.get("kind", "polarity_reversal")),
                    start=float(item.get("start", 0.0)),
                    end=float(item.get("end", 0.0)),
                    score=max(0.0, min(1.0, float(item.get("score", 0.5)))),
                    evidence=[{"modality": "llm", "text": str(item.get("explanation", ""))[:120]}],
                    explanation=str(item.get("explanation", ""))[:200],
                    confidence=0.5,  # LLM 单通道不过度承诺（P6 反伪精确）
                ))
            except (TypeError, ValueError):
                continue
        # LLM 结果并入规则结果而非覆盖
        return conflicts + llm_conflicts

    @staticmethod
    def _dedup(conflicts: list) -> list:
        seen = set()
        out = []
        for c in conflicts:
            key = (c.kind, round(c.start, 1), round(c.end, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        out.sort(key=lambda c: (c.start, c.end))
        return out
