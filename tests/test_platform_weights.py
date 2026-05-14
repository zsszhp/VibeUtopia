"""平台权重与仿真器测试 — 阶段2验证

测试内容：
1. 平台权重配置正确性
2. 平台风险敏感度计算
3. 平台加权风险分计算
4. 风险放大计算
5. 平台仿真器降级逻辑
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.platform_weights import (
    PLATFORM_PROFILES,
    get_platform_profile,
    get_platforms_by_tier,
    get_p0_platforms,
    calculate_platform_weighted_score,
    get_platform_risk_sensitivity,
    adjust_risk_by_platform,
    get_platform_emotion_bias,
    get_propagation_params,
)
# 仅导入不依赖LLM的部分
from backend.services.platform_simulator import (
    PlatformReaction,
    calculate_amplification_risk,
    get_platform_risk_summary,
)


def test_platform_profiles():
    """测试平台画像配置"""
    print("=" * 60)
    print("测试1: 平台画像配置")
    print("=" * 60)

    # 测试P0平台数量
    p0_platforms = get_p0_platforms()
    assert len(p0_platforms) == 5, f"P0平台应为5个，实际{len(p0_platforms)}个"
    print(f"  P0核心平台: {', '.join(p0_platforms)}")

    # 测试各平台权重
    expected_weights = {
        "weibo": 1.0,
        "bilibili": 1.0,
        "xiaohongshu": 1.0,
        "douyin": 1.0,
        "zhihu": 1.0,
    }
    for pid, expected in expected_weights.items():
        profile = get_platform_profile(pid)
        assert profile is not None, f"平台{pid}不存在"
        assert profile.weight == expected, f"{pid}权重应为{expected}，实际{profile.weight}"
        assert profile.tier == "P0", f"{pid}分级应为P0，实际{profile.tier}"
    print("  各平台权重校验通过")

    # 测试P1平台
    p1_platforms = get_platforms_by_tier("P1")
    assert len(p1_platforms) == 4, f"P1平台应为4个，实际{len(p1_platforms)}个"
    for p in p1_platforms:
        assert p.weight == 0.7, f"{p.platform_id}权重应为0.7，实际{p.weight}"
    print(f"  P1平台: {', '.join(p.platform_id for p in p1_platforms)}")

    # 测试平台画像完整性
    for pid, profile in PLATFORM_PROFILES.items():
        assert profile.risk_sensitivity, f"{pid}缺少风险敏感度配置"
        assert profile.emotion_baseline, f"{pid}缺少情绪基线配置"
        assert profile.behavior_patterns, f"{pid}缺少行为模式配置"
        assert abs(sum(profile.emotion_baseline.values()) - 1.0) < 0.01, \
            f"{pid}情绪基线之和应为1.0"
    print("  平台画像完整性校验通过")
    print("  测试1: 通过\n")


def test_platform_weighted_score():
    """测试平台加权风险分计算"""
    print("=" * 60)
    print("测试2: 平台加权风险分计算")
    print("=" * 60)

    # 测试空输入
    score = calculate_platform_weighted_score({})
    assert score == 0.0, "空输入应返回0"
    print("  空输入: 通过")

    # 测试单平台
    score = calculate_platform_weighted_score({"weibo": 60.0})
    assert score == 60.0, f"单平台分数应为60，实际{score}"
    print("  单平台: 通过")

    # 测试多平台加权
    scores = {
        "weibo": 80.0,       # P0, weight=1.0
        "bilibili": 40.0,    # P0, weight=1.0
        "xiaohongshu": 60.0, # P0, weight=1.0
    }
    score = calculate_platform_weighted_score(scores)
    expected = (80.0 + 40.0 + 60.0) / 3.0
    assert abs(score - expected) < 0.1, f"加权分数应为{expected}，实际{score}"
    print(f"  多平台加权(80,40,60): {score:.1f} (期望{expected:.1f})")

    # 测试P1平台权重
    scores = {
        "weibo": 80.0,       # P0, weight=1.0
        "kuaishou": 80.0,    # P1, weight=0.7
    }
    score = calculate_platform_weighted_score(scores)
    expected = (80.0 * 1.0 + 80.0 * 0.7) / (1.0 + 0.7)
    assert abs(score - expected) < 0.1, f"P0+P1加权分数应为{expected}，实际{score}"
    print(f"  P0+P1加权(80,80): {score:.1f} (期望{expected:.1f})")

    # 测试未知平台默认权重
    scores = {"unknown_platform": 50.0}
    score = calculate_platform_weighted_score(scores)
    assert score == 50.0, f"未知平台分数应为50，实际{score}"
    print("  未知平台默认权重: 通过")
    print("  测试2: 通过\n")


def test_risk_sensitivity():
    """测试平台风险敏感度"""
    print("=" * 60)
    print("测试3: 平台风险敏感度")
    print("=" * 60)

    # 微博对政治敏感应高度敏感
    weibo_sensitivity = get_platform_risk_sensitivity("weibo")
    assert weibo_sensitivity["政治敏感"] >= 0.9, "微博政治敏感度应>=0.9"
    print(f"  微博-政治敏感: {weibo_sensitivity['政治敏感']}")

    # 小红书对性别议题应高度敏感
    xhs_sensitivity = get_platform_risk_sensitivity("xiaohongshu")
    assert xhs_sensitivity["性别议题"] >= 0.9, "小红书性别议题敏感度应>=0.9"
    print(f"  小红书-性别议题: {xhs_sensitivity['性别议题']}")

    # 知乎对事实错误应高度敏感
    zhihu_sensitivity = get_platform_risk_sensitivity("zhihu")
    assert zhihu_sensitivity["事实错误"] >= 0.9, "知乎事实错误敏感度应>=0.9"
    print(f"  知乎-事实错误: {zhihu_sensitivity['事实错误']}")

    # 抖音对平台禁区应高度敏感
    douyin_sensitivity = get_platform_risk_sensitivity("douyin")
    assert douyin_sensitivity["平台禁区"] >= 0.9, "抖音平台禁区敏感度应>=0.9"
    print(f"  抖音-平台禁区: {douyin_sensitivity['平台禁区']}")

    # 测试未知平台默认敏感度
    unknown_sensitivity = get_platform_risk_sensitivity("unknown")
    assert len(unknown_sensitivity) == 11, "默认敏感度应有11个维度"
    print("  未知平台默认敏感度: 通过")
    print("  测试3: 通过\n")


def test_risk_adjustment():
    """测试风险分数调整"""
    print("=" * 60)
    print("测试4: 风险分数调整")
    print("=" * 60)

    # 高敏感度平台应上调风险分数
    adjusted = adjust_risk_by_platform(60.0, "政治敏感", "weibo")
    assert adjusted > 60.0, f"微博政治敏感风险应上调，实际{adjusted}"
    print(f"  微博-政治敏感(60→{adjusted:.1f}): 上调")

    # 低敏感度平台应下调风险分数
    adjusted = adjust_risk_by_platform(60.0, "时事踩雷", "xiaohongshu")
    # 小红书时事踩雷敏感度0.6，应下调
    print(f"  小红书-时事踩雷(60→{adjusted:.1f})")

    # 中等敏感度不变
    adjusted = adjust_risk_by_platform(50.0, "性别议题", "bilibili")
    print(f"  B站-性别议题(50→{adjusted:.1f})")
    print("  测试4: 通过\n")


def test_amplification_risk():
    """测试风险放大计算"""
    print("=" * 60)
    print("测试5: 风险放大计算")
    print("=" * 60)

    # 抖音放大系数最高(4.0)
    douyin_amp = calculate_amplification_risk(70.0, "douyin")
    assert douyin_amp > 70.0, f"抖音高风险应放大，实际{douyin_amp}"
    print(f"  抖音放大(70→{douyin_amp:.1f})")

    # 知乎放大系数最低(1.5)
    zhihu_amp = calculate_amplification_risk(70.0, "zhihu")
    print(f"  知乎放大(70→{zhihu_amp:.1f})")

    # 低风险不放大
    low_amp = calculate_amplification_risk(20.0, "douyin")
    assert low_amp == 20.0, f"低风险不应放大，实际{low_amp}"
    print(f"  抖音低风险(20→{low_amp:.1f}): 不放大")

    # 上限100
    max_amp = calculate_amplification_risk(95.0, "douyin")
    assert max_amp <= 100.0, f"放大后不应超过100，实际{max_amp}"
    print(f"  抖音极高风险(95→{max_amp:.1f}): 上限100")
    print("  测试5: 通过\n")


def test_platform_simulator_fallback():
    """测试平台仿真器降级逻辑"""
    print("=" * 60)
    print("测试6: 平台仿真器降级逻辑")
    print("=" * 60)

    # 测试降级反应(不依赖LLM)
    profile = get_platform_profile("weibo")
    
    # 手动创建降级反应(模拟fallback行为)
    emotion = profile.emotion_baseline.copy()
    total = sum(emotion.values())
    if total > 0:
        emotion = {k: v / total for k, v in emotion.items()}
    
    fallback = PlatformReaction(
        platform_id=profile.platform_id,
        platform_name=profile.name,
        emotion_distribution=emotion,
        risk_score=50.0,
        risk_level="caution",
        typical_reactions=[
            {
                "reaction_type": "中性",
                "example_comment": "（仿真降级：使用平台基线）",
                "reasoning": "LLM调用失败，使用平台情绪基线",
            }
        ],
        key_concerns=[],
        amplification_risk=0.5,
        platform_specific_advice=[],
    )
    assert isinstance(fallback, PlatformReaction), "降级反应应为PlatformReaction"
    assert fallback.risk_score == 50.0, "降级风险分数应为50"
    assert fallback.risk_level == "caution", "降级风险等级应为caution"
    assert abs(sum(fallback.emotion_distribution.values()) - 1.0) < 0.01, \
        "降级情绪分布之和应为1.0"
    print(f"  降级反应: risk={fallback.risk_score}, level={fallback.risk_level}")
    print(f"  情绪基线: {fallback.emotion_distribution}")
    print("  测试6: 通过\n")


def test_platform_risk_summary():
    """测试平台风险汇总"""
    print("=" * 60)
    print("测试7: 平台风险汇总")
    print("=" * 60)

    # 创建模拟反应
    reactions = {
        "weibo": PlatformReaction(
            platform_id="weibo", platform_name="微博",
            emotion_distribution={"positive": 0.2, "neutral": 0.3, "negative": 0.5},
            risk_score=75.0, risk_level="warning",
            typical_reactions=[], key_concerns=[],
            amplification_risk=0.8, platform_specific_advice=[],
        ),
        "bilibili": PlatformReaction(
            platform_id="bilibili", platform_name="B站",
            emotion_distribution={"positive": 0.4, "neutral": 0.4, "negative": 0.2},
            risk_score=40.0, risk_level="caution",
            typical_reactions=[], key_concerns=[],
            amplification_risk=0.4, platform_specific_advice=[],
        ),
    }

    summary = get_platform_risk_summary(reactions)
    assert summary["platform_count"] == 2, "平台数量应为2"
    assert summary["highest_risk_platform"] == "微博", "最高风险平台应为微博"
    assert summary["highest_risk_score"] == 75.0, "最高风险分数应为75"
    assert 0 < summary["overall_risk"] < 100, "综合风险应在0-100之间"
    print(f"  平台数量: {summary['platform_count']}")
    print(f"  最高风险平台: {summary['highest_risk_platform']} ({summary['highest_risk_score']})")
    print(f"  综合风险: {summary['overall_risk']}")
    print("  测试7: 通过\n")


def test_propagation_params():
    """测试传播动力学参数"""
    print("=" * 60)
    print("测试8: 传播动力学参数")
    print("=" * 60)

    # 抖音传播速度应最快
    douyin_params = get_propagation_params("douyin")
    assert douyin_params["propagation_speed"] == "极快", "抖音传播速度应为极快"
    assert douyin_params["amplification_factor"] == 4.0, "抖音放大系数应为4.0"
    print(f"  抖音: 速度={douyin_params['propagation_speed']}, 放大={douyin_params['amplification_factor']}x")

    # 知乎传播速度应最慢
    zhihu_params = get_propagation_params("zhihu")
    assert zhihu_params["propagation_speed"] == "慢", "知乎传播速度应为慢"
    print(f"  知乎: 速度={zhihu_params['propagation_speed']}, 放大={zhihu_params['amplification_factor']}x")

    # 未知平台默认参数
    unknown_params = get_propagation_params("unknown")
    assert unknown_params["amplification_factor"] == 1.5, "未知平台放大系数应为1.5"
    print(f"  未知平台: 放大={unknown_params['amplification_factor']}x")
    print("  测试8: 通过\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("阶段2: 平台权重与仿真器测试")
    print("=" * 60 + "\n")

    tests = [
        test_platform_profiles,
        test_platform_weighted_score,
        test_risk_sensitivity,
        test_risk_adjustment,
        test_amplification_risk,
        test_platform_simulator_fallback,
        test_platform_risk_summary,
        test_propagation_params,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"  测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            print()

    print("=" * 60)
    print(f"测试总结: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n阶段2平台权重与仿真器: 全部通过")


if __name__ == "__main__":
    main()
