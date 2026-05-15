from __future__ import annotations

"""反事实仿真模块 — 阶段6

"如果修改了某个高风险句子，舆论反应会怎样变化？"
生成反事实场景：修改文案→重新仿真→对比结果。
支持多种修改策略（删除/替换/软化语气），生成修改前后的对比报告。
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModificationStrategy:
    """修改策略"""
    strategy_id: str = ""
    strategy_type: str = ""        # delete / replace / soften / rephrase
    target_sentence: str = ""      # 目标句子
    modified_sentence: str = ""    # 修改后句子
    description: str = ""


@dataclass
class SimulationResult:
    """仿真结果"""
    overall_risk_score: float = 0.0
    risk_level: str = "green"
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    platform_reactions: Dict[str, Dict] = field(default_factory=dict)
    key_findings: List[str] = field(default_factory=list)


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
    """反事实仿真结果"""
    result_id: str = ""
    original_text: str = ""
    modified_text: str = ""
    strategy: Optional[ModificationStrategy] = None
    before: Optional[SimulationResult] = None
    after: Optional[SimulationResult] = None
    comparisons: List[BeforeAfterComparison] = field(default_factory=list)
    overall_improvement: float = 0.0
    recommendation: str = ""
    error: Optional[str] = None


class CounterfactualSimulator:
    """反事实仿真器"""

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
        """执行反事实仿真

        Args:
            text: 原始文案
            risk_items: 风险项列表
            strategy_type: 修改策略类型

        Returns:
            CounterfactualResult
        """
        result = CounterfactualResult(
            result_id=str(uuid.uuid4())[:8],
            original_text=text,
        )

        if not risk_items:
            result.error = "无风险项需要修改"
            result.recommendation = "当前文案无需修改"
            return result

        target_item = self._select_target_risk(risk_items)
        strategy = self._create_strategy(strategy_type, target_item, text)
        result.strategy = strategy

        modified_text = self._apply_modification(text, strategy)
        result.modified_text = modified_text

        result.before = self._simulate_original(text, risk_items)

        after_result = await self._simulate_modified(modified_text, text, risk_items)
        result.after = after_result

        result.comparisons = self._compare_before_after(result.before, result.after)
        result.overall_improvement = self._calc_overall_improvement(result.before, result.after)
        result.recommendation = self._generate_recommendation(result)

        return result

    async def simulate_multi_strategy(self, text: str, risk_items: List[dict]) -> List[CounterfactualResult]:
        """多策略对比仿真"""
        results = []
        for strategy_type in ["delete", "replace", "soften", "rephrase"]:
            r = await self.simulate(text, risk_items, strategy_type)
            results.append(r)

        results.sort(key=lambda r: r.overall_improvement, reverse=True)
        return results

    def _select_target_risk(self, risk_items: List[dict]) -> dict:
        """选择最高优先级的风险项"""
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "green": 0}
        return max(
            risk_items,
            key=lambda x: severity_order.get(x.get("severity", "green"), 0),
        )

    def _create_strategy(self, strategy_type: str, target_item: dict,
                         original_text: str) -> ModificationStrategy:
        """创建修改策略"""
        target_sentence = target_item.get("sentence", target_item.get("evidence", ""))
        template = self.STRATEGY_TEMPLATES.get(strategy_type, self.STRATEGY_TEMPLATES["soften"])

        modified = self._generate_modified_sentence(strategy_type, target_sentence)

        return ModificationStrategy(
            strategy_id=str(uuid.uuid4())[:8],
            strategy_type=strategy_type,
            target_sentence=target_sentence,
            modified_sentence=modified,
            description=template["description"],
        )

    def _generate_modified_sentence(self, strategy_type: str, sentence: str) -> str:
        """根据策略生成修改后句子"""
        if strategy_type == "delete":
            return ""

        if strategy_type == "replace":
            return f"[中性表述] {sentence[:20]}..."

        if strategy_type == "soften":
            softeners = ["可能", "或许", "一定程度上", "某种程度上"]
            import random
            softener = random.choice(softeners)
            if len(sentence) > 10:
                return sentence[:5] + softener + sentence[5:]
            return softener + sentence

        if strategy_type == "rephrase":
            return f"从另一个角度看，{sentence}"

        return sentence

    def _apply_modification(self, text: str, strategy: ModificationStrategy) -> str:
        """应用修改策略到文案"""
        if strategy.strategy_type == "delete":
            return text.replace(strategy.target_sentence, "").strip()

        if strategy.target_sentence in text:
            return text.replace(strategy.target_sentence, strategy.modified_sentence)

        return text + "\n" + strategy.modified_sentence

    def _simulate_original(self, text: str, risk_items: List[dict]) -> SimulationResult:
        """仿真原始文案结果"""
        dim_scores = {}
        for item in risk_items:
            dim = item.get("dimension", "未知")
            severity = item.get("severity", "green")
            score_map = {"critical": 90, "high": 75, "medium": 50, "low": 25, "green": 10}
            dim_scores[dim] = score_map.get(severity, 30)

        overall = sum(dim_scores.values()) / max(len(dim_scores), 1) if dim_scores else 20

        level = "green"
        if overall >= 80:
            level = "red"
        elif overall >= 60:
            level = "orange"
        elif overall >= 40:
            level = "yellow"

        return SimulationResult(
            overall_risk_score=round(overall, 1),
            risk_level=level,
            dimension_scores=dim_scores,
            platform_reactions=self._estimate_platform_reactions(overall),
            key_findings=[item.get("evidence", "")[:50] for item in risk_items[:3]],
        )

    async def _simulate_modified(self, modified_text: str, original_text: str,
                                  risk_items: List[dict]) -> SimulationResult:
        """仿真修改后文案结果"""
        dim_scores = {}
        for item in risk_items:
            dim = item.get("dimension", "未知")
            severity = item.get("severity", "green")
            score_map = {"critical": 90, "high": 75, "medium": 50, "low": 25, "green": 10}
            original_score = score_map.get(severity, 30)
            reduction = min(original_score * 0.4, 30)
            dim_scores[dim] = round(original_score - reduction, 1)

        overall = sum(dim_scores.values()) / max(len(dim_scores), 1) if dim_scores else 15

        try:
            llm_result = await self._llm_simulate(modified_text, original_text)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.warning("LLM仿真失败，使用规则降级: %s", e)

        level = "green"
        if overall >= 80:
            level = "red"
        elif overall >= 60:
            level = "orange"
        elif overall >= 40:
            level = "yellow"

        return SimulationResult(
            overall_risk_score=round(overall, 1),
            risk_level=level,
            dimension_scores=dim_scores,
            platform_reactions=self._estimate_platform_reactions(overall),
            key_findings=["修改后风险有所降低"],
        )

    async def _llm_simulate(self, modified_text: str, original_text: str) -> Optional[SimulationResult]:
        """使用LLM仿真修改后的舆论反应"""
        from backend.services.llm_client import call_llm

        prompt = f"""对比以下两段文案，预测修改后的舆论反应变化：

