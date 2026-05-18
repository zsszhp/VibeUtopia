"""
使用 GitHub API 直接创建提交
"""
import subprocess, os, json, base64, urllib.request, urllib.error

os.chdir(r"D:\project\VibeUtopia")

# 1. 获取当前 HEAD commit 和 tree
def api_get(url):
    req = urllib.request.Request(url)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def api_post(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()}

def api_patch(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()}

# 2. 获取当前 commit
commit = api_get("https://api.github.com/repos/zsszhp/VibeUtopia/commits/main")
tree_sha = commit["sha"]
base_tree = commit["commit"]["tree"]["sha"]
print(f"Current HEAD: {tree_sha[:8]}")
print(f"Base tree: {base_tree[:8]}")

# 3. 获取当前 tree (recursive)
tree_data = api_get(f"https://api.github.com/repos/zsszhp/VibeUtopia/git/trees/{base_tree}?recursive=1")
existing_paths = {item["path"]: item for item in tree_data.get("tree", [])}
print(f"Existing tree items: {len(existing_paths)}")

# 4. 读取新文件内容
new_files = [
    r"src\backend\services\checkpoint_manager.py",
    r"src\backend\services\resumable_analyzer.py",
    r"src\backend\routes_resume.py",
    r"src\backend\main.py",
    r"src\backend\services\__init___test.py",
    r"src\backend\routes_blogger.py",  # 确保包含所有修改
    r"src\backend\routes_local_models.py",
    r"data\TEST_REPORT.md",
    r".monkeycode\MEMORY.md",
]

# 也检查 git status 来看看哪些文件被修改了
def run_git(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.stdout, r.stderr, r.returncode

stdout, stderr, code = run_git(["git", "status", "--porcelain"])
print(f"\nGit status:\n{stdout}")

# 获取所有已修改/新增的文件
changed_files = []
for line in stdout.strip().split("\n"):
    if line.strip():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            status, path = parts
            changed_files.append(path)
        elif len(parts) == 1:
            # 处理文件名含空格的情况
            # git status --porcelain 格式: XY PATH 或 XY "PATH WITH SPACES"
            pass

print(f"\nChanged files: {changed_files}")

# 5. 构建新的 tree
tree_entries = []
for fpath in changed_files:
    full_path = os.path.join(r"D:\project\VibeUtopia", fpath)
    if not os.path.exists(full_path):
        print(f"  SKIP (not found): {fpath}")
        continue
    if os.path.isdir(full_path):
        print(f"  SKIP (dir): {fpath}")
        continue

    with open(full_path, "rb") as fh:
        content = fh.read()

    # 创建 blob
    blob = api_post("https://api.github.com/repos/zsszhp/VibeUtopia/git/blobs", {
        "content": base64.b64encode(content).decode("utf-8"),
        "encoding": "base64",
    })

    if "sha" not in blob:
        print(f"  FAIL blob: {fpath} - {blob}")
        continue

    tree_entries.append({
        "path": fpath.replace("\\", "/"),
        "mode": "100644",
        "type": "blob",
        "sha": blob["sha"],
    })
    print(f"  OK blob: {fpath} ({len(content)} bytes)")

print(f"\nTree entries: {len(tree_entries)}")

if not tree_entries:
    print("No files to commit!")
    exit(0)

# 6. 创建新 tree
new_tree = api_post("https://api.github.com/repos/zsszhp/VibeUtopia/git/trees", {
    "base_tree": base_tree,
    "tree": tree_entries,
})

if "sha" not in new_tree:
    print(f"FAIL creating tree: {new_tree}")
    exit(1)

print(f"New tree: {new_tree['sha'][:8]}")

# 7. 创建 commit
new_commit = api_post("https://api.github.com/repos/zsszhp/VibeUtopia/git/commits", {
    "message": "feat: 断点续传机制——checkpoint_manager+resumable_analyzer+routes_resume，解决长视频API限流中断后需从头重跑的问题，类似YOLO训练断点续训",
    "tree": new_tree["sha"],
    "parents": [tree_sha],
})

if "sha" not in new_commit:
    print(f"FAIL creating commit: {new_commit}")
    exit(1)

print(f"New commit: {new_commit['sha'][:8]}")

# 8. 更新 main 分支引用
update = api_patch(f"https://api.github.com/repos/zsszhp/VibeUtopia/git/refs/heads/main", {
    "sha": new_commit["sha"],
})

if "sha" in update.get("object", {}):
    print(f"✅ GitHub updated to: {update['object']['sha'][:8]}")
else:
    print(f"Result: {update}")

# 9. 同时推送到 gitee（用 git 命令）
print("\nPushing to gitee...")
r = subprocess.run(["git", "push", "gitee", "main"], capture_output=True, text=True, timeout=60)
print(f"gitee push exit={r.returncode}")
if r.stdout: print(f"stdout: {r.stdout}")
if r.stderr: print(f"stderr: {r.stderr}")

print("\nDone!")
