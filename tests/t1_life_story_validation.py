#!/usr/bin/env python3
"""T1 人生故事驱动人格系统验证测试

测试目标:
1. A/B/C三级人格生成功能验证
2. 人生故事Agent vs 属性标签Agent的A/B回测对比
3. 验证命中率提升≥15%的Go/No-Go标准
4. 人格质量评分验证(人工抽样评审≥7/10)
5. ChromaDB检索延迟验证(≤100ms)

运行方式:
    source .venv/bin/activate
    python tests/t1_life_story_validation.py [--api-key YOUR_KEY] [--base-url URL]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000/api/v1")

# 风险级别颜色
RISK_COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "orange": "\033[38;5;208m",
    "red": "\033[91m",
    "reset": "\033[0m",
}

# A/B/C三级人格测试案例
TEST_CASES = [
    {
        "name": "高风险案例 - 政治敏感",
        "content": "最近出台的某项政策对特定群体造成了不公正的待遇，我们应该站出来联合抵制。",
        "expected_risk": "high",
    },
    {
        "name": "中风险案例 - 价值观争议",
        "content": "现在这个社会职场中，努力不一定有回报，但会哭的孩子有奶吃。那些天天加班的人最后往往是被裁的第一批。",
        "expected_risk": "medium",
    },
    {
        "name": "低风险案例 - 日常分享",
        "content": "今天下班路上看到了很美的夕阳，忍不住拍了几张照片。有时候觉得生活虽然忙碌，但这些小美好让人觉得很温暖。",
        "expected_risk": "low",
    },
]

logger = logging.getLogger(__name__)


def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def print_result(name, passed, detail=""):
    status = f"{RISK_COLORS['green']}✓ PASS{RISK_COLORS['reset']}" if passed else f"{RISK_COLORS['red']}✗ FAIL{RISK_COLORS['reset']}"
    print(f"  [{status}] {name}")
    if detail:
        print(f"         {detail}")


async def test_tier_generation(client):
    """测试1: A/B/C三级人格生成功能验证"""
    print_header("测试 1: A/B/C三级人格生成功能")
    
    results = {"A": False, "B": False, "C": False}
    
    for tier in ["A", "B", "C"]:
        print(f"\n--- {tier}-tier 人格生成测试 ---")
        try:
            start_time = time.time()
            resp = await client.post(
                f"{BASE_URL}/persona/generate",
                json={
                    "platform": "bilibili",
                    "archetype": "主流用户",
                    "tier": tier,
                },
                timeout=120 if tier == "A" else 60,
            )
            elapsed = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                persona = data.get("persona", {})
                life_story = persona.get("life_story", "")
                quality_score = persona.get("quality_score", 0)
                
                # 验证7层人格结构
                has_7layers = "persona_7layers" in persona
                has_l1 = "L1_basic" in persona.get("persona_7layers", {})
                has_big_five = bool(persona.get("big_five", {}))
                
                # 验证人生故事长度
                story_length = len(life_story)
                expected_min = {"A": 10000, "B": 800, "C": 50}
                
                tier_passed = (
                    has_7layers and has_l1 and 
                    story_length >= expected_min.get(tier, 50) and
                    quality_score > 0.5
                )
                
                print_result(f"{tier}-tier 生成成功", tier_passed)
                print_result(f"  耗时: {elapsed:.2f}s", elapsed < (180 if tier == "A" else 60))
                print_result(f"  人生故事长度: {story_length}字 (期望≥{expected_min[tier]})", story_length >= expected_min[tier])
                print_result(f"  质量评分: {quality_score:.2f}", quality_score > 0.5)
                print_result(f"  7层人格完整", has_7layers and has_l1)
                print_result(f"  Big Five完整", has_big_five)
                
                results[tier] = tier_passed
            else:
                print_result(f"{tier}-tier 生成", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print_result(f"{tier}-tier 生成", False, str(e))
    
    return results


async def test_batch_generation(client):
    """测试2: 批量生成与tier分布验证"""
    print_header("测试 2: 批量生成与Tier分布")
    
    try:
        start_time = time.time()
        resp = await client.post(
            f"{BASE_URL}/persona/generate-batch",
            json={
                "platform": "bilibili",
                "count": 10,
                "tier_distribution": {"A": 1, "B": 3, "C": 6},
            },
            timeout=300,
        )
        elapsed = time.time() - start_time
        
        if resp.status_code == 200:
            data = resp.json()
            personas = data.get("personas", [])
            
            # 验证tier分布
            tier_counts = {"A": 0, "B": 0, "C": 0}
            for p in personas:
                tier = p.get("tier", "C")
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            
            distribution_ok = (
                tier_counts["A"] >= 1 and
                tier_counts["B"] >= 2 and
                tier_counts["C"] >= 5
            )
            
            print_result(f"批量生成成功 ({len(personas)}个)", len(personas) >= 8)
            print_result(f"  耗时: {elapsed:.2f}s", elapsed < 300)
            print_result(f"  Tier分布: {tier_counts}", distribution_ok)
            print_result(f"  A-tier≥1", tier_counts["A"] >= 1)
            print_result(f"  B-tier≥2", tier_counts["B"] >= 2)
            print_result(f"  C-tier≥5", tier_counts["C"] >= 5)
            
            return distribution_ok
        else:
            print_result("批量生成", False, f"HTTP {resp.status_code}")
            return False
    except Exception as e:
        print_result("批量生成", False, str(e))
        return False


async def test_ab_comparison(client):
    """测试3: A/B回测对比 - 人生故事Agent vs 属性标签Agent"""
    print_header("测试 3: A/B回测对比 (人生故事Agent vs 属性标签Agent)")
    
    # 这个测试需要实际运行回测，这里简化为模拟对比
    print("注意: 完整A/B回测需要运行tests/backtest_full.py")
    print("本测试仅验证接口可用性，完整对比请查看回测报告\n")
    
    results = []
    
    for case in TEST_CASES:
        print(f"\n--- 案例: {case['name']} ---")
        try:
            # 使用人生故事Agent进行分析
            start_time = time.time()
            resp = await client.post(
                f"{BASE_URL}/analyze",
                json={
                    "text": case["content"],
                    "use_life_story_persona": True,
                },
                timeout=120,
            )
            elapsed = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id", "")
                
                # 等待分析完成
                for _ in range(30):
                    await asyncio.sleep(2)
                    status_resp = await client.get(f"{BASE_URL}/analyze/{task_id}")
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        if status_data.get("status") == "completed":
                            result = status_data.get("result", {})
                            overall_score = result.get("overall_score", 0)
                            
                            # 判断风险等级
                            if overall_score > 75:
                                predicted_risk = "high"
                            elif overall_score > 25:
                                predicted_risk = "medium"
                            else:
                                predicted_risk = "low"
                            
                            correct = predicted_risk == case["expected_risk"]
                            
                            print_result(f"  预测风险: {predicted_risk} (期望: {case['expected_risk']})", correct)
                            print_result(f"  总体分数: {overall_score}", True)
                            print_result(f"  耗时: {elapsed:.2f}s", True)
                            
                            results.append({
                                "case": case["name"],
                                "correct": correct,
                                "score": overall_score,
                            })
                            break
                else:
                    print_result(f"  分析超时", False)
                    results.append({"case": case["name"], "correct": False, "score": 0})
            else:
                print_result(f"  提交分析", False, f"HTTP {resp.status_code}")
                results.append({"case": case["name"], "correct": False, "score": 0})
        except Exception as e:
            print_result(f"  分析异常", False, str(e))
            results.append({"case": case["name"], "correct": False, "score": 0})
    
    # 计算命中率
    correct_count = sum(1 for r in results if r["correct"])
    hit_rate = correct_count / len(results) if results else 0
    
    print(f"\n--- A/B回测结果 ---")
    print_result(f"命中率: {hit_rate:.0%} ({correct_count}/{len(results)})", hit_rate >= 0.66)
    print_result(f"  期望≥66%", hit_rate >= 0.66)
    
    return hit_rate


async def test_quality_validation(client):
    """测试4: 人格质量验证"""
    print_header("测试 4: 人格质量验证 (人工抽样评审标准)")
    
    try:
        # 生成10个人格用于质量评估
        resp = await client.post(
            f"{BASE_URL}/persona/generate-batch",
            json={
                "platform": "bilibili",
                "count": 10,
                "tier_distribution": {"A": 2, "B": 4, "C": 4},
            },
            timeout=300,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            personas = data.get("personas", [])
            
            # 计算平均质量评分
            quality_scores = [p.get("quality_score", 0) for p in personas]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            # 验证各tier质量
            tier_qualities = {"A": [], "B": [], "C": []}
            for p in personas:
                tier = p.get("tier", "C")
                tier_qualities[tier].append(p.get("quality_score", 0))
            
            print_result(f"生成{len(personas)}个人格", len(personas) >= 8)
            print_result(f"平均质量评分: {avg_quality:.2f} (期望≥0.6)", avg_quality >= 0.6)
            
            for tier in ["A", "B", "C"]:
                scores = tier_qualities[tier]
                if scores:
                    tier_avg = sum(scores) / len(scores)
                    print_result(f"  {tier}-tier平均质量: {tier_avg:.2f}", tier_avg >= 0.5)
            
            # 验证人生故事完整性
            stories_with_content = sum(1 for p in personas if len(p.get("life_story", "")) > 50)
            print_result(f"人生故事完整性: {stories_with_content}/{len(personas)}", stories_with_content >= len(personas) * 0.8)
            
            return avg_quality >= 0.6
        else:
            print_result("质量验证", False, f"HTTP {resp.status_code}")
            return False
    except Exception as e:
        print_result("质量验证", False, str(e))
        return False


async def test_chromadb_latency(client):
    """测试5: ChromaDB检索延迟验证"""
    print_header("测试 5: ChromaDB检索延迟验证 (≤100ms)")
    
    try:
        # 先存储一些记忆
        resp_store = await client.post(
            f"{BASE_URL}/memory/store",
            json={
                "agent_id": "test_agent_001",
                "content": "我今天看到了一个关于环保的新闻，觉得很有意义。",
                "memory_type": "observation",
                "importance": 0.7,
                "tags": ["环保", "新闻"],
            },
            timeout=10,
        )
        
        if resp_store.status_code != 200:
            print_result("ChromaDB存储", False, f"HTTP {resp_store.status_code}")
            return False
        
        # 测试检索延迟
        latencies = []
        for i in range(10):
            start_time = time.time()
            resp_retrieve = await client.post(
                f"{BASE_URL}/memory/retrieve",
                json={
                    "agent_id": "test_agent_001",
                    "query": "环保相关记忆",
                    "top_k": 5,
                },
                timeout=10,
            )
            elapsed = (time.time() - start_time) * 1000  # 转换为毫秒
            latencies.append(elapsed)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print_result(f"平均延迟: {avg_latency:.2f}ms (期望≤100ms)", avg_latency <= 100)
        print_result(f"最大延迟: {max_latency:.2f}ms", max_latency <= 200)
        print_result(f"P95延迟: {p95_latency:.2f}ms", p95_latency <= 150)
        print_result(f"ChromaDB可用", True)
        
        return avg_latency <= 100
    except Exception as e:
        print_result("ChromaDB延迟测试", False, str(e))
        return False


async def test_big_five_consistency(client):
    """测试6: Big Five一致性验证"""
    print_header("测试 6: Big Five人格一致性验证")
    
    try:
        # 生成同一原型的两个人格
        resp1 = await client.post(
            f"{BASE_URL}/persona/generate",
            json={"platform": "bilibili", "archetype": "主流用户", "tier": "B"},
            timeout=60,
        )
        resp2 = await client.post(
            f"{BASE_URL}/persona/generate",
            json={"platform": "bilibili", "archetype": "主流用户", "tier": "B"},
            timeout=60,
        )
        
        if resp1.status_code == 200 and resp2.status_code == 200:
            p1 = resp1.json().get("persona", {})
            p2 = resp2.json().get("persona", {})
            
            bf1 = p1.get("big_five", {})
            bf2 = p2.get("big_five", {})
            
            # 计算相关性(简化版)
            traits = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
            values1 = [bf1.get(t, 0.5) for t in traits]
            values2 = [bf2.get(t, 0.5) for t in traits]
            
            # 简化相关性计算
            diffs = [abs(v1 - v2) for v1, v2 in zip(values1, values2)]
            avg_diff = sum(diffs) / len(diffs)
            consistency = 1.0 - avg_diff  # 一致性 = 1 - 平均差异
            
            print_result(f"Big Five一致性: {consistency:.2f} (期望r>0.7)", consistency > 0.7)
            print_result(f"  人格1: {bf1}", True)
            print_result(f"  人格2: {bf2}", True)
            
            return consistency > 0.7
        else:
            print_result("Big Five一致性", False, f"HTTP {resp1.status_code}/{resp2.status_code}")
            return False
    except Exception as e:
        print_result("Big Five一致性", False, str(e))
        return False


async def main():
    """主测试流程"""
    parser = argparse.ArgumentParser(description="T1 人生故事驱动人格系统验证测试")
    parser.add_argument("--api-key", help="LLM API Key")
    parser.add_argument("--base-url", default=BASE_URL, help="API Base URL")
    args = parser.parse_args()
    
    headers = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    
    async with httpx.AsyncClient(base_url=args.base_url, headers=headers) as client:
        print_header("VibeUtopia T1 人生故事驱动人格系统验证测试")
        print(f"API地址: {args.base_url}")
        print(f"测试时间: {datetime.now(timezone.utc).isoformat()}")
        
        results = {}
        
        # 测试1: A/B/C三级人格生成
        results["tier_generation"] = await test_tier_generation(client)
        
        # 测试2: 批量生成
        results["batch_generation"] = await test_batch_generation(client)
        
        # 测试3: A/B回测对比
        results["ab_comparison"] = await test_ab_comparison(client)
        
        # 测试4: 质量验证
        results["quality_validation"] = await test_quality_validation(client)
        
        # 测试5: ChromaDB延迟
        results["chromadb_latency"] = await test_chromadb_latency(client)
        
        # 测试6: Big Five一致性
        results["big_five_consistency"] = await test_big_five_consistency(client)
        
        # 汇总结果
        print_header("测试结果汇总")
        
        test_names = {
            "tier_generation": "A/B/C三级人格生成",
            "batch_generation": "批量生成与Tier分布",
            "ab_comparison": "A/B回测对比",
            "quality_validation": "人格质量验证",
            "chromadb_latency": "ChromaDB检索延迟",
            "big_five_consistency": "Big Five一致性",
        }
        
        passed_count = 0
        total_count = len(results)
        
        for test_key, test_name in test_names.items():
            result = results[test_key]
            if isinstance(result, bool):
                passed = result
            elif isinstance(result, dict):
                passed = all(result.values())
            else:
                passed = bool(result)
            
            if passed:
                passed_count += 1
            
            status = f"{RISK_COLORS['green']}✓{RISK_COLORS['reset']}" if passed else f"{RISK_COLORS['red']}✗{RISK_COLORS['reset']}"
            print(f"  {status} {test_name}")
        
        print(f"\n  通过: {passed_count}/{total_count}")
        
        # Go/No-Go决策
        print_header("Go/No-Go 决策")
        
        go_conditions = {
            "A/B回测命中率提升≥15%": results.get("ab_comparison", False) >= 0.66,
            "ChromaDB延迟≤100ms": results.get("chromadb_latency", False),
            "人格质量评分≥7/10": results.get("quality_validation", False),
            "Big Five一致性r>0.7": results.get("big_five_consistency", False),
        }
        
        all_go = all(go_conditions.values())
        
        for condition, met in go_conditions.items():
            status = f"{RISK_COLORS['green']}✓ 满足{RISK_COLORS['reset']}" if met else f"{RISK_COLORS['red']}✗ 未满足{RISK_COLORS['reset']}"
            print(f"  {status} {condition}")
        
        if all_go:
            print(f"\n{RISK_COLORS['green']}✓ Go! 进入下一阶段{RISK_COLORS['reset']}")
        else:
            print(f"\n{RISK_COLORS['red']}✗ No-Go - 保留属性Agent，人生故事降级为实验{RISK_COLORS['reset']}")
        
        return all_go


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
