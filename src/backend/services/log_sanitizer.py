"""日志脱敏工具 — 防止 API Key / 口令进入日志与异常消息"""

from __future__ import annotations

import re

# 常见密钥形态：LongCat ak_ 前缀、OpenAI/DeepSeek sk- 前缀、Bearer token、长随机串赋值
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bak_[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.=]{8,}", re.IGNORECASE),
    re.compile(
        r"((?:api[_-]?key|apikey|token|secret|password|passwd|pwd)\s*[=:]\s*[\"']?)[^\s\"'&,;]{6,}",
        re.IGNORECASE,
    ),
)

_REDACTED = "<REDACTED>"


def redact_secrets(text: str) -> str:
    """将字符串中的密钥/口令替换为 <REDACTED>。

    用于所有对外输出的日志、异常消息与错误上下文，避免密钥泄漏到日志文件。
    """
    if not text:
        return text
    result = text
    result = _SECRET_PATTERNS[0].sub(_REDACTED, result)
    result = _SECRET_PATTERNS[1].sub(_REDACTED, result)
    result = _SECRET_PATTERNS[2].sub(r"\1" + _REDACTED, result)
    result = _SECRET_PATTERNS[3].sub(r"\1" + _REDACTED, result)
    return result


def redact_context(context: dict) -> dict:
    """递归脱敏错误上下文字典中的字符串值。"""
    if not context:
        return context
    redacted: dict = {}
    for k, v in context.items():
        if isinstance(v, str):
            redacted[k] = redact_secrets(v)
        elif isinstance(v, dict):
            redacted[k] = redact_context(v)
        elif isinstance(v, (list, tuple)):
            redacted[k] = [
                redact_secrets(i) if isinstance(i, str) else redact_context(i) if isinstance(i, dict) else i
                for i in v
            ]
        else:
            redacted[k] = v
    return redacted
