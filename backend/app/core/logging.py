"""ORION structured logging configuration and log formatting."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class OrionJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON without leaking sensitive credentials."""

    SENSITIVE_KEYS = {"password", "token", "secret", "gemini_api_key", "authorization", "key"}

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Include request_id if attached
        if hasattr(record, "request_id"):
            log_payload["request_id"] = record.request_id

        # Include custom extra metadata while redacting sensitive fields
        if hasattr(record, "meta") and isinstance(record.meta, dict):
            sanitized_meta = {}
            for k, v in record.meta.items():
                if any(sk in k.lower() for sk in self.SENSITIVE_KEYS):
                    sanitized_meta[k] = "[REDACTED]"
                else:
                    sanitized_meta[k] = v
            log_payload["meta"] = sanitized_meta

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures root and application loggers."""
    logger = logging.getLogger("orion")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on re-init
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(OrionJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = setup_logging()
