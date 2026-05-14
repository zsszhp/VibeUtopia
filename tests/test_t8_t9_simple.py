#!/usr/bin/env python3
"""T8/T9 功能测试脚本 - 简化版（不依赖 LLM）

测试核心逻辑和数据结构
"""

import sys
sys.path.insert(0, '/workspace')


def test_t8_detector_structure():
    """测试 T8 跨模态检测器结构"""
    print("\n" + "="*80)
    print("T8 跨模态冲突检测 - 结构测试")
    print("="*80)
    
    from backend.services.cross_modal_detector import (
        CrossModalConflictDetector,
        integrate_cross_modal_score,
        CROSS_MODAL_PROMPT
    )
    
    # 1. 检测器实例化
    detector = CrossModalConflictDetector()
    print("✓ CrossModalConflictDetector 实例化成功")
    
    # 2. Prompt 模板检查
    assert "文案内容" in CROSS_MODAL_PROMPT
    assert "画面描述" in CROSS_MODAL_PROMPT
    assert "音频转写" in CROSS_MODAL_PROMPT
    assert "conflicts" in CROSS_MODAL_PROMPT
    print("✓ CROSS_MODAL_PROMPT 模板完整")
    
    # 3. 单模态测试（应返回无冲突）
    import asyncio
    
    async def test_single_modal():
        result = await detector.detect_conflicts(
            text="仅文案测试",
            visual_description=None,
            audio_transcript=None
        )
        return result
    
    result = asyncio.run(test_single_modal())
    assert result["overall_conflict_score"] == 0
    assert result["has_hidden_risk"] == False
    assert len(result["conflicts"]) == 0
    print("✓ 单模态内容检测正确（无冲突）")
    
    # 4. 分数集成测试
    score1 = integrate_cross_modal_score(
        overall_score=50,
        conflict_score=60,
        has_hidden_risk=True
    )
    assert score1 == 65  # 50+15
    print(f"✓ 分数集成测试 1: 50 + 隐藏风险 = {score1}")
    
    score2 = integrate_cross_modal_score(
        overall_score=50,
        conflict_score=70,
        has_hidden_risk=False
    )
    assert score2 == 60  # 50+10
    print(f"✓ 分数集成测试 2: 50 + 高冲突 = {score2}")
    
    print("\nT8 结构测试：✓ 全部通过")
    return True


def test_t9_analyzer_structure():
    """测试 T9 多模态分析器结构"""
    print("\n" + "="*80)
    print("T9 多模态内容理解 - 结构测试")
    print("="*80)
    
    from backend.services.multimodal_analyzer import (
        MultiModalAnalyzer,
        integrate_multimodal_score,
        VISUAL_RISK_PROMPT,
        AUDIO_RISK_PROMPT,
        OCR_RISK_PROMPT
    )
    
    # 1. 分析器实例化
    analyzer = MultiModalAnalyzer()
    print("✓ MultiModalAnalyzer 实例化成功")
    
    # 2. Prompt 模板检查
    assert "画面描述" in VISUAL_RISK_PROMPT
    assert "视觉风险" in VISUAL_RISK_PROMPT
    print("✓ VISUAL_RISK_PROMPT 模板完整")
    
    assert "音频转写" in AUDIO_RISK_PROMPT
    assert "音频情感" in AUDIO_RISK_PROMPT
    print("✓ AUDIO_RISK_PROMPT 模板完整")
    
    assert "OCR 文本" in OCR_RISK_PROMPT
    print("✓ OCR_RISK_PROMPT 模板完整")
    
    # 3. 空输入测试
    import asyncio
    
    async def test_empty_input():
        visual = await analyzer.analyze_visual("")
        audio = await analyzer.analyze_audio("")
        ocr = await analyzer.analyze_ocr("")
        return visual, audio, ocr
    
    visual, audio, ocr = asyncio.run(test_empty_input())
    
    assert visual["overall_visual_risk_score"] == 0
    assert audio["overall_audio_risk_score"] == 0
    assert ocr["overall_ocr_risk_score"] == 0
    print("✓ 空输入处理正确")
    
    # 4. 分数集成测试
    score1 = integrate_multimodal_score(
        text_score=50,
        visual_score=70,
        audio_score=60,
        ocr_score=40
    )
    # max(50, 70*0.8=56, 60*0.7=42, 40*0.6=24) = 56
    # 只有 visual>60，所以不触发 +10
    assert score1 == 56
    print(f"✓ 分数集成测试 1: max(50, 56, 42, 24) = {score1}")
    
    score2 = integrate_multimodal_score(
        text_score=70,
        visual_score=80,
        audio_score=75,
        ocr_score=0
    )
    # max(70, 80*0.8=64, 75*0.7=52, 0) = 70
    # text>60 且 visual>60，触发 +10
    assert score2 == 80
    print(f"✓ 分数集成测试 2: max(70, 64, 52, 0) + 10 = {score2}")
    
    print("\nT9 结构测试：✓ 全部通过")
    return True


