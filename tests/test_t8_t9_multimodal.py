#!/usr/bin/env python3
"""T8/T9 功能测试脚本

使用真实回测案例测试：
1. T8 跨模态冲突检测
2. T9 多模态内容理解（模拟画面和音频输入）
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 测试案例 ====================

TEST_CASES = [
    {
        "name": "AI 一键脱衣黑产",
        "text": "分享一个 AI 照片处理技巧，可以把普通照片变成艺术照，效果非常逼真！",
        "visual_description": "画面展示女性裸露身体图片，配有'9.9 元一键脱衣'的文字说明，背景有色情网站广告",
        "audio_transcript": "只需 9.9 元，就能把任何女生的照片变成裸照，前男友可以用这个威胁复合",
        "expected_conflict": True,  # 文案声称"艺术照"但画面/音频是色情内容
        "expected_risk_score": 95,
    },
    {
        "name": "优思益假洋牌",
        "text": "澳洲优思益（Youthit）是 2010 年创立于墨尔本的高端保健品品牌，年销售额 3.1 亿",
        "visual_description": "画面显示广州工厂生产线，产品包装标注'澳大利亚品牌'，但地址是汽车维修站",
        "audio_transcript": "其实就是国内代工，包装成澳洲品牌，找个老外假装专家，全套手续 35 天搞定",
        "expected_conflict": True,  # 文案声称"澳洲品牌"但画面/音频揭露造假
        "expected_risk_score": 85,
    },
    {
        "name": "医疗谣言伪科学",
        "text": "每天喝这个神仙水，包治百病，不用吃药！成分经过科学配比，能改变人体酸碱度",
        "visual_description": "画面展示白醋、小苏打、柠檬汁混合，文字标注'治愈癌症糖尿病'",
        "audio_transcript": "这个水能治愈癌症、糖尿病、高血压，不用去医院，停掉正规治疗也没事",
        "expected_conflict": False,  # 文案和画面/音频一致，都是虚假医疗宣传
        "expected_risk_score": 90,
    },
    {
        "name": "安全内容示例",
        "text": "今天学习了一道家常菜红烧肉的做法，步骤简单，味道鲜美",
        "visual_description": "画面展示厨房烹饪场景，厨师正在制作红烧肉，背景干净整洁",
        "audio_transcript": "先将五花肉焯水，然后炒糖色，加入调料慢炖 40 分钟即可",
        "expected_conflict": False,  # 三模态一致且安全
        "expected_risk_score": 5,
    },
]


async def test_t8_cross_modal_detection():
    """测试 T8 跨模态冲突检测"""
    print("\n" + "="*80)
    print("T8 跨模态冲突检测测试")
    print("="*80)
    
    from backend.services.cross_modal_detector import CrossModalConflictDetector
    
    detector = CrossModalConflictDetector()
    
    results = []
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[案例 {i}/{len(TEST_CASES)}] {case['name']}")
        print("-" * 60)
        
        result = await detector.detect_conflicts(
            text=case["text"],
            visual_description=case["visual_description"],
            audio_transcript=case["audio_transcript"],
        )
        
        print(f"冲突分数：{result['overall_conflict_score']}")
        print(f"隐藏风险：{result['has_hidden_risk']}")
        print(f"冲突数量：{len(result['conflicts'])}")
        
        if result["conflicts"]:
            for conflict in result["conflicts"]:
                print(f"  - 类型：{conflict['type']}")
                print(f"    描述：{conflict['description']}")
                print(f"    风险分：{conflict['risk_score']}")
        
        print(f"总结：{result['summary']}")
        
        # 验证预期
        has_conflict = result["overall_conflict_score"] > 30 or result["has_hidden_risk"]
        expected = case["expected_conflict"]
        
        if has_conflict == expected:
            print("✓ 检测结果符合预期")
            results.append(True)
        else:
            print(f"✗ 检测结果不符合预期（期望：{expected}, 实际：{has_conflict}）")
            results.append(False)
    
    # 统计
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*80}")
    print(f"T8 测试通过率：{passed}/{total} = {passed/total*100:.1f}%")
    print("="*80)
    
    return passed == total


async def test_t9_multimodal_analysis():
    """测试 T9 多模态内容理解（模拟）"""
    print("\n" + "="*80)
    print("T9 多模态内容理解测试")
    print("="*80)
    
    from backend.services.multimodal_analyzer import MultiModalAnalyzer
    
    analyzer = MultiModalAnalyzer()
    
    results = []
    for i, case in enumerate(TEST_CASES, 1):
        print(f"\n[案例 {i}/{len(TEST_CASES)}] {case['name']}")
        print("-" * 60)
        
        # 画面分析
        visual_result = await analyzer.analyze_visual(
            visual_description=case["visual_description"]
        )
        print(f"画面风险分：{visual_result['overall_visual_risk_score']}")
        if visual_result["visual_risks"]:
            for risk in visual_result["visual_risks"]:
                print(f"  - {risk['type']}: {risk['description']}")
        
        # OCR 分析（从画面描述中提取文字）
        ocr_text = case["visual_description"].split('"')[1] if '"' in case["visual_description"] else ""
        if ocr_text:
            ocr_result = await analyzer.analyze_ocr(ocr_text=ocr_text)
            print(f"OCR 风险分：{ocr_result['overall_ocr_risk_score']}")
        
        # 音频分析
        audio_result = await analyzer.analyze_audio(
            audio_transcript=case["audio_transcript"]
        )
        print(f"音频风险分：{audio_result['overall_audio_risk_score']}")
        if audio_result["audio_risks"]:
            for risk in audio_result["audio_risks"]:
                print(f"  - {risk['type']}: {risk['description']}")
        
        # 多模态分数集成
        from backend.services.multimodal_analyzer import integrate_multimodal_score
        
        overall = integrate_multimodal_score(
            text_score=50,  # 假设文本基础风险分
            visual_score=visual_result["overall_visual_risk_score"],
            audio_score=audio_result["overall_audio_risk_score"],
            ocr_score=ocr_result["overall_ocr_risk_score"] if ocr_text else 0,
        )
        
        print(f"集成后总分：{overall}")
        print(f"预期风险分：{case['expected_risk_score']}")
        
        # 验证（允许±20 的误差）
        if abs(overall - case["expected_risk_score"]) <= 20:
            print("✓ 风险评分符合预期")
            results.append(True)
        else:
            print(f"✗ 风险评分偏差较大（期望：{case['expected_risk_score']}, 实际：{overall}）")
            results.append(False)
    
    # 统计
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*80}")
    print(f"T9 测试通过率：{passed}/{total} = {passed/total*100:.1f}%")
    print("="*80)
    
    return passed == total


async def test_keyframe_extraction():
    """测试关键帧提取（需要有视频文件）"""
    print("\n" + "="*80)
    print("关键帧提取测试")
    print("="*80)
    
    from backend.services.keyframe_extractor import KeyframeExtractor
    
    # 检查是否有测试视频
    test_video = Path("/workspace/cases/video/test.mp4")
    if not test_video.exists():
        print("⊘ 跳过：未找到测试视频文件")
        print("提示：将测试视频放到 /workspace/cases/video/test.mp4 可运行此测试")
        return True
    
    extractor = KeyframeExtractor({"max_frames": 10})
    result = await extractor.extract(str(test_video))
    
    print(f"视频时长：{result.duration:.2f}秒")
    print(f"总帧数：{result.total_frames}")
    print(f"提取方法：{result.method_used}")
    print(f"场景数：{result.scene_count}")
    print(f"关键帧数：{len(result.frames)}")
    
    for frame in result.frames[:5]:  # 只显示前 5 帧
        print(f"  - 帧{frame.index}: {frame.timestamp:.2f}s @ {frame.method}")
    
    if len(result.frames) > 0:
        print("✓ 关键帧提取成功")
        return True
    else:
        print("✗ 关键帧提取失败")
        return False


async def main():
    """主测试流程"""
    print("\n" + "█"*80)
    print("T8/T9 功能测试 - 使用真实回测案例")
    print("█"*80)
    
    # 测试 T8
    t8_passed = await test_t8_cross_modal_detection()
    
    # 测试 T9
    t9_passed = await test_t9_multimodal_analysis()
    
    # 测试关键帧提取
    keyframe_passed = await test_keyframe_extraction()
    
    # 总结
    print("\n" + "█"*80)
    print("测试总结")
    print("█"*80)
    print(f"T8 跨模态冲突检测：{'✓ 通过' if t8_passed else '✗ 失败'}")
    print(f"T9 多模态内容理解：{'✓ 通过' if t9_passed else '✗ 失败'}")
    print(f"关键帧提取：        {'✓ 通过' if keyframe_passed else '⊘ 跳过'}")
    
    all_passed = t8_passed and t9_passed
    print(f"\n总体结果：{'✓ 全部通过' if all_passed else '✗ 部分失败'}")
    print("█"*80 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
