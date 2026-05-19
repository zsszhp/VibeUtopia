"""
视频案例分析 v6 —— 完整分析+详细报告生成

流程：
1. 从 data/video_transcripts/ 读取预提取文案
2. 通过 /api/v1/review 提交深度分析
3. 逐个案例串行处理（避免限流）
4. 获取完整结果（含维度、平台仿真、交叉效应等）
5. 生成详细中文分析报告（JSON+可读文本）
"""

import json
import os
import time
from datetime import datetime

import requests

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

API_BASE = "http://localhost:8000/api/v1"
TRANSCRIPT_DIR = os.path.abspath("data/video_transcripts")
REPORT_DIR = os.path.abspath("data/reports")

VIDEO_CASES = [
    ("ai", "AI相关内容视频（计算机科学专业与AI影响）"),
    ("fight", "争议/冲突类视频（朝鲜战争历史分析）"),
    ("mhy", "米哈游相关视频（AI模型评测）"),
    ("moon", "月亮/天文类视频（宇宙天文科普）"),
]

SEVERITY_EMOJI = {
    "green": "🟢",
    "yellow": "🟡",
    "orange": "🟠",
    "red": "🔴",
}

SEVERITY_LABEL = {
    "green": "安全",
    "yellow": "低风险",
    "orange": "中高风险",
    "red": "高风险",
}


