#!/usr/bin/env python3
"""T9 多模态内容理解验证脚本

验证多模态内容理解模块的功能：
1. 视频画面风险分析
2. 音频转写风险分析
3. OCR文本风险分析
4. 多模态分数集成

预期准确率收益：+6%
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.multimodal_analyzer import MultiModalAnalyzer, integrate_multimodal_score

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("t9_validation")


async def test_multimodal_analysis():
    """测试多模态分析"""
    logger.info("=" * 60)
    logger.info("T9 多模态内容理解 - 功能测试")
    logger.info("=" * 60)

    analyzer = MultiModalAnalyzer()

    # 测试案例
    test_cases = [
        {
            "name": "暴力画面检测",
            "visual": "画面中出现打斗场景，有人流血，武器碰撞，表情痛苦",
            "audio": None,
            "ocr": None,
        },
        {
            "name": "敏感音频检测",
            "visual": None,
            "audio": "这段话其实包含了一些敏感内容，大家懂的，有些事情不能说但心里清楚",
            "ocr": None,
        },
        {
            "name": "OCR风险检测",
            "visual": None,
            "audio": None,
            "ocr": "图片中出现敏感标语，不当文字内容",
        },
        {
            "name": "安全内容",
            "visual": "画面展示美丽风景，蓝天白云，花草树木",
            "audio": "轻松愉快的音乐，鸟鸣声",
            "ocr": "欢迎标语，景点介绍",
        },
    ]

    results = []
    for tc in test_cases:
        logger.info(f"\n测试案例: {tc['name']}")

        # 画面分析
        if tc.get("visual"):
            visual_result = await analyzer.analyze_visual(tc["visual"])
            logger.info(f"  画面风险分: {visual_result['overall_visual_risk_score']}")
            logger.info(f"  画面风险数量: {len(visual_result.get('visual_risks', []))}")
        else:
            visual_result = {"overall_visual_risk_score": 0}
            logger.info(f"  画面风险分: 0 (无画面)")

        # 音频分析
        if tc.get("audio"):
            audio_result = await analyzer.analyze_audio(tc["audio"])
            logger.info(f"  音频风险分: {audio_result['overall_audio_risk_score']}")
            logger.info(f"  音频风险数量: {len(audio_result.get('audio_risks', []))}")
        else:
            audio_result = {"overall_audio_risk_score": 0}
            logger.info(f"  音频风险分: 0 (无音频)")

        # OCR分析
        if tc.get("ocr"):
            ocr_result = await analyzer.analyze_ocr(tc["ocr"])
            logger.info(f"  OCR风险分: {ocr_result['overall_ocr_risk_score']}")
            logger.info(f"  OCR风险数量: {len(ocr_result.get('ocr_risks', []))}")
        else:
            ocr_result = {"overall_ocr_risk_score": 0}
            logger.info(f"  OCR风险分: 0 (无OCR)")

        results.append({
            "name": tc["name"],
            "visual_score": visual_result["overall_visual_risk_score"],
            "audio_score": audio_result["overall_audio_risk_score"],
            "ocr_score": ocr_result["overall_ocr_risk_score"],
        })

    return results


def test_score_integration():
    """测试多模态分数集成"""
    logger.info("\n" + "=" * 60)
    logger.info("T9 多模态内容理解 - 分数集成测试")
    logger.info("=" * 60)

    test_cases = [
        {"text": 30, "visual": 0, "audio": 0, "ocr": 0, "expected": 30},
        {"text": 30, "visual": 80, "audio": 0, "ocr": 0, "expected": 64},
        {"text": 30, "visual": 0, "audio": 70, "ocr": 0, "expected": 49},
        {"text": 30, "visual": 80, "audio": 70, "ocr": 60, "expected": 64},
        {"text": 80, "visual": 90, "audio": 85, "ocr": 80, "expected": 90},
    ]

    results = []
    for tc in test_cases:
        adjusted = integrate_multimodal_score(
            tc["text"], tc["visual"], tc["audio"], tc["ocr"]
        )
        passed = adjusted == tc["expected"]
        logger.info(f"  文本={tc['text']}, 画面={tc['visual']}, 音频={tc['audio']}, OCR={tc['ocr']} "
                    f"→ 调整后={adjusted}, 预期={tc['expected']}, 通过={passed}")
        results.append({**tc, "actual": adjusted, "passed": passed})

    return results


async def main():
    """主测试流程"""
    logger.info("T9 多模态内容理解验证开始")
    logger.info(f"时间: {datetime.now().isoformat()}")

    # 测试1: 多模态分析
    analysis_results = await test_multimodal_analysis()

    # 测试2: 分数集成
    score_results = test_score_integration()

    # 汇总报告
    logger.info("\n" + "=" * 60)
    logger.info("T9 验证汇总报告")
    logger.info("=" * 60)

    score_passed = sum(1 for r in score_results if r["passed"])
    total_tests = len(score_results)

    logger.info(f"分数集成: {score_passed}/{total_tests} 通过")

    report = {
        "test_time": datetime.now().isoformat(),
        "analysis_results": analysis_results,
        "score_integration": score_results,
        "summary": {
            "score_passed": score_passed,
            "score_total": total_tests,
        },
        "status": "PASSED" if score_passed == total_tests else "PARTIAL",
    }

    # 保存报告
    report_dir = Path(__file__).parent.parent / "data" / "validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"t9_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"\n验证报告已保存: {report_path}")
    logger.info(f"验证状态: {report['status']}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
