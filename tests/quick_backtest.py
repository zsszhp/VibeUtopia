#!/usr/bin/env python3
"""快速回测验证 - 基于历史回测报告分析准确率"""

import json
from pathlib import Path
from datetime import datetime

# 加载历史回测报告
report_dir = Path("/workspace/data/backtest")
reports = list(report_dir.glob("report_*.json"))

if not reports:
    print("❌ 未找到历史回测报告")
    exit(1)

# 读取最新报告
latest_report = max(reports)
print(f"读取报告：{latest_report.name}")

with open(latest_report, "r", encoding="utf-8") as f:
    report_data = json.load(f)

print("\n" + "="*80)
print("回测验证结果")
print("="*80)

# 解析报告结构
if "summary" in report_data:
    summary = report_data["summary"]
    print(f"\n总案例数：{summary.get('total_cases', 'N/A')}")
    print(f"MVP 平均准确率：{summary.get('mvp_avg_accuracy', 'N/A')}")
    print(f"V2 平均准确率：{summary.get('v2_avg_accuracy', 'N/A')}")
    print(f"整体提升：{summary.get('overall_improvement', 'N/A')}")
    print(f"Go/No-Go 决策：{summary.get('go_no_go', 'N/A')}")
    
    if "comparisons" in report_data:
        comparisons = report_data["comparisons"]
        level_correct_count = sum(1 for c in comparisons if c.get("v2_accuracy", {}).get("level_correct", False))
        print(f"\n风险等级命中数：{level_correct_count}/{len(comparisons)} ({level_correct_count/len(comparisons)*100:.1f}%)")
else:
    # 简单格式
    total = report_data.get("total_cases", 0)
    correct = report_data.get("correct_predictions", 0)
    accuracy = report_data.get("overall_accuracy", 0)
    
    print(f"\n总案例数：{total}")
    print(f"正确预测：{correct}")
    print(f"准确率：{accuracy*100:.1f}%")

print("\n" + "="*80)

# 阶段 2 验收标准检查
accuracy = report_data.get("summary", {}).get("v2_avg_accuracy", report_data.get("overall_accuracy", 0))
if accuracy >= 0.6:
    print(f"✅ 阶段 2 验收通过：准确率 {accuracy*100:.1f}% ≥ 60%")
else:
    print(f"⏳ 阶段 2 验收待定：准确率 {accuracy*100:.1f}% < 60%")

print(f"\n报告时间：{report_data.get('created_at', 'N/A')}")
