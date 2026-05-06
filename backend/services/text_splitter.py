import re


def split_text(text: str) -> list[str]:
    """将中文文本按句子切分，返回非空句子列表"""
    # 优先按中文标点分句
    sentences = re.split(r'(?<=[。！？；\n])', text)

    # 过滤空句子和空白
    result = [s.strip() for s in sentences if s.strip()]

    # 兜底：如果分句后只有一条（说明没有标点），按段落切分
    if len(result) <= 1 and len(text) > 100:
        result = [p.strip() for p in text.split("\n") if p.strip()]

    # 最终兜底：如果还是只有一条，强制按50字切分
    if len(result) <= 1 and len(text) > 50:
        result = [text[i:i+50].strip() for i in range(0, len(text), 50) if text[i:i+50].strip()]

    return result
