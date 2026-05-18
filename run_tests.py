"""
VibeUtopia 测试视频完整分析脚本
对 tests/video 下的 4 个测试案例运行完整风控分析，输出详细报告
"""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime

# 设置路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

os.chdir(PROJECT_ROOT)

# 确保 data 目录存在
os.makedirs("data", exist_ok=True)

# 导入项目模块
from backend.config import settings
from backend.database import init_db, SessionLocal
from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
from backend.services.analyzer import run_analysis
from backend.services.video_extractor import extract_video_text

# 测试案例配置
TEST_CASES = [
    {
        "name": "ai",
        "dir": os.path.join(PROJECT_ROOT, "tests", "video", "ai"),
        "files": ["ai.mp4", "ai_音频.mp3"],
        "expected_risk": "AI相关内容风险",
    },
    {
        "name": "fight",
        "dir": os.path.join(PROJECT_ROOT, "tests", "video", "fight"),
        "files": ["fight.mp4", "fight_音频.mp3"],
        "expected_risk": "暴力/冲突内容风险",
    },
    {
        "name": "mhy",
        "dir": os.path.join(PROJECT_ROOT, "tests", "video", "mhy"),
        "files": ["mhy.mp4", "mhy.mp3"],
        "expected_risk": "游戏/商业内容风险",
    },
    {
        "name": "moon",
        "dir": os.path.join(PROJECT_ROOT, "tests", "video", "moon"),
        "files": ["moon.mp4", "moon_音频.mp3"],
        "expected_risk": "登月/科学内容风险",
    },
]


