import re
from typing import Any


PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b(?:sk|pk|api|key)_[A-Za-z0-9_\-]{16,}\b"),
]


async def redact(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    if isinstance(value, list):
        return [await redact(item) for item in value]
    if isinstance(value, dict):
        return {key: await redact(item) for key, item in value.items()}
    return value
