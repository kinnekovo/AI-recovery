import json
import logging
from typing import Any

from app.core.redaction import redact_sensitive_text


APP_LOGGER_NAME = "speech_rehab"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def app_logger() -> logging.Logger:
    return logging.getLogger(APP_LOGGER_NAME)


def log_event(level: str, category: str, event: str, **fields: Any) -> None:
    payload = {
        "category": category,
        "event": event,
        **{key: safe_log_value(value) for key, value in fields.items()},
    }
    logger = app_logger()
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def safe_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: safe_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe_log_value(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, BaseException):
        return {
            "type": value.__class__.__name__,
            "message": redact_sensitive_text(value),
        }
    return value
