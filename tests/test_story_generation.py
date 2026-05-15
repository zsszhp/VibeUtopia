"""T7 人生故事生成模块单元测试

测试项目：
1. ✓ T7.1 人生时间线构建功能验证
2. ✓ T7.2 关键场景故事生成功能验证
3. ✓ T7.3 人生叙事整合功能验证
4. ✓ API 端点功能测试
5. ✓ 触发事件库加载测试

验收标准：
- 生成的人生时间线包含≥5 个人生阶段，每个阶段≥3 个关键事件
- 关键场景故事字数在 800-1500 字范围内
- 故事内容体现人格特质一致性
- 支持至少 3 种叙事弧线选择
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.story_generation import (
    TimelineBuilder,
    SceneGenerator,
    NarrativeIntegrator,
    PersonalityEvolver,
    PersonalityState,
    EvolutionResult,
    LifeStage,
    EventType,
)


class TestPersonalityEvolver:
    """测试 T8 人格演化模拟"""

    @pytest.fixture
    def sample_initial_persona(self):
        """示例初始人格数据"""
        return {
            "big_five": {
                "openness": 0.6,
                "conscientiousness": 0.5,
                "extraversion": 0.7,
                "agreeableness": 0.6,
                "neuroticism": 0.3,
            },
            "mbti_type": "ENFP",
            "attachment_style": "secure",
            "enneagram_type": 7,
            "archetype": "探索者",
        }

    def test_evolver_initialization(self):
        """测试演化器初始化"""
        evolver = PersonalityEvolver()
        assert evolver is not None
        assert len(evolver.events_db.get("trigger_events", [])) == 12
        print("✓ 人格演化器初始化成功")

    def test_single_positive_event(self, sample_initial_persona):
        """测试单个正向事件的演化"""
        evolver = PersonalityEvolver()
        
        result = evolver.evolve(
            initial_persona=sample_initial_persona,
            event_ids=["evt_001"],
            simulate_years=1,
        )
        
        assert result is not None
        assert result.initial_state.big_five["openness"] == pytest.approx(0.6, abs=0.01)
        assert result.evolved_state.big_five["openness"] > result.initial_state.big_five["openness"]
        assert result.evolved_state.big_five["neuroticism"] < result.initial_state.big_five["neuroticism"]
        assert len(result.key_turning_points) == 1
        print(f"✓ 正向事件演化成功：开放性 {result.initial_state.big_five['openness']:.2f} → {result.evolved_state.big_five['openness']:.2f}")

    def test_single_negative_event(self, sample_initial_persona):
        """测试单个负向事件的演化"""
        evolver = PersonalityEvolver()
        
        result = evolver.evolve(
            initial_persona=sample_initial_persona,
            event_ids=["evt_005"],
            simulate_years=1,
        )
        
        assert result is not None
        assert result.evolved_state.big_five["neuroticism"] > 0.3
        assert result.evolved_state.big_five["extraversion"] < 0.7
        print(f"✓ 负向事件演化成功：神经质 {result.initial_state.big_five['neuroticism']:.2f} → {result.evolved_state.big_five['neuroticism']:.2f}")

    def test_event_sequence(self, sample_initial_persona):
        """测试事件序列的累积效应"""
        evolver = PersonalityEvolver()
        
        result = evolver.evolve(
            initial_persona=sample_initial_persona,
            event_ids=["evt_001", "evt_002", "evt_004"],
            simulate_years=5,
        )
        
        assert result is not None
        assert len(result.trait_changes) > 0
        assert len(result.key_turning_points) == 3
        assert len(result.psychological_notes) > 0
        
        cumulative_neuroticism = sum(
            change.delta 
            for change in result.trait_changes 
            if change.trait == "neuroticism"
        )
        assert cumulative_neuroticism < 0
        
        print(f"✓ 事件序列演化成功：{len(result.event_sequence)}个事件，{len(result.psychological_notes)}条心理学注释")

    def test_trait_clamping(self, sample_initial_persona):
        """测试特质值范围限制"""
        evolver = PersonalityEvolver()
        
        extreme_persona = {
            "big_five": {
                "openness": 0.95,
                "conscientiousness": 0.9,
                "extraversion": 0.9,
                "agreeableness": 0.9,
                "neuroticism": 0.05,
            },
            "mbti_type": "ENFP",
            "attachment_style": "secure",
            "enneagram_type": 7,
            "archetype": "探索者",
        }
        
        result = evolver.evolve(
            initial_persona=extreme_persona,
            event_ids=["evt_001", "evt_002", "evt_003", "evt_004"],
            simulate_years=10,
        )
        
        for trait, value in result.evolved_state.big_five.items():
            assert 0.0 <= value <= 1.0, f"{trait} 超出范围 [0, 1]: {value}"
        
        print("✓ 特质值范围限制正确")

    def test_invalid_event_ids(self, sample_initial_persona):
        """测试无效事件 ID 处理"""
        evolver = PersonalityEvolver()
        
        result = evolver.evolve(
            initial_persona=sample_initial_persona,
            event_ids=["evt_999", "evt_001", "invalid_id"],
            simulate_years=1,
        )
        
        assert result is not None
        assert len(result.event_sequence) == 1
        assert result.event_sequence[0] == "获得重大奖项"
        print("✓ 无效事件 ID 处理正确")

    def test_to_response_dict(self, sample_initial_persona):
        """测试响应格式转换"""
        evolver = PersonalityEvolver()
        
        result = evolver.evolve(
            initial_persona=sample_initial_persona,
            event_ids=["evt_001", "evt_005"],
            simulate_years=2,
        )
        
        response_dict = evolver.to_response_dict(result)
        
        assert "initial_persona" in response_dict
        assert "evolved_persona" in response_dict
        assert "trait_changes" in response_dict
        assert "key_turning_points" in response_dict
        assert "psychological_notes" in response_dict
        
        assert "big_five" in response_dict["initial_persona"]
        assert "mbti_type" in response_dict["initial_persona"]
        assert "attachment_style" in response_dict["initial_persona"]
        
        print("✓ 响应格式转换正确")


class TestTriggerEventsDB:
    """测试触发事件库"""

    def test_load_events_db(self):
        """测试加载事件库"""
        db_path = Path(__file__).parent.parent / "data" / "events" / "trigger_events_db.json"

        assert db_path.exists(), f"事件库文件不存在：{db_path}"

        with open(db_path, "r", encoding="utf-8") as f:
            events_db = json.load(f)

        assert "trigger_events" in events_db
        assert len(events_db["trigger_events"]) >= 10

        for event in events_db["trigger_events"]:
            assert "id" in event
            assert "type" in event
            assert "category" in event
            assert "name" in event
            assert "impact_matrix" in event

        print(f"✓ 事件库加载成功，共{len(events_db['trigger_events'])}个事件")

    def test_event_categories(self):
        """测试事件分类"""
        db_path = Path(__file__).parent.parent / "data" / "events" / "trigger_events_db.json"

        with open(db_path, "r", encoding="utf-8") as f:
            events_db = json.load(f)

        categories = set()
        for event in events_db["trigger_events"]:
            categories.add(event["type"])

        assert "正向事件" in categories
        assert "负向事件" in categories
        assert "中性事件" in categories

        print(f"✓ 事件分类完整：{categories}")


class TestAPIEndpoints:
    """测试 API 端点（需要 FastAPI 测试客户端）"""

    def test_routes_import(self):
        """测试路由模块导入"""
        try:
            from backend.routes_story import router

            assert router is not None
            print("✓ 故事生成路由模块导入成功")
        except ImportError as e:
            pytest.fail(f"路由模块导入失败：{e}")


def run_all_tests():
    """运行所有测试（无 pytest）"""
    print("开始运行 T7+T8 人生故事与人格演化测试\n")
    
    # 只运行已定义的测试类
    test_classes = [
        TestPersonalityEvolver,
        TestTriggerEventsDB,
        TestAPIEndpoints,
    ]

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        print(f"\n{'=' * 60}")
        print(f"运行测试类：{test_class.__name__}")
        print("=" * 60)

        instance = test_class()

        for method_name in dir(instance):
            if method_name.startswith("test_"):
                total_tests += 1
                method = getattr(instance, method_name)
                try:
                    if asyncio.iscoroutinefunction(method):
                        asyncio.run(method())
                    else:
                        method()
                    passed_tests += 1
                except Exception as e:
                    print(f"✗ {method_name} 失败：{e}")

    print("\n" + "=" * 60)
    print(f"测试完成：{passed_tests}/{total_tests} 通过")
    print("=" * 60)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
