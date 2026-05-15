#!/usr/bin/env python3
"""
使用真实回测案例测试 LongCat 模型的风险评估能力
测试模型：LongCat-Flash-Thinking-2601（当前可用最佳模型）
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

def test_risk_assessment(case_file: str, model_name: str, api_key: str) -> dict:
    """
    使用真实案例测试模型的风险评估能力
    
    Args:
        case_file: 案例文件路径
        model_name: 模型名称
        api_key: API Key
        
    Returns:
        测试结果字典
    """
    import requests
    
    # 读取案例
    with open(case_file, 'r', encoding='utf-8') as f:
        case_content = f.read()
    
    # 提取案例标题和风险等级
    lines = case_content.split('\n')
    title = lines[0].replace('#', '').strip() if lines[0].startswith('#') else 'Unknown'
    
    risk_level = 'Unknown'
    for line in lines:
        if '风险等级' in line and ':' in line:
            risk_level_raw = line.split(':')[1].strip()
            # 中文转英文
            if risk_level_raw == '高':
                risk_level = 'HIGH'
            elif risk_level_raw == '中':
                risk_level = 'MEDIUM'
            elif risk_level_raw == '低':
                risk_level = 'LOW'
            else:
                risk_level = risk_level_raw
            break
    
    url = "https://api.longcat.chat/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 简化的风险评估 prompt
    system_prompt = """你是一个专业的内容安全风险评估专家。请分析给定文案的风险等级。

风险等级划分：
- HIGH (76-100): 涉及政治敏感、法律合规、民族宗教、事实错误、平台禁区等红线
- MEDIUM (51-75): 涉及道德伦理、价值观倾向、情绪极化等
- LOW (0-50): 内容健康，无明显风险

请只返回 JSON 格式：
{
    "risk_level": "HIGH|MEDIUM|LOW",
    "risk_score": 数字，
    "risk_dimensions": ["维度 1", "维度 2", ...],
    "reasoning": "简短分析"
}"""
    
    user_prompt = f"""请分析以下文案的风险等级：

{case_content[:2000]}  # 限制长度避免超时"""
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        result = {
            "case_file": Path(case_file).name,
            "case_title": title,
            "expected_risk_level": risk_level,
            "model": model_name,
            "api_key_prefix": api_key[:15] + "...",
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "predicted_risk": None,
            "error": None
        }
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 尝试解析 JSON 响应
            try:
                # 清理响应文本
                json_str = response_text.strip()
                if json_str.startswith('```json'):
                    json_str = json_str.replace('```json', '').replace('```', '').strip()
                elif json_str.startswith('```'):
                    json_str = json_str.replace('```', '').strip()
                
                predicted_risk = json.loads(json_str)
                result["predicted_risk"] = predicted_risk
                
                # 处理不同字段名
                risk_level_pred = predicted_risk.get('risk_level') or predicted_risk.get('level', 'N/A')
                risk_score = predicted_risk.get('risk_score') or predicted_risk.get('score', 'N/A')
                reasoning = predicted_risk.get('reasoning') or predicted_risk.get('reason', '')
                
                # 判断是否匹配
                if risk_level_pred == risk_level:
                    result["match"] = True
                else:
                    result["match"] = False
                    
            except Exception as e:
                result["predicted_risk"] = {"raw_response": response_text}
                result["error"] = f"JSON parse error: {str(e)}"
                result["match"] = False
                
            result["usage"] = data.get("usage", {})
        else:
            result["error"] = response.text
            
        return result
        
    except Exception as e:
        return {
            "case_file": Path(case_file).name,
            "case_title": title,
            "expected_risk_level": risk_level,
            "model": model_name,
            "api_key_prefix": api_key[:15] + "...",
            "success": False,
            "error": str(e)
        }

def main():
    # 获取配置
    api_keys = os.getenv("LONGCAT_API_KEY", "").split(",")
    model = "LongCat-Flash-Thinking-2601"
    
    # 选取前 5 个案例进行测试
    case_dir = Path(__file__).parent.parent / "cases" / "paperwork"
    case_files = list(case_dir.glob("*.md"))[:5]
    
    print("=" * 80)
    print("LongCat 模型风险评估能力测试")
    print("=" * 80)
    print(f"\n测试模型：{model}")
    print(f"测试案例数：{len(case_files)}")
    print(f"API Keys: {len(api_keys)} 个")
    print("\n" + "=" * 80)
    
    # 测试每个案例
    all_results = []
    
    for case_file in case_files:
        print(f"\n[案例：{case_file.name}]")
        print("-" * 80)
        
        # 使用第一个 API Key 测试
        api_key = api_keys[0]
        result = test_risk_assessment(str(case_file), model, api_key)
        all_results.append(result)
        
        if result["success"]:
            print(f"  ✓ API 调用成功")
            if result.get("predicted_risk"):
                pred = result["predicted_risk"]
                risk_level_pred = pred.get('risk_level') or pred.get('level', 'N/A')
                risk_score = pred.get('risk_score') or pred.get('score', 'N/A')
                reasoning = pred.get('reasoning') or pred.get('reason', '')
                
                print(f"  预期风险等级：{result['expected_risk_level']}")
                print(f"  预测风险等级：{risk_level_pred}")
                print(f"  风险分数：{risk_score}")
                if "match" in result:
                    match_status = "✓ 匹配" if result["match"] else "✗ 不匹配"
                    print(f"  结果：{match_status}")
                if reasoning:
                    print(f"  分析：{reasoning[:100]}...")
        else:
            print(f"  ✗ 失败：{result.get('error', 'Unknown')[:200]}")
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    successful_tests = [r for r in all_results if r["success"]]
    matched_tests = [r for r in successful_tests if r.get("match", False)]
    
    print(f"\n总测试数：{len(all_results)}")
    print(f"API 调用成功：{len(successful_tests)}")
    print(f"风险等级匹配：{len(matched_tests)}")
    
    if successful_tests:
        accuracy = len(matched_tests) / len(successful_tests) * 100
        print(f"准确率：{accuracy:.1f}%")
        
        print("\n详细结果:")
        for result in all_results:
            status = "✓" if result.get("match", False) else "✗" if "match" in result else "?"
            pred_risk = result.get("predicted_risk")
            pred_level = pred_risk.get("risk_level", "N/A") if pred_risk else "N/A"
            print(f"  {status} {result['case_title'][:40]}: 预期={result['expected_risk_level']}, 预测={pred_level}")
    
    print("\n" + "=" * 80)
    
    return len(matched_tests) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
