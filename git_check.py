import subprocess, os, sys

r = []
r.append("=== Git Log (last 10) ===")
try:
    out = subprocess.run(["git", "log", "--oneline", "-10"], capture_output=True, text=True, timeout=10, cwd=os.path.dirname(__file__))
    r.append(out.stdout or "(empty)")
    if out.stderr:
        r.append(f"STDERR: {out.stderr}")
except Exception as e:
    r.append(f"ERROR: {e}")

r.append("\n=== Git Status ===")
try:
    out = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=10, cwd=os.path.dirname(__file__))
    r.append(out.stdout or "(empty)")
except Exception as e:
    r.append(f"ERROR: {e}")

r.append("\n=== Git Remote ===")
try:
    out = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=10, cwd=os.path.dirname(__file__))
    r.append(out.stdout or "(empty)")
except Exception as e:
    r.append(f"ERROR: {e}")

result = "\n".join(r)
with open("data/git_check_result.txt", "w", encoding="utf-8") as f:
    f.write(result)
print(result)
