"""V2.4 社交仿真快速验证 — 仅C级规则引擎（不调用LLM）"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_CASES = [
    {
        "case_id": "case1-celebrity-scandal",
        "name": "明星人设崩塌",
        "topic": "某顶流明星被曝出私生活混乱，与公众人设严重不符，引发全网热议。该明星此前以正能量形象获得大量代言，事件曝光后多个品牌宣布解约。",
    },
    {
        "case_id": "case2-gender-debate",
        "name": "性别议题争议",
        "topic": "某知名企业家在公开场合发表关于女性职场竞争力的争议性言论，称'女性在高压行业中天然劣势'，引发性别平等议题的激烈讨论。",
    },
    {
        "case_id": "case3-workplace-exploitation",
        "name": "职场压榨与996",
        "topic": "某互联网大厂员工猝死事件引发对996工作制的声讨，公司回应称'员工自愿加班'，进一步激化矛盾。多名前员工曝光公司压榨文化。",
    },
]


async def run_case(case: dict) -> dict:
    """运行单个测试案例 — 仅C级规则引擎"""
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.models import AgentTier

    case_id = case["case_id"]
    case_name = case["name"]
    topic = case["topic"]

    print(f"\n{'='*60}")
    print(f"案例: {case_name}")
    print(f"话题: {topic[:60]}...")
    print(f"{'='*60}")

    # 创建仿真引擎
    sim_id = f"test_{case_id}_{int(time.time())}"
    engine = SimulationEngine(
        sim_id=sim_id,
        topic=topic,
        config={
            "max_ticks": 20,
            "start_hour": 8,
            "time_acceleration": 60,
            "tick_interval": 0.1,
            "b_agent_per_tick": 0,  # 不使用LLM，纯C级
        },
    )

    # 持久化状态
    from backend.database import SessionLocal
    from backend.models import SimulationStatus
    db = SessionLocal()
    try:
        db.add(SimulationStatus(
            sim_id=sim_id, status="created", topic=topic,
            total_agents=0, config_json=json.dumps({"test_case": case_id, "c_only": True}),
        ))
        db.commit()
    finally:
        db.close()

    await engine.initialize()

    # 强制所有Agent为C级
    for aid in engine.agent_tiers:
        engine.agent_tiers[aid] = AgentTier.C

    print(f"  引擎初始化: {len(engine.agents)} 个Agent, 全部C级(规则引擎)")

    # 运行仿真
    t0 = time.time()
    await engine.run()
    sim_time = time.time() - t0
    print(f"  仿真完成: {engine.current_tick} ticks, 耗时 {sim_time:.1f}s")

    # 收集结果
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
        "sim_id": sim_id,
        "agent_count": len(engine.agents),
        "total_ticks": engine.current_tick,
        "sim_time_sec": round(sim_time, 1),
        "total_actions": total_actions,
        "by_type": by_type,
        "by_platform": by_platform,
        "tick_summaries": [
            {"tick": t.tick, "sim_time": t.sim_time, "time_slot": t.time_slot, "action_count": len(t.actions)}
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
        "platform_snapshots": {p: plat.get_snapshot() for p, plat in engine.platforms.items()},
    }

    # 保存到独立文件夹
    case_dir = os.path.join(TEST_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)

    with open(os.path.join(case_dir, "simulation_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Markdown报告
    md = f"# {case_name} — 社交仿真报告\n\n"
    md += f"- 话题: {topic}\n"
    md += f"- Agent数: {len(engine.agents)} (全部C级规则引擎)\n"
    md += f"- 仿真Tick: {engine.current_tick}\n"
    md += f"- 总行为数: {total_actions}\n"
    md += f"- 仿真耗时: {sim_time:.1f}s\n\n"
    md += f"## 行为分布\n\n| 类型 | 数量 |\n|------|------|\n"
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        md += f"| {t} | {c} |\n"
    md += f"\n## 平台分布\n\n| 平台 | 行为数 |\n|------|--------|\n"
    for p, c in sorted(by_platform.items(), key=lambda x: -x[1]):
        md += f"| {p} | {c} |\n"
    md += f"\n## 时间线\n\n| Tick | 时间 | 时段 | 行为数 |\n|------|------|------|--------|\n"
    for ts in result["tick_summaries"]:
        md += f"| {ts['tick']} | {ts['sim_time']} | {ts['time_slot']} | {ts['action_count']} |\n"
    md += f"\n## 样例行为\n\n"
    for sample in result["sample_actions"][:3]:
        md += f"### Tick {sample['tick']} ({sample['sim_time']})\n\n"
        for a in sample["actions"][:3]:
            content_preview = a.get("content", "")[:80] if a.get("content") else ""
            md += f"- **{a.get('agent_id','?')[:12]}...** @ {a.get('platform','')} → {a.get('action_type','')} {content_preview}\n"
        md += "\n"

    # 平台详细快照
    md += f"\n## 平台快照\n\n"
    for p, snap in result["platform_snapshots"].items():
        md += f"### {p}\n"
        for k, v in snap.items():
            md += f"- {k}: {v}\n"
        md += "\n"

    with open(os.path.join(case_dir, "simulation_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  报告已保存: {case_dir}")
    return result


async def main():
    print("=" * 60)
    print("V2.4 社交仿真验证 (C级规则引擎)")
    print(f"案例: {len(TEST_CASES)} 个")
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
    for r in summary["results"]:
        status = "PASS" if not r.get("error") else "FAIL"
        print(f"  [{status}] {r['case_name']}: {r.get('total_actions',0)} actions, {r.get('sim_time_sec',0):.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
