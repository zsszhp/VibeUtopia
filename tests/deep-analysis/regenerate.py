"""Regenerate all reports from DB with best-matching tasks (preferring tasks with agents)."""
import json
import os
import sqlite3
from datetime import datetime
from difflib import SequenceMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPERWORK_DIR = os.path.join(PROJECT_ROOT, "cases", "paperwork")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "tests", "deep-analysis")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "vibeutopia.db")

def similar(a, b):
    return SequenceMatcher(None, a[:200], b[:200]).ratio()

def fetch_analysis_result(task_id, conn):
    c = conn.cursor()
    c.execute("""SELECT overall_score, suggestion, dimensions_json, rewrites_json,
                        transcript_quality, dimension_weights, cross_effects, agents_json
                 FROM analysis_summaries WHERE task_id=?""", (task_id,))
    row = c.fetchone()
    if not row:
        return None
    summary = {
        "overall_score": row[0], "suggestion": row[1],
        "risk_dimensions": json.loads(row[2]) if row[2] else {},
        "transcript_quality": json.loads(row[4]) if row[4] else None,
        "dimension_weights": json.loads(row[5]) if row[5] else None,
        "cross_effects": json.loads(row[6]) if row[6] else [],
        "agents": json.loads(row[7]) if row[7] else [],
    }
    c.execute("SELECT sentence, dimension, severity, evidence, affected_groups FROM risk_items WHERE task_id=?", (task_id,))
    risk_items = [{"sentence": r[0], "dimension": r[1], "severity": r[2],
                   "evidence": r[3], "affected_groups": r[4].split(",") if r[4] else []}
                  for r in c.fetchall()]
    c.execute("SELECT platform, positive, neutral, negative, reason FROM platform_reactions WHERE task_id=?", (task_id,))
    platform_reactions = {r[0]: {"positive": r[1], "neutral": r[2], "negative": r[3], "reason": r[4] or ""}
                          for r in c.fetchall()}
    rewrites = json.loads(row[3]) if row[3] else []
    return {"task_id": task_id, "status": "completed", "summary": summary,
            "risk_items": risk_items, "platform_reactions": platform_reactions, "rewrites": rewrites}

