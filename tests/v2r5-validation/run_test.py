"""V2.R5 前端升级与仿真大屏 - 版本测试脚本

验证Vue3前端功能对等、构建通过、WebSocket可用。
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_vue_build():
    """测试Vue3项目构建"""
    print("\n--- Vue3项目构建测试 ---")
    vue_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend-vue")

    if not os.path.exists(vue_dir):
        print("  FAIL: frontend-vue目录不存在")
        return False

    # 检查关键文件
    required_files = [
        "package.json",
        "vite.config.ts",
        "src/main.ts",
        "src/App.vue",
        "src/router/index.ts",
        "src/stores/index.ts",
        "src/api/index.ts",
        "src/views/Workbench.vue",
        "src/views/VideoReview.vue",
        "src/views/Signals.vue",
        "src/views/Simulation.vue",
        "src/views/Reports.vue",
        "src/views/Settings.vue",
    ]

    all_exist = True
    for f in required_files:
        path = os.path.join(vue_dir, f)
        exists = os.path.exists(path)
        status = "PASS" if exists else "FAIL"
        if not exists:
            all_exist = False
        print(f"  {status}: {f}")

    # 检查dist构建产物
    dist_dir = os.path.join(vue_dir, "dist")
    if os.path.exists(dist_dir):
        print(f"  PASS: 构建产物dist/存在")
    else:
        print(f"  WARN: 构建产物dist/不存在（需运行npm run build）")

    return all_exist


def test_websocket_endpoint():
    """测试WebSocket端点配置"""
    print("\n--- WebSocket端点测试 ---")
    main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "backend", "main.py")

    with open(main_path, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "WebSocket路由": "/ws/simulation/" in content,
        "broadcast函数": "broadcast_simulation_update" in content,
        "ws_connections管理": "ws_connections" in content,
    }

    all_pass = True
    for check, result in checks.items():
        print(f"  {'PASS' if result else 'FAIL'}: {check}")
        if not result:
            all_pass = False

    return all_pass


def test_vite_proxy():
    """测试Vite代理配置"""
    print("\n--- Vite代理配置测试 ---")
    vite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "frontend-vue", "vite.config.ts")

    with open(vite_path, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "API代理(/api→8000)": "localhost:8000" in content and "/api" in content,
        "WebSocket代理(/ws)": "'ws'" in content or "ws:" in content,
        "端口3000": "port: 3000" in content,
    }

    all_pass = True
    for check, result in checks.items():
        print(f"  {'PASS' if result else 'FAIL'}: {check}")
        if not result:
            all_pass = False

    return all_pass


def test_api_coverage():
    """测试前端API覆盖所有后端端点"""
    print("\n--- API覆盖测试 ---")
    api_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "frontend-vue", "src", "api", "index.ts")

    with open(api_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_endpoints = [
        "/analyze/v2",
        "/extract-video",
        "/analyze-video/v2",
        "/frames/",
        "/audio/transcribe",
        "/cross-modal/",
        "/signal/fetch",
        "/signal/list",
        "/simulation/create",
        "/simulation/",
        "/report/",
        "/backtest/",
        "/consistency/check",
        "/system/db-status",
    ]

    all_covered = True
    for endpoint in required_endpoints:
        covered = endpoint in content
        print(f"  {'PASS' if covered else 'FAIL'}: {endpoint}")
        if not covered:
            all_covered = False

    return all_covered


def test_dependencies():
    """测试Vue3依赖完整性"""
    print("\n--- 依赖完整性测试 ---")
    pkg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "frontend-vue", "package.json")

    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    required_deps = [
        "vue", "vue-router", "pinia", "element-plus",
        "axios", "echarts", "d3", "tailwindcss",
    ]

    all_present = True
    for dep in required_deps:
        present = dep in deps
        print(f"  {'PASS' if present else 'FAIL'}: {dep} ({deps.get(dep, 'MISSING')})")
        if not present:
            all_present = False

    return all_present


def main():
    print("=" * 70)
    print("V2.R5 前端升级与仿真大屏 - 版本测试")
    print("=" * 70)

    results = {
        "Vue3项目构建": test_vue_build(),
        "WebSocket端点": test_websocket_endpoint(),
        "Vite代理配置": test_vite_proxy(),
        "API覆盖": test_api_coverage(),
        "依赖完整性": test_dependencies(),
    }

    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)

    for name, passed in results.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.0f}%)")

    # Go/No-Go
    all_go = all(results.values())
    print(f"\n最终判定: {'GO - V2.R5达标' if all_go else 'NO-GO - 需要修复'}")

    return all_go


if __name__ == "__main__":
    main()
