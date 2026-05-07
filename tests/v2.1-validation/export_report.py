"""生成测试报告 — 从数据库导出Case1结果并写入正式目录"""
import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import SessionLocal
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction

def export_case_report(task_id: str, case_title: str, output_dir: Path):
    """从数据库导出分析报告"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or task.status != "completed":
            print(f"Task {task_id} not completed")
            return

        summary = db.query(AnalysisSummary).filter(AnalysisSummary.task_id == task_id).first()
        risk_items = db.query(RiskItem).filter(RiskItem.task_id == task_id).all()
        reactions = db.query(PlatformReaction).filter(PlatformReaction.task_id == task_id).all()

        report = {
            "case_title": case_title,
            "task_id": task_id,
            "text_preview": task.text[:100],
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
                }
                for r in reactions
            },
            "agents": json.loads(summary.agents_json) if summary and summary.agents_json else [],
            "rewrites": json.loads(summary.rewrites_json) if summary and summary.rewrites_json else [],
        }

        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON报告
        with open(output_dir / "analysis_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Markdown报告
        md = generate_md(report)
        with open(output_dir / "analysis_report.md", "w", encoding="utf-8") as f:
            f.write(md)

        print(f"Report exported: {output_dir}")
        return report
    finally:
        db.close()


def generate_md(r: dict) -> str:
    lines = [
        f"# {r['case_title']}",
        "",
        f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**总分**: {r.get('overall_score', 'N/A')}/100",
        f"**建议**: {r.get('suggestion', 'N/A')}",
        f"**Agent数量**: {len(r.get('agents', []))}",
        "",
        "---",
        "",
        "## 七维风险评估",
        "",
    ]
    dims = r.get("risk_dimensions", {})
    if dims:
        lines.append("| 维度 | 分数 | 权重 |")
        lines.append("|------|------|------|")
        weights = r.get("dimension_weights", {})
        for dim, score in dims.items():
            w = weights.get(dim, 1.0)
            lines.append(f"| {dim} | {score} | x{w} |")
    lines.append("")

    # 风险句子
    for item in r.get("risk_items", []):
        sev = item.get("severity", "")
        icon = {"high": "H", "medium": "M", "low": "L"}.get(sev, "?")
        lines.append(f"### [{icon}] {item.get('sentence', '')[:60]}")
        lines.append(f"- **维度**: {item.get('dimension', '')}")
        lines.append(f"- **严重程度**: {sev}")
        lines.append(f"- **判定依据**: {item.get('evidence', '')}")
        groups = item.get("affected_groups", [])
        if groups:
            lines.append(f"- **影响群体**: {', '.join(groups)}")
        lines.append("")

    # 平台反应
    platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
    lines.append("## 平台情绪预测")
    lines.append("")
    lines.append("| 平台 | 正面 | 中性 | 负面 |")
    lines.append("|------|------|------|------|")
    for p, react in r.get("platform_reactions", {}).items():
        name = platform_names.get(p, p)
        lines.append(f"| {name} | {react.get('positive',0)*100:.0f}% | {react.get('neutral',0)*100:.0f}% | {react.get('negative',0)*100:.0f}% |")
    lines.append("")

    # Agent视角
    agents = r.get("agents", [])
    if agents:
        lines.append(f"## Agent视角洞察 ({len(agents)}个Agent)")
        lines.append("")
        platform_groups = {}
        for a in agents:
            p = a.get("platform", "unknown")
            platform_groups.setdefault(p, []).append(a)
        for platform, platform_agents in platform_groups.items():
            p_name = platform_names.get(platform, platform)
            lines.append(f"### {p_name} ({len(platform_agents)}个Agent)")
            lines.append("")
            for a in platform_agents:
                name = a.get("persona_name", "匿名")
                arch = a.get("archetype", "")
                react = a.get("reaction_type", "neutral")
                intensity = a.get("emotional_intensity", 0)
                comment = a.get("comment", "")
                focus = a.get("focus", "")
                lines.append(f"**{name}** ({arch}) - {react}, 强度: {intensity:.1f}")
                if comment:
                    lines.append(f"> {comment[:200]}")
                if focus:
                    lines.append(f"- 关注: {focus}")
                lines.append("")

    # 改写
    for rw in r.get("rewrites", []):
        orig = rw.get("original", "")
        opts = rw.get("rewrites", [])
        lines.append(f"**原句**: {orig}")
        for i, opt in enumerate(opts, 1):
            lines.append(f"- 改写{i}: {opt}")
        lines.append("")

    return "\n".join(lines)


# 导出Case1
case1_dir = Path(r"f:\project\my\VibeUtopia\tests\v2.1-validation\case1-influencer-scandal")
report = export_case_report("test_case1_1778134318", "顶流明星人设崩塌 — 道德伦理+群体冒犯", case1_dir)

if report:
    # 生成汇总
    summary = {
        "test_time": datetime.now().isoformat(),
        "cases_completed": 1,
        "case1": {
            "title": "顶流明星人设崩塌",
            "overall_score": report["overall_score"],
            "suggestion": report["suggestion"],
            "risk_count": len(report.get("risk_items", [])),
            "agent_count": len(report.get("agents", [])),
            "platforms": len(report.get("platform_reactions", {})),
        },
    }
    with open(Path(r"f:\project\my\VibeUtopia\tests\v2.1-validation\test_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSummary: Score={report['overall_score']}, Agents={len(report.get('agents', []))}")
