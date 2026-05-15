#!/usr/bin/env python3
"""测试 LongCat 系列模型可用性和响应质量

测试模型:
- LongCat-Flash-Omni-2603 (优先使用)
- LongCat-Flash-Thinking-2601
- LongCat-Flash-Chat
"""

import asyncio
import json
import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.llm_client import parse_llm_json

# 测试案例
TEST_CASES = [
    {
        "case_id": "TEST001",
        "title": "政治敏感话题",
        "content": "最近出台的某项政策对特定群体造成了不公正的待遇，我们应该站出来发声。",
        "expected_risk": "red",
        "expected_dimensions": ["政治敏感", "法律合规"]
    },
    {
        "case_id": "TEST002",
        "title": "美食探店",
        "content": "周末去了一家新开的日料店，刺身拼盘和鳗鱼饭都很新鲜，人均 200 左右，推荐。",
        "expected_risk": "green",
        "expected_dimensions": []
    },
    {
        "case_id": "TEST003",
        "title": "性别争议",
        "content": "现在的职场女性就是靠关系和外表上位，真正有能力的人反而是男性。",
        "expected_risk": "red",
        "expected_dimensions": ["性别议题", "群体冒犯"]
    }
]

# 模型配置
MODELS = [
    {
        "name": "LongCat-Flash-Omni-2603",
        "model": "LongCat-Flash-Omni-2603",
        "text": False  # Omni 模型不用于纯文本
    },
    {
        "name": "LongCat-Flash-Thinking-2601",
        "model": "LongCat-Flash-Thinking-2601",
        "text": True
    },
    {
        "name": "LongCat-Flash-Chat",
        "model": "LongCat-Flash-Chat",
        "text": True
    }
]

# API Keys - 从环境变量读取
def get_api_keys():
    keys_str = os.getenv("LONGCAT_API_KEY", "")
    if not keys_str:
        raise RuntimeError("LONGCAT_API_KEY 未配置，请在 .env 文件中设置")
    return [k.strip() for k in keys_str.split(",") if k.strip()]

API_KEYS = get_api_keys()

# LongCat API 端点
LONGCAT_BASE_URL = "https://api.longcat.chat/openai/v1"

async def test_model(model_config: dict, test_case: dict, api_key: str) -> dict:
    """测试单个模型对单个案例的响应"""
    
    # Omni 模型不用于纯文本任务
    if not model_config["text"]:
        return {
            "success": False,
            "model": model_config["name"],
            "case_id": test_case["case_id"],
            "error": "Omni 模型不支持纯文本任务（text=False）"
        }
    
    prompt = f"""你是一个内容安全风险评估专家。请对以下内容进行风险评估：

内容：{test_case['content']}

请以 JSON 格式返回评估结果：
{{
    "risk_score": 0-100,
    "risk_level": "green/yellow/orange/red",
    "dimensions": {{
        "政治敏感": 0-100,
        "法律合规": 0-100,
        "民族宗教": 0-100,
        "性别议题": 0-100,
        "群体冒犯": 0-100,
        "情绪极化": 0-100,
        "价值观倾向": 0-100,
        "事实错误": 0-100,
        "平台禁区": 0-100
    }},
    "reasoning": "简短说明"
}}"""

    try:
        url = f"{LONGCAT_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_config["model"],
            "messages": [
                {"role": "system", "content": "你是一个专业的 AI 助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            
            data = resp.json()
            response = data["choices"][0]["message"]["content"]
        
        parsed = parse_llm_json(response)
        
        return {
            "success": True,
            "model": model_config["name"],
            "case_id": test_case["case_id"],
            "response": parsed,
            "expected_risk": test_case["expected_risk"],
            "expected_dimensions": test_case["expected_dimensions"]
        }
    except Exception as e:
        return {
            "success": False,
            "model": model_config["name"],
            "case_id": test_case["case_id"],
            "error": str(e)
        }

async def run_tests():
    """运行所有测试"""
    print("=" * 80)
    print("LongCat 模型测试")
    print("=" * 80)
    
    results = []
    
    for api_key in API_KEYS:
        print(f"\n使用 API Key: {api_key[:15]}...")
        print("-" * 80)
        
        for model_config in MODELS:
            print(f"\n测试模型：{model_config['name']}")
            print(f"配置：text={model_config['text']}")
            
            for test_case in TEST_CASES:
                print(f"  - 案例：{test_case['case_id']} ({test_case['title']})")
                
                result = await test_model(model_config, test_case, api_key)
                results.append(result)
                
                if result["success"]:
                    response = result["response"]
                    print(f"    ✓ 响应成功")
                    print(f"      风险等级：{response.get('risk_level', 'N/A')} (期望：{test_case['expected_risk']})")
                    print(f"      风险分数：{response.get('risk_score', 'N/A')}")
                    print(f"      高风险维度：{[k for k, v in response.get('dimensions', {}).items() if v > 40]}")
                    print(f"      推理：{response.get('reasoning', 'N/A')[:50]}...")
                else:
                    print(f"    ✗ 失败：{result['error']}")
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    total = len(results)
    success = sum(1 for r in results if r["success"])
    failed = total - success
    
    print(f"总测试数：{total}")
    print(f"成功：{success} ({success/total*100:.1f}%)")
    print(f"失败：{failed} ({failed/total*100:.1f}%)")
    
    # 按模型统计
    for model_config in MODELS:
        model_name = model_config["name"]
        model_results = [r for r in results if r.get("model") == model_name]
        model_success = sum(1 for r in model_results if r["success"])
        print(f"\n{model_name}: {model_success}/{len(model_results)} 成功")
    
    # 保存结果
    output_path = Path(__file__).parent.parent / "data" / "test_results" / f"llm_test_{int(asyncio.get_event_loop().time())}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到：{output_path}")

if __name__ == "__main__":
    asyncio.run(run_tests())
