import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)


async def rewrite_sentence(sentence: str, dimension: str, severity: str) -> dict:
    """对高风险句子生成安全改写版本"""
    prompt_template = load_prompt("rewrite.txt")
    prompt = prompt_template.replace("{sentence}", sentence).replace("{dimension}", dimension).replace("{severity}", severity)

    try:
        response = await call_llm(prompt, task_type="rewrite")
        result = parse_llm_json(response, fallback=None)
        if result and "rewrites" in result:
            result.setdefault("original", sentence)
            return result
        return {"original": sentence, "rewrites": []}
    except Exception as e:
        logger.error("改写失败: %s", e)
        return {"original": sentence, "rewrites": []}
