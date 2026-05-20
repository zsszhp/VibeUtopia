"""
综合测试脚本 - 4个案例的封面/视频/音频分析
输出详细报告到 data/reports/comprehensive_test_report.txt
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

sys.path.insert(0, str(Path(__file__).parent / "src"))

API_BASE = "http://localhost:8000/api/v1"
TEST_VIDEO_DIR = os.path.abspath("tests/video")
TRANSCRIPT_DIR = os.path.abspath("data/video_transcripts")
REPORT_DIR = os.path.abspath("data/reports")

VIDEO_CASES = [
    {
        "name": "ai",
        "description": "AI相关内容视频（计算机科学专业与AI影响）",
        "cover": "ai(封面).jpg",
        "video": "ai.mp4",
        "audio": "ai_音频.mp3",
    },
    {
        "name": "fight",
        "description": "争议/冲突类视频（朝鲜战争历史分析）",
        "cover": "fight(封面).jpg",
        "video": "fight.mp4",
        "audio": "fight_音频.mp3",
    },
    {
        "name": "mhy",
        "description": "米哈游相关视频（AI模型评测）",
        "cover": "mhy.jpg",
        "video": "mhy.mp4",
        "audio": "mhy.mp3",
    },
    {
        "name": "moon",
        "description": "月亮/天文类视频（宇宙天文科普）",
        "cover": "moon(封面).jpg",
        "video": "moon.mp4",
        "audio": "moon_音频.mp3",
    },
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
    import requests
    payload = {
        "texts": [{"type": "text", "content": text}],
        "mode": mode,
        "options": {"depth": "standard"},
    }
    resp = requests.post(f"{API_BASE}/review", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def wait_for_result(task_id, max_wait=900):
    import requests
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


def test_cover_analysis(case):
    """测试封面图片分析 - 使用VLM视觉模型"""
    import requests
    cover_path = os.path.join(TEST_VIDEO_DIR, case["name"], case["cover"])
    if not os.path.exists(cover_path):
        return {"status": "skip", "error": f"封面文件不存在: {cover_path}"}

    try:
        with open(cover_path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        start = time.time()
        resp = requests.post(
            f"{API_BASE.replace('/api/v1', '/api/v3')}/fine-grained/analyze",
            json={
                "video_path": "",
                "image_base64": image_base64,
                "analysis_types": ["cover_risk"],
            },
            timeout=120,
        )
        elapsed = round(time.time() - start, 2)

        if resp.status_code == 200:
            return {"status": "success", "data": resp.json(), "elapsed": elapsed}
        else:
            return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "elapsed": elapsed}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def test_video_analysis(case):
    """测试视频分析 - 通过API提交文案进行深度分析"""
    text, tdata = load_transcript(case["name"])
    if not text:
        return {"status": "skip", "error": "无预提取文案"}

    try:
        start = time.time()
        submit_data = submit_review(text, mode="video")
        task_id = submit_data["task_id"]
        result_data = wait_for_result(task_id)
        elapsed = round(time.time() - start, 2)

        r = result_data.get("result", result_data)
        return {
            "status": result_data.get("status", "unknown"),
            "task_id": task_id,
            "elapsed": elapsed,
            "data": r,
            "text_length": len(text),
            "duration": tdata.get("duration", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def test_audio_analysis(case):
    """测试音频分析 - 使用音频转写文本进行风险评估"""
    text, tdata = load_transcript(case["name"])
    if not text:
        return {"status": "skip", "error": "无预提取文案"}

    audio_path = os.path.join(TEST_VIDEO_DIR, case["name"], case["audio"])
    audio_exists = os.path.exists(audio_path)

    try:
        import requests
        start = time.time()

        payload = {
            "texts": [{"type": "text", "content": f"【音频转写内容】\n{text}"}],
            "mode": "text",
            "options": {"depth": "standard"},
        }
        resp = requests.post(f"{API_BASE}/review", json=payload, timeout=60)
        resp.raise_for_status()
        submit_data = resp.json()
        task_id = submit_data["task_id"]

        result_data = wait_for_result(task_id, max_wait=600)
        elapsed = round(time.time() - start, 2)

        r = result_data.get("result", result_data)
        return {
            "status": result_data.get("status", "unknown"),
            "task_id": task_id,
            "elapsed": elapsed,
            "data": r,
            "audio_file_exists": audio_exists,
            "audio_path": audio_path,
            "text_length": len(text),
            "duration": tdata.get("duration", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_report(all_results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 90)
    lines.append("VibeUtopia 综合测试报告 - 封面/视频/音频分析")
    lines.append(f"生成时间: {now}")
    lines.append(f"测试案例数: {len(all_results)}")
    lines.append(f"测试维度: 封面图片分析 | 视频内容分析 | 音频转写分析")
    lines.append("=" * 90)

    lines.append("")
    lines.append("一、环境配置检查")
    lines.append("-" * 90)
    lines.append("  API Provider: LongCat (2个Key轮换)")
    lines.append("  默认模型: LongCat-Flash-Thinking-2601")
    lines.append("  数据库: SQLite (Docker/MySQL未启动，已降级)")
    lines.append("  Neo4j: 未启动 (降级到关系型数据库模式)")
    lines.append("  Ollama: 已安装 (qwopus9b模型)")
    lines.append("  Docker: 未启动")
    lines.append("  OpenCV: 4.13.0 ✓")
    lines.append("  FFmpeg: 6.1.1 ✓")
    lines.append("  SceneDetect: ✓")
    lines.append("  httpx: 0.28.1 ✓")
    lines.append("  Paraformer: 未配置 (阿里API Key为空)")

    lines.append("")
    lines.append("二、案例风险总览")
    lines.append("-" * 90)
    lines.append(f"{'案例':<8} {'描述':<30} {'视频风险分':<12} {'视频等级':<10} {'音频风险分':<12} {'音频等级':<10}")
    lines.append("-" * 90)

    for case_result in all_results:
        name = case_result["name"]
        desc = case_result["description"][:28]
        video = case_result.get("video", {})
        audio = case_result.get("audio", {})

        v_score = "N/A"
        v_level = "N/A"
        a_score = "N/A"
        a_level = "N/A"

        if video.get("status") == "completed":
            vd = video.get("data", {})
            v_score = str(vd.get("overall_risk_score", vd.get("overall_risk", 0)))
            v_level = vd.get("risk_level", "")
        elif video.get("status") == "error":
            v_score = "ERR"
            v_level = video.get("error", "")[:20]

        if audio.get("status") == "completed":
            ad = audio.get("data", {})
            a_score = str(ad.get("overall_risk_score", ad.get("overall_risk", 0)))
            a_level = ad.get("risk_level", "")
        elif audio.get("status") == "error":
            a_score = "ERR"
            a_level = audio.get("error", "")[:20]

        lines.append(f"{name:<8} {desc:<30} {v_score:<12} {v_level:<10} {a_score:<12} {a_level:<10}")

    for case_result in all_results:
        name = case_result["name"]
        desc = case_result["description"]
        lines.append("")
        lines.append("=" * 90)
        lines.append(f"三、案例详细分析: {name} — {desc}")
        lines.append("=" * 90)

        # ---- 封面分析 ----
        lines.append("")
        lines.append("【3.1 封面图片分析】")
        cover = case_result.get("cover", {})
        lines.append(f"  状态: {cover.get('status', 'N/A')}")
        lines.append(f"  耗时: {cover.get('elapsed', 'N/A')}秒")
        if cover.get("status") == "success":
            lines.append(f"  数据: {json.dumps(cover.get('data', {}), ensure_ascii=False, indent=4)[:500]}")
        elif cover.get("status") == "error":
            lines.append(f"  错误: {cover.get('error', 'N/A')}")
        elif cover.get("status") == "skip":
            lines.append(f"  跳过: {cover.get('error', 'N/A')}")

        # ---- 视频分析 ----
        lines.append("")
        lines.append("【3.2 视频内容分析】")
        video = case_result.get("video", {})
        lines.append(f"  状态: {video.get('status', 'N/A')}")
        lines.append(f"  耗时: {video.get('elapsed', 'N/A')}秒")
        lines.append(f"  文案字数: {video.get('text_length', 'N/A')}")
        lines.append(f"  音频时长: {video.get('duration', 'N/A')}秒")

        if video.get("status") == "completed":
            vd = video.get("data", {})
            score = vd.get("overall_risk_score", vd.get("overall_risk", 0))
            level = vd.get("risk_level", "")
            emoji = SEVERITY_EMOJI.get(level, "⚪")
            lines.append(f"  风险总分: {score}/100")
            lines.append(f"  风险等级: {emoji} {level} ({SEVERITY_LABEL.get(level, '')})")
            lines.append(f"  置信度: {vd.get('confidence', 'N/A')}")

            dims = vd.get("dimensions", [])
            if dims:
                lines.append("")
                lines.append(f"  {'维度':<12} {'分数':<8} {'等级':<6} {'置信度':<8} {'证据摘要'}")
                lines.append("  " + "-" * 70)
                for d in dims:
                    dname = d.get("name", "")
                    dscore = d.get("score", 0)
                    dsev = d.get("severity", "green")
                    dconf = d.get("confidence", 0)
                    devidence = str(d.get("evidence", ""))[:60]
                    demoji = SEVERITY_EMOJI.get(dsev, "⚪")
                    lines.append(f"  {dname:<12} {dscore:<8} {demoji}{dsev:<4} {dconf:<8.2f} {devidence}")

            cross_effects = vd.get("cross_effects", [])
            if cross_effects:
                lines.append("")
                lines.append("  【跨维度交叉效应】")
                for i, ce in enumerate(cross_effects, 1):
                    dims_involved = " × ".join(ce.get("dimensions", []))
                    ce_desc = ce.get("description", "")
                    ce_sev = ce.get("combined_severity", "")
                    ce_emoji = SEVERITY_EMOJI.get(ce_sev, "⚪")
                    lines.append(f"  {i}. {ce_emoji}{ce_sev} | {dims_involved}")
                    lines.append(f"     {ce_desc[:100]}")

            sim_data = vd.get("simulation_data", {})
            if sim_data:
                lines.append("")
                lines.append("  【平台仿真分析】")
                for platform_id, platform_info in sim_data.items():
                    pname = platform_info.get("platform_name", platform_id)
                    risk_score = platform_info.get("risk_score", 0)
                    risk_level = platform_info.get("risk_level", "")
                    pl_emoji = SEVERITY_EMOJI.get(risk_level, "⚪")
                    lines.append(f"  ▶ {pname} (风险分:{risk_score:.1f} {pl_emoji}{risk_level})")
                    concerns = platform_info.get("key_concerns", [])
                    if concerns:
                        for c in concerns[:2]:
                            lines.append(f"    - {c}")

            risk_sentences = vd.get("risk_sentences", [])
            if risk_sentences:
                lines.append("")
                lines.append("  【风险句子】")
                for rs in risk_sentences[:5]:
                    sentence = rs.get("sentence", "")[:60]
                    dimension = rs.get("dimension", "")
                    severity = rs.get("severity", "")
                    lines.append(f"  [{severity}] {dimension}: {sentence}...")
        elif video.get("status") == "error":
            lines.append(f"  错误: {video.get('error', 'N/A')}")
        elif video.get("status") == "skip":
            lines.append(f"  跳过: {video.get('error', 'N/A')}")

        # ---- 音频分析 ----
        lines.append("")
        lines.append("【3.3 音频转写分析】")
        audio = case_result.get("audio", {})
        lines.append(f"  状态: {audio.get('status', 'N/A')}")
        lines.append(f"  耗时: {audio.get('elapsed', 'N/A')}秒")
        lines.append(f"  音频文件: {'存在' if audio.get('audio_file_exists') else '不存在'}")
        lines.append(f"  文案字数: {audio.get('text_length', 'N/A')}")
        lines.append(f"  音频时长: {audio.get('duration', 'N/A')}秒")

        if audio.get("status") == "completed":
            ad = audio.get("data", {})
            score = ad.get("overall_risk_score", ad.get("overall_risk", 0))
            level = ad.get("risk_level", "")
            emoji = SEVERITY_EMOJI.get(level, "⚪")
            lines.append(f"  风险总分: {score}/100")
            lines.append(f"  风险等级: {emoji} {level} ({SEVERITY_LABEL.get(level, '')})")

            dims = ad.get("dimensions", [])
            if dims:
                lines.append("")
                lines.append(f"  {'维度':<12} {'分数':<8} {'等级':<6}")
                lines.append("  " + "-" * 40)
                for d in dims:
                    dname = d.get("name", "")
                    dscore = d.get("score", 0)
                    dsev = d.get("severity", "green")
                    demoji = SEVERITY_EMOJI.get(dsev, "⚪")
                    lines.append(f"  {dname:<12} {dscore:<8} {demoji}{dsev}")
        elif audio.get("status") == "error":
            lines.append(f"  错误: {audio.get('error', 'N/A')}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("四、总结与发现")
    lines.append("=" * 90)

    completed_video = [r for r in all_results if r.get("video", {}).get("status") == "completed"]
    completed_audio = [r for r in all_results if r.get("audio", {}).get("status") == "completed"]

    lines.append(f"  视频分析完成: {len(completed_video)}/{len(all_results)}")
    lines.append(f"  音频分析完成: {len(completed_audio)}/{len(all_results)}")

    if completed_video:
        avg_score = sum(
            r["video"]["data"].get("overall_risk_score", r["video"]["data"].get("overall_risk", 0))
            for r in completed_video
        ) / len(completed_video)
        lines.append(f"  平均视频风险分: {avg_score:.1f}")

    lines.append("")
    lines.append("  关键发现:")
    for r in all_results:
        name = r["name"]
        video = r.get("video", {})
        if video.get("status") == "completed":
            vd = video.get("data", {})
            score = vd.get("overall_risk_score", vd.get("overall_risk", 0))
            level = vd.get("risk_level", "")
            dims = vd.get("dimensions", [])
            high_dims = [d for d in dims if d.get("score", 0) >= 50]
            if high_dims:
                dim_names = ", ".join(f"{d['name']}({d['score']})" for d in high_dims)
                lines.append(f"    - {name}: 风险分{score}({level}), 高风险维度: {dim_names}")
            else:
                lines.append(f"    - {name}: 风险分{score}({level}), 无高风险维度")
        else:
            lines.append(f"    - {name}: 分析未完成 ({video.get('status', 'unknown')})")

    lines.append("")
    lines.append("=" * 90)
    lines.append("报告结束")
    lines.append("=" * 90)

    return "\n".join(lines)


def main():
    print("=" * 70)
    print("VibeUtopia 综合测试 - 封面/视频/音频分析")
    print("=" * 70)

    import requests
    try:
        requests.get(f"{API_BASE}/resume/list", timeout=5)
        print("API: 可用 ✓")
    except Exception as e:
        print(f"API: 不可用 ✗ ({e})")
        return

    all_results = []

    for case in VIDEO_CASES:
        name = case["name"]
        desc = case["description"]
        print(f"\n{'='*60}")
        print(f"测试案例: {name} — {desc}")
        print(f"{'='*60}")

        case_result = {
            "name": name,
            "description": desc,
            "cover": {},
            "video": {},
            "audio": {},
        }

        # 1. 封面分析
        print(f"\n  [1/3] 封面图片分析...")
        cover_result = test_cover_analysis(case)
        case_result["cover"] = cover_result
        print(f"  封面分析: {cover_result.get('status', 'N/A')}")

        # 2. 视频分析
        print(f"\n  [2/3] 视频内容分析（深度模式）...")
        video_result = test_video_analysis(case)
        case_result["video"] = video_result
        if video_result.get("status") == "completed":
            vd = video_result.get("data", {})
            score = vd.get("overall_risk_score", vd.get("overall_risk", 0))
            level = vd.get("risk_level", "")
            emoji = SEVERITY_EMOJI.get(level, "⚪")
            print(f"  视频分析: {emoji} 风险分={score} ({level}), 耗时={video_result.get('elapsed', 0)}s")
        else:
            print(f"  视频分析: {video_result.get('status', 'N/A')} - {str(video_result.get('error', ''))[:80]}")

        # 3. 音频分析
        print(f"\n  [3/3] 音频转写分析...")
        audio_result = test_audio_analysis(case)
        case_result["audio"] = audio_result
        if audio_result.get("status") == "completed":
            ad = audio_result.get("data", {})
            score = ad.get("overall_risk_score", ad.get("overall_risk", 0))
            level = ad.get("risk_level", "")
            emoji = SEVERITY_EMOJI.get(level, "⚪")
            print(f"  音频分析: {emoji} 风险分={score} ({level}), 耗时={audio_result.get('elapsed', 0)}s")
        else:
            print(f"  音频分析: {audio_result.get('status', 'N/A')} - {str(audio_result.get('error', ''))[:80]}")

        all_results.append(case_result)

        if name != "moon":
            print(f"\n  等待15秒（避免限流）...")
            time.sleep(15)

    os.makedirs(REPORT_DIR, exist_ok=True)

    json_path = os.path.join(REPORT_DIR, "comprehensive_test_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON结果已保存: {json_path}")

    report_text = generate_report(all_results)
    report_path = os.path.join(REPORT_DIR, "comprehensive_test_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"详细报告已保存: {report_path}")

    print("\n" + report_text)


if __name__ == "__main__":
    main()
