#!/usr/bin/env python3
"""LongCat API Key 快速测试脚本（简化版）

仅测试 1 个案例，快速验证 API Key 可用性
"""

import sys
import os
import httpx
import asyncio

# 配置
API_KEYS = [
    ("ak_2dP4Hf9Tc4sx3258dE9008Q81b638", "Key1"),
    ("ak_2mC1K99ZH6lS9Wh3dY3SE2C30YM7x", "Key2"),
]

MODELS = [
    "LongCat-Flash-Omni-2603",
    "LongCat-Flash-Thinking-2601",
    "LongCat-Flash-Chat",
]

BASE_URL = "https://api.longcat.chat/openai/v1"
TEST_PROMPT = "请用一句话介绍你自己。"


async def test_one_case(model_id: str, api_key: str, key_label: str):
    """测试单个案例"""
    try:
        url = f"{BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": "你是专业的 AI 助手。"},
                {"role": "user", "content": TEST_PROMPT},
            ],
            "temperature": 0.7,
            "max_tokens": 128,
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return True, f"成功 - {content[:50]}..."
            elif resp.status_code in (429, 402, 403):
                return False, f"配额耗尽 (HTTP {resp.status_code})"
            else:
                return False, f"失败 (HTTP {resp.status_code}) - {resp.text[:100]}"
                
    except Exception as e:
        return False, f"异常 - {str(e)}"


async def main():
    print("="*70)
    print("LongCat API Key 快速测试")
    print("="*70)
    
    results = {}
    
    for model_id in MODELS:
        print(f"\n测试模型：{model_id}")
        print("-"*70)
        results[model_id] = {}
        
        for api_key, key_label in API_KEYS:
            print(f"  测试 {key_label}...", end=" ", flush=True)
            success, message = await test_one_case(model_id, api_key, key_label)
            print(f"{'✓' if success else '✗'} {message}")
            results[model_id][key_label] = success
            
            if success:
                break  # Key1 成功就不测 Key2
    
    # 汇总
    print("\n" + "="*70)
    print("测试汇总")
    print("="*70)
    
    for model_id, key_results in results.items():
        success_keys = [k for k, v in key_results.items() if v]
        if success_keys:
            print(f"✓ {model_id}: {', '.join(success_keys)} 可用")
        else:
            print(f"✗ {model_id}: 所有 Key 不可用")


if __name__ == "__main__":
    asyncio.run(main())