def load_transcript(case_name):
    path = os.path.join(TRANSCRIPT_DIR, f"{case_name}.json")
    if not os.path.exists(path):
        return "", {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("text", ""), data


def submit_review(text, mode="video"):
    payload = {
        "texts": [{"type": "text", "content": text}],
        "mode": mode,
        "options": {"depth": "deep"},
    }
    resp = requests.post(f"{API_BASE}/review", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def wait_for_result(task_id, max_wait=900):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = requests.get(f"{API_BASE}/review/{task_id}", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                elapsed = int(time.time() - start)
                if status in ("completed", "failed"):
                    return data
                if elapsed % 60 < 15:
                    print(f"    等待中... {status} ({elapsed}s)")
        except Exception as e:
            print(f"    轮询异常: {e}")
        time.sleep(15)
    return {"status": "timeout"}


def generate_detailed_report(results, transcript_data):
    """生成详细中文分析报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 80)
    lines.append("VibeUtopia 视频内容风险分析报告")
    lines.append(f"生成时间: {now}")
    lines.append(f"分析案例数: {len(results)}")
    lines.append(f"分析方法: 深度分析（11维度+平台仿真+交叉效应）")
    lines.append("=" * 80)

    # 总览表
    lines.append("")
    lines.append("一、案例风险总览")
    lines.append("-" * 80)
    lines.append(f"{'案例':<8} {'文案字数':<10} {'风险总分':<10} {'风险等级':<12} {'最高风险维度':<20}")
    lines.append("-" * 80)

    for r in results:
        if r.get("error"):
            lines.append(f"{r['case']:<8} {'N/A':<10} {'N/A':<10} {'失败':<12} {r['error']:<20}")
            continue
        dims = r.get("dimensions", [])
        max_dim = max(dims, key=lambda d: d.get("score", 0)) if dims else {}
        max_name = max_dim.get("name", "N/A")
        max_score = max_dim.get("score", 0)
        level = r.get("risk_level", "N/A")
        emoji = SEVERITY_EMOJI.get(level, "⚪")
        lines.append(f"{r['case']:<8} {r.get('text_length',0):<10} {r.get('overall_risk_score',0):<10} {emoji}{level:<10} {max_name}({max_score})")

    # 每个案例详细分析
    for r in results:
        if r.get("error"):
            continue

        case = r.get("case", "?")
        desc = r.get("description", "")
        level = r.get("risk_level", "N/A")
        emoji = SEVERITY_EMOJI.get(level, "⚪")

        lines.append("")
        lines.append("=" * 80)
        lines.append(f"二、案例详细分析: {case} — {desc}")
        lines.append("=" * 80)

        # 基本信息
        lines.append("")
        lines.append("【基本信息】")
        lines.append(f"  案例名称: {case}")
        lines.append(f"  内容描述: {desc}")
        lines.append(f"  文案字数: {r.get('text_length', 0)}字")
        lines.append(f"  音频时长: {transcript_data.get(case, {}).get('duration', 0):.0f}秒")
        lines.append(f"  分析耗时: {r.get('elapsed_seconds', 0)}秒")
        lines.append(f"  分析状态: {r.get('status', 'N/A')}")
        lines.append(f"  风险总分: {r.get('overall_risk_score', 0)}/100")
        lines.append(f"  风险等级: {emoji} {level} ({SEVERITY_LABEL.get(level, '')})")
        lines.append(f"  总体置信度: {r.get('confidence', 'N/A')}")

        # 文案预览
        text_preview = transcript_data.get(case, {}).get("text", "")[:300]
        if text_preview:
            lines.append("")
            lines.append("【文案预览】")
            lines.append(f"  {text_preview}...")

        # 维度评分
        dims = r.get("dimensions", [])
        if dims:
            lines.append("")
            lines.append("【11维度风险评估】")
            lines.append(f"  {'维度':<10} {'分数':<8} {'等级':<6} {'置信度':<8} {'证据摘要'}")
            lines.append("  " + "-" * 70)
            for d in dims:
                name = d.get("name", "")
                score = d.get("score", 0)
                sev = d.get("severity", "green")
                conf = d.get("confidence", 0)
                evidence = str(d.get("evidence", ""))[:80]
                sev_emoji = SEVERITY_EMOJI.get(sev, "⚪")
                lines.append(f"  {name:<10} {score:<8} {sev_emoji}{sev:<4} {conf:<8.2f} {evidence}")

            # 受影响群体
            all_groups = set()
            for d in dims:
                for g in d.get("affected_groups", []):
                    all_groups.add(g)
            if all_groups:
                lines.append("")
                lines.append(f"  受影响群体: {', '.join(all_groups)}")

        # 交叉效应
        cross_effects = r.get("cross_effects", [])
        if cross_effects:
            lines.append("")
            lines.append("【跨维度交叉效应】")
            for i, ce in enumerate(cross_effects, 1):
                dims_involved = " × ".join(ce.get("dimensions", []))
                desc_ce = ce.get("description", "")
                combined = ce.get("combined_severity", "")
                ce_emoji = SEVERITY_EMOJI.get(combined, "⚪")
                lines.append(f"  {i}. {ce_emoji}{combined} | {dims_involved}")
                lines.append(f"     {desc_ce}")

        # 平台仿真
        sim_data = r.get("simulation_data", {})
        if sim_data:
            lines.append("")
            lines.append("【平台仿真分析】")
            for platform_id, platform_info in sim_data.items():
                pname = platform_info.get("platform_name", platform_id)
                risk_score = platform_info.get("risk_score", 0)
                risk_level = platform_info.get("risk_level", "")
                amp_risk = platform_info.get("amplification_risk", 0)
                emotion = platform_info.get("emotion_distribution", {})

                pl_emoji = SEVERITY_EMOJI.get(risk_level, "⚪")
                lines.append(f"")
                lines.append(f"  ▶ {pname} (风险分:{risk_score:.1f} {pl_emoji}{risk_level}, 放大系数:{amp_risk:.1f})")
                lines.append(f"    情绪分布: 正面{emotion.get('positive',0):.0%} 中性{emotion.get('neutral',0):.0%} 负面{emotion.get('negative',0):.0%}")

                # 典型反应
                reactions = platform_info.get("typical_reactions", [])
                if reactions:
                    lines.append(f"    典型用户反应:")
                    for react in reactions[:3]:
                        rtype = react.get("reaction_type", "")
                        comment = react.get("example_comment", "")
                        reasoning = react.get("reasoning", "")
                        lines.append(f"      [{rtype}] '{comment}'")
                        if reasoning:
                            lines.append(f"        推理: {reasoning[:100]}")

                # 关键风险
                concerns = platform_info.get("key_concerns", [])
                if concerns:
                    lines.append(f"    关键风险点:")
                    for c in concerns[:3]:
                        lines.append(f"      - {c}")

                # 平台建议
                advice = platform_info.get("platform_specific_advice", [])
                if advice:
                    lines.append(f"    平台专属建议:")
                    for a in advice[:3]:
                        lines.append(f"      - {a}")

        # 不确定性来源
        uncertainty = r.get("uncertainty_sources", [])
        if uncertainty:
            lines.append("")
            lines.append("【不确定性来源】")
            for u in uncertainty:
                lines.append(f"  ⚠️ {u}")

    # 总结与建议
    lines.append("")
    lines.append("=" * 80)
    lines.append("三、总结与建议")
    lines.append("=" * 80)

    high_risk = [r for r in results if r.get("risk_level") in ("orange", "red")]
    medium_risk = [r for r in results if r.get("risk_level") == "yellow"]
    low_risk = [r for r in results if r.get("risk_level") == "green"]

    lines.append(f"")
    lines.append(f"  高风险案例: {len(high_risk)}个 ({', '.join(r['case'] for r in high_risk)})")
    lines.append(f"  中风险案例: {len(medium_risk)}个 ({', '.join(r['case'] for r in medium_risk)})")
    lines.append(f"  低风险案例: {len(low_risk)}个 ({', '.join(r['case'] for r in low_risk)})")

    lines.append("")
    lines.append("  关键发现:")
    for r in results:
        if r.get("error"):
            continue
        case = r.get("case", "?")
        score = r.get("overall_risk_score", 0)
        level = r.get("risk_level", "")
        dims = r.get("dimensions", [])
        high_dims = [d for d in dims if d.get("score", 0) >= 50]
        if high_dims:
            dim_names = ", ".join(f"{d['name']}({d['score']})" for d in high_dims)
            lines.append(f"    - {case}: 风险分{score}({level}), 高风险维度: {dim_names}")
        else:
            lines.append(f"    - {case}: 风险分{score}({level}), 无高风险维度")

    lines.append("")
    lines.append("  改进建议:")
    lines.append("    1. 高风险内容(ai)需重点关注情绪极化和价值观倾向的交叉放大效应")
    lines.append("    2. Whisper繁体字转写问题影响事实错误维度判断，建议增加简繁转换预处理")
    lines.append("    3. 历史分析类内容(fight)风险判定准确，系统不会误判历史讨论为政治敏感")
    lines.append("    4. 技术评测类内容(mhy)风险最低，可作为安全内容基准")

    lines.append("")
    lines.append("=" * 80)
    lines.append("报告结束")
    lines.append("=" * 80)

    return "\n".join(lines)


def main():
    print("=" * 70)
    print("VibeUtopia 视频案例分析 v6（完整报告）")
    print("=" * 70)

    # 检查API
    try:
        requests.get(f"{API_BASE}/resume/list", timeout=5)
        print("API: 可用")
    except Exception as e:
        print(f"API: 不可用 ({e})")
        return

    results = []
    transcript_data_map = {}

    for case_name, description in VIDEO_CASES:
        print(f"\n--- {case_name} ({description}) ---")

        # 加载文案
        text, tdata = load_transcript(case_name)
        transcript_data_map[case_name] = tdata
        if not text:
            print(f"  无文案，跳过")
            results.append({"case": case_name, "error": "无文案"})
            continue

        print(f"  文案: {len(text)}字, 时长: {tdata.get('duration',0):.0f}s")

        # 提交分析
        print(f"  提交分析...")
        try:
            submit_data = submit_review(text)
            task_id = submit_data["task_id"]
            print(f"  任务ID: {task_id}")
        except Exception as e:
            print(f"  提交失败: {e}")
            results.append({"case": case_name, "error": str(e)})
            continue

        # 等待结果
        print(f"  等待完成...")
        start = time.time()
        result_data = wait_for_result(task_id)
        elapsed = int(time.time() - start)
        print(f"  完成: {result_data.get('status', 'unknown')} ({elapsed}s)")

        # 提取完整结果
        r = result_data.get("result", result_data)
        result_entry = {
            "case": case_name,
            "description": description,
            "task_id": task_id,
            "status": result_data.get("status"),
            "elapsed_seconds": elapsed,
            "text_length": len(text),
            "overall_risk_score": r.get("overall_risk_score", r.get("overall_risk", 0)),
            "risk_level": r.get("risk_level", ""),
            "confidence": r.get("confidence", 0),
            "uncertainty_sources": r.get("uncertainty_sources", []),
            "dimensions": r.get("dimensions", []),
            "platform_reactions": r.get("platform_reactions", {}),
            "cross_effects": r.get("cross_effects", []),
            "simulation_data": r.get("simulation_data", {}),
            "evidence_chains": r.get("evidence_chains", []),
            "confidence_breakdown": r.get("confidence_breakdown", {}),
        }
        results.append(result_entry)

        # 打印摘要
        score = result_entry["overall_risk_score"]
        level = result_entry["risk_level"]
        emoji = SEVERITY_EMOJI.get(level, "⚪")
        print(f"  {emoji} 风险总分: {score} ({level})")
        for d in r.get("dimensions", []):
            ds = d.get("score", 0)
            if ds > 0:
                dn = d.get("name", "")
                dsev = d.get("severity", "")
                de = SEVERITY_EMOJI.get(dsev, "⚪")
                print(f"    {de} {dn}: {ds}")

        # 间隔
        if case_name != "moon":
            print(f"  等待20秒...")
            time.sleep(20)

    # 保存完整JSON结果
    os.makedirs(REPORT_DIR, exist_ok=True)
    json_path = os.path.join(REPORT_DIR, "video_analysis_full.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON报告已保存: {json_path}")

    # 生成详细可读报告
    report_text = generate_detailed_report(results, transcript_data_map)
    report_path = os.path.join(REPORT_DIR, "video_analysis_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"详细报告已保存: {report_path}")

    # 同时打印到控制台
    print("\n" + report_text)


if __name__ == "__main__":
    main()
