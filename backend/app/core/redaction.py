import re


MAX_ERROR_MESSAGE_LENGTH = 240
REDACTED = "[REDACTED]"

SECRET_VALUE_PATTERNS = [
    re.compile(r"(?i)\b(authorization)\s*[:=]\s*(bearer\s+)?[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAKID[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\bcredential\s*=\s*[^,\s]+"),
]


def redact_sensitive_text(value: object, max_length: int = MAX_ERROR_MESSAGE_LENGTH) -> str:
    text = str(value) if value is not None else ""
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: redact_match(match), text)
    text = " ".join(text.split())
    if len(text) > max_length:
        return f"{text[: max_length - 3]}..."
    return text


def provider_error_summary(prefix: str, exc: BaseException | object) -> str:
    message = redact_sensitive_text(exc)
    return f"{prefix}：{message}" if message else prefix


def redact_match(match: re.Match[str]) -> str:
    text = match.group(0)
    if ":" in text:
        return f"{text.split(':', 1)[0]}: {REDACTED}"
    if "=" in text:
        return f"{text.split('=', 1)[0]}={REDACTED}"
    return REDACTED
