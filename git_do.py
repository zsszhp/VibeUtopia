import subprocess, os, sys

os.chdir(r"D:\project\VibeUtopia")
os.makedirs("data", exist_ok=True)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

with open(r"D:\project\VibeUtopia\data\git_do_result.txt", "w", encoding="utf-8") as f:
    # 1. git status
    out, err, code = run(["git", "status"])
    f.write(f"=== git status (exit={code}) ===\n{out}\n")
    if err: f.write(f"STDERR: {err}\n")

    # 2. git log
    out, err, code = run(["git", "log", "--oneline", "-10"])
    f.write(f"\n=== git log (exit={code}) ===\n{out}\n")

    # 3. git diff --stat HEAD~1
    out, err, code = run(["git", "diff", "--stat", "HEAD~1"])
    f.write(f"\n=== git diff HEAD~1 (exit={code}) ===\n{out}\n")

    # 4. 检查 remote
    out, err, code = run(["git", "remote", "-v"])
    f.write(f"\n=== git remote (exit={code}) ===\n{out}\n")

    # 5. 尝试 add + commit
    out, err, code = run(["git", "add", "-A"])
    f.write(f"\n=== git add -A (exit={code}) ===\n{out}\n")
    if err: f.write(f"STDERR: {err}\n")

    out, err, code = run(["git", "commit", "-m", "feat: 断点续传机制——checkpoint_manager+resumable_analyzer+routes_resume，解决长视频API限流中断问题"])
    f.write(f"\n=== git commit (exit={code}) ===\n{out}\n")
    if err: f.write(f"STDERR: {err}\n")

    # 6. 尝试 push gitee
    out, err, code = run(["git", "push", "gitee"])
    f.write(f"\n=== git push gitee (exit={code}) ===\n{out}\n")
    if err: f.write(f"STDERR: {err}\n")

    # 7. 尝试 push github
    out, err, code = run(["git", "push", "github"])
    f.write(f"\n=== git push github (exit={code}) ===\n{out}\n")
    if err: f.write(f"STDERR: {err}\n")

    # 8. 最终 log
    out, err, code = run(["git", "log", "--oneline", "-10"])
    f.write(f"\n=== final git log (exit={code}) ===\n{out}\n")

print("ALL DONE - check data/git_do_result.txt")
