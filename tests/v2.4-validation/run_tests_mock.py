"""V2.4 社交仿真验证 — 使用模拟Agent数据（不依赖LLM生成）"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TEST_DIR = os.path.dirname(os.path.abspath(__file__))

# 模拟Agent数据（覆盖4平台）
MOCK_AGENTS = {
    "bilibili": [
        {"persona_id": "bili_001", "platform": "bilibili", "archetype_base": "bili_core_acg",
         "L1_basic": {"age_range": "18-25", "gender": "male", "occupation": "学生", "region": "一线城市", "income": "中低", "education": "本科"},
         "L2_values": {"political_tendency": 4.0, "consumerism": 6.0, "family_tradition": 3.0, "social_justice": 7.0, "tech_optimism": 8.0},
         "L3_knowledge": {"professional_domains": ["ACG", "互联网"], "information_sources": ["B站", "微博"], "cognitive_level": "中等", "media_literacy": "高"},
         "L4_behavior": {"expression_style": "直率", "interaction_preference": "活跃评论", "content_preference": ["动画", "游戏"], "active_hours": "晚间"},
         "L5_correction": {"cultural_taboos": ["低俗内容"], "sensitive_triggers": ["资本操控"], "avoided_topics": [], "self_censorship": "低"},
         "L6_social": {"social_circles": ["二次元圈"], "influence_level": "活跃分子", "followed_kol_domains": ["动画UP主"], "social_activity": "高"},
         "L7_evolution": {"recent_experiences": ["追番被断更"], "emotional_baseline": "平稳", "attitude_changes": ["对平台越来越不满"], "memory_anchors": ["第一次追番"]}},
        {"persona_id": "bili_002", "platform": "bilibili", "archetype_base": "bili_tech_geek",
         "L1_basic": {"age_range": "25-30", "gender": "male", "occupation": "程序员/工程师", "region": "一线城市", "income": "高", "education": "硕士"},
         "L2_values": {"political_tendency": 5.0, "consumerism": 4.0, "family_tradition": 4.0, "social_justice": 6.0, "tech_optimism": 9.0},
         "L3_knowledge": {"professional_domains": ["技术", "编程"], "information_sources": ["GitHub", "知乎"], "cognitive_level": "高级", "media_literacy": "高"},
         "L4_behavior": {"expression_style": "中立", "interaction_preference": "偶尔评论", "content_preference": ["科技", "编程"], "active_hours": "深夜"},
         "L5_correction": {"cultural_taboos": [], "sensitive_triggers": ["技术偏见"], "avoided_topics": ["政治"], "self_censorship": "中等"},
         "L6_social": {"social_circles": ["技术圈"], "influence_level": "普通用户", "followed_kol_domains": ["技术博主"], "social_activity": "中等"},
         "L7_evolution": {"recent_experiences": ["项目上线成功"], "emotional_baseline": "积极", "attitude_changes": [], "memory_anchors": ["第一个开源项目"]}},
    ],
    "xiaohongshu": [
        {"persona_id": "xhs_001", "platform": "xiaohongshu", "archetype_base": "xhs_quality_seeker",
         "L1_basic": {"age_range": "25-35", "gender": "female", "occupation": "品质生活追求者", "region": "一线城市", "income": "中高", "education": "本科"},
         "L2_values": {"political_tendency": 5.0, "consumerism": 8.0, "family_tradition": 5.0, "social_justice": 6.0, "tech_optimism": 5.0},
         "L3_knowledge": {"professional_domains": ["时尚", "美妆"], "information_sources": ["小红书", "微博"], "cognitive_level": "中等", "media_literacy": "中等"},
         "L4_behavior": {"expression_style": "温和", "interaction_preference": "活跃评论", "content_preference": ["护肤", "美食"], "active_hours": "晚间"},
         "L5_correction": {"cultural_taboos": ["身材羞辱"], "sensitive_triggers": ["消费陷阱"], "avoided_topics": [], "self_censorship": "中等"},
         "L6_social": {"social_circles": ["品质生活圈"], "influence_level": "KOL", "followed_kol_domains": ["美妆博主"], "social_activity": "高"},
         "L7_evolution": {"recent_experiences": ["种草踩雷"], "emotional_baseline": "平稳", "attitude_changes": ["更理性消费"], "memory_anchors": ["第一次成功种草"]}},
    ],
    "zhihu": [
        {"persona_id": "zhihu_001", "platform": "zhihu", "archetype_base": "zhihu_rational_scholar",
         "L1_basic": {"age_range": "30-40", "gender": "male", "occupation": "学者/研究员", "region": "一线城市", "income": "中等", "education": "博士"},
         "L2_values": {"political_tendency": 4.0, "consumerism": 3.0, "family_tradition": 5.0, "social_justice": 7.0, "tech_optimism": 6.0},
         "L3_knowledge": {"professional_domains": ["社会科学", "经济学"], "information_sources": ["学术论文", "知乎"], "cognitive_level": "高级", "media_literacy": "高"},
         "L4_behavior": {"expression_style": "谨慎", "interaction_preference": "创作者", "content_preference": ["时政", "经济学"], "active_hours": "上午"},
         "L5_correction": {"cultural_taboos": ["学术不端"], "sensitive_triggers": ["民科"], "avoided_topics": ["娱乐八卦"], "self_censorship": "高"},
         "L6_social": {"social_circles": ["学术圈"], "influence_level": "KOL", "followed_kol_domains": ["经济学家"], "social_activity": "中等"},
         "L7_evolution": {"recent_experiences": ["论文被引用"], "emotional_baseline": "平稳", "attitude_changes": [], "memory_anchors": ["一次高赞回答"]}},
    ],
    "douyin": [
        {"persona_id": "dy_001", "platform": "douyin", "archetype_base": "dy_young_trendsetter",
         "L1_basic": {"age_range": "18-24", "gender": "female", "occupation": "学生", "region": "二线城市", "income": "低", "education": "本科"},
         "L2_values": {"political_tendency": 5.0, "consumerism": 7.0, "family_tradition": 3.0, "social_justice": 6.0, "tech_optimism": 7.0},
         "L3_knowledge": {"professional_domains": ["娱乐", "潮流"], "information_sources": ["抖音", "微博"], "cognitive_level": "中等", "media_literacy": "中等"},
         "L4_behavior": {"expression_style": "直率", "interaction_preference": "活跃评论", "content_preference": ["短视频", "挑战"], "active_hours": "晚间"},
         "L5_correction": {"cultural_taboos": ["低俗"], "sensitive_triggers": ["身材焦虑"], "avoided_topics": [], "self_censorship": "低"},
         "L6_social": {"social_circles": ["追星圈"], "influence_level": "活跃分子", "followed_kol_domains": ["爱豆"], "social_activity": "高"},
         "L7_evolution": {"recent_experiences": ["追星成功"], "emotional_baseline": "积极", "attitude_changes": [], "memory_anchors": ["第一次追星"]}},
        {"persona_id": "dy_002", "platform": "douyin", "archetype_base": "dy_patriotic_worker",
         "L1_basic": {"age_range": "35-50", "gender": "male", "occupation": "蓝领工人", "region": "三线城市", "income": "中低", "education": "高中"},
         "L2_values": {"political_tendency": 8.0, "consumerism": 3.0, "family_tradition": 8.0, "social_justice": 5.0, "tech_optimism": 4.0},
         "L3_knowledge": {"professional_domains": ["制造业"], "information_sources": ["抖音", "微信"], "cognitive_level": "初级", "media_literacy": "低"},
         "L4_behavior": {"expression_style": "激进", "interaction_preference": "偶尔评论", "content_preference": ["新闻", "军事"], "active_hours": "午间"},
         "L5_correction": {"cultural_taboos": ["侮辱国家"], "sensitive_triggers": ["崇洋媚外"], "avoided_topics": [], "self_censorship": "低"},
         "L6_social": {"social_circles": ["工友"], "influence_level": "普通用户", "followed_kol_domains": ["军事博主"], "social_activity": "中等"},
         "L7_evolution": {"recent_experiences": ["加班被扣工资"], "emotional_baseline": "低落", "attitude_changes": ["更关注劳动权益"], "memory_anchors": ["看到劳动者互助"]}},
    ],
}

TEST_CASES = [
    {"case_id": "case1-celebrity-scandal", "name": "明星人设崩塌",
     "topic": "某顶流明星被曝出私生活混乱，与公众人设严重不符，引发全网热议。该明星此前以正能量形象获得大量代言，事件曝光后多个品牌宣布解约。"},
    {"case_id": "case2-gender-debate", "name": "性别议题争议",
     "topic": "某知名企业家在公开场合发表关于女性职场竞争力的争议性言论，称'女性在高压行业中天然劣势'，引发性别平等议题的激烈讨论。"},
    {"case_id": "case3-workplace-exploitation", "name": "职场压榨与996",
     "topic": "某互联网大厂员工猝死事件引发对996工作制的声讨，公司回应称'员工自愿加班'，进一步激化矛盾。多名前员工曝光公司压榨文化。"},
]


def seed_mock_agents():
    """将模拟Agent写入数据库"""
    from backend.database import SessionLocal
    from backend.models import AgentRecord

    db = SessionLocal()
    try:
        count = 0
        for platform, agents in MOCK_AGENTS.items():
            for agent in agents:
                record = AgentRecord(
                    agent_id=agent["persona_id"],
                    platform=platform,
                    archetype_base=agent.get("archetype_base", ""),
                    persona_json=json.dumps(agent, ensure_ascii=False),
                    quality_score=0.8,
                    status="active",
                    version=1,
                )
                db.merge(record)
                count += 1
        db.commit()
        print(f"已插入 {count} 个模拟Agent到数据库")
        return count
    except Exception as e:
        db.rollback()
        print(f"插入失败: {e}")
        return 0
    finally:
        db.close()


async def run_case(case: dict) -> dict:
    from backend.services.simulation.engine import SimulationEngine
    from backend.services.simulation.models import AgentTier

    case_id = case["case_id"]
    case_name = case["name"]
    topic = case["topic"]

    print(f"\n{'='*60}")
    print(f"案例: {case_name}")
    print(f"{'='*60}")

    sim_id = f"test_{case_id}_{int(time.time())}"
    engine = SimulationEngine(
        sim_id=sim_id, topic=topic,
        config={"max_ticks": 20, "start_hour": 8, "time_acceleration": 60, "tick_interval": 0.1, "b_agent_per_tick": 0},
    )

    from backend.database import SessionLocal
    from backend.models import SimulationStatus
    db = SessionLocal()
    try:
        db.add(SimulationStatus(sim_id=sim_id, status="created", topic=topic, total_agents=0,
                                config_json=json.dumps({"test_case": case_id, "c_only": True})))
        db.commit()
    finally:
        db.close()

    await engine.initialize()
    for aid in engine.agent_tiers:
        engine.agent_tiers[aid] = AgentTier.C

    print(f"  Agent: {len(engine.agents)} 个, 平台: {list(engine.platforms.keys())}")

    t0 = time.time()
    await engine.run()
    sim_time = time.time() - t0

    total_actions = 0
    by_type = {}
    by_platform = {}
    for tick in engine.tick_results:
        for action in tick.actions:
            total_actions += 1
            by_type[action.action_type] = by_type.get(action.action_type, 0) + 1
            by_platform[action.platform] = by_platform.get(action.platform, 0) + 1

    result = {
        "case_id": case_id, "case_name": case_name, "topic": topic, "sim_id": sim_id,
        "agent_count": len(engine.agents), "total_ticks": engine.current_tick,
        "sim_time_sec": round(sim_time, 1), "total_actions": total_actions,
        "by_type": by_type, "by_platform": by_platform,
        "tick_summaries": [{"tick": t.tick, "sim_time": t.sim_time, "time_slot": t.time_slot, "action_count": len(t.actions)} for t in engine.tick_results],
        "sample_actions": [{"tick": t.tick, "sim_time": t.sim_time, "actions": [a.to_dict() for a in t.actions[:5]]} for t in engine.tick_results[:5]],
        "platform_snapshots": {p: plat.get_snapshot() for p, plat in engine.platforms.items()},
    }

    case_dir = os.path.join(TEST_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)

    with open(os.path.join(case_dir, "simulation_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    md = f"# {case_name} — 社交仿真报告\n\n"
    md += f"- 话题: {topic}\n- Agent数: {len(engine.agents)} (C级规则引擎)\n"
    md += f"- Tick: {engine.current_tick}\n- 总行为: {total_actions}\n- 耗时: {sim_time:.1f}s\n\n"
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
    for sample in result["sample_actions"][:5]:
        md += f"### Tick {sample['tick']} ({sample['sim_time']})\n\n"
        for a in sample["actions"][:3]:
            content_preview = a.get("content", "")[:80] if a.get("content") else ""
            md += f"- **{a.get('agent_id','?')[:12]}** @ {a.get('platform','')} → {a.get('action_type','')} {content_preview}\n"
        md += "\n"

    with open(os.path.join(case_dir, "simulation_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(f"  完成: {total_actions} 个行为, {sim_time:.1f}s")
    print(f"  行为分布: {by_type}")
    print(f"  平台分布: {by_platform}")
    print(f"  报告: {case_dir}")
    return result


async def main():
    print("=" * 60)
    print("V2.4 社交仿真验证 (模拟Agent + C级规则引擎)")
    print("=" * 60)

    agent_count = seed_mock_agents()
    if agent_count == 0:
        print("无法插入模拟Agent，测试终止")
        return

    results = []
    for case in TEST_CASES:
        try:
            result = await run_case(case)
            results.append(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append({"case_id": case["case_id"], "case_name": case["name"], "error": str(e)})

    summary = {
        "test_time": datetime.now().isoformat(), "total_cases": len(TEST_CASES),
        "results": [{"case_id": r.get("case_id"), "case_name": r.get("case_name", "ERROR"),
                      "agent_count": r.get("agent_count", 0), "total_ticks": r.get("total_ticks", 0),
                      "total_actions": r.get("total_actions", 0), "sim_time_sec": r.get("sim_time_sec", 0),
                      "by_type": r.get("by_type", {}), "by_platform": r.get("by_platform", {}),
                      "error": r.get("error")} for r in results],
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
