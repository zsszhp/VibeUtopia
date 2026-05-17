"""人格质量校验器 — 硬规则检查 + LLM软校验 + 自动修复"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.services.llm_client import call_llm, parse_llm_json

logger = logging.getLogger(__name__)


class QualityValidator:
    """人格一致性校验与修复"""

    # 硬规则定义: (检查函数, 修复建议)
    HARD_RULES = [
        # 规则1: 高学历 + 低认知水平 = 不一致
        (
            lambda p: _high_edu_low_cognitive(p),
            "高学历者认知水平不应为初级，已调整为中等",
        ),
        # 规则2: 低收入 + 高消费主义 = 不一致
        (
            lambda p: _low_income_high_consumerism(p),
            "低收入高消费主义不一致，已降低消费主义倾向",
        ),
        # 规则3: 激进表达 + 潜水 = 不一致
        (
            lambda p: _aggressive_lurker(p),
            "激进表达者不应为潜水模式，已调整为活跃评论",
        ),
        # 规则4: 高自我审查 + 无敏感触发 = 不一致
        (
            lambda p: _high_censorship_no_triggers(p),
            "高自我审查应有敏感触发点，已添加通用触发词",
        ),
        # 规则5: 情绪基线与近期经历矛盾
        (
            lambda p: _positive_baseline_negative_experiences(p),
            "积极基线与负面经历矛盾，已调整为平稳基线",
        ),
    ]

    def validate(self, persona: Dict[str, Any]) -> Tuple[float, List[str]]:
        """校验人格一致性

        Returns:
            (quality_score, issues) 质量分数0-1和问题列表
        """
        issues = []
        passed = 0
        total = len(self.HARD_RULES)

        for check_fn, message in self.HARD_RULES:
            if check_fn(persona):
                issues.append(message)
            else:
                passed += 1

        hard_score = passed / total if total > 0 else 1.0
        return hard_score, issues

    def auto_fix(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        """自动修复不一致的属性"""
        persona = _deep_copy_persona(persona)

        # 修复1: 高学历低认知
        if _high_edu_low_cognitive(persona):
            l1 = persona.get("L1_basic", {})
            edu = l1.get("education", "")
            if edu in ("本科", "硕士", "博士"):
                persona.setdefault("L3_knowledge", {})["cognitive_level"] = "中等"

        # 修复2: 低收入高消费
        if _low_income_high_consumerism(persona):
            l1 = persona.get("L1_basic", {})
            if l1.get("income", "") in ("低", "中低"):
                persona.setdefault("L2_values", {})["consumerism"] = 4.0

        # 修复3: 激进表达+潜水
        if _aggressive_lurker(persona):
            l4 = persona.get("L4_behavior", {})
            if l4.get("expression_style") == "激进":
                l4["interaction_preference"] = "活跃评论"

        # 修复4: 高审查无触发
        if _high_censorship_no_triggers(persona):
            l5 = persona.get("L5_correction", {})
            if l5.get("self_censorship") == "高":
                if not l5.get("sensitive_triggers"):
                    l5["sensitive_triggers"] = ["政治敏感话题", "人身攻击"]

        # 修复5: 积极基线负面经历
        if _positive_baseline_negative_experiences(persona):
            l7 = persona.get("L7_evolution", {})
            if l7.get("emotional_baseline") == "积极":
                l7["emotional_baseline"] = "平稳"

        return persona

    async def llm_validate(self, persona: Dict[str, Any]) -> Tuple[float, Optional[str]]:
        """LLM软校验：让LLM检查人格各层自洽性

        Returns:
            (score, fix_suggestion) 分数和建议
        """
        try:
            prompt = f"""请评估以下7层人格的自洽性，输出JSON：
{{"score": 0.0-1.0, "issues": ["问题1", "问题2"], "fix_suggestion": "修复建议"}}

人格数据：
{json.dumps(persona, ensure_ascii=False, indent=2)}

评估要点：
1. 各层属性之间是否逻辑自洽
2. 价值观与行为模式是否匹配
3. 知识背景与认知水平是否匹配
4. 社会关系与影响力是否匹配"""

            resp = await call_llm(prompt)
            data = parse_llm_json(resp)
            if data:
                score = float(data.get("score", 0.5))
                fix = data.get("fix_suggestion", "")
                return min(1.0, max(0.0, score)), fix
        except Exception as e:
            logger.debug(f"LLM软校验失败: {e}")

        return 0.5, None

    async def validate_and_fix(self, persona: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """完整校验+修复流程

        Returns:
            (fixed_persona, quality_score)
        """
        # 1. 硬规则自动修复
        fixed = self.auto_fix(persona)

        # 2. 硬规则评分
        hard_score, issues = self.validate(fixed)

        # 3. LLM软校验（可选，失败不影响）
        llm_score = None
        try:
            llm_score, fix_suggestion = await self.llm_validate(fixed)
            if fix_suggestion and llm_score < 0.6:
                logger.info(f"LLM建议修复: {fix_suggestion}")
        except Exception:
            pass

        # 4. 综合评分
        if llm_score is not None:
            quality_score = hard_score * 0.6 + llm_score * 0.4
        else:
            quality_score = hard_score

        return fixed, round(quality_score, 3)


# ── 硬规则检查函数 ──────────────────────────────────

def _high_edu_low_cognitive(p: dict) -> bool:
    edu = p.get("L1_basic", {}).get("education", "")
    cognitive = p.get("L3_knowledge", {}).get("cognitive_level", "中等")
    return edu in ("本科", "硕士", "博士") and cognitive == "初级"

def _low_income_high_consumerism(p: dict) -> bool:
    income = p.get("L1_basic", {}).get("income", "")
    consumerism = p.get("L2_values", {}).get("consumerism", 5.0)
    return income in ("低", "中低") and float(consumerism) >= 7.0

def _aggressive_lurker(p: dict) -> bool:
    style = p.get("L4_behavior", {}).get("expression_style", "")
    pref = p.get("L4_behavior", {}).get("interaction_preference", "")
    return style == "激进" and pref == "潜水"

def _high_censorship_no_triggers(p: dict) -> bool:
    censorship = p.get("L5_correction", {}).get("self_censorship", "")
    triggers = p.get("L5_correction", {}).get("sensitive_triggers", [])
    return censorship == "高" and (not triggers or len(triggers) == 0)

def _positive_baseline_negative_experiences(p: dict) -> bool:
    baseline = p.get("L7_evolution", {}).get("emotional_baseline", "")
    experiences = p.get("L7_evolution", {}).get("recent_experiences", [])
    negative_words = ["失业", "离婚", "被骗", "生病", "去世", "失败", "打击", "崩溃"]
    has_negative = any(w in str(experiences) for w in negative_words)
    return baseline == "积极" and has_negative

def _deep_copy_persona(p: dict) -> dict:
    """深拷贝人格字典"""
    import copy
    return copy.deepcopy(p)
