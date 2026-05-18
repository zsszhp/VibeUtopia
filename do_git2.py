import subprocess, os

os.chdir(r"D:\project\VibeUtopia")

with open(r"D:\project\VibeUtopia\data\git_result.txt", "w", encoding="utf-8") as f:
    f.write("=== Git Log (last 15) ===\n")
    r = subprocess.run(["git", "log", "--oneline", "-15"], capture_output=True, text=True, timeout=10)
    f.write(r.stdout)

    f.write("\n=== Git Status ===\n")
    r = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=10)
    f.write(r.stdout)

    f.write("\n=== Git Remote ===\n")
    r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=10)
    f.write(r.stdout)

    f.write("\n=== Git Branch ===\n")
    r = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, timeout=10)
    f.write(r.stdout)

print("Written to data/git_result.txt")
