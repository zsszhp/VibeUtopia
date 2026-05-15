#!/usr/bin/env python3
"""阶段 3 A/B 回测验证脚本 - 完整版

对比人生故事驱动 Agent (A 组) vs 属性标签 Agent (B 组) 的准确率差异

验收标准:
- A 组比 B 组命中率提升 ≥ 15%
- 使用 33 个回测案例进行测试
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.story_risk_associator import StoryRiskAssociator
from backend.services.enhanced_analyzer import run_enhanced_analysis


class CaseResult:
    """单个案例的测试结果"""
    def __init__(self, case_id: str, case_name: str, expected_level: str):
        self.case_id = case_id
        self.case_name = case_name
        self.expected_level = expected_level
        self.a_result: Dict[str, Any] = {}  # 人生故事 Agent
        self.b_result: Dict[str, Any] = {}  # 属性标签 Agent
        self.a_time: float = 0.0
        self.b_time: float = 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "expected_level": self.expected_level,
            "a_group": self.a_result,
            "b_group": self.b_result,
            "a_time_seconds": self.a_time,
            "b_time_seconds": self.b_time,
        }


def load_test_cases() -> List[Dict[str, str]]:
    """加载回测案例"""
    cases_dir = Path(__file__).parent.parent / "cases" / "paperwork"
    cases = []
    
    if not cases_dir.exists():
        print(f"❌ 案例目录不存在：{cases_dir}")
        return cases
    
    for case_file in cases_dir.glob("*.md"):
        try:
            with open(case_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 解析案例文件
            case_data = {"id": case_file.stem, "file": str(case_file)}
            
            # 提取风险等级 - 支持多种格式
            content_lower = content.lower()
            if "高风险" in content or "red" in content_lower or "不建议发布" in content:
                case_data["expected_level"] = "red"
            elif "中风险" in content or "orange" in content_lower or "建议修改" in content:
                case_data["expected_level"] = "orange"
            elif "低风险" in content or "yellow" in content_lower or "可发布" in content:
                case_data["expected_level"] = "yellow"
            else:
                # 默认绿色（安全）
                case_data["expected_level"] = "green"
            
            # 使用整个文件内容作为文案（去除 markdown 标题）
            lines = content.split("\n")
            text_lines = [line for line in lines if not line.startswith("# ")]
            case_data["text"] = "\n".join(text_lines).strip()
            
            if case_data["text"]:
                cases.append(case_data)
                
        except Exception as e:
            print(f"⚠️ 读取案例失败 {case_file.name}: {e}")
    
    print(f"📊 加载回测案例：{len(cases)}个")
    return cases


async def assess_with_story_agent(text: str, task_id: str) -> Dict[str, Any]:
    """A 组：使用人生故事增强 Agent 评估
    
    集成 StoryRiskAssociator，将人格特质映射到风险维度权重
    """
    try:
        # 使用 enhanced analyzer 的 quick 模式（不含仿真）
        # 但启用人生故事关联增强
        result = await run_enhanced_analysis(
            task_id=task_id,
            text=text,
            mode="quick",
            enable_signal=True,        # 启用信号匹配
            enable_entity_chain=True,  # 启用实体风险链
            enable_simulation=False,   # 不启用仿真（节省时间）
        )
        
        # 检查是否有人生故事关联结果
        has_story_association = (
            hasattr(result, 'story_association_result') and 
            result.story_association_result is not None
        )
        
        return {
            "risk_level": getattr(result, 'v2_suggestion', 'unknown'),
            "overall_score": getattr(result, 'v2_overall_score', 0),
            "suggestion": getattr(result, 'v2_suggestion', ''),
            "dimensions": getattr(result, 'v2_dimensions', {}),
            "confidence": getattr(result, 'confidence', 0.0),
            "has_story_association": has_story_association,
            "error": getattr(result, 'error', ''),
        }
        
    except Exception as e:
        return {"error": str(e)}


async def assess_with_attribute_agent(text: str, task_id: str) -> Dict[str, Any]:
    """B 组：使用传统属性标签 Agent 评估（不启用增强）
    
    使用基础 analyzer，不含人生故事关联
    """
    try:
        # 使用基础 analyzer（不经过 enhanced analyzer）
        from backend.services.analyzer import run_analysis
        
        result = await run_analysis(text)
        
        return {
            "risk_level": result.get("suggestion", "unknown"),
            "overall_score": result.get("overall_score", 0),
            "suggestion": result.get("suggestion", ""),
            "dimensions": result.get("dimensions", {}),
            "confidence": result.get("confidence", 0.0),
            "has_story_association": False,
            "error": "",
        }
        
    except Exception as e:
        return {"error": str(e)}


def check_accuracy_match(result: Dict[str, Any], expected_level: str) -> bool:
    """检查评估结果是否与预期风险等级匹配"""
    if "error" in result and result["error"]:
        return False
    
    # 获取建议文本
    suggestion = result.get("suggestion", "").lower()
    overall_score = result.get("overall_score", 0)
    
    # 风险等级映射规则
    # Red: 不建议发布 (overall_score >= 76)
    # Orange/Yellow: 建议修改 (overall_score 30-75)
    # Green: 可发布 (overall_score < 30)
    
    if expected_level == "red":
        # 高风险：分数≥76 或 明确建议"不建议发布"
        return overall_score >= 76 or "不建议发布" in suggestion or "red" in suggestion
    elif expected_level in ["orange", "yellow"]:
        # 中风险：分数 30-75 或 建议"建议修改"
        return 30 <= overall_score < 76 or "建议修改" in suggestion
    else:  # green
        # 低风险：分数<30 或 建议"可发布"
        return overall_score < 30 or "可发布" in suggestion or "green" in suggestion


async def run_ab_test():
    """执行 A/B 测试"""
    print("=" * 80)
    print("阶段 3 A/B 回测验证 - 完整版")
    print("人生故事驱动 Agent vs 属性标签 Agent")
    print("=" * 80)
    print(f"测试时间：{datetime.now().isoformat()}\n")
    
    # 加载测试案例
    test_cases = load_test_cases()
    
    if not test_cases:
        print("❌ 没有可用的测试案例")
        return None
    
    # 风险等级统计
    level_counts = {}
    for case in test_cases:
        level = case["expected_level"]
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print(f"📋 测试案例总数：{len(test_cases)}")
    for level, count in sorted(level_counts.items()):
        print(f"   - {level.upper()}类：{count}个")
    print()
    
    # 存储结果
    results: List[CaseResult] = []
    a_correct = 0
    b_correct = 0
    a_errors = 0
    b_errors = 0
    
    print("🚀 开始执行 A/B 测试...\n")
    
    for i, case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] 测试案例：{case['id']}")
        
        result = CaseResult(
            case_id=case["id"],
            case_name=case.get("id", "unknown"),
            expected_level=case["expected_level"],
        )
        
        task_id = f"ab_test_a_{case['id']}"
        
        # A 组测试（人生故事 Agent）
        print(f"   - A 组（人生故事 Agent）评估中...")
        start_time = time.time()
        try:
            a_result = await assess_with_story_agent(case["text"], task_id)
            result.a_time = time.time() - start_time
        except Exception as e:
            a_result = {"error": str(e)}
            result.a_time = time.time() - start_time
            a_errors += 1
        
        result.a_result = a_result
        a_match = check_accuracy_match(a_result, case["expected_level"])
        
        if a_match:
            a_correct += 1
            print(f"   ✅ A 组正确 (耗时：{result.a_time:.2f}s)")
        else:
            print(f"   ❌ A 组错误 (预期：{case['expected_level']}, 实际：{a_result.get('suggestion', 'N/A')})")
        
        # B 组测试（属性标签 Agent）
        task_id = f"ab_test_b_{case['id']}"
        print(f"   - B 组（属性标签 Agent）评估中...")
        start_time = time.time()
        try:
            b_result = await assess_with_attribute_agent(case["text"], task_id)
            result.b_time = time.time() - start_time
        except Exception as e:
            b_result = {"error": str(e)}
            result.b_time = time.time() - start_time
            b_errors += 1
        
        result.b_result = b_result
        b_match = check_accuracy_match(b_result, case["expected_level"])
        
        if b_match:
            b_correct += 1
            print(f"   ✅ B 组正确 (耗时：{result.b_time:.2f}s)")
        else:
            print(f"   ❌ B 组错误 (预期：{case['expected_level']}, 实际：{b_result.get('suggestion', 'N/A')})")
        
        results.append(result)
        print()
    
    # 计算准确率
    total_valid = len(test_cases) - a_errors - b_errors
    total = len(test_cases)
    a_accuracy = a_correct / total if total > 0 else 0
    b_accuracy = b_correct / total if total > 0 else 0
    improvement = (a_accuracy - b_accuracy) * 100
    
    print("\n" + "=" * 80)
    print("📊 A/B 测试结果汇总")
    print("=" * 80)
    print(f"测试案例总数：{total}")
    print(f"A 组（人生故事 Agent）正确数：{a_correct}/{total}，准确率：{a_accuracy*100:.1f}%")
    print(f"B 组（属性标签 Agent）正确数：{b_correct}/{total}，准确率：{b_accuracy*100:.1f}%")
    print(f"准确率提升：{improvement:+.1f}%")
    if a_errors > 0 or b_errors > 0:
        print(f"错误数：A 组 {a_errors}个，B 组 {b_errors}个")
    print()
    
    # 按风险等级分组统计
    print("📋 按风险等级分组统计:")
    for level in ["red", "orange", "yellow", "green"]:
        level_cases = [r for r in results if r.expected_level == level]
        if level_cases:
            a_level_correct = sum(1 for r in level_cases if check_accuracy_match(r.a_result, level))
            b_level_correct = sum(1 for r in level_cases if check_accuracy_match(r.b_result, level))
            level_total = len(level_cases)
            print(f"  {level.upper()}: A 组 {a_level_correct}/{level_total} ({a_level_correct/level_total*100:.0f}%) vs B 组 {b_level_correct}/{level_total} ({b_level_correct/level_total*100:.0f}%)")
    
    # 性能统计
    avg_a_time = sum(r.a_time for r in results) / len(results) if results else 0
    avg_b_time = sum(r.b_time for r in results) / len(results) if results else 0
    print(f"\n⏱️  平均耗时：A 组 {avg_a_time:.2f}s, B 组 {avg_b_time:.2f}s")
    
    # 验收结论
    print("\n" + "=" * 80)
    print("🎯 验收结论")
    print("=" * 80)
    
    if improvement >= 15:
        print(f"✅ **验收通过**: 人生故事 Agent 准确率提升 {improvement:.1f}% ≥ 15%")
        print(f"   可以进入阶段 4（效果提升）")
        status = "PASS"
    elif improvement > 0:
        print(f"⚠️ **部分通过**: 人生故事 Agent 准确率提升 {improvement:.1f}% < 15%")
        print(f"   建议继续优化人生故事生成质量")
        status = "PARTIAL"
    else:
        print(f"❌ **未通过**: 人生故事 Agent 准确率提升 {improvement:.1f}%")
        print(f"   需要重新设计人生故事与风险评估的关联机制")
        status = "FAIL"
    
    # 生成报告
    report = {
        "test_date": datetime.now().isoformat(),
        "total_cases": total,
        "errors": {
            "a_group": a_errors,
            "b_group": b_errors,
        },
        "a_group": {
            "correct": a_correct,
            "accuracy": a_accuracy,
            "avg_time_seconds": avg_a_time,
        },
        "b_group": {
            "correct": b_correct,
            "accuracy": b_accuracy,
            "avg_time_seconds": avg_b_time,
        },
        "improvement_percent": improvement,
        "status": status,
        "case_results": [r.to_dict() for r in results],
    }
    
    # 保存 JSON 报告
    json_report_path = Path(__file__).parent / "PHASE3_AB_TEST_FULL_REPORT.json"
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 报告
    md_report_path = generate_markdown_report(report, results)
    
    print(f"\n📄 详细报告已保存到:")
    print(f"   JSON: {json_report_path}")
    print(f"   Markdown: {md_report_path}")
    
    return report


def generate_markdown_report(report: Dict[str, Any], results: List[CaseResult]) -> Path:
    """生成 Markdown 格式报告"""
    report_path = Path(__file__).parent / "PHASE3_AB_TEST_FULL_REPORT.md"
    
    lines = [
        "# 阶段 3 A/B 回测验证报告 - 完整版",
        "",
        f"**执行时间**: {report['test_date']}",
        "",
        "## 测试目标",
        "验证人生故事驱动的 Agent 相比传统属性标签 Agent，在风险评估准确率上的提升是否≥15%。",
        "",
        "## 测试结果总览",
        "",
        f"- **测试案例总数**: {report['total_cases']}",
        f"- **A 组（人生故事 Agent）**: {report['a_group']['correct']}/{report['total_cases']} ({report['a_group']['accuracy']*100:.1f}%), 平均耗时 {report['a_group']['avg_time_seconds']:.2f}s",
        f"- **B 组（属性标签 Agent）**: {report['b_group']['correct']}/{report['total_cases']} ({report['b_group']['accuracy']*100:.1f}%), 平均耗时 {report['b_group']['avg_time_seconds']:.2f}s",
        f"- **准确率提升**: {report['improvement_percent']:+.1f}%",
        f"- **验收状态**: {report['status']}",
        "",
        "## 验收结论",
        "",
    ]
    
    if report['status'] == "PASS":
        lines.append(f"✅ **验收通过**: 人生故事 Agent 准确率提升 {report['improvement_percent']:.1f}% ≥ 15%")
        lines.append("")
        lines.append("根据蓝图的 Go/No-Go 规则，可以进入阶段 4（效果提升）。")
    elif report['status'] == "PARTIAL":
        lines.append(f"⚠️ **部分通过**: 人生故事 Agent 准确率提升 {report['improvement_percent']:.1f}% < 15%")
        lines.append("")
        lines.append("建议继续优化人生故事生成质量和关联机制。")
    else:
        lines.append(f"❌ **未通过**: 人生故事 Agent 准确率提升 {report['improvement_percent']:.1f}%")
        lines.append("")
        lines.append("需要重新设计人生故事与风险评估的关联机制。")
    
    lines.extend([
        "",
        "## 详细案例结果",
        "",
        "| 案例 ID | 预期等级 | A 组结果 | B 组结果 | A 组正确 | B 组正确 |",
        "|--------|---------|---------|---------|---------|---------|",
    ])
    
    for r in results:
        a_match = "✅" if check_accuracy_match(r.a_result, r.expected_level) else "❌"
        b_match = "✅" if check_accuracy_match(r.b_result, r.expected_level) else "❌"
        a_suggestion = r.a_result.get('suggestion', 'N/A')[:20]
        b_suggestion = r.b_result.get('suggestion', 'N/A')[:20]
        lines.append(f"| {r.case_id} | {r.expected_level} | {a_suggestion} | {b_suggestion} | {a_match} | {b_match} |")
    
    lines.extend([
        "",
        "## 下一步建议",
        "",
    ])
    
    if report['status'] == "PASS":
        lines.append("1. 进入阶段 4：效果提升")
        lines.append("2. 优化 ChromaDB 性能（模型预热）")
        lines.append("3. 集成阿里 Paraformer 音频转写")
    else:
        lines.append("1. 优化人生故事→风险评估关联机制")
        lines.append("2. 增加人格特质敏感度权重")
        lines.append("3. 引入小样本人工评审")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    return report_path


def main():
    """主函数"""
    try:
        report = asyncio.run(run_ab_test())
        
        if report:
            if report["status"] == "PASS":
                print("\n🎉 A/B 回测验证通过，可以进入阶段 4！")
                return 0
            else:
                print("\n⚠️ A/B 回测验证未完全通过，建议优化后重试")
                return 1
        else:
            print("\n❌ 测试执行失败")
            return 1
            
    except Exception as e:
        print(f"\n❌ 测试执行出错：{e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
