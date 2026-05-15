#!/usr/bin/env python3
"""T0.1 回测案例库基线测试 - 选取 3 个案例进行初步回测

根据蓝图阶段 1 验收标准：
- 3 个测试案例（高/中/低风险各 1 个）风险等级正确率 ≥ 2/3
- 建立第一版准确率基线（仅记录，不设要求）
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 从回测案例库中选取 3 个代表性案例
TEST_CASES = [
    {
        "name": "历史虚无主义被点名",
        "file": "cases/paperwork/历史虚无主义被点名.md",
        "expected_level": "red",
        "expected_score_range": [76, 100],
        "risk_dimension": "政治敏感"
    },
    {
        "name": "文案抄袭被实锤",
        "file": "cases/paperwork/文案抄袭被实锤.md",
        "expected_level": "yellow",
        "expected_score_range": [26, 50],
        "risk_dimension": "知识产权"
    },
    {
        "name": "手工酸奶造假",
        "file": "cases/paperwork/手工酸奶造假.md",
        "expected_level": "orange",
        "expected_score_range": [51, 75],
        "risk_dimension": "食品安全"
    }
]

def load_case_content(file_path: str) -> str:
    """读取案例内容"""
    full_path = Path(__file__).parent.parent / file_path
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

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

def main():
    print("=" * 60)
    print("T0.1 回测案例库基线测试")
    print("=" * 60)
    print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试案例数：{len(TEST_CASES)}")
    print()
    
    results = []
    
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n【案例 {i}/{len(TEST_CASES)}】{case['name']}")
        print("-" * 60)
        
        # 读取案例内容
        try:
            content = load_case_content(case["file"])
            print(f"案例维度：{case['risk_dimension']}")
            print(f"预期等级：{case['expected_level']}")
            print(f"预期分数：{case['expected_score_range'][0]}-{case['expected_score_range'][1]}")
            
            # 这里暂时跳过实际分析（因为需要 API 配额）
            # 实际运行时应调用风险评估模块
            print("⚠️  待执行：调用风险评估模块进行分析")
            
            result = {
                "case_name": case["name"],
                "expected_level": case["expected_level"],
                "expected_score_range": case["expected_score_range"],
                "actual_score": None,  # 待填充
                "actual_level": None,   # 待填充
                "level_correct": False, # 待计算
            }
            results.append(result)
            
        except Exception as e:
            print(f"❌ 错误：{e}")
    
    # 输出汇总报告
    print("\n" + "=" * 60)
    print("【测试汇总】")
    print("=" * 60)
    
    total = len(results)
    correct = sum(1 for r in results if r["level_correct"])
    
    print(f"总案例数：{total}")
    print(f"正确数：{correct}")
    print(f"准确率：{correct/total*100:.1f}%" if total > 0 else "N/A")
    print()
    
    if correct >= 2:
        print("✅ 通过蓝图阶段 1 验收标准（正确率 ≥ 2/3）")
    else:
        print("⚠️  未通过蓝图阶段 1 验收标准，需优化 Prompt")
    
    # 保存报告
    report = {
        "test_time": datetime.now().isoformat(),
        "total_cases": total,
        "correct_cases": correct,
        "accuracy": correct/total*100 if total > 0 else 0,
        "results": results,
    }
    
    report_path = Path(__file__).parent.parent / "data" / "backtest" / f"t0_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n报告已保存到：{report_path}")

if __name__ == "__main__":
    main()
