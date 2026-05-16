"""
Structured logger using ``structlog``.

Falls back to standard ``logging`` if structlog is not installed.
"""

import logging
import sys
from typing import Any


def get_logger(name: str = "agentic_rag", **kwargs: Any) -> Any:
    """
    Get a structured logger.

    Uses ``structlog`` if available, otherwise falls back to stdlib.
    """
    try:
        import structlog

        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )
        return structlog.get_logger(name, **kwargs)

    except ImportError:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
