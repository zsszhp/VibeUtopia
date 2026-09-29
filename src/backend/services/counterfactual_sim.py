from __future__ import annotations

"""反事实改写预估模块 — 阶段6

"如果修改了某个高风险句子，风险面会怎样变化？"

诚实化定性（本模块不声称全量仿真）：
- 改写由 rewriter/LLM 生成，失败时返回明确错误，不再产出占位符假句子
- 评分不再使用「固定衰减 min(原分*0.4, 30)」；优先对改写后文案重跑同一套静态评估，
  不可用时给出区间 + 方向性提示（允许"无改善/上升"结果）
- 输出一律标注「启发式预估，非全量仿真」
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DISCLAIMER = "启发式预估，非全量仿真。结果为改写前后的风险面方向性参考，不代表真实舆论传播结果。"

SEVERITY_SCORE_MAP = {"critical": 90, "high": 75, "medium": 50, "low": 25, "green": 10}


@dataclass
class ModificationStrategy:
    """修改策略"""
    strategy_id: str = ""
    strategy_type: str = ""        # delete / replace / soften / rephrase
    target_sentence: str = ""      # 目标句子
    modified_sentence: str = ""    # 修改后句子
    description: str = ""
    rewrite_note: str = ""         # 改写说明（来自 rewriter）


@dataclass
class SimulationResult:
    """单侧（改写前/后）风险面估计"""
    overall_risk_score: float = 0.0
    risk_level: str = "green"
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    platform_reactions: Dict[str, Dict] = field(default_factory=dict)
    key_findings: List[str] = field(default_factory=list)
    # 评分来源：risk_items_baseline / static_reevaluation / heuristic_range
    method: str = ""
    # heuristic_range 时的预估区间
    estimated_range: Optional[Dict[str, float]] = None


@dataclass
class BeforeAfterComparison:
    """修改前后对比"""
    dimension: str = ""
    before_score: float = 0.0
    after_score: float = 0.0
    change: float = 0.0
    change_direction: str = ""     # improved / worsened / unchanged


@dataclass
class CounterfactualResult:
    """反事实改写预估结果"""
    result_id: str = ""
    original_text: str = ""
    modified_text: str = ""
    strategy: Optional[ModificationStrategy] = None
    before: Optional[SimulationResult] = None
    after: Optional[SimulationResult] = None
    comparisons: List[BeforeAfterComparison] = field(default_factory=list)
    overall_improvement: float = 0.0
    # 诚实化字段
    improvement_range: Optional[Dict[str, float]] = None   # improvement 的预估区间
    direction_hint: str = ""       # likely_down / likely_up / uncertain
    confidence: str = "low"        # low / medium
    method: str = ""               # heuristic_rewrite_estimate / static_reevaluation
    disclaimer: str = DISCLAIMER
    recommendation: str = ""
    error: Optional[str] = None


class CounterfactualSimulator:
    """反事实改写预估器（非全量仿真）"""

    STRATEGY_TEMPLATES = {
        "delete": {
            "name": "删除策略",
            "description": "直接删除高风险句子",
        },
        "replace": {
            "name": "替换策略",
            "description": "用中性表述替换高风险内容",
        },
        "soften": {
            "name": "软化策略",
            "description": "保留核心意思但降低措辞强度",
        },
        "rephrase": {
            "name": "重述策略",
            "description": "用更安全的表达方式重新表述",
        },
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def simulate(self, text: str, risk_items: List[dict],
                        strategy_type: str = "soften") -> CounterfactualResult:
        """执行反事实改写预估

        Args:
            text: 原始文案
            risk_items: 风险项列表（含 dimension/severity/score/evidence）
            strategy_type: 修改策略类型

        Returns:
            CounterfactualResult
        """
        result = CounterfactualResult(
            result_id=str(uuid.uuid4())[:8],
            original_text=text,
            disclaimer=DISCLAIMER,
        )

        if not risk_items:
            result.error = "无风险项需要修改"
            result.recommendation = "当前文案无需修改"
            return result

        target_item = self._select_target_risk(risk_items)
        strategy, rewrite_error = await self._create_strategy(strategy_type, target_item)
        result.strategy = strategy

        if rewrite_error:
            result.error = rewrite_error
            result.recommendation = (
                f"改写失败：{rewrite_error}。未生成修改后文案，无法给出风险面预估。"
            )
            return result

        modified_text = self._apply_modification(text, strategy)
        result.modified_text = modified_text

        result.before = self._estimate_original(text, risk_items)

        after_result = await self._estimate_modified(modified_text, text, risk_items, strategy)
        result.after = after_result

        result.comparisons = self._compare_before_after(result.before, result.after)
        result.overall_improvement = self._calc_overall_improvement(result.before, result.after)
        result.method = self._resolve_method_label(after_result)
        result.improvement_range = self._calc_improvement_range(result.before, result.after)
        result.direction_hint = self._resolve_direction(result.before, result.after, result.improvement_range)
        result.confidence = "medium" if after_result.method == "static_reevaluation" else "low"
        result.recommendation = self._generate_recommendation(result)

        return result

    async def simulate_multi_strategy(self, text: str, risk_items: List[dict]) -> List[CounterfactualResult]:
        """多策略对比预估"""
        results = []
        for strategy_type in ["delete", "replace", "soften", "rephrase"]:
            r = await self.simulate(text, risk_items, strategy_type)
            results.append(r)

        results.sort(key=lambda r: r.overall_improvement, reverse=True)
        return results

    # ── 目标选择与改写 ──────────────────────────────────────

    def _select_target_risk(self, risk_items: List[dict]) -> dict:
        """选择最高优先级的风险项"""
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "green": 0}
        return max(
            risk_items,
            key=lambda x: (
                severity_order.get(x.get("severity", "green"), 0),
                x.get("score", 0),
            ),
        )

    async def _create_strategy(self, strategy_type: str,
                                target_item: dict) -> Tuple[ModificationStrategy, Optional[str]]:
        """创建修改策略。返回 (strategy, error)。error 非空表示改写失败。"""
        target_sentence = target_item.get("sentence") or target_item.get("evidence") or ""
        template = self.STRATEGY_TEMPLATES.get(strategy_type, self.STRATEGY_TEMPLATES["soften"])

        if not target_sentence.strip():
            return ModificationStrategy(
                strategy_id=str(uuid.uuid4())[:8],
                strategy_type=strategy_type,
                target_sentence="",
                modified_sentence="",
                description=template["description"],
            ), "风险项缺少可改写的原句文本（sentence/evidence 均为空）"

        if strategy_type == "delete":
            return ModificationStrategy(
                strategy_id=str(uuid.uuid4())[:8],
                strategy_type="delete",
                target_sentence=target_sentence,
                modified_sentence="",
                description=template["description"],
            ), None

        modified, note, error = await self._rewrite_via_llm(
            sentence=target_sentence,
            strategy_type=strategy_type,
            dimension=target_item.get("dimension", ""),
            severity=target_item.get("severity", "medium"),
        )
        if error:
            return ModificationStrategy(
                strategy_id=str(uuid.uuid4())[:8],
                strategy_type=strategy_type,
                target_sentence=target_sentence,
                modified_sentence="",
                description=template["description"],
            ), error

        return ModificationStrategy(
            strategy_id=str(uuid.uuid4())[:8],
            strategy_type=strategy_type,
            target_sentence=target_sentence,
            modified_sentence=modified,
            description=template["description"],
            rewrite_note=note,
        ), None

    async def _rewrite_via_llm(self, sentence: str, strategy_type: str,
                                dimension: str, severity: str) -> Tuple[str, str, Optional[str]]:
        """调用已有 rewriter 生成语义保留改写。返回 (改写句, 改写说明, error)。

        不再使用占位符拼接（[中性表述] / 第5字符插词 / 前缀套壳）。
        """
        try:
            from backend.services.rewriter import rewrite_sentence
        except Exception as e:
            return "", "", f"改写服务不可用: {e}"

        try:
            rw = await rewrite_sentence(sentence, dimension, severity)
        except Exception as e:
            logger.warning("改写调用失败: %s", e)
            return "", "", f"改写调用失败: {e}"

        if rw.get("is_transcript_noise"):
            return "", "", rw.get("transcript_note") or "该句疑似语音转写错误，请核实原文后再评估"

        if rw.get("is_redline"):
            return "", "", rw.get("redline_note") or "该内容触及红线维度，改写服务拒绝提供改写版本，建议不予发布"

        rewrites = rw.get("rewrites") or []
        rewrites = [r for r in rewrites if isinstance(r, dict) and (r.get("text") or "").strip()]
        if not rewrites:
            return "", "", "改写服务未返回有效改写结果，已拒绝生成占位改写句"

        # soften 偏保守版（通常第1条），replace/rephrase 偏清晰版（通常第2条）
        if strategy_type == "soften":
            picked = rewrites[0]
        else:
            picked = rewrites[-1]

        text = picked.get("text", "").strip()
        note = picked.get("rewrite_note", "")
        if not text:
            return "", "", "改写结果为空，已拒绝生成占位改写句"
        return text, note, None

    def _apply_modification(self, text: str, strategy: ModificationStrategy) -> str:
        """应用修改策略到文案"""
        if strategy.strategy_type == "delete":
            return text.replace(strategy.target_sentence, "").strip()

        if strategy.target_sentence in text:
            return text.replace(strategy.target_sentence, strategy.modified_sentence)

        return text + "\n" + strategy.modified_sentence

    # ── 改写前 / 改写后风险面估计 ──────────────────────────────

    def _estimate_original(self, text: str, risk_items: List[dict]) -> SimulationResult:
        """改写前基线：直接取风险评估产出的维度分，不做二次仿真。"""
        dim_scores: Dict[str, float] = {}
        for item in risk_items:
            dim = item.get("dimension", "未知")
            if "score" in item and item.get("score") is not None:
                try:
                    dim_scores[dim] = float(item["score"])
                    continue
                except (TypeError, ValueError):
                    pass
            severity = item.get("severity", "green")
            dim_scores[dim] = float(SEVERITY_SCORE_MAP.get(severity, 30))

        overall = sum(dim_scores.values()) / max(len(dim_scores), 1) if dim_scores else 20

        return SimulationResult(
            overall_risk_score=round(overall, 1),
            risk_level=self._score_to_level(overall),
            dimension_scores=dim_scores,
            platform_reactions=self._estimate_platform_reactions(overall),
            key_findings=[item.get("evidence", "")[:50] for item in risk_items[:3]],
            method="risk_items_baseline",
        )

    async def _estimate_modified(self, modified_text: str, original_text: str,
                                  risk_items: List[dict],
                                  strategy: ModificationStrategy) -> SimulationResult:
        """改写后风险面估计。

        优先对改写后文案重跑同一套静态评估；不可用时给出启发式区间估计
        （区间允许上升，不再保证"风险必降"）。
        """
        reeval = await self._try_static_reevaluation(modified_text)
        if reeval is not None:
            return reeval

        return self._heuristic_range_estimate(risk_items, strategy)

    async def _try_static_reevaluation(self, modified_text: str) -> Optional[SimulationResult]:
        """对改写后文案重跑静态评估（与原评估同一套 assessor）"""
        if not modified_text.strip():
            return None

        try:
            from backend.services.analyzer import calculate_overall_score
            from backend.services.risk_assessor import assess_risks
        except Exception as e:
            logger.warning("静态评估组件不可用，降级为启发式区间: %s", e)
            return None

        try:
            reeval = await assess_risks(modified_text)
        except Exception as e:
            logger.warning("改写后重评估失败，降级为启发式区间: %s", e)
            return None

        dims = reeval.get("dimensions") or []
        if not dims:
            logger.warning("改写后重评估无维度结果，降级为启发式区间")
            return None

        dim_scores = {}
        for d in dims:
            name = d.get("name", "未知")
            try:
                dim_scores[name] = float(d.get("score", 0))
            except (TypeError, ValueError):
                dim_scores[name] = 0.0

        try:
            overall, _, _ = calculate_overall_score(dims)
            overall = float(overall)
        except Exception:
            overall = sum(dim_scores.values()) / max(len(dim_scores), 1) if dim_scores else 20

        findings = [rs.get("evidence", "")[:50] for rs in (reeval.get("risk_sentences") or [])[:3]]
        return SimulationResult(
            overall_risk_score=round(overall, 1),
            risk_level=self._score_to_level(overall),
            dimension_scores=dim_scores,
            platform_reactions=self._estimate_platform_reactions(overall),
            key_findings=findings or ["已对改写后文案重跑静态评估"],
            method="static_reevaluation",
        )

    def _heuristic_range_estimate(self, risk_items: List[dict],
                                   strategy: ModificationStrategy) -> SimulationResult:
        """启发式区间估计（非全量仿真，非固定衰减）。

        - delete：目标风险句被移除，对应维度分预期下降，但不保证其他维度同步下降
        - replace/soften/rephrase：改写效果不确定，区间可覆盖上升
        """
        target_dim = ""
        for item in risk_items:
            target_sentence = item.get("sentence") or item.get("evidence") or ""
            if target_sentence and target_sentence == strategy.target_sentence:
                target_dim = item.get("dimension", "未知")
                break
        if not target_dim:
            target_dim = (risk_items[0].get("dimension", "未知") if risk_items else "未知")

        dim_scores: Dict[str, float] = {}
        dim_ranges: Dict[str, Tuple[float, float]] = {}
        for item in risk_items:
            dim = item.get("dimension", "未知")
            if "score" in item and item.get("score") is not None:
                try:
                    base = float(item["score"])
                except (TypeError, ValueError):
                    base = float(SEVERITY_SCORE_MAP.get(item.get("severity", "green"), 30))
            else:
                base = float(SEVERITY_SCORE_MAP.get(item.get("severity", "green"), 30))

            if dim == target_dim:
                if strategy.strategy_type == "delete":
                    # 句子移除后该维度证据减少：预期下降，但可能残留其他证据
                    low, high = max(0.0, base - 40), max(0.0, base - 10)
                else:
                    # 改写效果不确定：允许上升
                    low, high = max(0.0, base - 25), min(100.0, base + 15)
            else:
                # 非目标维度基本不动，仅留少量不确定性
                low, high = max(0.0, base - 5), min(100.0, base + 5)

            dim_ranges[dim] = (round(low, 1), round(high, 1))
            dim_scores[dim] = round((low + high) / 2, 1)

        overall_mid = sum(dim_scores.values()) / max(len(dim_scores), 1) if dim_scores else 20
        range_lows = [r[0] for r in dim_ranges.values()] or [overall_mid]
        range_highs = [r[1] for r in dim_ranges.values()] or [overall_mid]
        overall_low = round(sum(range_lows) / len(range_lows), 1)
        overall_high = round(sum(range_highs) / len(range_highs), 1)

        return SimulationResult(
            overall_risk_score=round(overall_mid, 1),
            risk_level=self._score_to_level(overall_mid),
            dimension_scores=dim_scores,
            platform_reactions=self._estimate_platform_reactions(overall_mid),
            key_findings=["启发式区间估计：改写效果未经完整重评估确认"],
            method="heuristic_range",
            estimated_range={"low": overall_low, "high": overall_high},
        )

    # ── 对比与建议 ──────────────────────────────────────

    def _compare_before_after(self, before: SimulationResult,
                               after: SimulationResult) -> List[BeforeAfterComparison]:
        """对比修改前后"""
        comparisons = []
        all_dims = set(list(before.dimension_scores.keys()) + list(after.dimension_scores.keys()))

        for dim in all_dims:
            b_score = before.dimension_scores.get(dim, 0)
            a_score = after.dimension_scores.get(dim, 0)
            change = a_score - b_score

            if change < -3:
                direction = "improved"
            elif change > 3:
                direction = "worsened"
            else:
                direction = "unchanged"

            comparisons.append(BeforeAfterComparison(
                dimension=dim,
                before_score=b_score,
                after_score=a_score,
                change=round(change, 1),
                change_direction=direction,
            ))

        return comparisons

    def _calc_overall_improvement(self, before: SimulationResult,
                                   after: SimulationResult) -> float:
        """计算总体变化（正数=风险下降，负数=风险上升）"""
        if not before or not after:
            return 0.0
        improvement = before.overall_risk_score - after.overall_risk_score
        return round(improvement, 1)

    def _calc_improvement_range(self, before: SimulationResult,
                                 after: SimulationResult) -> Optional[Dict[str, float]]:
        """improvement 的预估区间（仅启发式路径）"""
        if not after or after.method != "heuristic_range" or not after.estimated_range:
            return None
        before_score = before.overall_risk_score if before else 0.0
        # improvement = before - after，故 after 越大 improvement 越小
        low = round(before_score - after.estimated_range["high"], 1)
        high = round(before_score - after.estimated_range["low"], 1)
        return {"low": low, "high": high}

    def _resolve_method_label(self, after: SimulationResult) -> str:
        if after and after.method == "static_reevaluation":
            return "static_reevaluation"
        return "heuristic_rewrite_estimate"

    def _resolve_direction(self, before: SimulationResult, after: SimulationResult,
                            improvement_range: Optional[Dict[str, float]]) -> str:
        """方向性提示：down=风险面可能下降，up=可能上升，uncertain=不确定

        improvement = before - after，正值代表风险下降。
        仅当整个预估区间落在零轴一侧时才给 likely_*，跨零一律 uncertain。
        """
        if improvement_range:
            if improvement_range["high"] < 0:
                return "likely_up"
            if improvement_range["low"] > 0:
                return "likely_down"
            return "uncertain"

        # 点估计路径（重评估）：按变化幅度给方向，仍保留不确定性表述
        if not before or not after:
            return "uncertain"
        delta = before.overall_risk_score - after.overall_risk_score
        if delta > 3:
            return "likely_down"
        if delta < -3:
            return "likely_up"
        return "uncertain"

    def _generate_recommendation(self, result: CounterfactualResult) -> str:
        """生成修改建议（区间 + 方向性，不承诺"风险必降"）"""
        strategy_type = result.strategy.strategy_type if result.strategy else "该策略"
        before_score = result.before.overall_risk_score if result.before else 0
        after_score = result.after.overall_risk_score if result.after else 0

        if result.improvement_range:
            rng = result.improvement_range
            range_text = f"风险分变化约 {rng['low']:+.0f} ~ {rng['high']:+.0f} 分（正值=风险下降，负值=风险升高）"
        else:
            change = result.overall_improvement
            range_text = f"风险分变化约 {change:+.0f} 分（正值=风险下降，负值=风险升高）"

        if result.direction_hint == "likely_down":
            head = f"启发式预估：{strategy_type}策略可能降低风险面"
        elif result.direction_hint == "likely_up":
            head = f"启发式预估：{strategy_type}策略可能使风险面升高，请谨慎采用"
        else:
            head = f"启发式预估：{strategy_type}策略效果不确定，风险面可能下降也可能升高"

        body = f"{head}（{range_text}，改写前基线 {before_score:.0f} 分 → 预估 {after_score:.0f} 分）。"
        if result.strategy and result.strategy.rewrite_note:
            body += f"改写说明：{result.strategy.rewrite_note}。"
        body += DISCLAIMER
        return body

    # ── 辅助 ──────────────────────────────────────

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 80:
            return "red"
        if score >= 60:
            return "orange"
        if score >= 40:
            return "yellow"
        return "green"

    def _estimate_platform_reactions(self, risk_score: float) -> Dict[str, Dict]:
        """粗粒度平台反应倾向（线性启发式，仅作方向参考）"""
        negative = min(0.8, risk_score / 100)
        positive = max(0.1, 1 - negative - 0.3)
        neutral = 1 - positive - negative

        return {
            "weibo": {"positive": round(positive, 2), "neutral": round(neutral, 2), "negative": round(negative, 2)},
            "douyin": {"positive": round(positive + 0.05, 2), "neutral": round(neutral - 0.03, 2), "negative": round(negative - 0.02, 2)},
            "xiaohongshu": {"positive": round(positive + 0.1, 2), "neutral": round(neutral - 0.05, 2), "negative": round(negative - 0.05, 2)},
        }
