import logging

from backend.services.llm_client import call_llm, load_prompt, parse_llm_json

logger = logging.getLogger(__name__)


async def assess_risks(text: str) -> dict:
    """对文本进行七维风险评估"""
    prompt_template = load_prompt("risk_assessment.txt")
    prompt = prompt_template + text

    try:
        response = await call_llm(prompt)
        return parse_llm_json(response, fallback={"dimensions": [], "risk_sentences": []})
    except Exception as e:
        logger.error("风险评估失败: %s", e)
        return {"dimensions": [], "risk_sentences": []}
