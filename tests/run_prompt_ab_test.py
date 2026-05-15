#!/usr/bin/env python3
"""
Prompt 版本 A/B 测试脚本 — T2.2

使用真实案例对不同 Prompt 版本进行测试，评估效果对比。

使用方法:
    python tests/run_prompt_ab_test.py

输出:
    - 控制台显示测试结果
    - 报告保存到 data/ab_test_report_*.json
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.prompt_version_manager import PromptVersionManager
from backend.services.prompt_ab_test_runner import PromptABTestRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """运行 A/B 测试"""
    print("=" * 80)
    print("Prompt 版本 A/B 测试 — T2.2")
    print("=" * 80)
    print()
    
    # 加载测试案例
    cases_file = Path(__file__).parent.parent / "data" / "ab_test_cases.json"
    with open(cases_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    
    print(f"📦 加载测试案例：{len(test_cases)} 个")
    print()
    
    # 初始化版本管理器
    mgr = PromptVersionManager()
    
    # 列出所有可用的 Prompt
    prompts = mgr.list_prompts()
    if not prompts:
        print("❌ 暂无 Prompt 版本记录")
        print()
        print("请先使用以下命令注册版本:")
        print("  python backend/services/prompt_manager_cli.py register risk_assessment v1.0 backend/prompts/risk_assessment.txt")
        return
    
    print(f"📋 可用 Prompt 列表:")
    for prompt in prompts:
        versions = mgr.get_all_versions(prompt)
        version_list = ", ".join([v.version for v in versions])
        print(f"  • {prompt}: {version_list}")
    print()
    
    # 对 risk_assessment 进行 A/B 测试（如果有多个版本）
    if "risk_assessment" in prompts:
        versions = mgr.get_all_versions("risk_assessment")
        if len(versions) >= 2:
            print("🧪 开始 risk_assessment A/B 测试")
            print()
            
            # 选择最早的两个版本进行对比
            versions_sorted = sorted(versions, key=lambda v: v.created_at)
            version_a = versions_sorted[0].version
            version_b = versions_sorted[-1].version
            
            print(f"  版本 A: {version_a} (对照)")
            print(f"  版本 B: {version_b} (实验)")
            print(f"  测试案例：{len(test_cases)} 个")
            print()
            
            runner = PromptABTestRunner("risk_assessment", version_a, version_b)
            report = await runner.run_test(test_cases)
            
            print()
            print("=" * 80)
            print("测试结果")
            print("=" * 80)
            print()
            
            print(f"测试 ID: {report['test_id']}")
            print(f"胜出版本：{report['winner']}")
            print(f"样本数：{report['sample_size']}")
            print()
            
            print(f"📊 版本 A ({version_a}) 指标:")
            for metric, value in report["metrics_a"].items():
                print(f"  • {metric}: {value:.4f}")
            print()
            
            print(f"📊 版本 B ({version_b}) 指标:")
            for metric, value in report["metrics_b"].items():
                print(f"  • {metric}: {value:.4f}")
            print()
            
            # 保存报告
            output_dir = Path(__file__).parent.parent / "data" / "ab_tests"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"ab_test_report_{timestamp}.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            print(f"💾 报告已保存：{output_file}")
            print()
            
            # 详细案例结果
            print("=" * 80)
            print("详细案例结果")
            print("=" * 80)
            print()
            
            for i, case in enumerate(test_cases):
                result_a = report["details_a"][i]
                result_b = report["details_b"][i]
                
                print(f"案例 {i+1}: {case['name']}")
                print(f"  预期等级：{case['expected_level']}")
                print(f"  版本 A 预测：{result_a['actual_level']} ({'✓' if result_a['level_correct'] else '✗'})")
                print(f"  版本 B 预测：{result_b['actual_level']} ({'✓' if result_b['level_correct'] else '✗'})")
                print()
        else:
            print("⚠️  risk_assessment 只有一个版本，无法进行 A/B 测试")
            print()
            print("提示：可以修改后端/prompts/risk_assessment.txt 后注册为新版本")
            print()
    else:
        print("⚠️  risk_assessment 不在可用 Prompt 列表中")
        print()
    
    print("=" * 80)
    print("A/B 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
