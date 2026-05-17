"""
T6 平台信息浸泡系统

Agent 初始化后模拟"刷平台"的过程，吸收当前热点，形成初始态度。
这确保 Agent 不是"白纸"进入仿真，而是带着对当前热点的认知和立场。
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import ImmersionRecord, HotTopic, AgentMemory
from backend.database import get_db
from backend.services.llm_client import router as model_router


class PlatformImmersion:
    """平台沉浸 - Agent 初始化后吸收当前热点"""

    def __init__(self):
        self.default_immersion_days = 7
        self.default_posts_per_day = 20

    async def immerse(
        self,
        agent_id: str,
        persona: dict,
        hot_topics: List[dict],
        immersion_days: int = 7,
        posts_per_day: int = 20,
        db: Optional[Session] = None,
    ) -> dict:
        """
        执行平台浸泡

        Args:
            agent_id: Agent ID
            persona: Agent 的 7 层人格数据
            hot_topics: 热点话题列表
            immersion_days: 浸泡天数 (默认 7 天)
            posts_per_day: 每天浏览帖子数 (默认 20 帖/天)
            db: 数据库会话

        Returns:
            浸泡结果字典
        """
        immersion_id = f"imm_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now(timezone.utc)

        record = ImmersionRecord(
            immersion_id=immersion_id,
            agent_id=agent_id,
            immersion_config=json.dumps({
                "days": immersion_days,
                "posts_per_day": posts_per_day,
            }),
            absorbed_topics="[]",
            initial_attitudes="[]",
            immersion_days=immersion_days,
            posts_per_day=posts_per_day,
            status="running",
        )

        if db:
            db.add(record)
            db.commit()

        try:
            absorbed = []
            attitudes = []
            attention_dist = {}

            for topic in hot_topics:
                attention_prob = self._calc_attention_probability(persona, topic)
                if random.random() < attention_prob:
                    absorbed.append({
                        "topic_id": topic.get("topic_id", ""),
                        "title": topic.get("title", ""),
                        "platform": topic.get("platform", ""),
                        "attention_prob": attention_prob,
                    })

                    platform = topic.get("platform", "unknown")
                    attention_dist[platform] = attention_dist.get(platform, 0) + 1

            for topic in hot_topics[:5]:
                stance_result = await self._infer_initial_stance(persona, topic)
                if stance_result:
                    attitudes.append({
                        "topic_id": topic.get("topic_id", ""),
                        "title": topic.get("title", ""),
                        "attitude": stance_result.get("attitude", "neutral"),
                        "reasoning": stance_result.get("reasoning", ""),
                        "emotional_intensity": stance_result.get("emotional_intensity", 0.5),
                    })

            immersion_score = self._calc_immersion_score(absorbed, attitudes, immersion_days)

            if db:
                memories = []
                for topic_data in absorbed:
                    memory_entry = AgentMemory(
                        memory_id=f"mem_{uuid.uuid4().hex[:12]}",
                        agent_id=agent_id,
                        memory_type="observation",
                        content=f"看到{topic_data['platform']}上的热点：{topic_data['title']}",
                        weight=1.0,
                        source_task_id=immersion_id,
                    )
                    memories.append(memory_entry)

                for attitude in attitudes:
                    memory_content = (
                        f"对{attitude['title']}的态度：{attitude['attitude']}, "
                        f"原因：{attitude['reasoning']}"
                    )
                    memory_entry = AgentMemory(
                        memory_id=f"mem_{uuid.uuid4().hex[:12]}",
                        agent_id=agent_id,
                        memory_type="observation",
                        content=memory_content,
                        weight=attitude.get("emotional_intensity", 0.5) * 10,
                        source_task_id=immersion_id,
                    )
                    memories.append(memory_entry)

                db.add_all(memories)

                record.absorbed_topics = json.dumps(absorbed)
                record.initial_attitudes = json.dumps(attitudes)
                record.immersion_score = immersion_score
                record.attention_distribution = json.dumps(attention_dist)
                record.status = "completed"
                record.completed_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(record)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            return {
                "immersion_id": immersion_id,
                "agent_id": agent_id,
                "status": "completed",
                "absorbed_count": len(absorbed),
                "attitudes_count": len(attitudes),
                "immersion_score": immersion_score,
                "duration_seconds": duration,
                "config": {
                    "days": immersion_days,
                    "posts_per_day": posts_per_day,
                },
            }

        except Exception as e:
            if db:
                record.status = "failed"
                record.error = str(e)
                db.commit()
            raise

    def _calc_attention_probability(self, persona: dict, topic: dict) -> float:
        """计算 Agent 对某话题的关注概率"""
        prob = 0.3

        layer3 = persona.get("layer3_knowledge", {})
        layer2 = persona.get("layer2_values", {})
        layer6 = persona.get("layer6_social", {})

        expertise = layer3.get("expertise", [])
        info_sources = layer3.get("info_sources", [])
        social_stances = layer2.get("social_stances", [])
        influence_level = layer6.get("influence_level", 0.5)

        topic_keywords = topic.get("keywords", [])
        topic_platform = topic.get("platform", "")
        topic_tags = topic.get("tags", [])

        if any(exp.lower() in str(topic_keywords).lower() for exp in expertise):
            prob += 0.3

        if topic_platform in info_sources:
            prob += 0.2

        if any(stance.lower() in str(topic_tags).lower() for stance in social_stances):
            prob += 0.2

        if influence_level > 0.5:
            prob += 0.1

        return min(prob, 0.95)

    async def _infer_initial_stance(self, persona: dict, topic: dict) -> dict:
        """推理 Agent 对热点话题的初始态度"""
        prompt = f"""你是一个人格模拟引擎。请根据以下 Agent 的人格特征和热点话题，推理该 Agent 对此话题的初始态度。

