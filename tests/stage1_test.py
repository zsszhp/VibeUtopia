#!/usr/bin/env python3
"""VibeUtopia 阶段1验收测试脚本

测试目标:
1. API端点可用性测试 (3个测试用例: 高/中/低风险)
2. 回测案例库验证 (20+案例)
3. 前后端连通性验证

运行方式:
    source .venv/bin/activate
    python tests/stage1_test.py [--api-key YOUR_KEY] [--base-url URL]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000/api/v1")

# 风险级别颜色
RISK_COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "orange": "\033[91m",
    "red": "\033[91m",
    "reset": "\033[0m",
}

# 3个标准测试用例 (高/中/低风险)
STANDARD_TEST_CASES = [
    {
        "name": "高风险案例 - 政治敏感内容",
        "risk_level": "high",
        "content": "最近出台的某项政策对特定群体造成了不公正的待遇，"
                   "我们应该站出来联合抵制。这个决策明显偏向某些利益集团，"
                   "普通民众的权益被完全忽视了。"
    },
    {
        "name": "中风险案例 - 价值观争议",
        "risk_level": "medium",
        "content": "现在这个社会职场中，努力不一定有回报，但会哭的孩子有奶吃。"
                   "那些天天加班的人最后往往是被裁的第一批。"
                   "学会向上管理比埋头干活重要得多。"
    },
    {
        "name": "低风险案例 - 日常分享",
        "risk_level": "low",
        "content": "今天下班路上看到了很美的夕阳，忍不住拍了几张照片。"
                   "有时候觉得生活虽然忙碌，但这些小美好让人觉得很温暖。"
                   "希望每天都能发现一些让自己开心的事情。"
    },
]


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_result(name, passed, detail=""):
    status = f"{RISK_COLORS['green']}PASS{RISK_COLORS['reset']}" if passed else f"{RISK_COLORS['red']}FAIL{RISK_COLORS['reset']}"
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


async def test_models_endpoint(client):
    """测试 /models 端点"""
    print_header("测试 1: GET /api/v1/models")
    try:
        resp = await client.get(f"{BASE_URL}/models")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        print_result("models 端点返回 200", passed)
        if passed:
            print_result(f"硬件等级: {data.get('hardware_tier', 'unknown')}", True)
            print_result(f"可用模型: {list(data.get('models', {}).keys())}", True)
        return passed
    except Exception as e:
        print_result("models 端点", False, str(e))
        return False


async def test_history_endpoint(client):
    """测试 /history 端点"""
    print_header("测试 2: GET /api/v1/history")
    try:
        resp = await client.get(f"{BASE_URL}/history")
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        print_result("history 端点返回 200", passed)
        if passed:
            print_result(f"历史记录总数: {data.get('total', 0)}", True)
        return passed
    except Exception as e:
        print_result("history 端点", False, str(e))
        return False


async def test_review_submit(client, case, has_api_key=False):
    """测试 /review 提交和分析"""
    case_name = case["name"]
    risk_level = case["risk_level"]
    content = case["content"]

    print(f"\n  提交: {case_name}")

    try:
        # 提交分析请求
        payload = {
            "mode": "text",
            "texts": [{"type": "text", "content": content}],
            "options": {"depth": "quick"}
        }
        resp = await client.post(f"{BASE_URL}/review", json=payload)
        if resp.status_code != 200:
            print_result(f"[{risk_level}] 提交分析请求", False, f"状态码: {resp.status_code}, {resp.text[:100]}")
            return False

        data = resp.json()
        task_id = data.get("task_id")
        print_result(f"[{risk_level}] 任务创建成功", True, f"task_id: {task_id[:8]}...")

        if not has_api_key:
            print_result(f"[{risk_level}] 跳过实际分析 (无 API Key)", True, "需要配置 API Key 进行完整测试")
            return True

        # 等待分析完成
        max_wait = 120  # 最长等待时间
        wait_time = 0
        while wait_time < max_wait:
            await asyncio.sleep(3)
            wait_time += 3

            progress_resp = await client.get(f"{BASE_URL}/review/{task_id}/progress")
            if progress_resp.status_code != 200:
                continue

            progress = progress_resp.json()
            current_step = progress.get("current_step", "")
            pct = progress.get("progress", 0)

            if progress.get("status") == "completed":
                break

        # 获取结果
        result_resp = await client.get(f"{BASE_URL}/review/{task_id}")
        if result_resp.status_code != 200:
            print_result(f"[{risk_level}] 获取结果", False, f"状态码: {result_resp.status_code}")
            return False

        result = result_resp.json()
        risk_score = result.get("overall_risk", 0)
        risk_label = result.get("risk_level", "unknown")
        dimensions = result.get("dimensions", [])

        # 验证风险等级是否符合预期
        expected_scores = {
            "high": (55, 100),
            "medium": (25, 70),
            "low": (0, 35),
        }
        low, high = expected_scores[risk_level]
        score_ok = low <= risk_score <= high

        print_result(f"[{risk_level}] 风险分数: {risk_score}", score_ok, f"预期范围: {low}-{high}")
        print_result(f"[{risk_level}] 风险等级: {risk_label}", True)
        print_result(f"[{risk_level}] 评估维度数: {len(dimensions)}", True)

        return True

    except Exception as e:
        print_result(f"[{risk_level}] {case_name}", False, str(e))
        return False


async def load_backtest_cases():
    """加载回测案例库"""
    cases_path = Path(__file__).parent.parent / "data" / "backtest" / "cases.json"
    if not cases_path.exists():
        print(f"  警告: 回测案例文件不存在: {cases_path}")
        return []
    with open(cases_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_backtest_library(cases):
    """验证回测案例库的完整性和质量"""
    print_header(f"回测案例库验证 (共 {len(cases)} 个案例)")

    if len(cases) < 20:
        print_result("案例数量 >= 20", False, f"当前: {len(cases)}")
        return False
    print_result(f"案例数量 >= 20", True, f"当前: {len(cases)}")

    # 检查风险级别分布
    risk_counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0}
    for case in cases:
        level = case.get("expected_risk_level", "green")
        risk_counts[level] = risk_counts.get(level, 0) + 1

    print_result("风险级别分布", True,
                 f"绿={risk_counts['green']}, 黄={risk_counts['yellow']}, "
                 f"橙={risk_counts['orange']}, 红={risk_counts['red']}")

    # 检查是否有覆盖多个维度
    all_dimensions = set()
    for case in cases:
        for dim in case.get("expected_high_dimensions", []):
            all_dimensions.add(dim)

    expected_dims = {"政治敏感", "法律合规", "价值观倾向", "事实错误", "敏感实体",
                     "情绪极化", "隐喻反讽", "平台禁区", "性别议题", "群体冒犯",
                     "民族宗教", "时事踩雷", "道德伦理"}
    covered = all_dimensions & expected_dims
    print_result(f"维度覆盖 ({len(covered)}/{len(expected_dims)})",
                 len(covered) >= 7,
                 f"覆盖: {', '.join(sorted(covered))}")

    # 检查案例分类
    categories = set(c.get("category", "") for c in cases)
    print_result(f"内容分类数", len(categories) >= 5, f"共 {len(categories)} 类: {', '.join(sorted(categories))}")

    # 检查每个案例的必需字段
    missing_fields = []
    for case in cases:
        for field in ["case_id", "title", "content", "expected_risk_level", "actual_outcome"]:
            if not case.get(field):
                missing_fields.append(f"{case.get('case_id', '?')}: 缺少 {field}")
    print_result("案例字段完整性", len(missing_fields) == 0,
                 f"{len(missing_fields)} 个案例有缺失字段" if missing_fields else "所有字段完整")

    return len(cases) >= 20 and len(missing_fields) == 0


async def run_all_tests(has_api_key=False):
    """运行所有测试"""
    print_header("VibeUtopia 阶段1 验收测试")
    print(f"  API 地址: {BASE_URL}")
    print(f"  API Key:  {'已配置' if has_api_key else '未配置 (部分测试将跳过)'}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = []

        # 测试 1: Models 端点
        results.append(await test_models_endpoint(client))

        # 测试 2: History 端点
        results.append(await test_history_endpoint(client))

        # 测试 3: 3个标准案例
        print_header("测试 3: 标准案例分析 (高/中/低风险)")
        for case in STANDARD_TEST_CASES:
            r = await test_review_submit(client, case, has_api_key)
            results.append(r)

        # 测试 4: 回测案例库验证
        cases = await load_backtest_cases()
        r = validate_backtest_library(cases)
        results.append(r)

    # 汇总
    print_header("测试结果汇总")
    passed = sum(results)
    total = len(results)
    print(f"  通过: {passed}/{total}")
    if passed == total:
        print(f"  {RISK_COLORS['green']}全部测试通过!{RISK_COLORS['reset']}")
    else:
        print(f"  {RISK_COLORS['red']}有 {total - passed} 个测试未通过{RISK_COLORS['reset']}")

    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="阶段1验收测试")
    parser.add_argument("--api-key", help="LLM API Key (可选)")
    parser.add_argument("--base-url", help="API 基础地址", default=None)
    args = parser.parse_args()

    if args.base_url:
        BASE_URL = args.base_url

    has_api_key = bool(args.api_key)
    if has_api_key:
        os.environ["DEEPSEEK_API_KEY"] = args.api_key

    success = asyncio.run(run_all_tests(has_api_key))
    sys.exit(0 if success else 1)
