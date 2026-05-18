import subprocess, os
os.chdir(r"D:\project\VibeUtopia")
r = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True, timeout=10)
with open(r"D:\project\VibeUtopia\data\remote.txt", "w", encoding="utf-8") as f:
    f.write(r.stdout)
    f.write("\n")
    f.write(r.stderr)
print("done")