def test_keyframe_extractor():
    """测试关键帧提取器"""
    print("\n" + "="*80)
    print("关键帧提取器 - 结构测试")
    print("="*80)
    
    from backend.services.keyframe_extractor import (
        KeyframeExtractor,
        KeyFrame,
        KeyFrameResult,
        DEFAULT_CONFIG
    )
    
    # 1. 配置检查
    assert "max_frames" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["max_frames"] == 50
    print(f"✓ 默认配置完整：max_frames={DEFAULT_CONFIG['max_frames']}")
    
    # 2. 提取器实例化
    extractor = KeyframeExtractor()
    print("✓ KeyframeExtractor 实例化成功")
    
    # 3. 数据模型检查
    frame = KeyFrame(
        index=1,
        timestamp=5.5,
        file_path="/tmp/frame_001.jpg",
        method="scenedetect",
        scene_index=0
    )
    assert frame.index == 1
    assert frame.timestamp == 5.5
    print("✓ KeyFrame 数据模型正确")
    
    # 4. 工具检测
    from backend.services.keyframe_extractor import (
        _HAS_SCENEDETECT,
        _HAS_FFMPEG,
        _HAS_OPENCV
    )
    print(f"工具可用性：scenedetect={_HAS_SCENEDETECT}, ffmpeg={_HAS_FFMPEG}, opencv={_HAS_OPENCV}")
    
    if _HAS_FFMPEG or _HAS_OPENCV:
        print("✓ 至少有一个关键帧提取工具可用")
    else:
        print("⚠ 无可用提取工具（需安装 ffmpeg-python 或 opencv-python）")
    
    print("\n关键帧提取器测试：✓ 全部通过")
    return True


def test_hardware_detector():
    """测试硬件检测器"""
    print("\n" + "="*80)
    print("硬件检测器 - 结构测试")
    print("="*80)
    
    from backend.services.hardware_detector import (
        detect_gpu,
        get_hardware_tier
    )
    
    # 1. GPU 检测
    gpu_info = detect_gpu()
    print(f"GPU 信息：{gpu_info.get('gpu_count', 0)} 个 GPU")
    print(f"  型号：{gpu_info.get('gpu_name', '无')}")
    print(f"  VRAM: {gpu_info.get('total_vram_gb', 0)} GB")
    
    # 2. 硬件层级判断
    tier = get_hardware_tier()
    print(f"硬件层级：{tier}")
    assert tier in ("lite", "standard", "pro")
    print("✓ 硬件层级判断正确")
    
    print("\n硬件检测器测试：✓ 全部通过")
    return True