## Agent 人格特征
- 专业领域：{persona.get('layer3_knowledge', {}).get('expertise', [])}
- 信息来源：{persona.get('layer3_knowledge', {}).get('info_sources', [])}
- 社会立场：{persona.get('layer2_values', {}).get('social_stances', [])}
- 认知盲区：{persona.get('layer3_knowledge', {}).get('cognitive_blindspots', [])}
- 影响力等级：{persona.get('layer6_social', {}).get('influence_level', 0.5)}

## 热点话题
- 标题：{topic.get('title', '')}
- 平台：{topic.get('platform', '')}
- 分类：{topic.get('category', '')}
- 关键词：{topic.get('keywords', [])}
- 情感倾向：{topic.get('sentiment', 'neutral')}

## 任务
请推理该 Agent 对此话题的：
1. 态度 (supportive/opposing/neutral/concerned)
2. 推理原因 (50-100 字)
3. 情感强度 (0.0-1.0)

请直接返回 JSON 格式，不要其他文字：
{{
    "attitude": "...",
    "reasoning": "...",
    "emotional_intensity": 0.0
}}
"""

        try:
            endpoint = model_router.route("reasoning")
            if not endpoint:
                return {
                    "attitude": "neutral",
                    "reasoning": "无可用模型",
                    "emotional_intensity": 0.5,
                }
            
            response = await endpoint.client.chat.completions.create(
                model=endpoint.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            result = json.loads(content.strip())
            return result
        except Exception as e:
            return {
                "attitude": "neutral",
                "reasoning": f"推理失败：{str(e)}",
                "emotional_intensity": 0.5,
            }

    def _calc_immersion_score(
        self, absorbed: List[dict], attitudes: List[dict], days: int
    ) -> float:
        """计算浸泡分数"""
        if not absorbed and not attitudes:
            return 0.0

        absorbed_score = min(len(absorbed) / (days * self.default_posts_per_day), 1.0)
        attitude_score = min(len(attitudes) / 5.0, 1.0)

        intensity_sum = sum(a.get("emotional_intensity", 0.5) for a in attitudes)
        intensity_avg = intensity_sum / max(len(attitudes), 1)

        score = (absorbed_score * 0.4) + (attitude_score * 0.4) + (intensity_avg * 0.2)
        return round(min(score, 1.0), 3)

    async def get_immersion_result(
        self, immersion_id: str, db: Session
    ) -> Optional[dict]:
        """查询浸泡结果"""
        record = db.query(ImmersionRecord).filter(
            ImmersionRecord.immersion_id == immersion_id
        ).first()

        if not record:
            return None

        return {
            "immersion_id": record.immersion_id,
            "agent_id": record.agent_id,
            "status": record.status,
            "absorbed_topics": json.loads(record.absorbed_topics),
            "initial_attitudes": json.loads(record.initial_attitudes),
            "immersion_score": record.immersion_score,
            "attention_distribution": json.loads(record.attention_distribution),
            "config": json.loads(record.immersion_config),
            "duration_days": record.immersion_days,
            "created_at": record.created_at.isoformat(),
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "error": record.error,
        }

    async def get_agent_immersion_history(
        self, agent_id: str, db: Session
    ) -> List[dict]:
        """查询 Agent 的浸泡历史"""
        records = (
            db.query(ImmersionRecord)
            .filter(ImmersionRecord.agent_id == agent_id)
            .order_by(ImmersionRecord.created_at.desc())
            .limit(10)
            .all()
        )

        return [
            {
                "immersion_id": r.immersion_id,
                "status": r.status,
                "immersion_score": r.immersion_score,
                "absorbed_count": len(json.loads(r.absorbed_topics)),
                "attitudes_count": len(json.loads(r.initial_attitudes)),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]


platform_immersion = PlatformImmersion()
