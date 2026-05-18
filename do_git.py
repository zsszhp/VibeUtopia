import subprocess
os = __import__("os")
os.chdir(r"D:\project\VibeUtopia")

cmds = {
    "log": ["git", "log", "--oneline", "-15"],
    "status": ["git", "status"],
    "remote": ["git", "remote", "-v"],
    "branch": ["git", "branch", "-a"],
}

with open(r"D:\project\VibeUtopia\data\git_result.txt", "w", encoding="utf-8") as f:
    for name, cmd in cmds.items():
        f.write(f"\n=== {name} ===\n")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            f.write(r.stdout)
            if r.stderr:
                f.write(f"\n[stderr]: {r.stderr}\n")
        except Exception as e:
            f.write(f"ERROR: {e}\n")

print("done")
