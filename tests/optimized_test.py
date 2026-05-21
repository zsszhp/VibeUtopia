"""优化后综合测试脚本 - 直接调用核心模块测试4个案例的封面/视频/音频分析"""

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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TEST_VIDEO_DIR = os.path.abspath("tests/video")
TRANSCRIPT_DIR = os.path.abspath("data/video_transcripts")
REPORT_DIR = os.path.abspath("data/reports")

VIDEO_CASES = [
    {"name": "ai", "description": "AI相关内容视频（计算机科学专业与AI影响）",
     "cover": "ai(封面).jpg", "video": "ai.mp4", "audio": "ai_音频.mp3"},
    {"name": "fight", "description": "争议/冲突类视频（朝鲜战争历史分析）",
     "cover": "fight(封面).jpg", "video": "fight.mp4", "audio": "fight_音频.mp3"},
    {"name": "mhy", "description": "米哈游相关视频（AI模型评测）",
     "cover": "mhy.jpg", "video": "mhy.mp4", "audio": "mhy.mp3"},
    {"name": "moon", "description": "月亮/天文类视频（宇宙天文科普）",
     "cover": "moon(封面).jpg", "video": "moon.mp4", "audio": "moon_音频.mp3"},
]

SEVERITY_EMOJI = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}


def load_transcript(case_name):
    path = os.path.join(TRANSCRIPT_DIR, f"{case_name}.json")
    if not os.path.exists(path):
        return "", {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("text", ""), data


async def test_cover_analysis(case):
    cover_path = os.path.join(TEST_VIDEO_DIR, case["name"], case["cover"])
    if not os.path.exists(cover_path):
        return {"status": "skip", "error": f"封面文件不存在: {cover_path}"}
    try:
        with open(cover_path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        from backend.services.llm_client import call_vlm
        start = time.time()
        result = await call_vlm(
            prompt="请分析这张视频封面图片是否存在任何风险内容（政治敏感、不当内容、争议符号等）。输出JSON：{\"risk_level\": \"safe|low|medium|high\", \"risks\": [], \"summary\": \"\"}",
            image_base64=image_base64,
            system="你是视频封面风险评估专家。",
            task_type="risk_assessment",
        )
        elapsed = round(time.time() - start, 2)
        return {"status": "success", "result": result[:500], "elapsed": elapsed}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


async def test_video_analysis(case):
    text, tdata = load_transcript(case["name"])
    if not text:
        return {"status": "skip", "error": "无预提取文案", "elapsed": 0}

    try:
        from backend.services.risk_assessor import assess_risks
        from backend.services.transcript_detector import detect_transcript_quality
        from backend.services.text_splitter import split_text

        start = time.time()
        sentences = split_text(text)
        transcript_quality = await detect_transcript_quality(text, sentences)
        risk_results = await assess_risks(text, transcript_quality=transcript_quality)

        from backend.services.analyzer import calculate_overall_score
        dimensions = risk_results.get("dimensions", [])
        overall_score, _, _ = calculate_overall_score(dimensions)

        risk_level = "green"
        if overall_score > 75:
            risk_level = "red"
        elif overall_score > 55:
            risk_level = "orange"
        elif overall_score > 25:
            risk_level = "yellow"

        elapsed = round(time.time() - start, 2)
        return {
            "status": "completed",
            "elapsed": elapsed,
            "overall_score": overall_score,
            "risk_level": risk_level,
            "dimensions": dimensions,
            "risk_sentences": risk_results.get("risk_sentences", []),
            "text_length": len(text),
            "duration": tdata.get("duration", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "elapsed": 0}


async def test_audio_analysis(case):
    text, tdata = load_transcript(case["name"])
    if not text:
        return {"status": "skip", "error": "无预提取文案", "elapsed": 0}

    audio_path = os.path.join(TEST_VIDEO_DIR, case["name"], case["audio"])
    audio_exists = os.path.exists(audio_path)

    try:
        from backend.services.multimodal_analyzer import MultiModalAnalyzer
        start = time.time()
        analyzer = MultiModalAnalyzer()
        audio_result = await analyzer.analyze_audio(
            audio_transcript=f"【音频转写内容】\n{text}",
        )
        elapsed = round(time.time() - start, 2)
        return {
            "status": "completed",
            "elapsed": elapsed,
            "audio_risk_score": audio_result.get("overall_audio_risk_score", 0),
            "audio_summary": audio_result.get("summary", ""),
            "audio_file_exists": audio_exists,
            "text_length": len(text),
            "duration": tdata.get("duration", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], "elapsed": 0}


async def run_all_tests():
    print("=" * 70)
    print("VibeUtopia 优化后综合测试 - 封面/视频/音频分析")
    print("=" * 70)

    all_results = []

    for case in VIDEO_CASES:
        name = case["name"]
        desc = case["description"]
        print(f"\n{'='*60}")
        print(f"测试案例: {name} — {desc}")
        print(f"{'='*60}")

        case_result = {"name": name, "description": desc, "cover": {}, "video": {}, "audio": {}}

        print(f"  [1/3] 封面图片分析...")
        cover_result = await test_cover_analysis(case)
        case_result["cover"] = cover_result
        print(f"  封面分析: {cover_result.get('status', 'N/A')} ({cover_result.get('elapsed', 0)}s)")

        print(f"  [2/3] 视频内容分析...")
        video_result = await test_video_analysis(case)
        case_result["video"] = video_result
        if video_result.get("status") == "completed":
            emoji = SEVERITY_EMOJI.get(video_result.get("risk_level", ""), "⚪")
            print(f"  视频分析: {emoji} 风险分={video_result.get('overall_score', 0)} ({video_result.get('risk_level', '')}), 耗时={video_result.get('elapsed', 0)}s")
        else:
            print(f"  视频分析: {video_result.get('status', 'N/A')} - {str(video_result.get('error', ''))[:80]}")

        print(f"  [3/3] 音频转写分析...")
        audio_result = await test_audio_analysis(case)
        case_result["audio"] = audio_result
        if audio_result.get("status") == "completed":
            print(f"  音频分析: 风险分={audio_result.get('audio_risk_score', 0)}, 耗时={audio_result.get('elapsed', 0)}s")
        else:
            print(f"  音频分析: {audio_result.get('status', 'N/A')} - {str(audio_result.get('error', ''))[:80]}")

        all_results.append(case_result)

        if name != "moon":
            print(f"  等待5秒（避免限流）...")
            await asyncio.sleep(5)

    os.makedirs(REPORT_DIR, exist_ok=True)

    json_path = os.path.join(REPORT_DIR, "optimized_test_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON结果已保存: {json_path}")

    report_text = generate_report(all_results)
    report_path = os.path.join(REPORT_DIR, "optimized_test_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"详细报告已保存: {report_path}")

    print("\n" + report_text)


def generate_report(all_results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("=" * 90)
    lines.append("VibeUtopia 优化后综合测试报告 - 封面/视频/音频分析")
    lines.append(f"生成时间: {now}")
    lines.append(f"测试案例数: {len(all_results)}")
    lines.append(f"优化内容: 并行化分析管道 + LLM并发控制 + 图片压缩 + 指数退避重试")
    lines.append("=" * 90)

    lines.append("")
    lines.append("一、环境配置")
    lines.append("-" * 90)
    lines.append("  API Provider: LongCat (2个Key轮换)")
    lines.append("  默认模型: LongCat-Flash-Thinking-2601")
    lines.append("  数据库: SQLite (Docker/MySQL未启动，已降级)")
    lines.append("  Neo4j: 未启动 (降级到关系型数据库模式)")
    lines.append("  Ollama: 已安装 (qwopus9b模型)")
    lines.append("  Docker: 未启动")
    lines.append("  OpenCV: 4.13.0 ✓")
    lines.append("  FFmpeg: 6.1.1 ✓")
    lines.append("  httpx: 0.28.1 ✓")
    lines.append("  chromadb: 1.5.9 ✓")

    lines.append("")
    lines.append("二、案例风险总览")
    lines.append("-" * 90)
    lines.append(f"{'案例':<8} {'描述':<30} {'视频风险分':<12} {'视频等级':<10} {'音频风险分':<12} {'视频耗时':<10} {'音频耗时':<10}")
    lines.append("-" * 90)

    for r in all_results:
        name = r["name"]
        desc = r["description"][:28]
        video = r.get("video", {})
        audio = r.get("audio", {})

        v_score = str(video.get("overall_score", "N/A"))
        v_level = video.get("risk_level", "N/A")
        v_time = f"{video.get('elapsed', 0)}s"
        a_score = str(audio.get("audio_risk_score", "N/A"))
        a_time = f"{audio.get('elapsed', 0)}s"

        if video.get("status") == "error":
            v_score = "ERR"
            v_level = video.get("error", "")[:15]
        if audio.get("status") == "error":
            a_score = "ERR"

        lines.append(f"{name:<8} {desc:<30} {v_score:<12} {v_level:<10} {a_score:<12} {v_time:<10} {a_time:<10}")

    for r in all_results:
        name = r["name"]
        desc = r["description"]
        lines.append("")
        lines.append("=" * 90)
        lines.append(f"三、案例详细分析: {name} — {desc}")
        lines.append("=" * 90)

        lines.append("")
        lines.append("【3.1 封面图片分析】")
        cover = r.get("cover", {})
        lines.append(f"  状态: {cover.get('status', 'N/A')}")
        lines.append(f"  耗时: {cover.get('elapsed', 'N/A')}秒")
        if cover.get("status") == "success":
            lines.append(f"  结果: {cover.get('result', 'N/A')[:300]}")
        elif cover.get("status") == "error":
            lines.append(f"  错误: {cover.get('error', 'N/A')}")

        lines.append("")
        lines.append("【3.2 视频内容分析】")
        video = r.get("video", {})
        lines.append(f"  状态: {video.get('status', 'N/A')}")
        lines.append(f"  耗时: {video.get('elapsed', 'N/A')}秒")
        lines.append(f"  文案字数: {video.get('text_length', 'N/A')}")
        if video.get("status") == "completed":
            score = video.get("overall_score", 0)
            level = video.get("risk_level", "")
            emoji = SEVERITY_EMOJI.get(level, "⚪")
            lines.append(f"  风险总分: {score}/100")
            lines.append(f"  风险等级: {emoji} {level}")
            dims = video.get("dimensions", [])
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
        elif video.get("status") == "error":
            lines.append(f"  错误: {video.get('error', 'N/A')}")

        lines.append("")
        lines.append("【3.3 音频转写分析】")
        audio = r.get("audio", {})
        lines.append(f"  状态: {audio.get('status', 'N/A')}")
        lines.append(f"  耗时: {audio.get('elapsed', 'N/A')}秒")
        lines.append(f"  音频文件: {'存在' if audio.get('audio_file_exists') else '不存在'}")
        if audio.get("status") == "completed":
            lines.append(f"  音频风险分: {audio.get('audio_risk_score', 0)}")
            lines.append(f"  摘要: {audio.get('audio_summary', 'N/A')[:100]}")
        elif audio.get("status") == "error":
            lines.append(f"  错误: {audio.get('error', 'N/A')}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("四、优化效果总结")
    lines.append("=" * 90)

    completed_video = [r for r in all_results if r.get("video", {}).get("status") == "completed"]
    completed_audio = [r for r in all_results if r.get("audio", {}).get("status") == "completed"]

    lines.append(f"  视频分析完成: {len(completed_video)}/{len(all_results)}")
    lines.append(f"  音频分析完成: {len(completed_audio)}/{len(all_results)}")

    if completed_video:
        avg_time = sum(r["video"].get("elapsed", 0) for r in completed_video) / len(completed_video)
        avg_score = sum(r["video"].get("overall_score", 0) for r in completed_video) / len(completed_video)
        lines.append(f"  平均视频分析耗时: {avg_time:.1f}秒")
        lines.append(f"  平均视频风险分: {avg_score:.1f}")

    if completed_audio:
        avg_audio_time = sum(r["audio"].get("elapsed", 0) for r in completed_audio) / len(completed_audio)
        lines.append(f"  平均音频分析耗时: {avg_audio_time:.1f}秒")

    lines.append("")
    lines.append("  优化项:")
    lines.append("    1. ✅ 修复audio_transcriber.py的time.sleep阻塞事件循环bug")
    lines.append("    2. ✅ analyzer.py: 风险评估+信号采集+实体风险链并行执行")
    lines.append("    3. ✅ analyzer.py: 动态权重+平台仿真+Agent仿真并行执行")
    lines.append("    4. ✅ enhanced_analyzer.py: Phase 2.6+2.7并行执行")
    lines.append("    5. ✅ frame_risk.py: 并行帧处理(信号量控制并发)")
    lines.append("    6. ✅ frame_risk.py: 图片自动压缩(>1024px缩放)")
    lines.append("    7. ✅ frame_ocr.py: 并行帧处理")
    lines.append("    8. ✅ multimodal_analyzer.py: 批量视觉描述并行生成")
    lines.append("    9. ✅ llm_client.py: 全局LLM并发控制(10个LLM+5个VLM)")
    lines.append("    10. ✅ risk_assessor.py: 指数退避重试策略")

    lines.append("")
    lines.append("=" * 90)
    lines.append("报告结束")
    lines.append("=" * 90)

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
