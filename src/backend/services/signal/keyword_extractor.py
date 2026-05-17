"""LLM关键词提取器 - 从种子事件中提取搜索关键词"""

import logging
from typing import List

from backend.services.llm_client import call_llm, parse_llm_json
from backend.services.signal.models import SearchKeyword

logger = logging.getLogger(__name__)

KEYWORD_PROMPT = """事件标题：{title}
事件描述：{description}

请提取3-5个搜索关键词，用于在微博/小红书/B站/知乎上搜索相关评论。
要求：
1. 关键词要具体，能搜到真实讨论
2. 包含事件核心实体名
3. 考虑不同平台可能使用的不同表述

输出JSON格式：
{{
    "keywords": [
        {{"keyword": "关键词", "platforms": ["微博","知乎"], "priority": 1}}
    ]
}}"""


class KeywordExtractor:
    """从种子事件中提取搜索关键词"""

    async def extract(
        self, event_title: str, event_description: str = ""
    ) -> List[SearchKeyword]:
        """LLM提取3-5个搜索关键词"""
        prompt = KEYWORD_PROMPT.format(
            title=event_title, description=event_description or "无详细描述"
        )

        try:
            response = await call_llm(
                prompt,
                system="你是一个搜索关键词提取专家，擅长从事件中提取高搜索价值的关键词。",
                task_type="persona_simulation",
            )
            data = parse_llm_json(response, fallback={"keywords": []})
            keywords_data = data.get("keywords", [])

            results: List[SearchKeyword] = []
            for kw in keywords_data:
                if not kw.get("keyword"):
                    continue
                results.append(
                    SearchKeyword(
                        keyword=kw["keyword"],
                        platforms=kw.get("platforms", ["微博", "知乎"]),
                        priority=kw.get("priority", 3),
                    )
                )

            # 如果LLM未返回有效结果，用标题本身作为关键词
            if not results:
                results.append(
                    SearchKeyword(
                        keyword=event_title[:20],
                        platforms=["微博", "知乎", "B站"],
                        priority=1,
                    )
                )

            return results

        except Exception as e:
            logger.error("KeywordExtractor: 提取失败 %s", e)
            # 降级：用标题前20字作为关键词
            return [
                SearchKeyword(
                    keyword=event_title[:20],
                    platforms=["微博", "知乎"],
                    priority=1,
                )
            ]
