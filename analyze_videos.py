"""
视频案例分析 v5 —— 使用预提取文案提交分析

1. 从 data/video_transcripts/ 读取预提取的文案
2. 通过 /api/v1/review 提交文本分析
3. 逐个案例串行处理
4. 汇总生成详细报告
"""

import json
import os
import time

import requests

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

API_BASE = "http://localhost:8000/api/v1"
TRANSCRIPT_DIR = os.path.abspath("data/video_transcripts")

VIDEO_CASES = [
    ("ai", "AI相关内容视频（计算机科学专业与AI影响）"),
    ("fight", "争议/冲突类视频（朝鲜战争历史分析）"),
    ("mhy", "米哈游相关视频（AI模型评测）"),
    ("moon", "月亮/天文类视频（宇宙天文科普）"),
]


def load_transcript(case_name):
    path = os.path.join(TRANSCRIPT_DIR, f"{case_name}.json")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("text", "")


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


def main():
    print("=" * 70)
    print("VibeUtopia 视频案例分析 v5（预提取文案）")
    print("=" * 70)

    # 检查API
    try:
        requests.get(f"{API_BASE}/resume/list", timeout=5)
        print("API: 可用")
    except Exception as e:
        print(f"API: 不可用 ({e})")
        return

    results = []

    for case_name, description in VIDEO_CASES:
        print(f"\n--- {case_name} ({description}) ---")

        # 加载文案
        text = load_transcript(case_name)
        if not text:
            print(f"  无文案，跳过")
            results.append({"case": case_name, "error": "无文案"})
            continue

        print(f"  文案: {len(text)}字")
        print(f"  预览: {text[:100]}...")

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

        # 提取结果
        r = result_data.get("result", {})
        result_entry = {
            "case": case_name,
            "description": description,
            "task_id": task_id,
            "status": result_data.get("status"),
            "elapsed_seconds": elapsed,
            "text_length": len(text),
            "overall_risk_score": r.get("overall_risk_score", 0),
            "risk_level": r.get("risk_level", ""),
            "suggestion": r.get("suggestion", ""),
            "dimensions": [
                {
                    "name": d.get("name", ""),
                    "score": d.get("score", 0),
                    "severity": d.get("severity", ""),
                    "evidence": str(d.get("evidence", ""))[:300],
                    "confidence": d.get("confidence", 0),
                }
                for d in r.get("dimensions", [])
            ],
            "platform_reactions": r.get("platform_reactions", {}),
            "cross_effects": r.get("cross_effects", {}),
        }
        results.append(result_entry)

        # 打印摘要
        if result_data.get("status") == "completed":
            print(f"  风险总分: {r.get('overall_risk_score', 0)}")
            print(f"  风险等级: {r.get('risk_level', '')}")
            for d in r.get("dimensions", []):
                score = d.get("score", 0)
                if score > 0:
                    print(f"    {d.get('name','')}: {score} ({d.get('severity','')})")

        # 间隔
        if case_name != "moon":
            print(f"  等待20秒...")
            time.sleep(20)

    # 汇总报告
    print(f"\n\n{'='*70}")
    print("视频案例分析报告")
    print(f"{'='*70}")

    for r in results:
        print(f"\n{r.get('case','?')} ({r.get('description','')}):")
        print(f"  状态: {r.get('status','?')} | 耗时: {r.get('elapsed_seconds',0)}s | 文案: {r.get('text_length',0)}字")
        if r.get("error"):
            print(f"  错误: {r['error']}")
        else:
            print(f"  风险: {r.get('overall_risk_score',0)} ({r.get('risk_level','')})")
            print(f"  建议: {str(r.get('suggestion',''))[:200]}")
            for d in r.get("dimensions", []):
                if d.get("score", 0) > 0:
                    print(f"    {d['name']}: {d['score']} ({d['severity']}) - {d.get('evidence','')[:80]}")

            # 平台反应
            reactions = r.get("platform_reactions", {})
            if reactions:
                print(f"  平台反应:")
                for platform, reaction in list(reactions.items())[:5]:
                    if isinstance(reaction, dict):
                        pos = reaction.get("positive", 0)
                        neg = reaction.get("negative", 0)
                        neu = reaction.get("neutral", 0)
                        print(f"    {platform}: 正面{pos:.0%} 中性{neu:.0%} 负面{neg:.0%}")

    # 保存
    report_path = os.path.abspath("data/video_analysis_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
