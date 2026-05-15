#!/usr/bin/env python3
"""LongCat API Key 可用性测试脚本

测试三个模型：
1. LongCat-Flash-Omni-2603 (优先使用)
2. LongCat-Flash-Thinking-2601
3. LongCat-Flash-Chat

测试两个 API Key 的可用性
"""

import sys
import os
import asyncio
import httpx

sys.path.insert(0, '/workspace')

# 设置环境变量
os.environ['LONGCAT_API_KEY'] = 'ak_2dP4Hf9Tc4sx3258dE9008Q81b638,ak_2mC1K99ZH6lS9Wh3dY3SE2C30YM7x'
os.environ['MODEL_CONFIG_PATH'] = '/workspace/config/model_config.yaml'

from backend.services.llm_client import call_llm, registry, router

TEST_PROMPT = "请用一句话介绍你自己。"
TEST_SYSTEM = "你是一个专业的 AI 助手。"

# 测试案例列表
TEST_CASES = [
    {"id": 1, "type": "simple_qa", "prompt": "太阳系有多少颗行星？", "expect": "直接回答"},
    {"id": 2, "type": "reasoning", "prompt": "如果 A 比 B 高，B 比 C 高，那么 A 和 C 谁高？为什么？", "expect": "逻辑推理"},
    {"id": 3, "type": "creative", "prompt": "请用 50 字描述春天的景象。", "expect": "创意写作"},
    {"id": 4, "type": "code", "prompt": "用 Python 写一个计算阶乘的函数。", "expect": "代码生成"},
    {"id": 5, "type": "analysis", "prompt": "分析这句话的深层含义：'人生就像一盒巧克力，你永远不知道下一颗是什么味道。'", "expect": "文本分析"},
]


async def test_model(model_id: str, api_key: str, key_label: str):
    """测试指定模型和 API Key"""
    print(f"\n{'='*80}")
    print(f"测试模型：{model_id} | API Key: {key_label}")
    print(f"{'='*80}")
    
    base_url = "https://api.longcat.chat/openai/v1"
    
    success_count = 0
    fail_count = 0
    
    for case in TEST_CASES:
        try:
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": TEST_SYSTEM},
                    {"role": "user", "content": case["prompt"]},
                ],
                "temperature": 0.7,
                "max_tokens": 512,
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    print(f"✓ 案例{case['id']} ({case['type']}): 成功 | 响应长度：{len(content)} 字符")
                    success_count += 1
                elif resp.status_code in (429, 402, 403):
                    print(f"✗ 案例{case['id']} ({case['type']}): 配额耗尽 (HTTP {resp.status_code})")
                    fail_count += 1
                    return success_count, fail_count, "quota_exhausted"
                else:
                    print(f"✗ 案例{case['id']} ({case['type']}): 失败 (HTTP {resp.status_code}) - {resp.text[:100]}")
                    fail_count += 1
                    
        except Exception as e:
            print(f"✗ 案例{case['id']} ({case['type']}): 异常 - {str(e)}")
            fail_count += 1
    
    status = "quota_exhausted" if fail_count > 0 and success_count == 0 else "success"
    return success_count, fail_count, status


async def main():
    print("\n" + "="*80)
    print("LongCat API Key 可用性测试")
    print("="*80)
    
    # 加载配置
    print("\n[步骤 1] 加载模型配置...")
    print(f"配置文件：/workspace/config/model_config.yaml")
    print(f"API Keys: ak_2dP4Hf9Tc4sx3258dE9008Q81b638, ak_2mC1K99ZH6lS9Wh3dY3SE2C30YM7x")
    
    # 测试模型列表
    models_to_test = [
        "LongCat-Flash-Omni-2603",
        "LongCat-Flash-Thinking-2601",
        "LongCat-Flash-Chat",
    ]
    
    api_keys = [
        ("ak_2dP4Hf9Tc4sx3258dE9008Q81b638", "Key1"),
        ("ak_2mC1K99ZH6lS9Wh3dY3SE2C30YM7x", "Key2"),
    ]
    
    results = {}
    
    for model_id in models_to_test:
        print(f"\n{'#'*80}")
        print(f"# 测试模型：{model_id}")
        print(f"{'#'*80}")
        
        results[model_id] = {}
        
        for api_key, key_label in api_keys:
            success, fail, status = await test_model(model_id, api_key, key_label)
            results[model_id][key_label] = {
                "success": success,
                "fail": fail,
                "status": status,
            }
            
            if status == "quota_exhausted":
                print(f"→ {key_label} 配额耗尽，跳过后续测试")
                break
    
    # 汇总报告
    print("\n" + "="*80)
    print("测试汇总报告")
    print("="*80)
    
    for model_id, key_results in results.items():
        print(f"\n{model_id}:")
        for key_label, result in key_results.items():
            status_icon = "✓" if result["status"] == "success" else "✗"
            print(f"  {status_icon} {key_label}: 成功 {result['success']}/{len(TEST_CASES)} 案例")
    
    # 推荐配置
    print("\n" + "="*80)
    print("推荐配置建议")
    print("="*80)
    
    # 找出最优模型
    best_model = None
    best_key = None
    
    for model_id in ["LongCat-Flash-Omni-2603", "LongCat-Flash-Thinking-2601", "LongCat-Flash-Chat"]:
        for key_label, result in results.get(model_id, {}).items():
            if result["status"] == "success":
                best_model = model_id
                best_key = key_label
                break
        if best_model:
            break
    
    if best_model:
        print(f"\n✓ 推荐使用：{best_model} + {best_key}")
        print(f"  该组合在测试中表现稳定，建议作为主力模型")
    else:
        print("\n✗ 所有模型/Key 组合均失败，请检查：")
        print("  1. API Key 是否有效")
        print("  2. 网络连接是否正常")
        print("  3. 模型服务是否可用")
    
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
