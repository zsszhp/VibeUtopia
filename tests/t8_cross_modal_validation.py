#!/usr/bin/env python3
"""T8 跨模态冲突检测验证脚本

验证跨模态冲突检测模块的功能：
1. 文案vs画面冲突检测
2. 文案vs音频冲突检测
3. 画面vs音频冲突检测
4. 隐藏风险检测（单模态安全但其他模态有风险）

预期准确率收益：+7%
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.cross_modal_detector import CrossModalConflictDetector, integrate_cross_modal_score

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("t8_validation")


async def test_cross_modal_conflicts():
    """测试跨模态冲突检测"""
    logger.info("=" * 60)
    logger.info("T8 跨模态冲突检测 - 功能测试")
    logger.info("=" * 60)

    detector = CrossModalConflictDetector()

    # 测试案例
    test_cases = [
        {
            "name": "文案安全但画面有风险",
            "text": "今天天气真好，适合出去走走",
            "visual": "画面中出现暴力场景，有人打斗，血腥内容",
            "audio": None,
            "expected_conflict": True,
        },
        {
            "name": "文案积极但音频消极",
            "text": "我们的产品非常优秀，受到用户一致好评",
            "visual": None,
            "audio": "这个产品其实问题很多，用户投诉率很高，质量堪忧",
            "expected_conflict": True,
        },
        {
            "name": "三模态一致安全",
            "text": "春天来了，花朵开放，景色很美",
            "visual": "画面展示春天花园，花朵盛开，阳光明媚",
            "audio": "鸟鸣声，轻松愉快的背景音乐",
            "expected_conflict": False,
        },
        {
            "name": "单模态内容（无冲突）",
            "text": "这是一段普通的文案",
            "visual": None,
            "audio": None,
            "expected_conflict": False,
        },
        {
            "name": "画面和音频冲突",
            "text": "这是一部恐怖电影",
            "visual": "画面展示恐怖场景，血腥暴力",
            "audio": "音频内容轻松愉快，喜剧风格",
            "expected_conflict": True,
        },
    ]

    results = []
    for tc in test_cases:
        logger.info(f"\n测试案例: {tc['name']}")
        logger.info(f"  文案: {tc['text'][:50]}...")
        logger.info(f"  画面: {tc.get('visual', '无')[:50] if tc.get('visual') else '无'}")
        logger.info(f"  音频: {tc.get('audio', '无')[:50] if tc.get('audio') else '无'}")

        result = await detector.detect_conflicts(
            text=tc["text"],
            visual_description=tc.get("visual"),
            audio_transcript=tc.get("audio"),
        )

        has_conflict = len(result.get("conflicts", [])) > 0 or result.get("has_hidden_risk", False)
        passed = has_conflict == tc["expected_conflict"]

        logger.info(f"  冲突数量: {len(result.get('conflicts', []))}")
        logger.info(f"  冲突分数: {result.get('overall_conflict_score', 0)}")
        logger.info(f"  隐藏风险: {result.get('has_hidden_risk', False)}")
        logger.info(f"  预期冲突: {tc['expected_conflict']}, 实际: {has_conflict}, 通过: {passed}")

        results.append({
            "name": tc["name"],
            "passed": passed,
            "result": result,
        })

    return results


def test_score_integration():
    """测试分数集成"""
    logger.info("\n" + "=" * 60)
    logger.info("T8 跨模态冲突检测 - 分数集成测试")
    logger.info("=" * 60)

    test_cases = [
        {"overall": 30, "conflict": 0, "hidden": False, "expected": 30},
        {"overall": 30, "conflict": 60, "hidden": False, "expected": 40},
        {"overall": 30, "conflict": 0, "hidden": True, "expected": 45},
        {"overall": 30, "conflict": 60, "hidden": True, "expected": 45},
        {"overall": 80, "conflict": 70, "hidden": True, "expected": 95},
    ]

    results = []
    for tc in test_cases:
        adjusted = integrate_cross_modal_score(tc["overall"], tc["conflict"], tc["hidden"])
        passed = adjusted == tc["expected"]
        logger.info(f"  原始分={tc['overall']}, 冲突分={tc['conflict']}, 隐藏风险={tc['hidden']} "
                    f"→ 调整后={adjusted}, 预期={tc['expected']}, 通过={passed}")
        results.append({**tc, "actual": adjusted, "passed": passed})

    return results


async def main():
    """主测试流程"""
    logger.info("T8 跨模态冲突检测验证开始")
    logger.info(f"时间: {datetime.now().isoformat()}")

    # 测试1: 冲突检测
    conflict_results = await test_cross_modal_conflicts()

    # 测试2: 分数集成
    score_results = test_score_integration()

    # 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("T8 验证汇总报告")
    logger.info("=" * 60)

    conflict_passed = sum(1 for r in conflict_results if r["passed"])
    score_passed = sum(1 for r in score_results if r["passed"])
    total_passed = conflict_passed + score_passed
    total_tests = len(conflict_results) + len(score_results)

    logger.info(f"冲突检测: {conflict_passed}/{len(conflict_results)} 通过")
    logger.info(f"分数集成: {score_passed}/{len(score_results)} 通过")
    logger.info(f"总计: {total_passed}/{total_tests} 通过")

    report = {
        "test_time": datetime.now().isoformat(),
        "conflict_detection": conflict_results,
        "score_integration": score_results,
        "summary": {
            "conflict_passed": conflict_passed,
            "conflict_total": len(conflict_results),
            "score_passed": score_passed,
            "score_total": len(score_results),
            "total_passed": total_passed,
            "total_tests": total_tests,
        },
        "status": "PASSED" if total_passed == total_tests else "PARTIAL",
    }

    # 保存报告
    report_dir = Path(__file__).parent.parent / "data" / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"t8_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n验证报告已保存: {report_path}")
    logger.info(f"验证状态: {report['status']}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
