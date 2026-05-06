import json
import logging
import re

from backend.services.llm_client import call_llm, load_prompt

logger = logging.getLogger(__name__)


async def assess_risks(text: str) -> dict:
    """对文本进行七维风险评估"""
    prompt_template = load_prompt("risk_assessment.txt")
    prompt = prompt_template + text

    try:
        response = await call_llm(prompt)
        return _parse_response(response)
    except Exception as e:
        logger.error(f"风险评估失败: {e}")
        return {"dimensions": [], "risk_sentences": []}


def _parse_response(response: str) -> dict:
    """解析 LLM 返回的 JSON，降级用正则提取"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 降级：尝试提取最外层的 JSON 对象
    brace_match = re.search(r'\{[\s\S]*\}', response)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("风险评估结果解析失败，返回空结果")
    return {"dimensions": [], "risk_sentences": []}
