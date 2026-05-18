import subprocess, os, sys

os.chdir(r"D:\project\VibeUtopia")
log = []

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    log.append(f"$ {' '.join(cmd)}")
    log.append(f"  exit={r.returncode}")
    if r.stdout.strip():
        log.append(f"  stdout: {r.stdout.strip()}")
    if r.stderr.strip():
        log.append(f"  stderr: {r.stderr.strip()}")
    return r

# 1. git status
run(["git", "status", "--porcelain"])

# 2. git add
run(["git", "add", "-A"])

# 3. git commit
run(["git", "commit", "-m", "feat: 断点续传机制 checkpoint_manager+resumable_analyzer+routes_resume"])

# 4. git log (verify commit)
run(["git", "log", "--oneline", "-5"])

# 5. git push gitee
r = run(["git", "push", "gitee"])
if r.returncode != 0:
    log.append("  GITEE PUSH FAILED, trying with --force")
    run(["git", "push", "gitee", "--force"])

# 6. git push github
r = run(["git", "push", "github"])
if r.returncode != 0:
    log.append("  GITHUB PUSH FAILED, trying with --force")
    run(["git", "push", "github", "--force"])

# 7. final log
run(["git", "log", "--oneline", "-5"])

# write output
output = "\n".join(log)
with open(r"D:\project\VibeUtopia\data\git_push_result.txt", "w", encoding="utf-8") as f:
    f.write(output)
print(output)
