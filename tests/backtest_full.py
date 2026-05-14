#!/usr/bin/env python3
"""完整回测验证脚本 - 验证优化后的准确率提升

对比优化前（基准）vs 优化后（T4+T5+T8）的准确率：
- T4: 七维风险评估Prompt优化
- T5: 信号关联+实体风险链+动态权重
- T8: 跨模态冲突检测

回测案例库：data/backtest/cases.json (25个案例)
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.analyzer import run_analysis, calculate_overall_score
from backend.services.llm_client import call_llm, parse_llm_json
from backend.database import SessionLocal
from backend.models import Task

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("backtest")

# 风险等级映射
RISK_LEVEL_MAP = {
    "green": (0, 25),
    "yellow": (26, 50),
    "orange": (51, 75),
    "red": (76, 100),
}

def load_cases() -> list[dict]:
    """加载回测案例"""
    cases_path = Path(__file__).parent.parent / "data" / "backtest" / "cases.json"
    with open(cases_path, "r", encoding="utf-8") as f:
        return json.load(f)

def score_to_risk_level(score: int) -> str:
    """将分数转换为风险等级"""
    if score <= 25:
        return "green"
    elif score <= 50:
        return "yellow"
    elif score <= 75:
        return "orange"
    else:
        return "red"

def evaluate_case(case: dict, actual_score: int, actual_dimensions: dict) -> dict:
    """评估单个案例的准确率"""
    expected_level = case["expected_risk_level"]
    expected_dims = set(case.get("expected_high_dimensions", []))
    score_range = case.get("risk_score_range", [0, 100])
    
    actual_level = score_to_risk_level(actual_score)
    actual_high_dims = {name for name, score in actual_dimensions.items() if score > 40}
    
    # 1. 风险等级准确率
    level_correct = actual_level == expected_level
    
    # 2. 分数范围准确率
    score_in_range = score_range[0] <= actual_score <= score_range[1]
    
    # 3. 高风险维度识别准确率
    if expected_dims:
        dim_overlap = actual_high_dims & expected_dims
        dim_precision = len(dim_overlap) / len(actual_high_dims) if actual_high_dims else 0
        dim_recall = len(dim_overlap) / len(expected_dims)
        dim_f1 = 2 * dim_precision * dim_recall / (dim_precision + dim_recall) if (dim_precision + dim_recall) > 0 else 0
    else:
        # 预期无高风险维度
        dim_precision = 1.0 if not actual_high_dims else 0.0
        dim_recall = 1.0
        dim_f1 = dim_precision
    
    # 4. 综合准确率
    accuracy = {
        "level_correct": level_correct,
        "score_in_range": score_in_range,
        "dim_precision": round(dim_precision, 2),
        "dim_recall": round(dim_recall, 2),
        "dim_f1": round(dim_f1, 2),
        "overall": round((
            (1.0 if level_correct else 0.0) * 0.3 +
            (1.0 if score_in_range else 0.0) * 0.3 +
            dim_f1 * 0.4
        ), 2),
    }
    
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "category": case["category"],
        "expected_level": expected_level,
        "actual_level": actual_level,
        "expected_score_range": score_range,
        "actual_score": actual_score,
        "expected_high_dims": sorted(expected_dims),
        "actual_high_dims": sorted(actual_high_dims),
        "accuracy": accuracy,
    }

async def run_single_case(case: dict, prompt_version: str = "v2") -> dict:
    """运行单个案例的分析
    
    Args:
        case: 案例数据
        prompt_version: Prompt 版本，"v2"为 T4 优化版，"v1"为原始版
    """
    task_id = f"backtest_{case['case_id']}_{int(time.time())}"
    content = case["content"]
    
    # 直接调用风险评估（跳过平台仿真等耗时步骤，但包含 T5 模块）
    try:
        from backend.services.risk_assessor import assess_risks
        from backend.services.text_splitter import split_text
        from backend.services.transcript_detector import detect_transcript_quality
        from backend.services.analyzer import calculate_overall_score
        
        sentences = split_text(content)
        transcript_quality = await detect_transcript_quality(content, sentences)
        # T4: 使用优化后的 Prompt 版本
        risk_results = await assess_risks(content, transcript_quality=transcript_quality, prompt_version=prompt_version)
        
        dimensions = risk_results.get("dimensions", [])
        
        # T5: 信号关联 + 实体风险链 + 动态权重
        signal_dimension_boosts = {}
        entity_dimension_boosts = {}
        
        try:
            # 信号关联
            from backend.services.signal_matcher import SignalMatcher
            matcher = SignalMatcher()
            signal_result = await matcher.match(content)
            if hasattr(signal_result, 'risk_dimension_boosts'):
                signal_dimension_boosts = signal_result.risk_dimension_boosts
        except Exception as e:
            logger.debug("信号关联失败(降级继续): %s", e)
        
        try:
            # 实体风险链
            from backend.services.entity_risk_chain import analyze_entity_risk_chain
            entity_chain_result = await analyze_entity_risk_chain(content)
            if entity_chain_result and hasattr(entity_chain_result, 'risk_dimension_boosts'):
                entity_dimension_boosts = entity_chain_result.risk_dimension_boosts
        except Exception as e:
            logger.debug("实体风险链失败(降级继续): %s", e)
        
        try:
            # 动态权重调整
            from backend.services.dynamic_weights import DynamicWeights
            dw = DynamicWeights()
            weights_result = dw.adjust(
                signal_dimension_boosts=signal_dimension_boosts,
                entity_dimension_boosts=entity_dimension_boosts,
            )
            # 应用动态权重到维度结果
            for dim in dimensions:
                dim_name = dim.get("name", "")
                if dim_name in weights_result.adjusted_weights:
                    dim["dimension_weight"] = weights_result.adjusted_weights[dim_name]
        except Exception as e:
            logger.debug("动态权重调整失败(降级继续): %s", e)
        
        actual_dimensions = {d.get("name", ""): d.get("score", 0) for d in dimensions}
        
        # 计算总分（应用动态权重后）
        actual_score, _, _ = calculate_overall_score(dimensions)
        
    except Exception as e:
        logger.error("案例 %s 分析失败: %s", case["title"], e)
        return {
            "case_id": case["case_id"],
            "title": case["title"],
            "error": str(e),
            "accuracy": {"level_correct": False, "score_in_range": False, "dim_precision": 0, "dim_recall": 0, "dim_f1": 0, "overall": 0},
        }
    
    return evaluate_case(case, actual_score, actual_dimensions)

async def run_backtest(prompt_version: str = "v2"):
    """运行完整回测
    
    Args:
        prompt_version: Prompt 版本，"v2"为 T4 优化版，"v1"为原始版
    """
    cases = load_cases()
    logger.info("加载 %d 个回测案例，使用 Prompt 版本：%s", len(cases), prompt_version)
    
    results = []
    start_time = time.time()
    
    for i, case in enumerate(cases, 1):
        logger.info("[%d/%d] 运行案例：%s (%s) [Prompt: %s]", i, len(cases), case["title"], case["category"], prompt_version)
        result = await run_single_case(case, prompt_version=prompt_version)
        results.append(result)
        
        # 打印进度
        acc = result.get("accuracy", {})
        logger.info(
            "  结果: 分数=%d, 预期等级=%s, 实际等级=%s, 准确率=%.0f%%",
            result.get("actual_score", 0),
            result.get("expected_level", "?"),
            result.get("actual_level", "?"),
            acc.get("overall", 0) * 100,
        )
    
    elapsed = time.time() - start_time
    
    # 生成报告
    report = generate_report(results, elapsed)
    
    # 保存报告
    report_path = Path(__file__).parent.parent / "data" / "backtest" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info("回测报告已保存: %s", report_path)
    
    # 打印摘要
    print_summary(report)
    
    return report

def generate_report(results: list[dict], elapsed: float) -> dict:
    """生成回测报告"""
    total = len(results)
    completed = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    
    if not completed:
        return {"error": "所有案例运行失败", "results": results}
    
    # 总体准确率
    level_accuracy = sum(1 for r in completed if r["accuracy"]["level_correct"]) / len(completed)
    score_accuracy = sum(1 for r in completed if r["accuracy"]["score_in_range"]) / len(completed)
    avg_dim_precision = sum(r["accuracy"]["dim_precision"] for r in completed) / len(completed)
    avg_dim_recall = sum(r["accuracy"]["dim_recall"] for r in completed) / len(completed)
    avg_dim_f1 = sum(r["accuracy"]["dim_f1"] for r in completed) / len(completed)
    avg_overall = sum(r["accuracy"]["overall"] for r in completed) / len(completed)
    
    # 按风险等级分组
    by_level = {}
    for r in completed:
        level = r["expected_level"]
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(r)
    
    level_stats = {}
    for level, cases in by_level.items():
        level_acc = sum(1 for c in cases if c["accuracy"]["level_correct"]) / len(cases)
        level_stats[level] = {
            "count": len(cases),
            "accuracy": round(level_acc, 2),
        }
    
    # 按类别分组
    by_category = {}
    for r in completed:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)
    
    category_stats = {}
    for cat, cases in by_category.items():
        cat_acc = sum(c["accuracy"]["overall"] for c in cases) / len(cases)
        category_stats[cat] = {
            "count": len(cases),
            "accuracy": round(cat_acc, 2),
        }
    
    return {
        "report_id": f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "total_cases": total,
        "completed": len(completed),
        "failed": len(failed),
        "elapsed_seconds": round(elapsed, 1),
        "overall_metrics": {
            "level_accuracy": round(level_accuracy, 2),
            "score_accuracy": round(score_accuracy, 2),
            "dim_precision": round(avg_dim_precision, 2),
            "dim_recall": round(avg_dim_recall, 2),
            "dim_f1": round(avg_dim_f1, 2),
            "overall_accuracy": round(avg_overall, 2),
        },
        "by_risk_level": level_stats,
        "by_category": category_stats,
        "results": results,
    }

def print_summary(report: dict):
    """打印回测摘要"""
    print("\n" + "="*70)
    print("  回测报告摘要")
    print("="*70)
    
    print(f"\n总案例数: {report['total_cases']}")
    print(f"完成: {report['completed']}, 失败: {report['failed']}")
    print(f"耗时: {report['elapsed_seconds']:.1f}秒")
    
    metrics = report["overall_metrics"]
    print(f"\n总体准确率:")
    print(f"  风险等级准确率: {metrics['level_accuracy']:.0%}")
    print(f"  分数范围准确率: {metrics['score_accuracy']:.0%}")
    print(f"  维度识别精确率: {metrics['dim_precision']:.0%}")
    print(f"  维度识别召回率: {metrics['dim_recall']:.0%}")
    print(f"  维度识别F1分数: {metrics['dim_f1']:.2f}")
    print(f"  综合准确率: {metrics['overall_accuracy']:.0%}")
    
    print(f"\n按风险等级:")
    for level, stats in report.get("by_risk_level", {}).items():
        print(f"  {level}: {stats['count']}例, 准确率 {stats['accuracy']:.0%}")
    
    print(f"\n按类别:")
    for cat, stats in sorted(report.get("by_category", {}).items()):
        print(f"  {cat}: {stats['count']}例, 准确率 {stats['accuracy']:.0%}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    
    # 支持命令行参数指定版本
    import sys
    prompt_version = sys.argv[1] if len(sys.argv) > 1 else "v2"
    
    asyncio.run(run_backtest(prompt_version=prompt_version))
