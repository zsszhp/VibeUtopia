"""Prompt A/B测试运行器 — T2.2

使用真实案例对不同Prompt版本进行A/B测试，评估哪个版本效果更好。
评估指标包括：风险等级准确率、维度覆盖率、改写质量等。
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services.prompt_version_manager import PromptVersionManager
from backend.services.llm_client import call_llm, load_prompt
from backend.services.risk_assessor import assess_risks

logger = logging.getLogger(__name__)

# 预设测试案例
DEFAULT_TEST_CASES = [
    {
        "name": "高风险案例-明星塌房",
        "text": "某某明星被曝出私下代孕，还涉及偷税漏税，粉丝群体已经开始大规模脱粉。",
        "expected_level": "high",
    },
    {
        "name": "中风险案例-争议话题",
        "text": "最近某品牌的广告涉嫌性别歧视，引发网友热议，有人认为这是正常营销。",
        "expected_level": "medium",
    },
    {
        "name": "低风险案例-日常分享",
        "text": "今天去了新开的咖啡馆，环境不错，推荐大家去试试。",
        "expected_level": "low",
    },
]


class PromptABTestRunner:
    """Prompt A/B测试运行器"""

    def __init__(self, prompt_name: str, version_a: str, version_b: str):
        self.prompt_name = prompt_name
        self.version_a = version_a
        self.version_b = version_b
        self.mgr = PromptVersionManager()
        self.results_a: List[Dict[str, Any]] = []
        self.results_b: List[Dict[str, Any]] = []

    async def run_test(
        self,
        test_cases: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """运行A/B测试

        Args:
            test_cases: 测试案例列表 [{"name": "", "text": "", "expected_level": ""}]

        Returns:
            测试报告
        """
        cases = test_cases or DEFAULT_TEST_CASES
        logger.info("开始A/B测试: %s (%s vs %s), 案例数=%d",
                   self.prompt_name, self.version_a, self.version_b, len(cases))

        pv_a = self.mgr.get_version(self.prompt_name, self.version_a)
        pv_b = self.mgr.get_version(self.prompt_name, self.version_b)

        if not pv_a or not pv_b:
            raise ValueError("指定版本不存在")

        total_a = 0
        correct_a = 0
        total_b = 0
        correct_b = 0

        for i, case in enumerate(cases):
            text = case["text"]
            expected = case.get("expected_level", "")
            case_name = case.get("name", f"case_{i}")

            logger.info("测试案例 %d/%d: %s", i + 1, len(cases), case_name)

            result_a = await self._evaluate_with_version(pv_a.content, text, expected)
            result_b = await self._evaluate_with_version(pv_b.content, text, expected)

            self.results_a.append(result_a)
            self.results_b.append(result_b)

            if result_a["level_correct"]:
                correct_a += 1
            total_a += 1

            if result_b["level_correct"]:
                correct_b += 1
            total_b += 1

        # 计算综合指标
        metrics_a = {
            "accuracy": round(correct_a / total_a, 4) if total_a > 0 else 0,
            "avg_risk_score": round(sum(r.get("risk_score", 0) for r in self.results_a) / len(self.results_a), 2) if self.results_a else 0,
            "avg_response_time": round(sum(r.get("response_time", 0) for r in self.results_a) / len(self.results_a), 2) if self.results_a else 0,
            "parse_success_rate": round(sum(1 for r in self.results_a if r.get("parse_ok")) / len(self.results_a), 4) if self.results_a else 0,
        }
        metrics_b = {
            "accuracy": round(correct_b / total_b, 4) if total_b > 0 else 0,
            "avg_risk_score": round(sum(r.get("risk_score", 0) for r in self.results_b) / len(self.results_b), 2) if self.results_b else 0,
            "avg_response_time": round(sum(r.get("response_time", 0) for r in self.results_b) / len(self.results_b), 2) if self.results_b else 0,
            "parse_success_rate": round(sum(1 for r in self.results_b if r.get("parse_ok")) / len(self.results_b), 4) if self.results_b else 0,
        }

        # 记录到A/B测试管理器
        test_config = self.mgr.create_ab_test(
            prompt_name=self.prompt_name,
            version_a=self.version_a,
            version_b=self.version_b,
            test_name=f"Auto Test: {self.version_a} vs {self.version_b}",
        )

        for r in self.results_a:
            self.mgr.record_ab_test_result(
                test_id=test_config["test_id"],
                version="a",
                metrics={"accuracy": 1.0 if r["level_correct"] else 0.0, "risk_score": r.get("risk_score", 0)},
            )

        for r in self.results_b:
            self.mgr.record_ab_test_result(
                test_id=test_config["test_id"],
                version="b",
                metrics={"accuracy": 1.0 if r["level_correct"] else 0.0, "risk_score": r.get("risk_score", 0)},
            )

        conclusion = self.mgr.conclude_ab_test(test_config["test_id"])

        report = {
            "test_id": test_config["test_id"],
            "prompt_name": self.prompt_name,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "metrics_a": metrics_a,
            "metrics_b": metrics_b,
            "winner": conclusion.winner if conclusion else "unknown",
            "sample_size": len(cases),
            "details_a": self.results_a,
            "details_b": self.results_b,
            "conclusion": conclusion.to_dict() if conclusion else None,
        }

        logger.info("A/B测试完成: 胜出者=%s", report["winner"])
        return report

    async def _evaluate_with_version(
        self,
        prompt_content: str,
        text: str,
        expected_level: str,
    ) -> Dict[str, Any]:
        """使用指定Prompt版本评估文案"""
        start_time = time.time()
        try:
            prompt = prompt_content + "\n\n待分析文案:\n" + text
            response = await call_llm(prompt, task_type="risk_assessment")
            response_time = time.time() - start_time

            # 尝试解析JSON响应
            try:
                result = json.loads(response)
                parse_ok = True
                risk_score = result.get("overall_score", 0)
            except json.JSONDecodeError:
                result = {}
                parse_ok = False
                risk_score = 0

            # 判断风险等级
            actual_level = "low"
            if risk_score > 75:
                actual_level = "high"
            elif risk_score > 40:
                actual_level = "medium"

            level_correct = (actual_level == expected_level)

            return {
                "parse_ok": parse_ok,
                "risk_score": risk_score,
                "actual_level": actual_level,
                "expected_level": expected_level,
                "level_correct": level_correct,
                "response_time": round(response_time, 2),
                "response_snippet": response[:200] if response else "",
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error("评估失败: %s", e)
            return {
                "parse_ok": False,
                "risk_score": 0,
                "actual_level": "error",
                "expected_level": expected_level,
                "level_correct": False,
                "response_time": round(response_time, 2),
                "error": str(e),
            }


async def run_platform_prompt_ab_test(
    platform: str,
    version_a: str = "v1.0",
    version_b: str = "v2.0",
    test_cases: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """便捷函数: 运行平台Prompt的A/B测试

    Args:
        platform: 平台标识 (weibo, bilibili, etc.)
        version_a: 版本A
        version_b: 版本B
        test_cases: 自定义测试案例

    Returns:
        测试报告
    """
    prompt_name = f"persona_{platform}"
    runner = PromptABTestRunner(prompt_name, version_a, version_b)
    return await runner.run_test(test_cases)


async def register_default_versions():
    """将现有的Prompt文件注册为v1.0版本"""
    mgr = PromptVersionManager()
    prompts_dir = mgr.prompts_dir

    persona_files = list(prompts_dir.glob("persona_*.txt"))
    for pf in persona_files:
        prompt_name = pf.stem
        with open(pf, "r", encoding="utf-8") as f:
            content = f.read()
        mgr.register_version(
            prompt_name=prompt_name,
            version="v1.0",
            content=content,
            metadata={
                "source": f"prompts/{pf.name}",
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "description": f"从现有文件导入的初始版本",
            },
        )
        logger.info("注册默认版本: %s v1.0", prompt_name)

    return {"registered": [pf.stem for pf in persona_files]}
