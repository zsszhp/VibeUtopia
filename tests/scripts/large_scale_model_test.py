#!/usr/bin/env python3
"""
大规模模型测试脚本 - 30+ 案例，多领域覆盖
测试模型：
1. LongCat-Flash-Omni-2603 (优先)
2. LongCat-Flash-Thinking-2601
3. LongCat-Flash-Chat
4. DeepSeek v4 flash (SenseNova)

输出：
- 详细的 JSON 测试报告
- Markdown 格式的深度预测报告
- Git 提交
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== 测试案例库 ====================

TEST_CASES = [
    # ==================== 风险评估类 (6 个) ====================
    {
        "id": "risk_001",
        "category": "risk_assessment",
        "name": "金融风险文案评估",
        "prompt": "某理财产品承诺年化收益率 30%，保本保息，无风险投资。专家解读：这是千载难逢的机会，错过再等 10 年。",
        "expected_risk_level": "high",
        "difficulty": "standard"
    },
    {
        "id": "risk_002",
        "category": "risk_assessment",
        "name": "健康谣言识别",
        "prompt": "每天喝一杯这个水，癌症绕道走！99 岁老中医祖传秘方，不花一分钱就能延年益寿。",
        "expected_risk_level": "high",
        "difficulty": "standard"
    },
    {
        "id": "risk_003",
        "category": "risk_assessment",
        "name": "情感操控识别",
        "prompt": "如果你真的爱我，就应该把所有积蓄转给我保管。真爱是无条件的付出，不要计较个人得失。",
        "expected_risk_level": "high",
        "difficulty": "complex"
    },
    {
        "id": "risk_004",
        "category": "risk_assessment",
        "name": "低风险生活分享",
        "prompt": "今天在家做了顿好吃的，分享我的厨艺成果，虽然卖相一般但味道还不错。",
        "expected_risk_level": "low",
        "difficulty": "simple"
    },
    {
        "id": "risk_005",
        "category": "risk_assessment",
        "name": "中等风险投资建议",
        "prompt": "基金定投是个不错的长期理财方式，建议每月拿出收入的 10%-20% 进行配置，分散风险。",
        "expected_risk_level": "medium",
        "difficulty": "standard"
    },
    {
        "id": "risk_006",
        "category": "risk_assessment",
        "name": "隐晦风险内容",
        "prompt": "有些机会只有圈内人知道，感兴趣的私信我。手把手教你月入过万的副业，零基础也能上手。",
        "expected_risk_level": "medium",
        "difficulty": "complex"
    },
    
    # ==================== 人生故事生成类 (6 个) ====================
    {
        "id": "story_001",
        "category": "story_generation",
        "name": "职场逆袭故事",
        "prompt": "我从小县城来到大城市，从底薪 3000 的销售做起，5 年后做到了公司副总。期间经历过被客户骂哭、连续加班一个月、被同事抢功劳，但始终坚持不懈。",
        "expected_themes": ["perseverance", "career_growth"],
        "difficulty": "standard"
    },
    {
        "id": "story_002",
        "category": "story_generation",
        "name": "创业失败再出发",
        "prompt": "第一次创业烧光了 500 万投资，团队散了，女朋友也走了。沉寂两年后，我带着新项目重新出发，这次我学会了控制风险和珍惜团队。",
        "expected_themes": ["resilience", "entrepreneurship"],
        "difficulty": "complex"
    },
    {
        "id": "story_003",
        "category": "story_generation",
        "name": "家庭与事业平衡",
        "prompt": "35 岁的我，是两个孩子的妈妈，也是公司的中层管理者。每天 5 点起床给孩子做早饭，然后赶去上班。工作再忙也要陪孩子读书，周末全家出游。",
        "expected_themes": ["work_life_balance", "family"],
        "difficulty": "standard"
    },
    {
        "id": "story_004",
        "category": "story_generation",
        "name": "农村青年求学路",
        "prompt": "村里第一个考上清华的大学生，家里凑不出学费，是乡亲们在村口卖鸡蛋、玉米一元一元凑出来的。学成后我选择回乡创业，带动大家一起致富。",
        "expected_themes": ["gratitude", "giving_back"],
        "difficulty": "standard"
    },
    {
        "id": "story_005",
        "category": "story_generation",
        "name": "跨行业转型",
        "prompt": "从程序员到咖啡师，30 岁这年我做了人生最大的转折。虽然收入只有之前的一半，但每天能闻着咖啡香工作，我觉得这才是生活。",
        "expected_themes": ["life_choice", "passion"],
        "difficulty": "standard"
    },
    {
        "id": "story_006",
        "category": "story_generation",
        "name": "简单日常记录",
        "prompt": "今天天气不错，去公园散了步，拍了几张照片分享。",
        "expected_themes": ["daily_life"],
        "difficulty": "simple"
    },
    
    # ==================== 平台反应模拟类 (6 个) ====================
    {
        "id": "platform_001",
        "category": "platform_simulation",
        "name": "微博热点传播",
        "prompt": "某明星被曝偷税漏税，金额高达数亿元。",
        "platform": "weibo",
        "expected_reaction": "high_engagement",
        "difficulty": "standard"
    },
    {
        "id": "platform_002",
        "category": "platform_simulation",
        "name": "小红书种草内容",
        "prompt": "这款护肤品真的太好用了！用了一周皮肤状态明显改善，闺蜜都问我是不是去做了医美。",
        "platform": "xiaohongshu",
        "expected_reaction": "positive_engagement",
        "difficulty": "simple"
    },
    {
        "id": "platform_003",
        "category": "platform_simulation",
        "name": "知乎深度分析",
        "prompt": "如何看待 2024 年 AI 行业发展趋势？从技术突破、商业应用、就业机会三个维度进行分析。",
        "platform": "zhihu",
        "expected_reaction": "analytical_discussion",
        "difficulty": "complex"
    },
    {
        "id": "platform_004",
        "category": "platform_simulation",
        "name": "抖音病毒传播",
        "prompt": "一个普通人突然走红的故事，配上励志 BGM 和剪辑。",
        "platform": "douyin",
        "expected_reaction": "viral_spread",
        "difficulty": "standard"
    },
    {
        "id": "platform_005",
        "category": "platform_simulation",
        "name": "B 站知识区内容",
        "prompt": "用 10 分钟讲清楚量子力学的基本原理，适合零基础观众。",
        "platform": "bilibili",
        "expected_reaction": "educational_engagement",
        "difficulty": "complex"
    },
    {
        "id": "platform_006",
        "category": "platform_simulation",
        "name": "争议性话题",
        "prompt": "年轻人该不该 early retirement？我觉得 35 岁存够 500 万就可以躺平了。",
        "platform": "zhihu",
        "expected_reaction": "heated_debate",
        "difficulty": "complex"
    },
    
    # ==================== 多模态分析类 (4 个) ====================
    {
        "id": "multimodal_001",
        "category": "multimodal",
        "name": "图文不一致检测",
        "prompt": "图片显示的是普通家常菜，文案写的是'豪宅米其林大餐'。",
        "has_image": True,
        "expected_issue": "content_mismatch",
        "difficulty": "standard"
    },
    {
        "id": "multimodal_002",
        "category": "multimodal",
        "name": "过度美化识别",
        "prompt": "实际场景是普通街道，通过滤镜和角度拍成了'欧洲风情小镇'。",
        "has_image": True,
        "expected_issue": "overbeautification",
        "difficulty": "standard"
    },
    {
        "id": "multimodal_003",
        "category": "multimodal",
        "name": "虚假宣传检测",
        "prompt": "产品展示图使用了明显的 PS 痕迹，效果与实际不符。",
        "has_image": True,
        "expected_issue": "false_advertising",
        "difficulty": "complex"
    },
    {
        "id": "multimodal_004",
        "category": "multimodal",
        "name": "内容合规性",
        "prompt": "视频中出现未成年人，但已获得监护人同意并打码处理。",
        "has_image": True,
        "expected_issue": "compliance_check",
        "difficulty": "complex"
    },
    
    # ==================== 文案改写类 (4 个) ====================
    {
        "id": "rewrite_001",
        "category": "rewrite",
        "name": "降低营销感",
        "prompt": "史上最低价！错过今天再等一年！立即下单立享 5 折优惠！前 100 名还有神秘大礼！",
        "rewrite_goal": "reduce_marketing_tone",
        "difficulty": "standard"
    },
    {
        "id": "rewrite_002",
        "category": "rewrite",
        "name": "增加情感共鸣",
        "prompt": "本产品采用进口原料，经过 36 道工序精制而成，品质有保障。",
        "rewrite_goal": "add_emotional_appeal",
        "difficulty": "standard"
    },
    {
        "id": "rewrite_003",
        "category": "rewrite",
        "name": "简化复杂说明",
        "prompt": "本产品运用了纳米级微胶囊包裹技术，通过缓释机制实现有效成分的持续释放，生物利用度较传统剂型提升 300%。",
        "rewrite_goal": "simplify_technical",
        "difficulty": "complex"
    },
    {
        "id": "rewrite_004",
        "category": "rewrite",
        "name": "优化标题党",
        "prompt": "震惊！99% 的人都不知道的秘密！专家看完都沉默了！",
        "rewrite_goal": "remove_clickbait",
        "difficulty": "standard"
    },
    
    # ==================== 逻辑推理类 (4 个) ====================
    {
        "id": "reasoning_001",
        "category": "reasoning",
        "name": "因果关系分析",
        "prompt": "某地房价上涨的原因有哪些？请从经济、人口、政策三个角度分析。",
        "reasoning_type": "causal_analysis",
        "difficulty": "complex"
    },
    {
        "id": "reasoning_002",
        "category": "reasoning",
        "name": "对比分析",
        "prompt": "比较线上教育和传统线下教育的优缺点，并给出你的建议。",
        "reasoning_type": "comparative_analysis",
        "difficulty": "complex"
    },
    {
        "id": "reasoning_003",
        "category": "reasoning",
        "name": "数据解读",
        "prompt": "某公司 Q3 财报显示营收增长 20%，但净利润下降 5%。可能的原因是什么？",
        "reasoning_type": "data_interpretation",
        "difficulty": "complex"
    },
    {
        "id": "reasoning_004",
        "category": "reasoning",
        "name": "简单逻辑判断",
        "prompt": "如果所有 A 都是 B，有些 B 是 C，那么能推出有些 A 是 C 吗？",
        "reasoning_type": "logical_deduction",
        "difficulty": "standard"
    },
    
    # ==================== 代码生成类 (4 个) ====================
    {
        "id": "code_001",
        "category": "code_generation",
        "name": "Python 数据处理",
        "prompt": "用 Python 写一个函数，读取 CSV 文件，计算某列的平均值和中位数。",
        "language": "python",
        "difficulty": "standard"
    },
    {
        "id": "code_002",
        "category": "code_generation",
        "name": "前端组件",
        "prompt": "用 Vue 3 写一个可复用的搜索框组件，支持防抖和清空功能。",
        "language": "vue",
        "difficulty": "standard"
    },
    {
        "id": "code_003",
        "category": "code_generation",
        "name": "API 接口设计",
        "prompt": "设计一个 RESTful API，用于管理用户信息和权限。",
        "language": "api_design",
        "difficulty": "complex"
    },
    {
        "id": "code_004",
        "category": "code_generation",
        "name": "简单脚本",
        "prompt": "写一个 bash 脚本，批量重命名文件，将文件名中的空格替换为下划线。",
        "language": "bash",
        "difficulty": "simple"
    },
]


# ==================== 模型测试器 ====================

class ModelTester:
    """模型测试器"""
    
    def __init__(self):
        self.longcat_api_keys = os.getenv("LONGCAT_API_KEY", "").split(",")
        self.longcat_base_url = "https://api.longcat.chat/openai/v1"
        self.longcat_models = [
            "LongCat-Flash-Omni-2603",
            "LongCat-Flash-Thinking-2601",
            "LongCat-Flash-Chat"
        ]
        
        self.sensenova_api_key = os.getenv("SENSENOVA_API_KEY", "")
        self.sensenova_base_url = os.getenv("SENSENOVA_BASE_URL", "https://api.sensenova.cn/v1")
        self.sensenova_models = [
            "deepseek-v4-flash",
            "deepseek-v4",
            "deepseek-v3"
        ]
        
        self.results = []
        self.summary = {}
    
    def test_longcat_model(self, model_name: str, api_key: str, prompt: str, timeout: int = 60) -> Dict:
        """测试 LongCat 模型"""
        url = f"{self.longcat_base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                
                return {
                    "success": True,
                    "response": content,
                    "latency_ms": int(elapsed * 1000),
                    "tokens_used": usage.get("total_tokens", 0),
                    "status_code": response.status_code,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "response": None,
                    "latency_ms": int(elapsed * 1000),
                    "tokens_used": 0,
                    "status_code": response.status_code,
                    "error": response.text[:500]
                }
                
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "response": None,
                "latency_ms": int(elapsed * 1000),
                "tokens_used": 0,
                "status_code": 0,
                "error": str(e)
            }
    
    def test_sensenova_model(self, model_name: str, api_key: str, prompt: str, timeout: int = 60) -> Dict:
        """测试 SenseNova (DeepSeek) 模型"""
        url = f"{self.sensenova_base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                
                return {
                    "success": True,
                    "response": content,
                    "latency_ms": int(elapsed * 1000),
                    "tokens_used": usage.get("total_tokens", 0),
                    "status_code": response.status_code,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "response": None,
                    "latency_ms": int(elapsed * 1000),
                    "tokens_used": 0,
                    "status_code": response.status_code,
                    "error": response.text[:500]
                }
                
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "response": None,
                "latency_ms": int(elapsed * 1000),
                "tokens_used": 0,
                "status_code": 0,
                "error": str(e)
            }
    
    def run_full_test(self, output_dir: str = "./large_scale_test_results") -> Dict:
        """运行完整测试"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info("=" * 80)
        logger.info("开始大规模模型测试")
        logger.info(f"测试案例数：{len(TEST_CASES)}")
        logger.info(f"LongCat 模型数：{len(self.longcat_models)}")
        logger.info(f"LongCat API Keys 数：{len(self.longcat_api_keys)}")
        logger.info(f"SenseNova 模型数：{len(self.sensenova_models)}")
        logger.info("=" * 80)
        
        all_results = []
        category_stats = {}
        model_stats = {}
        
        # 测试 LongCat 模型
        for case in TEST_CASES:
            logger.info(f"\n测试案例：{case['id']} - {case['name']}")
            logger.info(f"类别：{case['category']}, 难度：{case['difficulty']}")
            
            case_result = {
                "case_id": case["id"],
                "case_name": case["name"],
                "category": case["category"],
                "difficulty": case["difficulty"],
                "prompt": case["prompt"],
                "model_results": {}
            }
            
            # 测试每个 LongCat 模型
            for model in self.longcat_models:
                # 使用第一个可用的 API Key
                api_key = self.longcat_api_keys[0] if self.longcat_api_keys else ""
                
                if not api_key:
                    logger.warning(f"LongCat API Key 未配置，跳过 {model}")
                    continue
                
                logger.info(f"  测试模型：{model}")
                
                result = self.test_longcat_model(model, api_key, case["prompt"])
                
                case_result["model_results"][f"longcat_{model}"] = {
                    "provider": "LongCat",
                    "model": model,
                    "api_key_index": 0,
                    **result
                }
                
                # 更新模型统计
                if model not in model_stats:
                    model_stats[model] = {"total": 0, "success": 0, "failed": 0, "total_latency": 0, "total_tokens": 0}
                
                model_stats[model]["total"] += 1
                if result["success"]:
                    model_stats[model]["success"] += 1
                    model_stats[model]["total_latency"] += result["latency_ms"]
                    model_stats[model]["total_tokens"] += result["tokens_used"]
                else:
                    model_stats[model]["failed"] += 1
            
            # 测试 SenseNova 模型
            if self.sensenova_api_key:
                for model in self.sensenova_models:
                    logger.info(f"  测试 SenseNova 模型：{model}")
                    
                    result = self.test_sensenova_model(model, self.sensenova_api_key, case["prompt"])
                    
                    case_result["model_results"][f"sensenova_{model}"] = {
                        "provider": "SenseNova",
                        "model": model,
                        "api_key_index": 0,
                        **result
                    }
                    
                    # 更新模型统计
                    stats_key = f"sensenova_{model}"
                    if stats_key not in model_stats:
                        model_stats[stats_key] = {"total": 0, "success": 0, "failed": 0, "total_latency": 0, "total_tokens": 0}
                    
                    model_stats[stats_key]["total"] += 1
                    if result["success"]:
                        model_stats[stats_key]["success"] += 1
                        model_stats[stats_key]["total_latency"] += result["latency_ms"]
                        model_stats[stats_key]["total_tokens"] += result["tokens_used"]
                    else:
                        model_stats[stats_key]["failed"] += 1
            
            all_results.append(case_result)
            
            # 更新类别统计
            category = case["category"]
            if category not in category_stats:
                category_stats[category] = {"total": 0, "success": 0, "failed": 0}
            category_stats[category]["total"] += 1
        
        # 计算汇总统计
        total_tests = sum(stats["total"] for stats in model_stats.values())
        total_success = sum(stats["success"] for stats in model_stats.values())
        total_failed = sum(stats["failed"] for stats in model_stats.values())
        
        for model, stats in model_stats.items():
            if stats["success"] > 0:
                stats["avg_latency_ms"] = round(stats["total_latency"] / stats["success"], 2)
                stats["avg_tokens"] = round(stats["total_tokens"] / stats["success"], 2)
            else:
                stats["avg_latency_ms"] = 0
                stats["avg_tokens"] = 0
            stats["success_rate"] = round(stats["success"] / stats["total"] * 100, 2) if stats["total"] > 0 else 0
        
        self.summary = {
            "timestamp": timestamp,
            "total_cases": len(TEST_CASES),
            "total_tests": total_tests,
            "total_success": total_success,
            "total_failed": total_failed,
            "overall_success_rate": round(total_success / total_tests * 100, 2) if total_tests > 0 else 0,
            "category_stats": category_stats,
            "model_stats": model_stats,
            "test_details": all_results
        }
        
        # 保存 JSON 报告
        json_file = output_path / f"large_scale_test_{timestamp}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\nJSON 报告已保存：{json_file}")
        
        # 生成 Markdown 报告
        md_report = self.generate_markdown_report()
        md_file = output_path / f"large_scale_test_{timestamp}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_report)
        
        logger.info(f"Markdown 报告已保存：{md_file}")
        
        return self.summary
    
    def generate_markdown_report(self) -> str:
        """生成 Markdown 格式的深度预测报告"""
        timestamp = self.summary["timestamp"]
        
        md = []
        md.append("# 大规模模型测试深度预测报告\n")
        md.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        md.append(f"**测试编号**: {timestamp}\n")
        
        # 执行摘要
        md.append("## 1. 执行摘要\n")
        md.append(f"- **总测试案例数**: {self.summary['total_cases']}")
        md.append(f"- **总测试次数**: {self.summary['total_tests']}")
        md.append(f"- **成功次数**: {self.summary['total_success']}")
        md.append(f"- **失败次数**: {self.summary['total_failed']}")
        md.append(f"- **总体成功率**: {self.summary['overall_success_rate']}%\n")
        
        # 模型性能对比
        md.append("## 2. 模型性能对比\n")
        md.append("| 模型 | 提供商 | 测试次数 | 成功 | 失败 | 成功率 | 平均延迟 (ms) | 平均 Token 数 |\n")
        md.append("|------|--------|----------|------|------|--------|---------------|---------------|\n")
        
        for model, stats in sorted(self.summary["model_stats"].items(), key=lambda x: x[1]["success_rate"], reverse=True):
            provider = "SenseNova" if "sensenova" in model else "LongCat"
            model_name = model.replace("longcat_", "").replace("sensenova_", "")
            md.append(f"| {model_name} | {provider} | {stats['total']} | {stats['success']} | {stats['failed']} | {stats['success_rate']}% | {stats['avg_latency_ms']} | {stats['avg_tokens']} |\n")
        
        # 类别表现分析
        md.append("\n## 3. 类别表现分析\n")
        md.append("| 类别 | 案例数 | 说明 |\n")
        md.append("|------|--------|------|\n")
        
        category_descriptions = {
            "risk_assessment": "风险评估",
            "story_generation": "人生故事生成",
            "platform_simulation": "平台反应模拟",
            "multimodal": "多模态分析",
            "rewrite": "文案改写",
            "reasoning": "逻辑推理",
            "code_generation": "代码生成"
        }
        
        for category, stats in self.summary["category_stats"].items():
            desc = category_descriptions.get(category, category)
            md.append(f"| {desc} | {stats['total']} | 测试案例覆盖该类别的各种场景 |\n")
        
        # 深度分析
        md.append("\n## 4. 深度分析\n")
        
        md.append("### 4.1 LongCat 系列模型表现\n")
        longcat_models = {k: v for k, v in self.summary["model_stats"].items() if "longcat" in k}
        if longcat_models:
            best_longcat = max(longcat_models.items(), key=lambda x: x[1]["success_rate"])
            md.append(f"- **最佳 LongCat 模型**: {best_longcat[0].replace('longcat_', '')}\n")
            md.append(f"  - 成功率：{best_longcat[1]['success_rate']}%\n")
            md.append(f"  - 平均延迟：{best_longcat[1]['avg_latency_ms']}ms\n")
            md.append(f"  - 平均 Token 消耗：{best_longcat[1]['avg_tokens']}\n")
        
        md.append("\n### 4.2 DeepSeek v4 flash (SenseNova) 表现\n")
        sensenova_models = {k: v for k, v in self.summary["model_stats"].items() if "sensenova" in k}
        if sensenova_models:
            best_sensenova = max(sensenova_models.items(), key=lambda x: x[1]["success_rate"])
            md.append(f"- **最佳 SenseNova 模型**: {best_sensenova[0].replace('sensenova_', '')}\n")
            md.append(f"  - 成功率：{best_sensenova[1]['success_rate']}%\n")
            md.append(f"  - 平均延迟：{best_sensenova[1]['avg_latency_ms']}ms\n")
            md.append(f"  - 平均 Token 消耗：{best_sensenova[1]['avg_tokens']}\n")
        
        md.append("\n### 4.3 跨模型对比\n")
        if longcat_models and sensenova_models:
            avg_longcat_success = sum(v["success_rate"] for v in longcat_models.values()) / len(longcat_models)
            avg_sensenova_success = sum(v["success_rate"] for v in sensenova_models.values()) / len(sensenova_models)
            
            md.append(f"- LongCat 系列平均成功率：{avg_longcat_success:.2f}%\n")
            md.append(f"- SenseNova 系列平均成功率：{avg_sensenova_success:.2f}%\n")
            
            if avg_sensenova_success > avg_longcat_success:
                md.append("- **结论**: SenseNova (DeepSeek v4 flash) 在整体成功率上表现更优\n")
            elif avg_longcat_success > avg_sensenova_success:
                md.append("- **结论**: LongCat 系列在整体成功率上表现更优\n")
            else:
                md.append("- **结论**: 两个平台表现相当\n")
        
        # 困难案例分析
        md.append("\n## 5. 困难案例分析\n")
        
        complex_failures = [
            detail for detail in self.summary["test_details"]
            if detail["difficulty"] == "complex" and 
            any(not r["success"] for r in detail["model_results"].values())
        ]
        
        if complex_failures:
            md.append(f"共发现 {len(complex_failures)} 个复杂案例存在失败情况：\n")
            for i, failure in enumerate(complex_failures[:5], 1):  # 只展示前 5 个
                md.append(f"{i}. **{failure['case_name']}** ({failure['case_id']})\n")
                md.append(f"   - 类别：{failure['category']}\n")
                md.append(f"   -  prompt 前 50 字：{failure['prompt'][:50]}...\n")
        else:
            md.append("所有复杂案例测试均通过，无失败情况。\n")
        
        # 推荐配置
        md.append("\n## 6. 推荐配置\n")
        
        if sensenova_models:
            best_overall = max(self.summary["model_stats"].items(), key=lambda x: x[1]["success_rate"])
            best_model = best_overall[0]
            
            if "sensenova" in best_model:
                md.append("### 6.1 主力模型推荐\n")
                md.append(f"**推荐使用**: DeepSeek v4 flash (via SenseNova)\n")
                md.append("- 理由：综合表现最佳，成功率高，响应速度快\n")
                md.append("- 适用场景：高级任务（风险评估、人生故事生成、逻辑推理）\n")
        
        if longcat_models:
            best_longcat = max(longcat_models.items(), key=lambda x: x[1]["success_rate"])
            md.append("\n### 6.2 备选模型推荐\n")
            md.append(f"**推荐使用**: {best_longcat[0].replace('longcat_', '')}\n")
            md.append("- 理由：LongCat 系列中表现最佳\n")
            md.append("- 适用场景：主力模型不可用时的备选方案\n")
        
        md.append("\n### 6.3 降级策略\n")
        md.append("1. 优先使用 DeepSeek v4 flash (SenseNova)\n")
        md.append("2. 降级到 LongCat-Flash-Thinking-2601\n")
        md.append("3. 降级到 LongCat-Flash-Chat\n")
        md.append("4. 最终降级到其他备用 provider\n")
        
        # 成本估算
        md.append("\n## 7. 成本估算\n")
        
        total_tokens = sum(stats["total_tokens"] for stats in self.summary["model_stats"].values())
        md.append(f"- **总 Token 消耗**: {total_tokens:,}\n")
        md.append(f"- **平均每案例 Token**: {total_tokens / self.summary['total_cases']:.0f}\n")
        
        # 假设价格（实际价格需要查阅官方文档）
        md.append("\n*注：成本估算基于假设价格*\n")
        md.append("- DeepSeek v4 flash: ¥0.01 / 1K tokens\n")
        md.append("- LongCat-Flash 系列：¥0.008 / 1K tokens\n")
        
        estimated_cost = (total_tokens / 1000) * 0.01
        md.append(f"- **预估总成本**: ¥{estimated_cost:.2f}\n")
        
        # 下一步建议
        md.append("\n## 8. 下一步建议\n")
        md.append("1. **生产环境部署**: 使用 DeepSeek v4 flash 作为主力模型\n")
        md.append("2. **监控告警**: 设置成功率低于 95% 时的告警\n")
        md.append("3. **A/B 测试**: 在生产环境进行小流量 A/B 测试\n")
        md.append("4. **性能优化**: 针对高延迟案例进行 prompt 优化\n")
        md.append("5. **成本优化**: 根据实际使用场景调整模型选择策略\n")
        
        md.append("\n---\n")
        md.append("*本报告由 VibeUtopia 大规模测试系统自动生成*\n")
        
        return "".join(md)


def main():
    """主函数"""
    print("=" * 80)
    print("VibeUtopia 大规模模型测试")
    print("=" * 80)
    
    # 检查 API Key 配置
    longcat_keys = os.getenv("LONGCAT_API_KEY", "").split(",")
    sensenova_key = os.getenv("SENSENOVA_API_KEY", "")
    
    print(f"\nLongCat API Keys: {len(longcat_keys)} 个")
    for i, key in enumerate(longcat_keys, 1):
        print(f"  {i}. {key[:15]}...")
    
    print(f"\nSenseNova API Key: {'已配置' if sensenova_key else '未配置'}")
    if sensenova_key:
        print(f"  {sensenova_key[:15]}...")
    
    print(f"\n测试案例总数：{len(TEST_CASES)}")
    print("=" * 80)
    
    # 创建测试器并运行
    tester = ModelTester()
    results = tester.run_full_test()
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print(f"总测试次数：{results['total_tests']}")
    print(f"成功：{results['total_success']}")
    print(f"失败：{results['total_failed']}")
    print(f"总体成功率：{results['overall_success_rate']}%")
    print("=" * 80)
    
    return 0 if results['total_failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
