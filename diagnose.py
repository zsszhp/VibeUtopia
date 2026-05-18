"""诊断脚本 - 输出到文件"""
import sys, os, traceback

log = []
log.append(f"Python: {sys.version}")
log.append(f"Executable: {sys.executable}")
log.append(f"CWD: {os.getcwd()}")
log.append(f"PATH: {os.environ.get('PATH', '')[:200]}")
log.append("")

# 检查关键依赖
log.append("=== 依赖检查 ===")
for mod in ["fastapi", "uvicorn", "sqlalchemy", "cv2", "numpy", "httpx", "yaml", "dotenv", "pydantic", "chromadb"]:
    try:
        m = __import__(mod)
        v = getattr(m, "__version__", "OK")
        log.append(f"  OK {mod}: {v}")
    except ImportError as e:
        log.append(f"  FAIL {mod}: {e}")

log.append("")

# 检查 .env
log.append("=== .env 检查 ===")
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    log.append(f"  .env exists: {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("LONGCAT_API_KEY="):
                v = line.split("=",1)[1].strip()
                log.append(f"  LONGCAT_API_KEY: {'SET('+v[:8]+'...)' if v and len(v)>8 else 'EMPTY'}")
            elif line.startswith("LONGCAT_BASE_URL="):
                log.append(f"  {line}")
            elif line.startswith("DATABASE_URL="):
                log.append(f"  {line}")
            elif line.startswith("DEFAULT_PROVIDER="):
                log.append(f"  {line}")
            elif line.startswith("DEFAULT_MODEL="):
                log.append(f"  {line}")
else:
    log.append(f"  .env NOT FOUND: {env_path}")

log.append("")

# 检查后端导入
log.append("=== 后端导入检查 ===")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
try:
    import backend.main
    log.append("  OK: backend.main imported")
except Exception as e:
    log.append(f"  FAIL: backend.main import error: {e}")
    log.append(traceback.format_exc())

log.append("")

# 检查 FFmpeg
log.append("=== FFmpeg 检查 ===")
import subprocess
try:
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
    if r.returncode == 0:
        log.append(f"  OK: {r.stdout.split(chr(10))[0]}")
    else:
        log.append(f"  FAIL: exit code {r.returncode}")
except FileNotFoundError:
    log.append("  NOT FOUND: ffmpeg not in PATH")
except Exception as e:
    log.append(f"  ERROR: {e}")

log.append("")

# 检查测试视频
log.append("=== 测试视频检查 ===")
vd = os.path.join(os.path.dirname(__file__), "tests", "video")
for case in ["ai", "fight", "mhy", "moon"]:
    cd = os.path.join(vd, case)
    if os.path.exists(cd):
        files = os.listdir(cd)
        sizes = []
        for f in files:
            fp = os.path.join(cd, f)
            sizes.append(f"{f}({os.path.getsize(fp):,}B)")
        log.append(f"  OK {case}/: {', '.join(sizes)}")
    else:
        log.append(f"  MISSING {case}/")

# 写输出
output = "\n".join(log)
out_path = os.path.join(os.path.dirname(__file__), "diagnose_out.txt")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(output)
print(f"Written to {out_path}")
