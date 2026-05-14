#!/usr/bin/env python3
"""T4 Prompt 优化对比测试 - 对比 v1 vs v2 的准确率提升"""

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

from backend.services.analyzer import calculate_overall_score
from backend.services.risk_assessor import assess_risks
from backend.services.text_splitter import split_text
from backend.services.transcript_detector import detect_transcript_quality

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("backtest_ab")

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
        "expected_level": expected_level,
        "actual_level": actual_level,
        "expected_score_range": score_range,
        "actual_score": actual_score,
        "expected_high_dims": sorted(expected_dims),
        "actual_high_dims": sorted(actual_high_dims),
        "accuracy": accuracy,
    }

async def run_single_case(case: dict, prompt_version: str) -> dict:
    """运行单个案例的分析"""
    content = case["content"]
    
    try:
        sentences = split_text(content)
        transcript_quality = await detect_transcript_quality(content, sentences)
        risk_results = await assess_risks(content, transcript_quality=transcript_quality, prompt_version=prompt_version)
        
        dimensions = risk_results.get("dimensions", [])
        actual_dimensions = {d.get("name", ""): d.get("score", 0) for d in dimensions}
        actual_score, _, _ = calculate_overall_score(dimensions)
        
    except Exception as e:
        logger.error("案例 %s 分析失败：%s", case["title"], e)
        return {
            "case_id": case["case_id"],
            "title": case["title"],
            "error": str(e),
            "accuracy": {"level_correct": False, "score_in_range": False, "dim_precision": 0, "dim_recall": 0, "dim_f1": 0, "overall": 0},
        }
    
    return evaluate_case(case, actual_score, actual_dimensions)

async def run_ab_test():
    """运行 A/B 对比测试"""
    cases = load_cases()
    logger.info("加载 %d 个回测案例", len(cases))
    
    # 运行 v1（基准）
    logger.info("="*70)
    logger.info("运行 v1（基准版本）")
    logger.info("="*70)
    v1_results = []
    start_time = time.time()
    
    for i, case in enumerate(cases, 1):
        logger.info("[v1][%d/%d] %s", i, len(cases), case["title"])
        result = await run_single_case(case, prompt_version="v1")
        v1_results.append(result)
    
    v1_elapsed = time.time() - start_time
    
    # 运行 v2（T4 优化版）
    logger.info("="*70)
    logger.info("运行 v2（T4 优化版）")
    logger.info("="*70)
    v2_results = []
    start_time = time.time()
    
    for i, case in enumerate(cases, 1):
        logger.info("[v2][%d/%d] %s", i, len(cases), case["title"])
        result = await run_single_case(case, prompt_version="v2")
        v2_results.append(result)
    
    v2_elapsed = time.time() - start_time
    
    # 生成对比报告
    v1_report = generate_report(v1_results, v1_elapsed, "v1")
    v2_report = generate_report(v2_results, v2_elapsed, "v2")
    
    comparison_report = compare_reports(v1_report, v2_report)
    
    # 保存报告
    report_path = Path(__file__).parent.parent / "data" / "backtest" / f"t4_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, ensure_ascii=False, indent=2)
    
    logger.info("对比报告已保存：%s", report_path)
    
    # 打印摘要
    print_comparison_summary(comparison_report)
    
    return comparison_report

def generate_report(results: list[dict], elapsed: float, version: str) -> dict:
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
    
    return {
        "version": version,
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
        "results": results,
    }