原始文案：{original_text[:500]}
修改后文案：{modified_text[:500]}

请以JSON格式返回预测结果：
```json
{{
  "overall_risk_score": 0-100,
  "risk_level": "green/yellow/orange/red",
  "dimension_scores": {{"维度名": 分数}},
  "key_findings": ["发现1", "发现2"],
  "platform_reactions": {{"weibo": {{"positive": 0.5, "neutral": 0.3, "negative": 0.2}}}}
}}
```"""

        try:
            response = await call_llm(prompt, task_type="default")
            import re
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = response.strip()

            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(json_str[start:end])
                return SimulationResult(
                    overall_risk_score=float(data.get("overall_risk_score", 30)),
                    risk_level=data.get("risk_level", "green"),
                    dimension_scores=data.get("dimension_scores", {}),
                    platform_reactions=data.get("platform_reactions", {}),
                    key_findings=data.get("key_findings", []),
                )
        except Exception as e:
            logger.warning("LLM仿真解析失败: %s", e)
        return None

    def _estimate_platform_reactions(self, risk_score: float) -> Dict[str, Dict]:
        """估算平台反应"""
        negative = min(0.8, risk_score / 100)
        positive = max(0.1, 1 - negative - 0.3)
        neutral = 1 - positive - negative

        return {
            "weibo": {"positive": round(positive, 2), "neutral": round(neutral, 2), "negative": round(negative, 2)},
            "douyin": {"positive": round(positive + 0.05, 2), "neutral": round(neutral - 0.03, 2), "negative": round(negative - 0.02, 2)},
            "xiaohongshu": {"positive": round(positive + 0.1, 2), "neutral": round(neutral - 0.05, 2), "negative": round(negative - 0.05, 2)},
        }

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
        """计算总体改善幅度"""
        if not before or not after:
            return 0.0
        improvement = before.overall_risk_score - after.overall_risk_score
        return round(improvement, 1)

    def _generate_recommendation(self, result: CounterfactualResult) -> str:
        """生成修改建议"""
        if result.overall_improvement > 20:
            return f"建议采用{result.strategy.strategy_type}策略，预计风险可降低{result.overall_improvement:.0f}分"
        elif result.overall_improvement > 10:
            return f"采用{result.strategy.strategy_type}策略有一定效果，风险降低{result.overall_improvement:.0f}分"
        elif result.overall_improvement > 0:
            return f"采用{result.strategy.strategy_type}策略效果有限，建议尝试其他策略"
        return "当前策略未能降低风险，建议重新审视内容"
