"""快速测试 - 直接写结果到文件"""
import sys, os, json

# 写结果到文件的日志
result_file = os.path.join(os.path.dirname(__file__), "data", "quick_test_result.json")
os.makedirs("data", exist_ok=True)

results = {"python_version": sys.version, "cwd": os.getcwd(), "checks": []}

# 1. 依赖检查
for mod in ["fastapi", "uvicorn", "sqlalchemy", "cv2", "numpy", "httpx", "yaml", "dotenv", "pydantic", "chromadb"]:
    try:
        m = __import__(mod)
        v = getattr(m, "__version__", "OK")
        results["checks"].append({"module": mod, "status": "OK", "version": v})
    except ImportError as e:
        results["checks"].append({"module": mod, "status": "FAIL", "error": str(e)})

# 2. 后端导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
try:
    from backend.config import settings
    results["checks"].append({"module": "backend.config", "status": "OK", "provider": settings.DEFAULT_PROVIDER, "model": settings.DEFAULT_MODEL})
except Exception as e:
    results["checks"].append({"module": "backend.config", "status": "FAIL", "error": str(e)})

try:
    from backend.database import init_db, SessionLocal
    init_db()
    results["checks"].append({"module": "backend.database", "status": "OK"})
except Exception as e:
    results["checks"].append({"module": "backend.database", "status": "FAIL", "error": str(e)})

try:
    from backend.services.llm_client import registry
    ep_count = len(registry.endpoints)
    results["checks"].append({"module": "llm_client", "status": "OK", "endpoints": ep_count})
except Exception as e:
    results["checks"].append({"module": "llm_client", "status": "FAIL", "error": str(e)})

try:
    from backend.services.checkpoint_manager import CheckpointManager, AnalysisCheckpoint
    results["checks"].append({"module": "checkpoint_manager", "status": "OK"})
except Exception as e:
    results["checks"].append({"module": "checkpoint_manager", "status": "FAIL", "error": str(e)})

try:
    from backend.services.resumable_analyzer import ResumableAnalyzer
    results["checks"].append({"module": "resumable_analyzer", "status": "OK"})
except Exception as e:
    results["checks"].append({"module": "resumable_analyzer", "status": "FAIL", "error": str(e)})

# 3. 视频文件
vd = os.path.join(os.path.dirname(__file__), "tests", "video")
for case in ["ai", "fight", "mhy", "moon"]:
    cd = os.path.join(vd, case)
    if os.path.exists(cd):
        files = os.listdir(cd)
        results["checks"].append({"module": f"video_{case}", "status": "OK", "files": files})
    else:
        results["checks"].append({"module": f"video_{case}", "status": "FAIL", "error": "dir not found"})

# 写结果
with open(result_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 同时写可读版本
md_file = os.path.join(os.path.dirname(__file__), "data", "quick_test_result.md")
with open(md_file, "w", encoding="utf-8") as f:
    f.write("# 快速环境检查结果\n\n")
    for c in results["checks"]:
        icon = "✅" if c["status"] == "OK" else "❌"
        f.write(f"- {icon} **{c['module']}**: {c.get('version', c.get('error', c['status']))}\n")
        if c.get("endpoints"):
            f.write(f"  - 端点数: {c['endpoints']}\n")
        if c.get("files"):
            f.write(f"  - 文件: {', '.join(c['files'])}\n")

print(f"Results written to {result_file}")