def generate_report(case, result, output_dir):
    case_id = case["case_id"]
    summary = result.get("summary", {})
    risk_items = result.get("risk_items", [])
    platform_reactions = result.get("platform_reactions", {})
    rewrites = result.get("rewrites", [])
    agents = summary.get("agents", [])
    dims = summary.get("risk_dimensions", {})
    case_dir = os.path.join(output_dir, case_id)
    os.makedirs(case_dir, exist_ok=True)

    json_report = {
        "case_id": case_id, "title": case["title"], "source": case["source"],
        "task_id": result.get("task_id"), "analysis_time": datetime.now().isoformat(),
        "input_text_preview": case["text"][:300],
        "overall_score": summary.get("overall_score", 0), "suggestion": summary.get("suggestion", ""),
        "risk_dimensions": dims, "dimension_weights": summary.get("dimension_weights"),
        "cross_effects": summary.get("cross_effects", []),
        "risk_items": risk_items, "platform_reactions": platform_reactions,
        "rewrites": rewrites, "agents_count": len(agents), "agents": agents,
        "transcript_quality": summary.get("transcript_quality"),
    }
    with open(os.path.join(case_dir, "analysis_report.json"), "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    score = summary.get("overall_score", 0)
    suggestion = summary.get("suggestion", "")
    score_icon = "🟢" if score <= 25 else ("🟡" if score <= 55 else "🔴")
    md = f"# {case['title']} — 深度风控分析报告\n\n"
    md += f"> 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n> 来源: {case['source']}\n> 任务ID: {result.get('task_id', 'N/A')}\n\n"
    md += f"## 总体评估\n\n| 指标 | 结果 |\n|------|------|\n"
    md += f"| 风险总分 | {score_icon} **{score}/100** |\n| 发布建议 | **{suggestion}** |\n| 参与Agent | {len(agents)} 个 |\n| 风险句子 | {len(risk_items)} 处 |\n| 涉及平台 | {len(platform_reactions)} 个 |\n\n"

    tq = summary.get("transcript_quality")
    if tq:
        md += f"## 转写质量检测\n\n| 指标 | 值 |\n|------|------|\n| 质量等级 | {tq.get('quality_level', 'N/A')} |\n| 质量分数 | {tq.get('quality_score', 'N/A')} |\n\n"

    if dims:
        md += f"## 七维风险评估\n\n| 维度 | 分数 | 风险等级 | 评估 |\n|------|------|----------|------|\n"
        for dim, val in dims.items():
            level = "低" if val <= 20 else ("中" if val <= 50 else "高")
            bar = "█" * (val // 5) + "░" * (20 - val // 5)
            md += f"| {dim} | {val} | {level} | {bar} |\n"
        md += "\n"
        weights = summary.get("dimension_weights")
        if weights:
            md += f"### 维度权重分配\n\n| 维度 | 权重 |\n|------|------|\n"
            for dim, weight in weights.items():
                md += f"| {dim} | {weight:.2f} |\n"
            md += "\n"

    cross = summary.get("cross_effects", [])
    if cross:
        md += f"## 交叉风险分析\n\n多个风险维度同时触发时，会产生交叉放大效应：\n\n"
        for ce in cross:
            dims_list = ce.get("dimensions", [])
            desc = ce.get("description", "")
            sev = ce.get("combined_severity", "")
            md += f"- **{' + '.join(dims_list)}** (联合严重度: {sev})\n  - {desc}\n"
        md += "\n"

    if risk_items:
        md += f"## 风险句子定位\n\n"
        for i, item in enumerate(risk_items, 1):
            sev = item.get("severity", "medium")
            icon = "🔴" if sev == "high" else ("🟡" if sev == "medium" else "🟢")
            sentence = item.get("sentence", "")
            md += f"### {i}. {icon} \"{sentence[:80]}{'...' if len(sentence) > 80 else ''}\"\n\n"
            md += f"| 属性 | 详情 |\n|------|------|\n| 风险维度 | {item.get('dimension', '')} |\n| 严重程度 | {sev} |\n| 判定依据 | {item.get('evidence', '')} |\n"
            groups = item.get("affected_groups", [])
            if groups:
                md += f"| 影响群体 | {', '.join(groups)} |\n"
            md += "\n"

    md += f"## 平台情绪预测\n\n"
    platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音", "weibo": "微博"}
    for platform_key, reaction in platform_reactions.items():
        name = platform_names.get(platform_key, platform_key)
        pos, neu, neg = reaction.get("positive", 0), reaction.get("neutral", 0), reaction.get("negative", 0)
        reason = reaction.get("reason", "")
        pos_bar = "█" * int(pos * 20)
        neu_bar = "█" * int(neu * 20)
        neg_bar = "█" * int(neg * 20)
        md += f"### {name}\n\n| 情绪 | 占比 | 分布 |\n|------|------|------|\n"
        md += f"| 正面 | {pos*100:.0f}% | {pos_bar} |\n| 中性 | {neu*100:.0f}% | {neu_bar} |\n| 负面 | {neg*100:.0f}% | {neg_bar} |\n\n"
        if reason:
            agent_section, other_reason = "", ""
            for line in reason.split("\n"):
                if line.strip().startswith("[Agent反应]"):
                    agent_section = line.strip()
                elif line.strip().startswith("[群体分化]"):
                    other_reason += line.strip() + "\n"
                else:
                    other_reason += line + "\n"
            if other_reason.strip():
                md += f"**分析**: {other_reason.strip()}\n\n"
            if agent_section:
                cleaned = agent_section.replace("[Agent反应] ", "")
                md += f"**Agent反应摘要**: {cleaned}\n\n"

    if agents:
        md += f"## Agent视角洞察 ({len(agents)}个)\n\n"
        platform_groups = {}
        for agent in agents:
            p = agent.get("platform", "unknown")
            platform_groups.setdefault(p, []).append(agent)
        for platform_key, p_agents in platform_groups.items():
            name = platform_names.get(platform_key, platform_key)
            md += f"### {name} ({len(p_agents)}个Agent)\n\n"
            for a in p_agents[:5]:
                rt = a.get("reaction_type", "neutral")
                icon = "👍" if rt == "positive" else ("😐" if rt == "neutral" else "👎")
                pname = a.get("persona_name", "匿名")
                archetype = a.get("archetype", "")
                comment = a.get("comment", "")
                intensity = a.get("emotional_intensity", 0)
                md += f"**{icon} {pname}** ({archetype}) — 情感强度: {intensity:.1f}\n\n"
                if comment:
                    md += f"> {comment}\n\n"

    if rewrites:
        md += f"## 安全改写建议\n\n"
        for i, rw in enumerate(rewrites, 1):
            original = rw.get("original", "")
            options = rw.get("rewrites", [])
            if not original and not options:
                continue
            md += f"### 改写 {i}\n\n"
            if original:
                md += f"**原句**: {original}\n\n"
            if options:
                md += f"**建议改写**:\n\n"
                for j, opt in enumerate(options, 1):
                    md += f"{j}. {opt}\n"
            md += "\n"

    md += f"## 结论与建议\n\n"
    if score <= 25:
        md += f"该内容总体风险较低（{score}/100），可以安全发布。但仍需关注各平台的细微情绪差异，做好舆情监控。\n"
    elif score <= 55:
        md += f"该内容存在一定风险（{score}/100），建议根据上述风险句子进行修改后再发布。重点关注高风险维度的措辞调整。\n"
    else:
        md += f"该内容风险较高（{score}/100），不建议直接发布。需要系统性修改，降低各维度风险分数后再行评估。\n"
    high_dims = [d for d, v in dims.items() if v > 50]
    if high_dims:
        md += f"\n**重点关注的维度**: {', '.join(high_dims)}\n"

    with open(os.path.join(case_dir, "analysis_report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    return json_report


def main():
    print("=" * 60)
    print("Regenerate all reports from DB")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get ALL completed tasks with their text and agent count
    c.execute("""SELECT t.id, t.text, 
                        COALESCE(json_array_length(a.agents_json), 0) as agent_count,
                        a.overall_score
                 FROM tasks t
                 LEFT JOIN analysis_summaries a ON t.id = a.task_id
                 WHERE t.status='completed'
                 ORDER BY a.overall_score DESC NULLS LAST, t.created_at DESC""")
    all_tasks = c.fetchall()

    # Build all cases
    all_cases = []

    # Paperwork cases
    for fname in sorted(os.listdir(PAPERWORK_DIR)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(PAPERWORK_DIR, fname), "r", encoding="utf-8") as f:
            content = f.read()
        case_name = fname.replace(".md", "")
        title_line = content.split("\n")[0].replace("#", "").strip()
        all_cases.append({"case_id": case_name, "title": title_line or case_name, "text": content, "source": "paperwork"})

    # Hot topic cases
    all_cases.append({
        "case_id": "hot-ifeng-iran-war",
        "title": "[热点] 伊朗战争: 特朗普突然叫停自由计划内幕披露",
        "text": "# 伊朗战争: 特朗普突然叫停自由计划内幕披露\n\n这是一个从凤凰网热榜抓取的实时热点话题，需要评估其在社交媒体上的舆论风险。该话题在凤凰网上引发广泛讨论，涉及公众利益和社会关注。",
        "source": "hotlist-ifeng",
    })

    all_reports = []
    for case in all_cases:
        # Find BEST matching task (prefer higher similarity + more agents)
        candidates = []
        for task_id, task_text, agent_count, task_score in all_tasks:
            if not task_text:
                continue
            sim = similar(case["text"], task_text)
            if sim > 0.4:
                candidates.append((sim, agent_count or 0, task_id))

        # Sort by: first by agent_count (desc), then by similarity (desc)
        candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)

        if candidates:
            best = candidates[0]
            task_id = best[2]
            result = fetch_analysis_result(task_id, conn)
            if result:
                agents = result.get("summary", {}).get("agents", [])
                if len(agents) > 0:
                    report = generate_report(case, result, OUTPUT_DIR)
                    if report:
                        all_reports.append(report)
                        print(f"  OK {case['title'][:35]}: score={report.get('overall_score')} agents={len(agents)} task={task_id[:8]}")
                    else:
                        print(f"  SKIP {case['title'][:35]}: report gen failed")
                else:
                    print(f"  SKIP {case['title'][:35]}: 0 agents (task={task_id[:8]})")
            else:
                print(f"  SKIP {case['title'][:35]}: no DB result")
        else:
            print(f"  SKIP {case['title'][:35]}: no matching task")

    conn.close()

    # Write summary
    summary_data = {
        "test_time": datetime.now().isoformat(),
        "total_cases": len(all_reports),
        "success_count": len(all_reports),
        "results": [{"case_id": r.get("case_id"), "title": r.get("title"),
                     "overall_score": r.get("overall_score"), "suggestion": r.get("suggestion"),
                     "risk_items_count": len(r.get("risk_items", [])),
                     "agents_count": r.get("agents_count", len(r.get("agents", [])))}
                    for r in all_reports],
    }
    with open(os.path.join(OUTPUT_DIR, "test_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    md = "# 深度风控分析汇总报告\n\n"
    md += f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n> 成功: {len(all_reports)} 个案例\n\n"
    md += "| # | 案例 | 风险总分 | 发布建议 | 风险项 | Agent数 |\n|---|------|----------|----------|--------|--------|\n"
    for i, r in enumerate(summary_data["results"], 1):
        title = r.get("title", "?")[:30]
        score = r.get("overall_score", "N/A")
        suggestion = r.get("suggestion", "N/A")
        risk_count = r.get("risk_items_count", 0)
        agents_count = r.get("agents_count", 0)
        md += f"| {i} | {title} | {score} | {suggestion} | {risk_count} | {agents_count} |\n"

    scores = [r.get("overall_score", 0) for r in summary_data["results"] if r.get("overall_score") is not None]
    if scores:
        low = sum(1 for s in scores if s <= 25)
        mid = sum(1 for s in scores if 25 < s <= 55)
        high = sum(1 for s in scores if s > 55)
        md += f"\n## 风险分布\n\n- 低风险 (0-25): {low} 个\n- 中风险 (26-55): {mid} 个\n- 高风险 (56-100): {high} 个\n- 平均分: {sum(scores)/len(scores):.1f}\n"

    with open(os.path.join(OUTPUT_DIR, "summary_report.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n{'='*60}")
    print(f"报告生成完成! 共 {len(all_reports)} 个深度分析报告")
    print(f"报告目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
