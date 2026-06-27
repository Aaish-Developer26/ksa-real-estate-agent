"""Configures structured JSON logging for the application."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_NOISY_LOGGERS: list[str] = ["httpx", "httpcore", "urllib3", "asyncio", "celery"]


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as a JSON string.

        Args:
            record: The log record emitted by the logging framework.

        Returns:
            A single-line JSON string containing timestamp, level,
            logger name, message, module, function, line number, and
            formatted exception info (or null if no exception occurred).
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "exc_info": self.formatException(record.exc_info)
            if record.exc_info
            else None,
        }
        return json.dumps(payload)


def setup_logging(log_level: str = "DEBUG") -> None:
    """Configure the root logger to emit structured JSON to stdout.

    Args:
        log_level: The minimum log level for the root logger
            (e.g. "DEBUG", "INFO", "WARNING", "ERROR").
    """
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stream_handler)
    root_logger.setLevel(log_level)

    for noisy_logger_name in _NOISY_LOGGERS:
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger configured by ``setup_logging``.

    Args:
        name: The logger name, typically ``__name__`` of the calling module.

    Returns:
        A standard library ``Logger`` instance.
    """
    return logging.getLogger(name)
