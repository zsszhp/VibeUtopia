"""
通过 GitHub API 直接推送新文件到 GitHub 仓库
使用 gh CLI 获取 token
"""
import subprocess, os, json, base64, urllib.request, urllib.error

os.chdir(r"D:\project\VibeUtopia")

# 1. 获取 GitHub token
def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

# 尝试从 gh 获取 token
token = None
stdout, stderr, code = run(["gh", "auth", "token"])
if code == 0 and stdout:
    token = stdout
    print(f"✅ Got token from gh CLI")
else:
    # 尝试环境变量
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        print(f"✅ Got token from env")
    else:
        print(f"❌ No token available")
        print(f"gh auth token exit={code}, stderr={stderr[:200]}")
        exit(1)

# 2. 获取当前 HEAD
def api_call(method, path, data=None):
    url = f"https://api.github.com{path}"
    if data:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
    else:
        req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return {"error": str(e), "body": e.read().decode()}, e.code

resp, code = api_call("GET", "/repos/zsszhp/VibeUtopia/commits/main")
if "sha" not in resp:
    print(f"❌ Failed to get HEAD: {resp}")
    exit(1)

head_sha = resp["sha"]
base_tree = resp["commit"]["tree"]["sha"]
print(f"HEAD: {head_sha[:8]}, tree: {base_tree[:8]}")

# 3. 获取 git status 来确定要提交的文件
stdout, stderr, code = run(["git", "status", "--porcelain"])
changed = []
for line in stdout.strip().split("\n"):
    if not line.strip():
        continue
    # 格式: XY PATH 或 XY "PATH"
    status = line[:2]
    path = line[3:].strip().strip('"')
    if status.strip():  # 有状态码 = 有改动
        full = os.path.join(r"D:\project\VibeUtopia", path)
        if os.path.isfile(full):
            changed.append((status, path, full))

print(f"\nChanged files ({len(changed)}):")
for s, p, f in changed:
    print(f"  {s} {p}")

# 4. 创建 blobs 和 tree entries
entries = []
for status, rel_path, full_path in changed:
    with open(full_path, "rb") as fh:
        raw = fh.read()
    b64 = base64.b64encode(raw).decode("utf-8")

    resp, code = api_call("POST", "/repos/zsszhp/VibeUtopia/git/blobs", {
        "content": b64,
        "encoding": "base64",
    })
    if "sha" not in resp:
        print(f"  ❌ blob failed: {rel_path} - {resp}")
        continue

    entries.append({
        "path": rel_path.replace("\\", "/"),
        "mode": "100644",
        "type": "blob",
        "sha": resp["sha"],
    })
    print(f"  ✅ blob: {rel_path} ({len(raw)} bytes)")

if not entries:
    print("No files to commit!")
    exit(0)

# 5. 创建新 tree
resp, code = api_call("POST", "/repos/zsszhp/VibeUtopia/git/trees", {
    "base_tree": base_tree,
    "tree": entries,
})
if "sha" not in resp:
    print(f"❌ tree creation failed: {resp}")
    exit(1)
new_tree_sha = resp["sha"]
print(f"\nNew tree: {new_tree_sha[:8]}")

# 6. 创建 commit
resp, code = api_call("POST", "/repos/zsszhp/VibeUtopia/git/commits", {
    "message": "feat: 断点续传机制——checkpoint_manager+resumable_analyzer+routes_resume，解决长视频API限流中断后需从头重跑的问题，类似YOLO训练断点续训",
    "tree": new_tree_sha,
    "parents": [head_sha],
})
if "sha" not in resp:
    print(f"❌ commit creation failed: {resp}")
    exit(1)
new_commit_sha = resp["sha"]
print(f"New commit: {new_commit_sha[:8]}")

# 7. 更新 main 分支
resp, code = api_call("PATCH", "/repos/zsszhp/VibeUtopia/git/refs/heads/main", {
    "sha": new_commit_sha,
})
if code in (200, 201):
    print(f"✅ GitHub main branch updated to {new_commit_sha[:8]}")
else:
    print(f"⚠️ Update result: {resp}")

# 8. 同时尝试 gitee
print("\nPushing to gitee...")
stdout, stderr, code = run(["git", "push", "gitee", "main"], timeout=60)
print(f"gitee push: exit={code}")
if stdout: print(f"stdout: {stdout[:300]}")
if stderr: print(f"stderr: {stderr[:300]}")

print("\n✅ Done!")
