"""V2.1 综合验证测试 — 3个深度分析案例 + 信号采集验证

测试内容：
1. 信号采集：热榜抓取、增量检测
2. 3个高风险文案的深度分析（5 Agent/平台 × 4平台 = 20 Agent/案例）
3. 每个案例生成独立报告文件

案例选择原则：覆盖7维风险中的多维度
- Case1: 明星人设崩塌（道德伦理+群体冒犯）
- Case2: 性别议题争议（性别议题+政治敏感）
- Case3: 职场压榨与996（群体冒犯+道德伦理+法律合规）
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TEST_DIR = Path(__file__).parent

# 测试文案
TEST_CASES = [
    {
        "case_id": "case1",
        "title": "顶流明星人设崩塌 — 道德伦理+群体冒犯",
        "description": "某顶流明星被曝光私生活混乱、出轨、粉丝经济剥削，文案为品牌方想发布的声明",
        "text": """近日关于我司代言艺人张某的负面传闻，我们高度重视。经核实，相关指控存在部分不实之处，但张某确实存在不当个人行为。我司决定暂停与张某的一切商业合作，并将已拍摄内容暂时下架。

我们理解广大粉丝和公众的失望，但恳请大家在事实未完全查清前，不要轻信和传播未经证实的信息。同时我们也希望媒体朋友能给予必要的隐私空间。

对于已购买相关产品的消费者，我们将在一周内公布退换方案。感谢大家的理解与支持。""",
    },
    {
        "case_id": "case2",
        "title": "性别议题争议内容 — 性别议题+政治敏感",
        "description": "某品牌营销文案涉及性别刻板印象，引发争议后的回应",
        "text": """关于近期"好妻子应该做的十件事"系列广告引发的讨论，我们认真倾听了各方声音。

该系列创意初衷是致敬传统家庭价值观，绝非固化性别角色。我们承认表达方式确实存在不当之处，对此深表歉意。即日起，该系列广告全面下架。

未来我们将组建更加多元的创意审核团队，确保内容传递平等包容的价值观。同时也希望这场讨论能促进社会对性别议题的理性对话，而非对立与攻击。

我们承诺，每一次失误都是成长的契机。""",
    },
    {
        "case_id": "case3",
        "title": "职场压榨与996 — 群体冒犯+道德伦理+法律合规",
        "description": "某互联网公司HR对外发布的招聘宣传文案，美化加班文化",
        "text": """加入我们，和最优秀的人一起战斗！

在这里，你不会觉得996是煎熬——因为热爱让你忘记时间。我们提供的不是一份工作，而是一个改变世界的机会。那些说我们压榨员工的人，可能从未体会过为梦想拼搏的快感。

我们的团队平均年龄28岁，每个人都在用200%的热情创造价值。当然，付出就有回报——期权、成长、视野，这些都是躺平者永远得不到的。

