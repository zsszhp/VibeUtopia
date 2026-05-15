#!/usr/bin/env python3
"""
测试 LongCat 系列模型的可用性
测试模型：
1. LongCat-Flash-Omni-2603 (优先)
2. LongCat-Flash-Thinking-2601 (备选)
3. LongCat-Flash-Chat (备选)
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

def test_model(model_name: str, api_key: str, test_prompt: str = "你好，请用一句话介绍你自己。") -> dict:
    """
    测试单个模型的可用性
    
    Args:
        model_name: 模型名称
        api_key: API Key
        test_prompt: 测试提示词
        
    Returns:
        测试结果字典
    """
    import requests
    
    url = "https://api.longcat.chat/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": test_prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        result = {
            "model": model_name,
            "api_key_prefix": api_key[:10] + "...",
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response": None,
            "error": None
        }
        
        if response.status_code == 200:
            data = response.json()
            result["response"] = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
            result["usage"] = data.get("usage", {})
        else:
            result["error"] = response.text
            
        return result
        
    except Exception as e:
        return {
            "model": model_name,
            "api_key_prefix": api_key[:10] + "...",
            "success": False,
            "error": str(e)
        }

def main():
    # 获取配置
    api_keys = os.getenv("LONGCAT_API_KEY", "").split(",")
    models_to_test = [
        "LongCat-Flash-Omni-2603",  # 优先
        "LongCat-Flash-Thinking-2601",  # 备选
        "LongCat-Flash-Chat"  # 备选
    ]
    
    print("=" * 80)
    print("LongCat 模型可用性测试")
    print("=" * 80)
    print(f"\n配置的 API Keys: {len(api_keys)} 个")
    for i, key in enumerate(api_keys, 1):
        print(f"  {i}. {key[:15]}...")
    print(f"\n待测试模型：{len(models_to_test)} 个")
    for i, model in enumerate(models_to_test, 1):
        print(f"  {i}. {model}")
    print("\n" + "=" * 80)
    
    # 测试每个模型和 API Key 的组合
    all_results = []
    
    for model in models_to_test:
        print(f"\n[测试模型：{model}]")
        print("-" * 80)
        
        for api_key in api_keys:
            print(f"\n  使用 API Key: {api_key[:15]}...")
            
            # 简单的测试问题
            test_prompt = "你好，请用一句话介绍你自己。"
            
            result = test_model(model, api_key, test_prompt)
            all_results.append(result)
            
            if result["success"]:
                print(f"    ✓ 成功!")
                print(f"    响应：{result['response'][:100]}...")
                if "usage" in result:
                    print(f"    消耗：{result['usage']}")
            else:
                print(f"    ✗ 失败!")
                print(f"    状态码：{result.get('status_code', 'N/A')}")
                print(f"    错误：{result.get('error', 'Unknown')[:200]}")
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    successful_tests = [r for r in all_results if r["success"]]
    failed_tests = [r for r in all_results if not r["success"]]
    
    print(f"\n总测试次数：{len(all_results)}")
    print(f"成功：{len(successful_tests)}")
    print(f"失败：{len(failed_tests)}")
    
    if successful_tests:
        print("\n✓ 可用的模型配置：")
        for result in successful_tests:
            print(f"  - 模型：{result['model']}, API Key: {result['api_key_prefix']}")
    
    if failed_tests:
        print("\n✗ 不可用的配置：")
        for result in failed_tests:
            print(f"  - 模型：{result['model']}, API Key: {result['api_key_prefix']}")
            print(f"    错误：{str(result.get('error', 'Unknown'))[:100]}")
    
    # 推荐配置
    print("\n" + "=" * 80)
    print("推荐配置")
    print("=" * 80)
    
    # 优先推荐 Omni 模型
    omni_success = [r for r in successful_tests if "Omni" in r["model"]]
    thinking_success = [r for r in successful_tests if "Thinking" in r["model"]]
    chat_success = [r for r in successful_tests if "Chat" in r["model"]]
    
    if omni_success:
        print(f"\n✓ 优先使用：LongCat-Flash-Omni-2603")
        print(f"  可用 API Key: {omni_success[0]['api_key_prefix']}")
    elif thinking_success:
        print(f"\n✓ 备选使用：LongCat-Flash-Thinking-2601")
        print(f"  可用 API Key: {thinking_success[0]['api_key_prefix']}")
    elif chat_success:
        print(f"\n✓ 备选使用：LongCat-Flash-Chat")
        print(f"  可用 API Key: {chat_success[0]['api_key_prefix']}")
    else:
        print("\n✗ 所有模型测试均失败，请检查 API Key 或网络连接")
    
    print("\n" + "=" * 80)
    
    return len(successful_tests) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
