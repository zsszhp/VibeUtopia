"""
VibeUtopia 完整自包含测试脚本
1. 诊断环境
2. 初始化数据库
3. 运行4个视频测试案例
4. 输出详细报告到 data/full_test_report.md
"""
import sys
import os
import json
import time
import uuid
import traceback
from datetime import datetime
from io import StringIO

# ===== 设置路径 =====
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
os.chdir(PRO_ROOT := PROJECT_ROOT)
os.makedirs("data", exist_ok=True)

report_lines = []
def rpt(s=""):
    report_lines.append(s)

# ===== 1. 环境诊断 =====
rpt("=" * 60)
rpt("VibeUtopia 完整测试报告")
rpt(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
rpt("=" * 60)

rpt("\n## 1. 环境诊断\n")
rpt(f"Python: {sys.version}")
rpt(f"路径: {sys.executable}\n")

# 依赖检查
rpt("### 1.1 关键依赖\n")
critical = [
    ("fastapi", "FastAPI"), ("uvicorn", "Uvicorn"), ("sqlalchemy", "SQLAlchemy"),
    ("cv2", "OpenCV"), ("numpy", "NumPy"), ("httpx", "HTTPX"), ("yaml", "PyYAML"),
    ("dotenv", "python-dotenv"), ("pydantic", "Pydantic"), ("chromadb", "ChromaDB"),
    ("torch", "PyTorch"), ("scenedetect", "PySceneDetect"), ("ffmpeg", "ffmpeg-python"),
]
all_deps_ok = True
for mod, name in critical:
    try:
        m = __import__(mod)
        v = getattr(m, "__version__", "已安装")
        rpt(f"  ✅ {name}: {v}")
    except ImportError:
        rpt(f"  ❌ {name}: 未安装")
        all_deps_ok = False

# .env 检查
rpt("\n### 1.2 .env 配置\n")
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("LONGCAT_API_KEY="):
            v = line.split("=",1)[1].strip()
            rpt(f"  {'✅' if v and len(v) > 8 else '❌'} LONGCAT_API_KEY: {'已配置(' + v[:8] + '...)' if v and len(v) > 8 else '未配置'}")
        elif line.startswith("LONGCAT_BASE_URL="):
            rpt(f"  ✅ {line}")
        elif line.startswith("DATABASE_URL="):
            rpt(f"  ℹ️ {line}")
        elif line.startswith("DEFAULT_PROVIDER="):
            rpt(f"  ℹ️ {line}")
        elif line.startswith("DEFAULT_MODEL="):
            rpt(f"  ℹ️ {line}")
else:
    rpt("  ❌ .env 文件不存在")

# FFmpeg 检查
rpt("\n### 1.3 FFmpeg\n")
import subprocess
try:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        rpt(f"  ✅ {result.stdout.split(chr(10))[0]}")
    else:
        rpt(f"  ❌ FFmpeg 返回错误: {result.returncode}")
except FileNotFoundError:
    rpt("  ❌ FFmpeg 未找到（需要安装并添加到 PATH）")
except Exception as e:
    rpt(f"  ⚠️ FFmpeg 检查失败: {e}")

# 测试视频检查
rpt("\n### 1.4 测试视频文件\n")
video_dir = os.path.join(PROJECT_ROOT, "tests", "video")
test_cases = {
    "ai": {"files": ["ai.mp4", "ai_音频.mp3"], "desc": "AI相关"},
    "fight": {"files": ["fight.mp4", "fight_音频.mp3"], "desc": "暴力/冲突"},
    "mhy": {"files": ["mhy.mp4", "mhy.mp3"], "desc": "游戏/商业"},
    "moon": {"files": ["moon.mp4", "moon_音频.mp3"], "desc": "登月/科学"},
}
for case_name, case_info in test_cases.items():
    case_dir = os.path.join(video_dir, case_name)
    if os.path.exists(case_dir):
        found = []
        for f in case_info["files"]:
            fp = os.path.join(case_dir, f)
            if os.path.exists(fp):
                found.append(f"{f}({os.path.getsize(fp):,}B)")
            else:
                found.append(f"{f}(缺失)")
        rpt(f"  ✅ {case_name}/ ({case_info['desc']}): {', '.join(found)}")
    else:
        rpt(f"  ❌ {case_name}/: 目录不存在")

# ===== 2. 导入后端 =====
rpt("\n## 2. 后端模块导入\n")
try:
    from backend.config import settings
    rpt(f"  ✅ config: DEFAULT_PROVIDER={settings.DEFAULT_PROVIDER}, DEFAULT_MODEL={settings.DEFAULT_MODEL}")
except Exception as e:
    rpt(f"  ❌ config 导入失败: {e}")
    rpt(traceback.format_exc())

try:
    from backend.database import init_db, SessionLocal
    rpt("  ✅ database 导入成功")
except Exception as e:
    rpt(f"  ❌ database 导入失败: {e}")
    rpt(traceback.format_exc())

try:
    from backend.models import Task, AnalysisSummary, RiskItem, PlatformReaction
    rpt("  ✅ models 导入成功")
except Exception as e:
    rpt(f"  ❌ models 导入失败: {e}")
    rpt(traceback.format_exc())

try:
    from backend.services.llm_client import registry, router, call_llm
    rpt(f"  ✅ llm_client: {len(registry.endpoints)} 个端点可用")
    for ep in registry.endpoints:
        rpt(f"    - {ep.provider}/{ep.model_id} (tier={ep.tier}, key={ep.key_label or 'Key1'})")
except Exception as e:
    rpt(f"  ❌ llm_client 导入失败: {e}")
    rpt(traceback.format_exc())

try:
    from backend.services.video_extractor import extract_video_text
    rpt("  ✅ video_extractor 导入成功")
except Exception as e:
    rpt(f"  ❌ video_extractor 导入失败: {e}")

try:
    from backend.services.keyframe_extractor import get_extractor_status
    status = get_extractor_status()
    rpt(f"  ✅ keyframe_extractor: {status}")
except Exception as e:
    rpt(f"  ❌ keyframe_extractor 导入失败: {e}")

try:
    from backend.services.fine_grained import FineGrainedPipeline
    rpt("  ✅ fine_grained 模块导入成功")
except Exception as e:
    rpt(f"  ⚠️ fine_grained 导入警告: {e}")

# ===== 3. 初始化数据库 =====
rpt("\n## 3. 数据库初始化\n")
try:
    init_db()
    rpt("  ✅ 数据库初始化成功")
except Exception as e:
    rpt(f"  ⚠️ 数据库初始化警告: {e}")

# ===== 4. 运行测试案例 =====
rpt("\n" + "=" * 60)
rpt("## 4. 测试案例执行")
rpt("=" * 60)

import asyncio
from backend.services.analyzer import run_analysis

async def run_all_tests():
    results = []

    for case_name, case_info in test_cases.items():
        case_dir = os.path.join(video_dir, case_name)
        case_result = {
            "name": case_name,
            "desc": case_info["desc"],
            "start_time": time.time(),
            "end_time": 0,
            "status": "pending",
            "errors": [],
            "analysis": None,
        }

        rpt(f"\n### 案例: {case_name} ({case_info['desc']})")
        rpt(f"  目录: {case_dir}")

        # 找到视频文件
        video_path = None
        for f in case_info["files"]:
            if f.endswith(".mp4"):
                fp = os.path.join(case_dir, f)
                if os.path.exists(fp):
                    video_path = fp
                    break

        if not video_path:
            case_result["status"] = "skipped"
            case_result["errors"].append("未找到视频文件")
            rpt("  ⚠️ 跳过: 未找到视频文件")
            results.append(case_result)
            continue

        rpt(f"  视频: {video_path}")

        # 提取文案
        text = ""
        try:
            from backend.services.video_extractor import extract_video_text
            extract_result = await extract_video_text(video_path)
            text = extract_result.get("text", "")
            source = extract_result.get("source", "")
            rpt(f"  文案提取: source={source}, length={len(text)}")
            if text:
                preview = text[:150].replace("\n", " ")
                rpt(f"  文案预览: {preview}...")
            else:
                rpt("  ⚠️ 文案为空，将使用默认分析文本")
        except Exception as e:
            case_result["errors"].append(f"文案提取失败: {e}")
            rpt(f"  ⚠️ 文案提取失败: {e}")

        if not text or len(text.strip()) < 10:
            text = f"这是{case_name}测试视频的内容。视频文件存在但文案提取结果为空。"

        # 运行风控分析
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

            rpt(f"  任务ID: {task_id}")
            rpt(f"  正在分析...")

            analysis = await run_analysis(task_id, text[:5000])
            case_result["analysis"] = analysis
            case_result["task_id"] = task_id
            case_result["status"] = "completed"

            rpt(f"\n  📊 分析结果:")
            rpt(f"     总体风险分: {analysis.get('overall_score', 'N/A')}")
            rpt(f"     风险等级: {analysis.get('risk_level', 'N/A')}")
            rpt(f"     建议: {analysis.get('suggestion', 'N/A')}")

            dimensions = analysis.get("dimensions", [])
            if dimensions:
                rpt(f"     风险维度 ({len(dimensions)}个):")
                for dim in dimensions:
                    name = dim.get("name", "")
                    score = dim.get("score", 0)
                    severity = dim.get("severity", "green")
                    rpt(f"       {'🔴' if severity=='red' else '🟠' if severity=='orange' else '🟡' if severity=='yellow' else '🟢'} {name}: {score}分 ({severity})")

            platform_reactions = analysis.get("platform_reactions", [])
            if platform_reactions:
                rpt(f"     平台反应 ({len(platform_reactions)}个):")
                for pr in platform_reactions:
                    platform = pr.get("platform", "")
                    pos = pr.get("positive", 0)
                    neg = pr.get("negative", 0)
                    rpt(f"       📌 {platform}: 正面{pos:.0%} 负面{neg:.0%}")

            confidence = analysis.get("confidence", {})
            if confidence:
                rpt(f"     置信度: {confidence.get('overall_confidence', 'N/A')}")

        except Exception as e:
            case_result["status"] = "failed"
            case_result["errors"].append(f"分析失败: {e}")
            rpt(f"  ❌ 分析失败: {e}")
            rpt(traceback.format_exc())

        case_result["end_time"] = time.time()
        duration = case_result["end_time"] - case_result["start_time"]
        case_result["duration"] = round(duration, 2)
        rpt(f"  ⏱️ 耗时: {duration:.1f}秒")

        results.append(case_result)

    return results

# 运行异步测试
try:
    test_results = asyncio.run(run_all_tests())
except Exception as e:
    rpt(f"\n❌ 测试执行异常: {e}")
    rpt(traceback.format_exc())
    test_results = []

# ===== 5. 总结报告 =====
rpt("\n" + "=" * 60)
rpt("## 5. 测试总结")
rpt("=" * 60)

total = len(test_results)
passed = sum(1 for r in test_results if r["status"] == "completed")
failed = sum(1 for r in test_results if r["status"] == "failed")
skipped = sum(1 for r in test_results if r["status"] == "skipped")
total_time = sum(r.get("duration", 0) for r in test_results)

rpt(f"\n  📊 统计:")
rpt(f"     总计: {total}")
rpt(f"     ✅ 通过: {passed}")
rpt(f"     ❌ 失败: {failed}")
rpt(f"     ⏭️ 跳过: {skipped}")
rpt(f"     ⏱️ 总耗时: {total_time:.1f}秒")

rpt(f"\n  详细结果:")
for r in test_results:
    status_emoji = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(r["status"], "❓")
    rpt(f"\n  {status_emoji} {r['name']} ({r['desc']}) - {r['status']} ({r.get('duration', 0):.1f}s)")
    if r.get("analysis"):
        a = r["analysis"]
        rpt(f"     风险分: {a.get('overall_score', 'N/A')} | 等级: {a.get('risk_level', 'N/A')} | 建议: {a.get('suggestion', 'N/A')}")
    for e in r.get("errors", []):
        rpt(f"     ⚠️ {e}")

rpt("\n" + "=" * 60)
rpt("报告结束")
rpt("=" * 60)

# 写报告
report_text = "\n".join(report_lines)
report_path = os.path.join(PROJECT_ROOT, "data", "full_test_report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_text)

# 同时写 JSON 版本
json_path = os.path.join(PROJECT_ROOT, "data", "full_test_report.json")
json_results = []
for r in test_results:
    jr = {k: v for k, v in r.items() if k != "analysis" or isinstance(v, (dict, type(None)))}
    if isinstance(r.get("analysis"), dict):
        jr["analysis"] = {k: v for k, v in r["analysis"].items()
                         if isinstance(v, (str, int, float, bool, dict, list, type(None)))}
    json_results.append(jr)

with open(json_path, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "total_time": round(total_time, 2)},
        "results": json_results,
    }, f, ensure_ascii=False, indent=2)

# 输出到 stdout（供外部捕获）
print(report_text)
print(f"\n报告已保存: {report_path}")
print(f"JSON已保存: {json_path}")
