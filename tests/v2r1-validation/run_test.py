"""V2.R1 版本测试脚本 - 10案例 MVP vs V2 对比"""

import asyncio
import json
import sys
import time
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent.parent

# 测试案例
TEST_CASES = [
    {
        "id": "case_01",
        "name": "哈佛蒋雨融演讲争议",
        "file": "cases/paperwork/哈佛蒋雨融演讲争议.md",
        "expected_dimensions": ["道德伦理", "群体冒犯", "时事踩雷"],
    },
    {
        "id": "case_02",
        "name": "全红婵饭圈侵入式监控",
        "file": "cases/paperwork/全红婵饭圈侵入式监控.md",
        "expected_dimensions": ["群体冒犯", "道德伦理"],
    },
    {
        "id": "case_03",
        "name": "同济大学教师论文造假",
        "file": "cases/paperwork/同济大学教师论文造假.md",
        "expected_dimensions": ["道德伦理", "法律合规"],
    },
    {
        "id": "case_04",
        "name": "王妈背刺打工人",
        "file": "cases/paperwork/王妈背刺打工人.md",
        "expected_dimensions": ["群体冒犯", "道德伦理"],
    },
    {
        "id": "case_05",
        "name": "网红小英卖惨塌房",
        "file": "cases/paperwork/网红小英卖惨塌房.md",
        "expected_dimensions": ["道德伦理", "群体冒犯"],
    },
    {
        "id": "case_06",
        "name": "闫学晶直播翻车",
        "file": "cases/paperwork/闫学晶直播翻车.md",
        "expected_dimensions": ["道德伦理"],
    },
    {
        "id": "case_07",
        "name": "优思益假洋牌事件",
        "file": "cases/paperwork/优思益假洋牌事件.md",
        "expected_dimensions": ["法律合规", "群体冒犯"],
    },
    {
        "id": "case_08",
        "name": "张雨绮代孕风波",
        "file": "cases/paperwork/张雨绮代孕风波.md",
        "expected_dimensions": ["道德伦理", "法律合规"],
    },
    {
        "id": "case_09",
        "name": "AI一键脱衣黑产",
        "file": "cases/paperwork/AI一键脱衣黑产.md",
        "expected_dimensions": ["法律合规", "道德伦理"],
    },
    {
        "id": "case_10",
        "name": "安全文案基准",
        "file": None,
        "text": "今天天气真不错，阳光明媚，适合出门散步。路边的花开得正好，微风拂面，心情愉快。",
        "expected_dimensions": [],
    },
]


async def run_test():
    """运行所有测试案例，对比MVP和V2结果"""
    from backend.services.enhanced_analyzer import run_enhanced_analysis
    from backend.services.analyzer import run_analysis
    from backend.database import SessionLocal, init_db
    from backend.models import Task

    init_db()

    results = []

    for case in TEST_CASES:
        # 读取文案
        if case.get("file"):
            file_path = ROOT / case["file"]
            if file_path.exists():
                text = file_path.read_text(encoding="utf-8")[:2000]
            else:
                print(f"  [跳过] 文件不存在: {file_path}")
                continue
        else:
            text = case.get("text", "")

        if len(text.strip()) < 10:
            print(f"  [跳过] 文案太短: {case['name']}")
            continue

        print(f"\n{'='*60}")
        print(f"测试案例: {case['name']} (预期维度: {case['expected_dimensions']})")
        print(f"{'='*60}")

        # 运行V2 quick模式
        db = SessionLocal()
        try:
            task_id_v2 = f"test_v2_{case['id']}"
            task = Task(id=task_id_v2, text=text[:500], status="processing", model="v2-quick")
            db.add(task)
            db.commit()
        finally:
            db.close()

        start = time.time()
        v2_result = await run_enhanced_analysis(
            task_id=task_id_v2,
            text=text,
            mode="quick",
            enable_signal=True,
            enable_entity_chain=True,
            enable_simulation=False,
        )
        v2_time = time.time() - start

        # 汇总结果
        case_result = {
            "case_id": case["id"],
            "case_name": case["name"],
            "expected_dimensions": case["expected_dimensions"],
            "mvp_score": v2_result.mvp_overall_score,
            "v2_score": v2_result.v2_overall_score,
            "mvp_dimensions": v2_result.mvp_dimensions,
            "v2_dimensions": v2_result.v2_dimensions,
            "signal_matches_count": len(v2_result.signal_match_result.matches) if v2_result.signal_match_result else 0,
            "entity_chains_count": len(v2_result.entity_risk_chain_result.chains) if v2_result.entity_risk_chain_result else 0,
            "confidence": v2_result.confidence,
            "analysis_time": v2_time,
            "has_dynamic_weight_adjustment": bool(v2_result.dynamic_weights_result and v2_result.dynamic_weights_result.adjustments),
            "error": v2_result.error,
        }

        results.append(case_result)

        # 输出摘要
        print(f"  MVP分数: {v2_result.mvp_overall_score}, V2分数: {v2_result.v2_overall_score}")
        print(f"  信号关联: {case_result['signal_matches_count']}条")
        print(f"  实体风险链: {case_result['entity_chains_count']}条")
        print(f"  可信度: {v2_result.confidence:.0%}")
        print(f"  耗时: {v2_time:.1f}s")
        if v2_result.error:
            print(f"  错误: {v2_result.error}")

    # 生成报告
    report = {
        "version": "V2.R1",
        "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(results),
        "results": results,
        "summary": {
            "avg_mvp_score": sum(r["mvp_score"] for r in results) / len(results) if results else 0,
            "avg_v2_score": sum(r["v2_score"] for r in results) / len(results) if results else 0,
            "avg_signal_matches": sum(r["signal_matches_count"] for r in results) / len(results) if results else 0,
            "avg_entity_chains": sum(r["entity_chains_count"] for r in results) / len(results) if results else 0,
            "avg_confidence": sum(r["confidence"] for r in results) / len(results) if results else 0,
            "avg_analysis_time": sum(r["analysis_time"] for r in results) / len(results) if results else 0,
            "dynamic_weight_adjustment_rate": sum(1 for r in results if r["has_dynamic_weight_adjustment"]) / len(results) if results else 0,
        },
    }

    # 保存报告
    report_dir = ROOT / "reports" / "version-comparison"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "R1_vs_MVP.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已保存: {report_path}")

    return report


if __name__ == "__main__":
    asyncio.run(run_test())
