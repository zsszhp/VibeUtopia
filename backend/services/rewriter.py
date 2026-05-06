import json
import logging
import re

from backend.services.llm_client import call_llm, load_prompt

logger = logging.getLogger(__name__)


async def rewrite_sentence(sentence: str, dimension: str, severity: str) -> dict:
    """对高风险句子生成安全改写版本"""
    prompt_template = load_prompt("rewrite.txt")
    prompt = prompt_template.replace("{sentence}", sentence).replace("{dimension}", dimension).replace("{severity}", severity)

    try:
        response = await call_llm(prompt)
        return _parse_response(response, sentence)
    except Exception as e:
        logger.error(f"改写失败: {e}")
        return {"original": sentence, "rewrites": []}


def _parse_response(response: str, original: str) -> dict:
    """解析 LLM 返回的 JSON"""
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

    # 降级：提取引号中的内容作为改写
    rewrites = re.findall(r'"([^"]{10,})"', response)
    if rewrites:
        return {"original": original, "rewrites": rewrites[:2]}

    return {"original": original, "rewrites": []}