如果你也是那个愿意为理想燃烧的人，我们等你。不是每个人都能扛住这里的节奏，但留下来的，都是真正的精英。""",
    },
]


async def test_signal_collection():
    """测试信号采集系统"""
    from backend.services.signal.fetcher import HotlistFetcher
    from backend.services.signal.rss_fetcher import RssFetcher
    from backend.services.signal.event_detector import EventDetector

    results = {}

    # 1. 热榜抓取测试
    print("=" * 60)
    print("[1/4] 测试热榜抓取...")
    fetcher = HotlistFetcher()
    hotlist_results = await fetcher.fetch_all()
    total_signals = sum(len(v) for v in hotlist_results.values())
    results["hotlist"] = {
        "total_signals": total_signals,
        "platforms": {k: len(v) for k, v in hotlist_results.items()},
        "sample_titles": {
            k: [s.title for s in v[:3]]
            for k, v in hotlist_results.items()
        },
    }
    print(f"  热榜抓取完成: {total_signals} 条信号, 覆盖 {len(hotlist_results)} 个平台")

    # 2. RSS抓取测试
    print("[2/4] 测试RSS抓取...")
    import yaml
    config_path = PROJECT_ROOT / "config" / "signal_config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    feeds = config.get("signal", {}).get("rss", {}).get("feeds", [])
    rss_fetcher = RssFetcher()
    rss_results = await rss_fetcher.fetch_all(feeds)
    total_rss = sum(len(v) for v in rss_results.values())
    results["rss"] = {
        "total_signals": total_rss,
        "feeds": {k: len(v) for k, v in rss_results.items()},
    }
    print(f"  RSS抓取完成: {total_rss} 条信号")

    # 3. 事件检测测试
    print("[3/4] 测试事件检测...")
    all_signals = []
    for signals in hotlist_results.values():
        all_signals.extend(signals)
    if all_signals:
        detector = EventDetector()
        events = await detector.detect_events(all_signals[:100])  # 限制信号数量控制LLM成本
        results["event_detection"] = {
            "input_signals": min(len(all_signals), 100),
            "detected_events": len(events),
            "events": [
                {
                    "title": e.title,
                    "category": e.category.value,
                    "signal_strength": e.signal_strength,
                    "crawl_depth": e.crawl_depth.value,
                    "source_count": len(e.sources),
                }
                for e in sorted(events, key=lambda x: x.signal_strength, reverse=True)[:10]
            ],
        }
        print(f"  事件检测完成: {len(events)} 个事件")
    else:
        results["event_detection"] = {"error": "无信号输入"}
        print("  事件检测跳过: 无信号")

    # 4. 增量检测测试
    print("[4/4] 测试增量检测(数据库写入)...")
    from backend.database import SessionLocal
    from backend.services.signal.incremental import IncrementalDetector
    db = SessionLocal()
    try:
        detector = IncrementalDetector(db)
        incremental = await detector.detect(hotlist_results)
        results["incremental"] = {
            "new": len(incremental.get("new", [])),
            "changed": len(incremental.get("changed", [])),
            "unchanged": len(incremental.get("unchanged", [])),
        }
        print(f"  增量检测: 新增 {results['incremental']['new']}, 变化 {results['incremental']['changed']}")
    finally:
        db.close()

    return results


async def test_analysis_case(case: dict):
    """测试单个分析案例"""
    from backend.services.analyzer import run_analysis
    from backend.database import SessionLocal, engine
    import backend.models
    from backend.database import init_db
    init_db()

    print(f"\n{'=' * 60}")
    print(f"分析案例: {case['title']}")
    print(f"文案长度: {len(case['text'])} 字符")
    print("-" * 60)

    start_time = time.time()
    task_id = f"test_{case['case_id']}_{int(time.time())}"

    # 创建Task记录
    db = SessionLocal()
    try:
        from backend.models import Task
        task = Task(id=task_id, text=case["text"], status="processing", model="test")
        db.add(task)
        db.commit()
    finally:
        db.close()

    # 运行分析
    try:
        await run_analysis(task_id, case["text"])
    except Exception as e:
        print(f"  分析异常: {e}")

    elapsed = time.time() - start_time

    # 获取结果
    db = SessionLocal()
    try:
        from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or task.status != "completed":
            print(f"  分析未完成, 状态: {task.status if task else 'missing'}")
            return {"case_id": case["case_id"], "status": "failed", "error": "analysis not completed"}

        summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).first()
        risk_items = db.query(RiskItem).filter(RiskItem.task_id == task_id).all()
        reactions = db.query(PlatformReaction).filter(PlatformReaction.task_id == task_id).all()
    finally:
        db.close()

    # 组装报告
    report = {
        "case_id": case["case_id"],
        "title": case["title"],
        "description": case["description"],
        "text_length": len(case["text"]),
        "elapsed_seconds": round(elapsed, 1),
        "overall_score": summary.overall_score if summary else None,
        "suggestion": summary.suggestion if summary else None,
        "risk_dimensions": json.loads(summary.dimensions_json) if summary and summary.dimensions_json else {},
        "dimension_weights": json.loads(summary.dimension_weights) if summary and summary.dimension_weights else {},
        "cross_effects": json.loads(summary.cross_effects) if summary and summary.cross_effects else [],
        "risk_items": [
            {
                "sentence": r.sentence,
                "dimension": r.dimension,
                "severity": r.severity,
                "evidence": r.evidence,
                "affected_groups": r.affected_groups.split(",") if r.affected_groups else [],
            }
            for r in risk_items
        ],
        "platform_reactions": {
            r.platform: {
                "positive": r.positive,
                "neutral": r.neutral,
                "negative": r.negative,
                "reason": r.reason,
            }
            for r in reactions
        },
        "agents": json.loads(summary.agents_json) if summary and summary.agents_json else [],
        "rewrites": json.loads(summary.rewrites_json) if summary and summary.rewrites_json else [],
    }

    print(f"  总分: {report['overall_score']}")
    print(f"  建议: {report['suggestion']}")
    print(f"  风险句子: {len(report['risk_items'])} 条")
    print(f"  平台反应: {len(report['platform_reactions'])} 个平台")
    print(f"  Agent数: {len(report['agents'])} 个")
    print(f"  耗时: {report['elapsed_seconds']}s")

    return report


async def main():
    """主测试流程"""
    print("VibeUtopia V2.1 综合验证测试")
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"测试目录: {TEST_DIR}")

    # ===== Part 1: 信号采集测试 =====
    print("\n" + "=" * 60)
    print("PART 1: 信号采集系统测试")
    print("=" * 60)

    try:
        signal_results = await test_signal_collection()
        signal_report_path = TEST_DIR / "signal_collection_report.json"
        with open(signal_report_path, "w", encoding="utf-8") as f:
            json.dump(signal_results, f, ensure_ascii=False, indent=2)
        print(f"\n信号采集报告已保存: {signal_report_path}")
    except Exception as e:
        print(f"\n信号采集测试失败: {e}")
        import traceback
        traceback.print_exc()
        signal_results = {"error": str(e)}

    # ===== Part 2: 深度分析测试 =====
    print("\n" + "=" * 60)
    print("PART 2: 3个深度分析案例测试")
    print("=" * 60)

    analysis_results = {}
    for case in TEST_CASES:
        try:
            report = await test_analysis_case(case)
            case_dir = TEST_DIR / f"case{case['case_id']}-{case['title'].split('—')[0].strip()}"
            case_dir.mkdir(parents=True, exist_ok=True)

            report_path = case_dir / "analysis_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            # 生成可读的Markdown报告
            md_report = generate_markdown_report(case, report)
            md_path = case_dir / "analysis_report.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_report)

            print(f"  报告已保存: {case_dir}")
            analysis_results[case["case_id"]] = report
        except Exception as e:
            print(f"  案例 {case['case_id']} 分析失败: {e}")
            import traceback
            traceback.print_exc()

    # ===== Part 3: 汇总 =====
    print("\n" + "=" * 60)
    print("测试完成汇总")
    print("=" * 60)

    summary = {
        "test_time": datetime.now().isoformat(),
        "signal_collection": {
            "status": "pass" if "error" not in signal_results else "fail",
            "total_signals": signal_results.get("hotlist", {}).get("total_signals", 0),
            "platforms_tested": len(signal_results.get("hotlist", {}).get("platforms", {})),
            "events_detected": signal_results.get("event_detection", {}).get("detected_events", 0),
        },
        "analysis_cases": {},
    }

    for case_id, report in analysis_results.items():
        summary["analysis_cases"][case_id] = {
            "overall_score": report.get("overall_score"),
            "suggestion": report.get("suggestion"),
            "risk_count": len(report.get("risk_items", [])),
            "agent_count": len(report.get("agents", [])),
            "elapsed": report.get("elapsed_seconds"),
        }

    summary_path = TEST_DIR / "test_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 打印汇总表
    print(f"\n{'案例':<25} {'总分':<8} {'建议':<12} {'风险句':<8} {'Agent':<8} {'耗时':<8}")
    print("-" * 75)
    for case_id, info in summary["analysis_cases"].items():
        print(f"{case_id:<25} {info['overall_score'] or 'N/A':<8} {info['suggestion'] or 'N/A':<12} {info['risk_count']:<8} {info['agent_count']:<8} {info['elapsed'] or 'N/A':<8}")

    print(f"\n信号采集: {summary['signal_collection']['total_signals']} 条信号, {summary['signal_collection']['events_detected']} 个事件检测")
    print(f"\n所有报告保存在: {TEST_DIR}")


def generate_markdown_report(case: dict, report: dict) -> str:
    """生成可读的Markdown分析报告"""
    lines = [
        f"# {case['title']}",
        "",
        f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**文案长度**: {report.get('text_length', 0)} 字符",
        f"**分析耗时**: {report.get('elapsed_seconds', 0)} 秒",
        "",
        "---",
        "",
        "## 总体评估",
        "",
        f"- **总分**: {report.get('overall_score', 'N/A')}/100",
        f"- **建议**: {report.get('suggestion', 'N/A')}",
        "",
    ]

    # 风险维度
    dims = report.get("risk_dimensions", {})
    if dims:
        lines.append("## 七维风险评估")
        lines.append("")
        lines.append("| 维度 | 分数 |")
        lines.append("|------|------|")
        for dim, score in dims.items():
            lines.append(f"| {dim} | {score} |")
        lines.append("")

    # 风险句子
    risk_items = report.get("risk_items", [])
    if risk_items:
        lines.append("## 风险句子定位")
        lines.append("")
        for item in risk_items:
            severity = item.get("severity", "")
            icon = {"high": "H", "medium": "M", "low": "L"}.get(severity, "?")
            lines.append(f"### [{icon}] {item.get('sentence', '')[:50]}...")
            lines.append(f"- **维度**: {item.get('dimension', '')}")
            lines.append(f"- **严重程度**: {severity}")
            lines.append(f"- **判定依据**: {item.get('evidence', '')}")
            groups = item.get("affected_groups", [])
            if groups:
                lines.append(f"- **影响群体**: {', '.join(groups)}")
            lines.append("")

    # 平台反应
    reactions = report.get("platform_reactions", {})
    if reactions:
        platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
        lines.append("## 平台情绪预测")
        lines.append("")
        lines.append("| 平台 | 正面 | 中性 | 负面 |")
        lines.append("|------|------|------|------|")
        for platform, r in reactions.items():
            name = platform_names.get(platform, platform)
            lines.append(f"| {name} | {r.get('positive', 0)*100:.0f}% | {r.get('neutral', 0)*100:.0f}% | {r.get('negative', 0)*100:.0f}% |")
        lines.append("")

    # Agent视角
    agents = report.get("agents", [])
    if agents:
        lines.append("## Agent 视角洞察")
        lines.append("")
        platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
        lines.append(f"共 **{len(agents)}** 个差异化Agent参与模拟")
        lines.append("")

        # 按平台分组
        platform_groups = {}
        for agent in agents:
            p = agent.get("platform", "unknown")
            if p not in platform_groups:
                platform_groups[p] = []
            platform_groups[p].append(agent)

        for platform, platform_agents in platform_groups.items():
            p_name = platform_names.get(platform, platform)
            lines.append(f"### {p_name} ({len(platform_agents)}个Agent)")
            lines.append("")
            for agent in platform_agents:
                reaction = agent.get("reaction_type", "neutral")
                persona_name = agent.get("persona_name", "匿名用户")
                archetype = agent.get("archetype", "")
                comment = agent.get("comment", "")
                focus = agent.get("focus", "")
                intensity = agent.get("emotional_intensity", 0)

                lines.append(f"**{persona_name}** ({archetype}) - 反应: {reaction}, 情感强度: {intensity:.1f}")
                if comment:
                    lines.append(f"> {comment}")
                if focus:
                    lines.append(f"- 关注点: {focus}")
                lines.append("")

    # 改写建议
    rewrites = report.get("rewrites", [])
    if rewrites:
        lines.append("## 安全改写建议")
        lines.append("")
        for rw in rewrites:
            original = rw.get("original", "")
            options = rw.get("rewrites", [])
            lines.append(f"**原句**: {original}")
            if options:
                for i, opt in enumerate(options, 1):
                    lines.append(f"- 改写{i}: {opt}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