async def analyze_video(case: dict) -> dict:
    """分析单个视频案例"""
    case_name = case["name"]
    case_dir = case["dir"]
    result = {
        "case_name": case_name,
        "case_dir": case_dir,
        "files_found": [],
        "files_missing": [],
        "video_extract": None,
        "analysis": None,
        "errors": [],
        "start_time": time.time(),
        "end_time": 0,
        "duration_seconds": 0,
    }

    print(f"\n{'='*60}")
    print(f"  测试案例: {case_name}")
    print(f"{'='*60}")

    # 1. 检查文件
    print(f"\n  [1] 文件检查:")
    for f in case["files"]:
        fp = os.path.join(case_dir, f)
        if os.path.exists(fp):
            size = os.path.getsize(fp)
            result["files_found"].append(f"{f} ({size:,} bytes)")
            print(f"      ✅ {f} ({size:,} bytes)")
        else:
            result["files_missing"].append(f)
            print(f"      ❌ {f} 不存在")

    if not result["files_found"]:
        result["errors"].append("没有找到任何测试文件")
        print(f"  ⚠️ 跳过：没有测试文件")
        return result

    # 2. 提取视频文案
    print(f"\n  [2] 视频文案提取:")
    video_path = None
    for f in case["files"]:
        if f.endswith(".mp4"):
            video_path = os.path.join(case_dir, f)
            break

    if video_path and os.path.exists(video_path):
        try:
            extract_result = await extract_video_text(video_path)
            result["video_extract"] = extract_result
            text = extract_result.get("text", "")
            source = extract_result.get("source", "")
            error = extract_result.get("error", "")
            if error:
                print(f"      ⚠️ 提取警告: {error}")
            print(f"      来源: {source}")
            print(f"      文案长度: {len(text)} 字")
            if text:
                preview = text[:200].replace("\n", " ")
                print(f"      文案预览: {preview}...")
        except Exception as e:
            result["errors"].append(f"视频提取失败: {e}")
            print(f"      ❌ 提取失败: {e}")
            text = ""
    else:
        text = ""
        print(f"      ⚠️ 没有找到视频文件")

    # 3. 运行风控分析
    print(f"\n  [3] 风控分析:")
    if not text or len(text.strip()) < 10:
        # 使用默认测试文本
        text = f"这是{case_name}测试案例的内容。视频文件已上传但文案提取结果为空，使用文件名作为分析内容。"
        print(f"      ⚠️ 文案为空，使用默认文本")

    try:
        task_id = f"test_{case_name}_{uuid.uuid4().hex[:8]}"
        db = SessionLocal()
        task = Task(
            id=task_id,
            text=text[:5000],
            status="processing",
            model=settings.DEFAULT_MODEL or "test",
            mode="video",
            depth="standard",
        )
        db.add(task)
        db.commit()
        db.close()

        print(f"      任务ID: {task_id}")
        print(f"      正在分析中...")

        analysis_result = await run_analysis(task_id, text[:5000])

        result["analysis"] = analysis_result
        result["task_id"] = task_id

        # 输出分析结果摘要
        print(f"\n  [4] 分析结果摘要:")
        print(f"      📊 总体风险分: {analysis_result.get('overall_score', 'N/A')}")
        print(f"      🚦 风险等级: {analysis_result.get('risk_level', 'N/A')}")
        print(f"      💡 建议: {analysis_result.get('suggestion', 'N/A')}")

        dimensions = analysis_result.get("dimensions", [])
        if dimensions:
            print(f"\n      📋 风险维度 ({len(dimensions)}个):")
            for dim in dimensions:
                name = dim.get("name", "")
                score = dim.get("score", 0)
                severity = dim.get("severity", "green")
                emoji = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(severity, "⚪")
                print(f"        {emoji} {name}: {score}分 ({severity})")

        platform_reactions = analysis_result.get("platform_reactions", [])
        if platform_reactions:
            print(f"\n      📱 平台反应 ({len(platform_reactions)}个平台):")
            for pr in platform_reactions:
                platform = pr.get("platform", "")
                pos = pr.get("positive", 0)
                neg = pr.get("negative", 0)
                neu = pr.get("neutral", 0)
                print(f"        📌 {platform}: 正面{pos:.0%} 中性{neu:.0%} 负面{neg:.0%}")

        confidence = analysis_result.get("confidence", {})
        if confidence:
            print(f"\n      🎯 置信度: {confidence.get('overall_confidence', 'N/A')}")
            breakdown = confidence.get("breakdown", {})
            for k, v in breakdown.items():
                print(f"        - {k}: {v}")

    except Exception as e:
        result["errors"].append(f"风控分析失败: {e}")
        print(f"      ❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    result["end_time"] = time.time()
    result["duration_seconds"] = round(result["end_time"] - result["start_time"], 2)
    print(f"\n  ⏱️ 耗时: {result['duration_seconds']}秒")

    return result


async def main():
    """主测试流程"""
    print("╔" + "═" * 58 + "╗")
    print("║  VibeUtopia 测试视频完整分析                        ║")
    print("║  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "                              ║")
    print("╚" + "═" * 58 + "╝")

    # 初始化数据库
    print("\n[初始化] 数据库...")
    try:
        init_db()
        print("  ✅ 数据库初始化完成")
    except Exception as e:
        print(f"  ⚠️ 数据库初始化警告: {e}")

    # 检查配置
    print("\n[配置检查]")
    print(f"  DEFAULT_PROVIDER: {settings.DEFAULT_PROVIDER}")
    print(f"  DEFAULT_MODEL: {settings.DEFAULT_MODEL}")
    print(f"  DATABASE_URL: {settings.DATABASE_URL}")
    has_key = bool(os.getenv("LONGCAT_API_KEY"))
    print(f"  LONGCAT_API_KEY: {'已配置' if has_key else '未配置'}")

    # 逐个运行测试案例
    all_results = []
    for case in TEST_CASES:
        try:
            result = await analyze_video(case)
            all_results.append(result)
        except Exception as e:
            print(f"\n  ❌ 案例 {case['name']} 运行异常: {e}")
            all_results.append({
                "case_name": case["name"],
                "errors": [str(e)],
            })

    # 输出总报告
    print("\n\n")
    print("╔" + "═" * 58 + "╗")
    print("║  📊 完整测试报告                                    ║")
    print("╚" + "═" * 58 + "╝")

    total_time = 0
    success_count = 0
    fail_count = 0

    for r in all_results:
        name = r["case_name"]
        errors = r.get("errors", [])
        analysis = r.get("analysis", {})
        duration = r.get("duration_seconds", 0)
        total_time += duration

        if errors:
            fail_count += 1
            status = "❌ 失败"
        else:
            success_count += 1
            status = "✅ 通过"

        print(f"\n  {status} {name}")
        print(f"    耗时: {duration}s")
        if analysis:
            print(f"    风险分: {analysis.get('overall_score', 'N/A')}")
            print(f"    风险等级: {analysis.get('risk_level', 'N/A')}")
            print(f"    建议: {analysis.get('suggestion', 'N/A')}")
            dims = analysis.get("dimensions", [])
            if dims:
                high_risk = [d for d in dims if d.get("severity") in ("red", "orange")]
                if high_risk:
                    print(f"    高风险维度: {', '.join(d['name']+'('+str(d['score'])+')' for d in high_risk)}")
        if errors:
            for e in errors:
                print(f"    错误: {e}")

    print(f"\n{'─'*60}")
    print(f"  📈 统计: {success_count}通过 / {fail_count}失败 / 总计{len(all_results)}")
    print(f"  ⏱️ 总耗时: {total_time:.1f}秒")
    print(f"{'─'*60}")

    # 保存报告到文件
    report_path = os.path.join(PROJECT_ROOT, "data", "test_report.json")
    serializable_results = []
    for r in all_results:
        sr = {k: v for k, v in r.items() if k != "analysis" or isinstance(v, (dict, type(None)))}
        if isinstance(r.get("analysis"), dict):
            sr["analysis"] = {k: v for k, v in r["analysis"].items() if isinstance(v, (str, int, float, bool, dict, list, type(None)))}
        serializable_results.append(sr)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(all_results),
                "passed": success_count,
                "failed": fail_count,
                "total_time_seconds": round(total_time, 2),
            },
            "results": serializable_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  📄 报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
