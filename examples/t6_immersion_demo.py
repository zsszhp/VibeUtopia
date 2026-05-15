"""
T6 平台信息浸泡系统 - 使用示例

演示如何使用平台浸泡系统 API。
"""

import asyncio
import json
import aiohttp


SAMPLE_PERSONA = {
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


async def create_hot_topic(session, title, platform, category, tags, keywords, sentiment="neutral"):
    """创建热点话题"""
    url = "http://localhost:8000/api/v1/hot-topics"
    payload = {
        "title": title,
        "platform": platform,
        "category": category,
        "tags": tags,
        "keywords": keywords,
        "sentiment": sentiment,
    }
    
    async with session.post(url, json=payload) as response:
        result = await response.json()
        print(f"✓ 创建热点话题：{title}")
        return result


async def list_hot_topics(session):
    """查询热点话题列表"""
    url = "http://localhost:8000/api/v1/hot-topics"
    
    async with session.get(url) as response:
        result = await response.json()
        print(f"✓ 查询到 {result.get('total', 0)} 个热点话题")
        return result


async def create_immersion(session, agent_id, persona, immersion_days=7, posts_per_day=20):
    """创建浸泡任务"""
    url = "http://localhost:8000/api/v1/immersion/create"
    payload = {
        "agent_id": agent_id,
        "persona_json": json.dumps(persona),
        "immersion_days": immersion_days,
        "posts_per_day": posts_per_day,
    }
    
    async with session.post(url, json=payload) as response:
        result = await response.json()
        print(f"✓ 创建浸泡任务完成: {result.get('immersion_id')}")
        return result


async def get_immersion_result(session, immersion_id):
    """查询浸泡结果"""
    url = f"http://localhost:8000/api/v1/immersion/{immersion_id}"
    
    async with session.get(url) as response:
        result = await response.json()
        print(f"✓ 浸泡结果：状态={result.get('status')}, 分数={result.get('immersion_score')}")
        return result


async def get_immersion_history(session, agent_id):
    """查询浸泡历史"""
    url = f"http://localhost:8000/api/v1/agent/{agent_id}/immersion/history"
    
    async with session.get(url) as response:
        result = await response.json()
        print(f"✓ 浸泡历史：{len(result.get('history', []))} 条记录")
        return result


async def main():
    """主流程演示"""
    print("=" * 60)
    print("T6 平台信息浸泡系统 - 使用示例")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # Step 1: 创建热点话题
        print("\n1. 创建热点话题...")
        await create_hot_topic(
            session,
            title="AI 伦理争议：某大厂大模型被指歧视女性",
            platform="weibo",
            category="科技",
            tags=["科技伦理", "女性权益"],
            keywords=["AI", "伦理", "性别歧视", "大模型"],
            sentiment="negative",
        )
        
        await create_hot_topic(
            session,
            title="B 站 UP 主集体抗议平台创作激励政策调整",
            platform="bilibili",
            category="社会",
            tags=["创作者经济"],
            keywords=["B 站", "UP 主", "创作激励", "抗议"],
            sentiment="negative",
        )
        
        await create_hot_topic(
            session,
            title="知乎热议：35 岁程序员失业现象背后的社会问题",
            platform="zhihu",
            category="社会",
            tags=["就业", "互联网从业者"],
            keywords=["程序员", "失业", "年龄歧视", "互联网"],
            sentiment="negative",
        )
        
        # Step 2: 查询热点话题列表
        print("\n2. 查询热点话题列表...")
        topics_result = await list_hot_topics(session)
        
        # Step 3: 创建浸泡任务
        print("\n3. 创建浸泡任务...")
        immersion_result = await create_immersion(
            session,
            agent_id="agent_demo_001",
            persona=SAMPLE_PERSONA,
            immersion_days=7,
            posts_per_day=20,
        )
        
        immersion_id = immersion_result.get("immersion_id")
        
        # Step 4: 查询浸泡结果
        print("\n4. 查询浸泡结果...")
        result = await get_immersion_result(session, immersion_id)
        
        # 输出详细信息
        print(f"\n浸泡详情:")
        print(f"  - 吸收话题数：{result.get('absorbed_count', 0)}")
        print(f"  - 形成态度数：{result.get('attitudes_count', 0)}")
        print(f"  - 浸泡分数：{result.get('immersion_score', 0):.3f}")
        print(f"  - 配置：{result.get('config', {})}")
        
        # Step 5: 查询浸泡历史
        print("\n5. 查询浸泡历史...")
        await get_immersion_history(session, "agent_demo_001")
        
        print("\n" + "=" * 60)
        print("演示完成!")
        print("=" * 60)


if __name__ == "__main__":
    print("\n提示：请确保后端服务已启动 (python backend/main.py)")
    print("按 Enter 键开始演示，或 Ctrl+C 退出...")
    
    try:
        input()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已退出")
