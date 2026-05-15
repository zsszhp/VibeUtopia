"""
T6 平台信息浸泡系统测试
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.platform_immersion import PlatformImmersion
from backend.models import HotTopic, ImmersionRecord
from backend.database import SessionLocal, engine, Base


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_persona():
    return {
        "layer1_demographics": {
            "age": 28,
            "gender": "female",
            "location": "上海",
            "occupation": "互联网从业者",
        },
        "layer2_values": {
            "worldview": "进步主义",
            "moral_foundation": "关爱/公平",
            "social_stances": ["女性权益", "科技向善", "环境保护"],
        },
        "layer3_knowledge": {
            "expertise": ["人工智能", "社交媒体", "科技伦理"],
            "info_sources": ["知乎", "微博", "少数派"],
            "cognitive_blindspots": ["游戏", "娱乐八卦"],
        },
        "layer4_memory": {
            "formative_events": ["2019 年参与#MeToo 运动", "2022 年见证 AI 爆发"],
        },
        "layer5_identity": {
            "narrative": "从传统行业转型 AI 的产品经理，关注技术对社会的影响",
        },
        "layer6_social": {
            "influence_level": 0.7,
            "network_size": 5000,
        },
        "layer7_behavior": {
            "posting_frequency": 0.6,
            "engagement_style": "理性讨论",
        },
    }


@pytest.fixture
def sample_hot_topics():
    return [
        {
            "topic_id": "hot_001",
            "title": "AI 伦理争议：某大厂大模型被指歧视女性",
            "platform": "weibo",
            "category": "科技",
            "keywords": ["AI", "伦理", "性别歧视", "大模型"],
            "tags": ["科技伦理", "女性权益"],
            "sentiment": "negative",
        },
        {
            "topic_id": "hot_002",
            "title": "B 站 UP 主集体抗议平台创作激励政策调整",
            "platform": "bilibili",
            "category": "社会",
            "keywords": ["B 站", "UP 主", "创作激励", "抗议"],
            "tags": ["创作者经济"],
            "sentiment": "negative",
        },
        {
            "topic_id": "hot_003",
            "title": "知乎热议：35 岁程序员失业现象背后的社会问题",
            "platform": "zhihu",
            "category": "社会",
            "keywords": ["程序员", "失业", "年龄歧视", "互联网"],
            "tags": ["就业", "互联网从业者"],
            "sentiment": "negative",
        },
        {
            "topic_id": "hot_004",
            "title": "小红书美妆博主推荐国货崛起",
            "platform": "xiaohongshu",
            "category": "美妆",
            "keywords": ["美妆", "国货", "博主推荐"],
            "tags": ["消费", "国货"],
            "sentiment": "positive",
        },
        {
            "topic_id": "hot_005",
            "title": "抖音神曲洗脑现象引发文化讨论",
            "platform": "douyin",
            "category": "文化",
            "keywords": ["抖音", "神曲", "文化", "洗脑"],
            "tags": ["娱乐", "文化"],
            "sentiment": "neutral",
        },
    ]


async def test_platform_immersion_basic(sample_persona, sample_hot_topics):
    """测试平台浸泡基本功能"""
    immersion = PlatformImmersion()
    
    with patch.object(immersion, '_infer_initial_stance', new_callable=AsyncMock) as mock_stance:
        mock_stance.return_value = {
            "attitude": "concerned",
            "reasoning": "基于人格特征推理出的态度",
            "emotional_intensity": 0.7,
        }
        
        result = await immersion.immerse(
            agent_id="agent_test_001",
            persona=sample_persona,
            hot_topics=sample_hot_topics,
            immersion_days=7,
            posts_per_day=20,
            db=None,
        )
        
        assert result["status"] == "completed"
        assert result["agent_id"] == "agent_test_001"
        assert "immersion_id" in result
        assert result["absorbed_count"] > 0
        assert result["attitudes_count"] > 0
        assert 0 <= result["immersion_score"] <= 1.0


def test_attention_probability_calculation(sample_persona, sample_hot_topics):
    """测试关注度概率计算"""
    immersion = PlatformImmersion()
    
    ai_ethics_topic = sample_hot_topics[0]
    beauty_topic = sample_hot_topics[3]
    
    prob_ai = immersion._calc_attention_probability(sample_persona, ai_ethics_topic)
    prob_beauty = immersion._calc_attention_probability(sample_persona, beauty_topic)
    
    assert 0.0 <= prob_ai <= 1.0
    assert 0.0 <= prob_beauty <= 1.0
    assert prob_ai > prob_beauty


async def test_initial_stance_inference(sample_persona, sample_hot_topics):
    """测试初始态度推理"""
    immersion = PlatformImmersion()
    
    with patch.object(immersion.llm_client, 'chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = MagicMock(
            choices=[MagicMock(
                message=MagicMock(
                    content='{"attitude": "concerned", "reasoning": "测试原因", "emotional_intensity": 0.7}'
                )
            )]
        )
        
        result = await immersion._infer_initial_stance(sample_persona, sample_hot_topics[0])
        
        assert "attitude" in result
        assert "reasoning" in result
        assert "emotional_intensity" in result
        assert 0.0 <= result["emotional_intensity"] <= 1.0


def test_immersion_score_calculation(sample_persona):
    """测试浸泡分数计算"""
    immersion = PlatformImmersion()
    
    absorbed = [{"topic_id": f"t{i}"} for i in range(10)]
    attitudes = [
        {"emotional_intensity": 0.8},
        {"emotional_intensity": 0.6},
        {"emotional_intensity": 0.9},
        {"emotional_intensity": 0.5},
        {"emotional_intensity": 0.7},
    ]
    
    score = immersion._calc_immersion_score(absorbed, attitudes, days=7)
    
    assert 0.0 <= score <= 1.0


async def test_platform_immersion_with_db(db_session, sample_persona, sample_hot_topics):
    """测试平台浸泡数据库操作"""
    for topic_data in sample_hot_topics:
        topic = HotTopic(
            topic_id=topic_data["topic_id"],
            title=topic_data["title"],
            platform=topic_data["platform"],
            category=topic_data.get("category"),
            tags=json.dumps(topic_data.get("tags", [])),
            keywords=json.dumps(topic_data.get("keywords", [])),
            sentiment=topic_data.get("sentiment", "neutral"),
        )
        db_session.add(topic)
    db_session.commit()
    
    immersion = PlatformImmersion()
    
    with patch.object(immersion, '_infer_initial_stance', new_callable=AsyncMock) as mock_stance:
        mock_stance.return_value = {
            "attitude": "concerned",
            "reasoning": "基于人格特征推理出的态度",
            "emotional_intensity": 0.7,
        }
        
        result = await immersion.immerse(
            agent_id="agent_db_test_001",
            persona=sample_persona,
            hot_topics=sample_hot_topics,
            immersion_days=7,
            posts_per_day=20,
            db=db_session,
        )
        
        assert result["status"] == "completed"
        
        immersion_record = db_session.query(ImmersionRecord).filter(
            ImmersionRecord.agent_id == "agent_db_test_001"
        ).first()
        
        assert immersion_record is not None
        assert immersion_record.status == "completed"
        assert immersion_record.immersion_score > 0


async def test_get_immersion_result(db_session, sample_persona, sample_hot_topics):
    """测试查询浸泡结果"""
    immersion = PlatformImmersion()
    
    with patch.object(immersion, '_infer_initial_stance', new_callable=AsyncMock) as mock_stance:
        mock_stance.return_value = {
            "attitude": "concerned",
            "reasoning": "基于人格特征推理出的态度",
            "emotional_intensity": 0.7,
        }
        
        result = await immersion.immerse(
            agent_id="agent_query_test_001",
            persona=sample_persona,
            hot_topics=sample_hot_topics,
            immersion_days=7,
            posts_per_day=20,
            db=db_session,
        )
        
        immersion_id = result["immersion_id"]
        
        query_result = await immersion.get_immersion_result(immersion_id, db_session)
        
        assert query_result is not None
        assert query_result["immersion_id"] == immersion_id
        assert query_result["agent_id"] == "agent_query_test_001"
        assert query_result["status"] == "completed"


async def test_get_agent_immersion_history(db_session, sample_persona, sample_hot_topics):
    """测试查询 Agent 浸泡历史"""
    immersion = PlatformImmersion()
    
    with patch.object(immersion, '_infer_initial_stance', new_callable=AsyncMock) as mock_stance:
        mock_stance.return_value = {
            "attitude": "concerned",
            "reasoning": "基于人格特征推理出的态度",
            "emotional_intensity": 0.7,
        }
        
        for i in range(3):
            await immersion.immerse(
                agent_id="agent_history_test_001",
                persona=sample_persona,
                hot_topics=sample_hot_topics,
                immersion_days=7,
                posts_per_day=20,
                db=db_session,
            )
        
        history = await immersion.get_agent_immersion_history("agent_history_test_001", db_session)
        
        assert len(history) <= 10
        assert all("immersion_id" in h for h in history)
        assert all("status" in h for h in history)


def test_attention_by_expertise(sample_persona):
    """测试基于专业领域的关注度计算"""
    immersion = PlatformImmersion()
    
    ai_topic = {
        "topic_id": "ai_topic",
        "title": "AI 技术突破",
        "platform": "zhihu",
        "keywords": ["人工智能", "AI", "技术"],
        "tags": ["科技"],
    }
    
    game_topic = {
        "topic_id": "game_topic",
        "title": "新游戏发布",
        "platform": "bilibili",
        "keywords": ["游戏", "发布", "评测"],
        "tags": ["娱乐"],
    }
    
    prob_ai = immersion._calc_attention_probability(sample_persona, ai_topic)
    prob_game = immersion._calc_attention_probability(sample_persona, game_topic)
    
    assert prob_ai > prob_game


def test_attention_by_info_sources(sample_persona):
    """测试基于信息来源偏好的关注度计算"""
    immersion = PlatformImmersion()
    
    zhihu_topic = {
        "topic_id": "zhihu_topic",
        "title": "知乎热点",
        "platform": "zhihu",
        "keywords": ["社会"],
        "tags": ["社会"],
    }
    
    douyin_topic = {
        "topic_id": "douyin_topic",
        "title": "抖音热点",
        "platform": "douyin",
        "keywords": ["娱乐"],
        "tags": ["娱乐"],
    }
    
    prob_zhihu = immersion._calc_attention_probability(sample_persona, zhihu_topic)
    prob_douyin = immersion._calc_attention_probability(sample_persona, douyin_topic)
    
    assert prob_zhihu > prob_douyin


def test_attention_by_social_stances(sample_persona):
    """测试基于社会立场的关注度计算"""
    immersion = PlatformImmersion()
    
    feminist_topic = {
        "topic_id": "feminist_topic",
        "title": "女性权益相关话题",
        "platform": "weibo",
        "keywords": ["女性"],
        "tags": ["女性权益", "社会"],
    }
    
    neutral_topic = {
        "topic_id": "neutral_topic",
        "title": "中性话题",
        "platform": "weibo",
        "keywords": ["新闻"],
        "tags": ["新闻"],
    }
    
    prob_feminist = immersion._calc_attention_probability(sample_persona, feminist_topic)
    prob_neutral = immersion._calc_attention_probability(sample_persona, neutral_topic)
    
    assert prob_feminist > prob_neutral


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
