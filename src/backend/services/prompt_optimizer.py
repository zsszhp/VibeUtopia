"""T4 Prompt 迭代优化器 — 基于回测案例库优化风险评估 Prompt

通过分析回测未命中案例，识别 Prompt 中的问题，自动调整：
1. 维度权重
2. 评分阈值规则
3. 交叉影响规则
4. 维度定义描述

使用 T2.2 的 Prompt 版本管理器记录每次迭代。
"""
import copy
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.services.backtest_cases import BacktestCase, get_all_cases
from backend.services.prompt_version_manager import PromptVersionManager
from backend.services.backtest_runner import BacktestRunner, score_to_level

logger = logging.getLogger(__name__)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class PromptOptimizer:
    """Prompt 迭代优化器"""

    def __init__(self, prompt_name: str = "risk_assessment"):
        self.prompt_name = prompt_name
        self.mgr = PromptVersionManager()
        self.cases = get_all_cases()
        self.iteration_history: List[Dict[str, Any]] = []

    def analyze_missed_cases(
        self,
        backtest_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """分析未命中案例，识别问题模式

        Args:
            backtest_results: 回测结果

        Returns:
            问题分析报告
        """
        missed = [r for r in backtest_results if not r.get("level_match", False)]
        case_map = {c.case_id: c for c in self.cases}

        # 按类别分组未命中案例
        by_category: Dict[str, List] = {}
        by_dimension: Dict[str, int] = {}
        by_expected_level: Dict[str, List] = {}

        for result in missed:
            case = case_map.get(result.get("case_id"))
            if not case:
                continue

            cat = case.category.value
            expected = case.expected_risk_level.value

            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(result)

            if expected not in by_expected_level:
                by_expected_level[expected] = []
            by_expected_level[expected].append(result)

            # 统计涉及的维度
            for dim in result.get("dimensions", []):
                dim_name = dim.get("name", "unknown")
                by_dimension[dim_name] = by_dimension.get(dim_name, 0) + 1

        # 识别问题模式
        patterns = []

        # 模式 1: 某类别集中未命中
        for cat, results in by_category.items():
            cat_cases = [c for c in self.cases if c.category.value == cat]
            hit_rate = len(cat_cases) - len(results)
            if len(results) >= 2:
                patterns.append({
                    "type": "category_low_accuracy",
                    "category": cat,
                    "missed_count": len(results),
                    "hit_rate": round(hit_rate / len(cat_cases), 4) if cat_cases else 0,
                })

        # 模式 2: 某维度频繁出现
        for dim_name, count in sorted(by_dimension.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count >= 2:
                patterns.append({
                    "type": "dimension_frequent",
                    "dimension": dim_name,
                    "count": count,
                })

        # 模式 3: 高风险案例未命中
        if by_expected_level.get("high"):
            patterns.append({
                "type": "high_risk_missed",
                "count": len(by_expected_level["high"]),
                "cases": [r.get("case_name") for r in by_expected_level["high"]],
            })

        # 模式 4: 评分差距分析
        score_gaps = []
        for result in missed:
            case = case_map.get(result.get("case_id"))
            if case:
                expected_mid = (case.expected_overall_score_range[0] + case.expected_overall_score_range[1]) / 2
                actual = result.get("overall_score", 0)
                gap = actual - expected_mid
                score_gaps.append({
                    "case_name": case.case_name,
                    "expected_mid": expected_mid,
                    "actual": actual,
                    "gap": gap,
                })

        avg_gap = sum(abs(sg["gap"]) for sg in score_gaps) / len(score_gaps) if score_gaps else 0
        systematic_bias = "underestimate" if sum(sg["gap"] for sg in score_gaps) < 0 else "overestimate"

        analysis = {
            "total_missed": len(missed),
            "by_category": {k: len(v) for k, v in by_category.items()},
            "by_expected_level": {k: len(v) for k, v in by_expected_level.items()},
            "dimension_frequency": by_dimension,
            "patterns": patterns,
            "score_gaps": score_gaps,
            "avg_gap": round(avg_gap, 2),
            "systematic_bias": systematic_bias,
        }

        return analysis

    def generate_optimization_suggestions(
        self,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """基于问题分析生成优化建议"""
        suggestions = []

        for pattern in analysis.get("patterns", []):
            ptype = pattern.get("type")

            # 建议 1: 某类别准确率低
            if ptype == "category_low_accuracy":
                cat = pattern.get("category")
                if cat == "ethics":
                    suggestions.append({
                        "target": "道德伦理维度",
                        "action": "降低 HIGH 阈值",
                        "reason": f"道德伦理类别准确率仅{pattern.get('hit_rate', 0)*100:.0f}%",
                        "change": "将道德伦理 HIGH 阈值从 76 降至 70",
                        "priority": "high",
                    })
                elif cat == "consumer":
                    suggestions.append({
                        "target": "消费欺诈维度",
                        "action": "增加权重",
                        "reason": f"消费维权类别未命中{pattern.get('missed_count')}例",
                        "change": "将消费欺诈相关维度权重从 1.0 提升至 1.2",
                        "priority": "medium",
                    })

            # 建议 2: 某维度频繁出现问题
            elif ptype == "dimension_frequent":
                dim = pattern.get("dimension")
                suggestions.append({
                    "target": f"{dim}维度",
                    "action": "优化评分规则",
                    "reason": f"该维度在未命中案例中出现{pattern.get('count')}次",
                    "change": f"细化{dim}的评分标准和证据要求",
                    "priority": "medium",
                })

            # 建议 3: 高风险案例未命中
            elif ptype == "high_risk_missed":
                suggestions.append({
                    "target": "高风险判定规则",
                    "action": "降低 HIGH 阈值或增强交叉影响",
                    "reason": f"{pattern.get('count')}个高风险案例被低估",
                    "change": "将 HIGH 阈值从 76 降至 72，或增强多维度叠加规则",
                    "priority": "high",
                })

        # 建议 4: 系统性偏差
        bias = analysis.get("systematic_bias")
        if bias == "underestimate":
            suggestions.append({
                "target": "整体评分",
                "action": "全局分数上调",
                "reason": f"系统性低估风险，平均差距{analysis.get('avg_gap', 0):.1f}分",
                "change": "所有维度基础分数 +5，或调整 severity→score 映射",
                "priority": "high" if analysis.get("avg_gap", 0) > 5 else "medium",
            })
        elif bias == "overestimate":
            suggestions.append({
                "target": "整体评分",
                "action": "全局分数下调",
                "reason": f"系统性高估风险，平均差距{analysis.get('avg_gap', 0):.1f}分",
                "change": "所有维度基础分数 -5，或提高 HIGH 阈值",
                "priority": "medium",
            })

        return suggestions

    def apply_optimization(
        self,
        suggestion: Dict[str, Any],
        prompt_content: str,
    ) -> str:
        """应用单个优化建议到 Prompt 内容"""
        optimized = prompt_content
        target = suggestion.get("target", "")
        action = suggestion.get("action", "")
        change = suggestion.get("change", "")

        # 优化 1: 调整维度权重
        if "权重" in action:
            if "道德伦理" in target:
                # 找到道德伦理权重行并修改
                optimized = re.sub(
                    r'("道德伦理"[^}]*"dimension_weight":\s*)1\.0',
                    r'\g<1>1.2',
                    optimized,
                )
            elif "消费" in target or "群体冒犯" in target:
                optimized = re.sub(
                    r'("群体冒犯"[^}]*"dimension_weight":\s*)1\.0',
                    r'\g<1>1.2',
                    optimized,
                )

        # 优化 2: 调整 HIGH 阈值
        elif "阈值" in action:
            if "高风险" in target or "道德伦理" in target:
                # 将 HIGH 阈值从 76 降至 72
                optimized = re.sub(
                    r'HIGH 区间\(76\+\)',
                    'HIGH 区间 (72+)',
                    optimized,
                )
                optimized = re.sub(
                    r'触碰即 HIGH\(76\+\)',
                    '触碰即 HIGH(72+)',
                    optimized,
                )
                # 调整评分细则
                optimized = re.sub(
                    r'- 76-100: HIGH',
                    '- 72-100: HIGH',
                    optimized,
                )
                optimized = re.sub(
                    r'分数必须≥76',
                    '分数必须≥72',
                    optimized,
                )

        # 优化 3: 全局分数调整
        elif "全局" in action or "整体" in action:
            if "上调" in action:
                # 增加基础分数映射
                old_map = "- 26-50: MEDIUM-LOW"
                new_map = "- 30-55: MEDIUM-LOW"
                if old_map in optimized:
                    optimized = optimized.replace(old_map, new_map)

        # 优化 4: 增强交叉影响规则
        if "交叉影响" in change:
            # 添加新的交叉影响规则
            cross_rule = '- "道德伦理"+"消费欺诈" → combined_severity="high"，欺诈 + 道德双重风险\n'
            if '## 维度交叉影响规则' in optimized:
                optimized = optimized.replace(
                    '## 维度交叉影响规则',
                    f'## 维度交叉影响规则\n{cross_rule}',
                )

        return optimized

    def run_iteration(
        self,
        version_a: str,
        suggestions: List[Dict[str, Any]],
        run_backtest: bool = True,
    ) -> Dict[str, Any]:
        """执行一轮迭代优化

        Args:
            version_a: 当前版本号
            suggestions: 优化建议列表
            run_backtest: 是否运行回测验证

        Returns:
            迭代结果
        """
        # 获取当前版本内容
        current_version = self.mgr.get_version(self.prompt_name, version_a)
        if not current_version:
            raise ValueError(f"版本 {version_a} 不存在")

        # 应用优先级最高的建议
        high_priority = [s for s in suggestions if s.get("priority") == "high"]
        if not high_priority:
            high_priority = suggestions[:1]  # 至少应用一个

        optimized_content = current_version.content
        applied_suggestions = []

        for sugg in high_priority[:3]:  # 最多应用 3 个建议
            new_content = self.apply_optimization(sugg, optimized_content)
            if new_content != optimized_content:
                optimized_content = new_content
                applied_suggestions.append(sugg)
                logger.info("应用优化: %s", sugg.get("target"))

        # 注册新版本
        version_b = f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        self.mgr.register_version(
            prompt_name=self.prompt_name,
            version=version_b,
            content=optimized_content,
            metadata={
                "based_on": version_a,
                "optimizations": [s.get("target") for s in applied_suggestions],
                "changes": [s.get("change") for s in applied_suggestions],
            },
        )

        # 运行回测验证
        backtest_result = None
        if run_backtest:
            runner = BacktestRunner(self.cases)
            # 使用模拟模式快速验证
            report = runner._generate_report(0)
            backtest_result = report.get("summary", {})

        iteration = {
            "from_version": version_a,
            "to_version": version_b,
            "applied_suggestions": applied_suggestions,
            "backtest_result": backtest_result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.iteration_history.append(iteration)
        logger.info("迭代完成：%s → %s", version_a, version_b)

        return iteration

    def get_optimization_summary(self) -> Dict[str, Any]:
        """获取优化历史总结"""
        return {
            "total_iterations": len(self.iteration_history),
            "iterations": self.iteration_history,
            "current_recommendation": self.mgr.get_recommended_version(self.prompt_name),
        }


def main():
    """主函数：演示优化流程"""
    print(f"{YELLOW}T4 Prompt 优化器 — 基于 T0.1 案例库{RESET}")
    print()

    optimizer = PromptOptimizer()

    # 1. 运行初始回测
    print("步骤 1: 运行初始回测...")
    runner = BacktestRunner(optimizer.cases)
    initial_report = runner._generate_report(0)
    initial_accuracy = initial_report.get("summary", {}).get("overall_accuracy", 0)
    print(f"  初始准确率：{initial_accuracy*100:.1f}%")
    print()

    # 2. 分析未命中案例
    print("步骤 2: 分析未命中案例...")
    # 使用模拟结果
    mock_results = []
    for case in optimizer.cases:
        mock_result = runner._run_mock(case)
        mock_results.append(mock_result)

    analysis = optimizer.analyze_missed_cases(mock_results)
    print(f"  未命中案例数：{analysis['total_missed']}")
    print(f"  系统性偏差：{analysis.get('systematic_bias', 'none')}")
    print(f"  平均差距：{analysis.get('avg_gap', 0):.1f}分")
    print()

    # 3. 生成优化建议
    print("步骤 3: 生成优化建议...")
    suggestions = optimizer.generate_optimization_suggestions(analysis)
    for i, sugg in enumerate(suggestions[:5], 1):
        print(f"  {i}. [{sugg.get('priority')}] {sugg.get('target')}: {sugg.get('action')}")
        print(f"     原因：{sugg.get('reason')}")
        print(f"     修改：{sugg.get('change')}")
    print()

    # 4. 注册初始版本
    print("步骤 4: 注册 Prompt 版本...")
    # 从文件加载当前 Prompt
    prompts_dir = optimizer.mgr.prompts_dir
    prompt_file = prompts_dir / "risk_assessment.txt"
    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read()
        optimizer.mgr.register_version(
            prompt_name="risk_assessment",
            version="v1.0",
            content=content,
            metadata={"description": "初始版本"},
        )
        print("  已注册 v1.0")
    print()

    # 5. 执行迭代优化
    if suggestions:
        print("步骤 5: 执行迭代优化...")
        iteration = optimizer.run_iteration("v1.0", suggestions, run_backtest=False)
        print(f"  版本：{iteration['from_version']} → {iteration['to_version']}")
        print(f"  应用优化：{len(iteration['applied_suggestions'])}项")
        print()

    # 6. 总结
    print("步骤 6: 优化总结...")
    summary = optimizer.get_optimization_summary()
    print(f"  总迭代次数：{summary['total_iterations']}")
    print(f"  当前推荐版本：{summary.get('current_recommendation', 'N/A')}")
    print()

    print(f"{GREEN}T4 Prompt 优化流程演示完成{RESET}")


if __name__ == "__main__":
    main()