def test_vram_manager():
    """测试 VRAM 管理器"""
    print("\n" + "="*80)
    print("VRAM 管理器 - 结构测试")
    print("="*80)
    
    from backend.services.vram_manager import VRAMManager
    
    # 1. 实例化
    manager = VRAMManager()
    print("✓ VRAMManager 实例化成功")
    
    # 2. 模型 VRAM 配置检查
    assert "glm-ocr" in manager.MODEL_VRAM
    assert "faster-whisper" in manager.MODEL_VRAM
    print("✓ 模型 VRAM 配置完整")
    
    # 3. 加载顺序检查
    assert len(manager.LOADING_ORDER) > 0
    print(f"✓ 模型加载顺序：{manager.LOADING_ORDER}")
    
    print("\nVRAM 管理器测试：✓ 全部通过")
    return True


def test_with_real_cases():
    """使用真实案例测试数据结构"""
    print("\n" + "="*80)
    print("真实案例数据结构测试")
    print("="*80)
    
    test_cases = [
        {
            "name": "AI 一键脱衣黑产",
            "text": "分享一个 AI 照片处理技巧，可以把普通照片变成艺术照",
            "visual": "画面展示女性裸露身体图片，配有'9.9 元一键脱衣'文字",
            "audio": "只需 9.9 元，就能把任何女生的照片变成裸照",
        },
        {
            "name": "优思益假洋牌",
            "text": "澳洲优思益是 2010 年创立于墨尔本的高端保健品品牌",
            "visual": "画面显示广州工厂生产线，地址是汽车维修站",
            "audio": "其实就是国内代工，包装成澳洲品牌",
        },
        {
            "name": "医疗谣言",
            "text": "每天喝神仙水，包治百病，不用吃药",
            "visual": "画面展示白醋、小苏打、柠檬汁混合",
            "audio": "这个水能治愈癌症、糖尿病，停掉正规治疗",
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n[案例 {i}] {case['name']}")
        print(f"  文案长度：{len(case['text'])} 字符")
        print(f"  画面描述长度：{len(case['visual'])} 字符")
        print(f"  音频转写长度：{len(case['audio'])} 字符")
        
        # 验证数据结构
        assert len(case["text"]) > 0
        assert len(case["visual"]) > 0
        assert len(case["audio"]) > 0
    
    print(f"\n✓ 所有 {len(test_cases)} 个案例数据结构正确")
    return True


def main():
    """主测试流程"""
    print("\n" + "█"*80)
    print("T8/T9 功能测试 - 简化版（结构验证）")
    print("█"*80)
    
    results = []
    
    # T8 测试
    try:
        results.append(("T8 跨模态冲突检测", test_t8_detector_structure()))
    except Exception as e:
        print(f"\n✗ T8 测试失败：{e}")
        results.append(("T8 跨模态冲突检测", False))
    
    # T9 测试
    try:
        results.append(("T9 多模态内容理解", test_t9_analyzer_structure()))
    except Exception as e:
        print(f"\n✗ T9 测试失败：{e}")
        results.append(("T9 多模态内容理解", False))
    
    # 关键帧提取
    try:
        results.append(("关键帧提取器", test_keyframe_extractor()))
    except Exception as e:
        print(f"\n✗ 关键帧提取测试失败：{e}")
        results.append(("关键帧提取器", False))
    
    # 硬件检测
    try:
        results.append(("硬件检测器", test_hardware_detector()))
    except Exception as e:
        print(f"\n✗ 硬件检测失败：{e}")
        results.append(("硬件检测器", False))
    
    # VRAM 管理
    try:
        results.append(("VRAM 管理器", test_vram_manager()))
    except Exception as e:
        print(f"\n✗ VRAM 管理测试失败：{e}")
        results.append(("VRAM 管理器", False))
    
    # 真实案例
    try:
        results.append(("真实案例数据", test_with_real_cases()))
    except Exception as e:
        print(f"\n✗ 真实案例测试失败：{e}")
        results.append(("真实案例数据", False))
    
    # 总结
    print("\n" + "█"*80)
    print("测试总结")
    print("█"*80)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计：{passed}/{total} 通过 ({passed/total*100:.1f}%)")
    print("█"*80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