def compare_reports(v1_report: dict, v2_report: dict) -> dict:
    """生成对比报告"""
    v1_metrics = v1_report["overall_metrics"]
    v2_metrics = v2_report["overall_metrics"]
    
    improvements = {
        "level_accuracy": round(v2_metrics["level_accuracy"] - v1_metrics["level_accuracy"], 2),
        "score_accuracy": round(v2_metrics["score_accuracy"] - v1_metrics["score_accuracy"], 2),
        "dim_precision": round(v2_metrics["dim_precision"] - v1_metrics["dim_precision"], 2),
        "dim_recall": round(v2_metrics["dim_recall"] - v1_metrics["dim_recall"], 2),
        "dim_f1": round(v2_metrics["dim_f1"] - v1_metrics["dim_f1"], 2),
        "overall_accuracy": round(v2_metrics["overall_accuracy"] - v1_metrics["overall_accuracy"], 2),
    }
    
    # 找出改进和退步的案例
    improved_cases = []
    regressed_cases = []
    
    for i in range(len(v1_report["results"])):
        v1_acc = v1_report["results"][i]["accuracy"]["overall"]
        v2_acc = v2_report["results"][i]["accuracy"]["overall"]
        change = round(v2_acc - v1_acc, 2)
        
        if change > 0.1:  # 提升超过 10%
            improved_cases.append({
                "case_id": v1_report["results"][i]["case_id"],
                "title": v1_report["results"][i]["title"],
                "v1_accuracy": v1_acc,
                "v2_accuracy": v2_acc,
                "improvement": change,
            })
        elif change < -0.1:  # 下降超过 10%
            regressed_cases.append({
                "case_id": v1_report["results"][i]["case_id"],
                "title": v1_report["results"][i]["title"],
                "v1_accuracy": v1_acc,
                "v2_accuracy": v2_acc,
                "regression": change,
            })
    
    return {
        "comparison_summary": {
            "v1_version": "v1 (基准)",
            "v2_version": "v2 (T4 优化)",
            "v1_elapsed": v1_report["elapsed_seconds"],
            "v2_elapsed": v2_report["elapsed_seconds"],
        },
        "v1_metrics": v1_metrics,
        "v2_metrics": v2_metrics,
        "improvements": improvements,
        "improved_cases": improved_cases,
        "regressed_cases": regressed_cases,
        "detailed_results": {
            "v1": v1_report["results"],
            "v2": v2_report["results"],
        },
    }

def print_comparison_summary(report: dict):
    """打印对比摘要"""
    print("\n" + "="*70)
    print("  T4 Prompt 优化对比测试报告")
    print("="*70)
    
    summary = report["comparison_summary"]
    print(f"\n版本对比：{summary['v1_version']} vs {summary['v2_version']}")
    print(f"耗时：v1={summary['v1_elapsed']:.1f}s, v2={summary['v2_elapsed']:.1f}s")
    
    print("\n准确率对比:")
    print(f"{'指标':<20} {'v1':<10} {'v2':<10} {'提升':<10}")
    print("-"*50)
    
    v1_metrics = report["v1_metrics"]
    v2_metrics = report["v2_metrics"]
    improvements = report["improvements"]
    
    for metric in ["level_accuracy", "score_accuracy", "dim_precision", "dim_recall", "dim_f1", "overall_accuracy"]:
        v1_val = f"{v1_metrics[metric]:.0%}"
        v2_val = f"{v2_metrics[metric]:.0%}"
        imp_val = f"+{improvements[metric]:.0%}" if improvements[metric] > 0 else f"{improvements[metric]:.0%}"
        print(f"{metric:<20} {v1_val:<10} {v2_val:<10} {imp_val:<10}")
    
    print("\n改进案例:")
    improved = report["improved_cases"]
    if improved:
        for case in improved[:5]:  # 显示前 5 个
            print(f"  - {case['case_id']}: {case['title']} (准确率：{case['v1_accuracy']:.0%} → {case['v2_accuracy']:.0%}, +{case['improvement']:.0%})")
    else:
        print("  无明显改进案例")
    
    print("\n退步案例:")
    regressed = report["regressed_cases"]
    if regressed:
        for case in regressed[:5]:  # 显示前 5 个
            print(f"  - {case['case_id']}: {case['title']} (准确率：{case['v1_accuracy']:.0%} → {case['v2_accuracy']:.0%}, {case['regression']:.0%})")
    else:
        print("  无明显退步案例")
    
    print("\n" + "="*70)
    
    # 输出最终结论
    overall_improvement = improvements["overall_accuracy"]
    if overall_improvement > 0:
        print(f"T4 Prompt 优化成功！整体准确率提升：+{overall_improvement:.0%}")
        print(f"预期准确率收益：+12%，实际提升：+{overall_improvement:.0%}")
        if overall_improvement >= 0.12:
            print("✓ 达到预期目标！")
        else:
            print("○ 接近目标，可继续优化")
    else:
        print(f"T4 Prompt 优化未达预期，准确率变化：{overall_improvement:.0%}")
        print("建议：分析退步案例，进一步调整 Prompt")
    print("="*70)

if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    asyncio.run(run_ab_test())
