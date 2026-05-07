"""V2.4 社交仿真验证 — 3个案例测试

测试流程：
1. 生成Agent（每平台5个 = 20个）
2. 创建仿真任务
3. 运行仿真（短时：20 ticks）
4. 导出结果到独立文件夹
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

# 3个测试案例
TEST_CASES = [
    {
        "case_id": "case1-celebrity-scandal",
        "name": "明星人设崩塌",
        "topic": "某顶流明星被曝出私生活混乱，与公众人设严重不符，引发全网热议。该明星此前以正能量形象获得大量代言，事件曝光后多个品牌宣布解约。",
        "risk_dimensions": ["道德伦理", "群体冒犯"],
    },
    {
        "case_id": "case2-gender-debate",
        "name": "性别议题争议",
        "topic": "某知名企业家在公开场合发表关于女性职场竞争力的争议性言论，称'女性在高压行业中天然劣势'，引发性别平等议题的激烈讨论。",
        "risk_dimensions": ["政治敏感", "性别议题"],
    },
    {
        "case_id": "case3-workplace-exploitation",
        "name": "职场压榨与996",
        "topic": "某互联网大厂员工猝死事件引发对996工作制的声讨，公司回应称'员工自愿加班'，进一步激化矛盾。多名前员工曝光公司压榨文化。",
        "risk_dimensions": ["群体冒犯", "道德伦理", "法律合规"],
    },
]


async def run_case(case: dict) -> dict:
    """运行单个测试案例"""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.persona_generator import generate_agents_cross_platform

    case_id = case["case_id"]
    case_name = case["name"]
    topic = case["topic"]

    print(f"\n{'='*60}")
    print(f"案例: {case_name}")
    print(f"话题: {topic[:80]}...")
    print(f"{'='*60}")

    # Step 1: 生成Agent
    print("[1/4] 生成Agent...")
    t0 = time.time()
    agents_result = await generate_agents_cross_platform(
        platforms=["bilibili", "xiaohongshu", "zhihu", "douyin"],
        count_per_platform=5,
        persist=True,
    )
    agent_count = sum(len(v) for v in agents_result.values())
    gen_time = time.time() - t0
    print(f"  生成 {agent_count} 个Agent, 耗时 {gen_time:.1f}s")

    # Step 2: 创建仿真
    print("[2/4] 创建仿真引擎...")
    sim_id = f"test_{case_id}_{int(time.time())}"
    engine = SimulationEngine(
        sim_id=sim_id,
        topic=topic,
        config={
            "max_ticks": 20,  # 短时测试
            "start_hour": 8,
            "time_acceleration": 60,
            "tick_interval": 0.3,
            "b_agent_per_tick": 3,
        },
    )

    # 持久化仿真状态
    from backend.database import SessionLocal
    from backend.models import SimulationStatus
    db = SessionLocal()
    try:
        db.add(SimulationStatus(
            sim_id=sim_id,
            status="created",
            topic=topic,
            total_agents=0,
            config_json=json.dumps({"test_case": case_id}, ensure_ascii=False),
        ))
        db.commit()
    finally:
        db.close()

    await engine.initialize()
    print(f"  引擎初始化完成: {len(engine.agents)} 个Agent, {len(engine.platforms)} 个平台")

    # Step 3: 运行仿真
    print("[3/4] 运行仿真 (20 ticks)...")
    t0 = time.time()
    await engine.run()
    sim_time = time.time() - t0
    print(f"  仿真完成: {engine.current_tick} ticks, 耗时 {sim_time:.1f}s")

    # Step 4: 收集结果
    print("[4/4] 收集结果...")
    status = engine.get_status()

    # 统计行为
    total_actions = 0
    by_type = {}
    by_platform = {}
    for tick in engine.tick_results:
        for action in tick.actions:
            total_actions += 1
            by_type[action.action_type] = by_type.get(action.action_type, 0) + 1
            by_platform[action.platform] = by_platform.get(action.platform, 0) + 1

    result = {
        "case_id": case_id,
        "case_name": case_name,
        "topic": topic,
        "risk_dimensions": case["risk_dimensions"],
        "sim_id": sim_id,
        "agent_count": agent_count,
        "gen_time_sec": round(gen_time, 1),
        "total_ticks": engine.current_tick,
        "sim_time_sec": round(sim_time, 1),
        "total_actions": total_actions,
        "by_type": by_type,
        "by_platform": by_platform,
        "platform_snapshots": status.get("platforms", {}),
        "tick_summaries": [
            {
                "tick": t.tick,
                "sim_time": t.sim_time,
                "time_slot": t.time_slot,
                "action_count": len(t.actions),
            }
            for t in engine.tick_results
        ],
        "sample_actions": [
            {
                "tick": t.tick,
                "sim_time": t.sim_time,
                "actions": [a.to_dict() for a in t.actions[:5]],
            }
            for t in engine.tick_results[:5]
        ],
    }

    # 保存到独立文件夹
    case_dir = os.path.join(TEST_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)

    # JSON报告
    with open(os.path.join(case_dir, "simulation_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Markdown报告
    md = f"# {case_name} — 社交仿真报告\n\n"
    md += f"- 话题: {topic}\n"
    md += f"- 风险维度: {', '.join(case['risk_dimensions'])}\n"
    md += f"- Agent数: {agent_count}\n"
    md += f"- 仿真Tick: {engine.current_tick}\n"
    md += f"- 总行为数: {total_actions}\n\n"
    md += f"## 行为分布\n\n"
    md += f"| 类型 | 数量 |\n|------|------|\n"
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        md += f"| {t} | {c} |\n"
    md += f"\n## 平台分布\n\n"
    md += f"| 平台 | 行为数 |\n|------|--------|\n"
    for p, c in sorted(by_platform.items(), key=lambda x: -x[1]):
        md += f"| {p} | {c} |\n"
    md += f"\n## 时间线\n\n"
    md += f"| Tick | 时间 | 时段 | 行为数 |\n|------|------|------|--------|\n"
    for ts in result["tick_summaries"]:
        md += f"| {ts['tick']} | {ts['sim_time']} | {ts['time_slot']} | {ts['action_count']} |\n"

    # 样例行为
    md += f"\n## 样例行为\n\n"
    for sample in result["sample_actions"][:3]:
        md += f"### Tick {sample['tick']} ({sample['sim_time']})\n\n"
        for a in sample["actions"][:3]:
            content_preview = a.get("content", "")[:100] if a.get("content") else ""
            md += f"- **{a.get('agent_id','?')[:12]}...** @ {a.get('platform','')} → {a.get('action_type','')} {content_preview}\n"
        md += "\n"

    with open(os.path.join(case_dir, "simulation_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  报告已保存到: {case_dir}")
    return result


async def main():
    """运行所有测试案例"""
    print("=" * 60)
    print("V2.4 社交仿真验证")
    print(f"测试案例: {len(TEST_CASES)} 个")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    results = []
    for case in TEST_CASES:
        try:
            result = await run_case(case)
            results.append(result)
        except Exception as e:
            print(f"案例 {case['case_id']} 失败: {e}")
            import traceback
            traceback.print_exc()
            results.append({"case_id": case["case_id"], "error": str(e)})

    # 汇总
    summary = {
        "test_time": datetime.now().isoformat(),
        "total_cases": len(TEST_CASES),
        "results": [
            {
                "case_id": r.get("case_id"),
                "case_name": r.get("case_name", "ERROR"),
                "agent_count": r.get("agent_count", 0),
                "total_ticks": r.get("total_ticks", 0),
                "total_actions": r.get("total_actions", 0),
                "sim_time_sec": r.get("sim_time_sec", 0),
                "error": r.get("error"),
            }
            for r in results
        ],
    }

    with open(os.path.join(TEST_DIR, "test_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("测试完成!")
    print(f"{'='*60}")
    for r in summary["results"]:
        status = "✓" if not r.get("error") else "✗"
        print(f"  {status} {r['case_name']}: {r.get('total_actions',0)} actions, {r.get('sim_time_sec',0):.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
