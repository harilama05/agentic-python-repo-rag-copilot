"""
Central logging configuration for the Agentic Python Repo RAG Copilot.

This module provides a single get_logger() helper used by API routes,
services, indexing scripts, retrieval, and agent code.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


_LOGGER_CONFIGURED = False


def configure_logging(
    log_dir: str = "logs",
    log_file: str = "app.log",
    level: int = logging.INFO,
) -> None:
    """
    Configure console and rotating-file logging.

    Safe to call multiple times. Only the first call applies handlers.
    """
    global _LOGGER_CONFIGURED

    if _LOGGER_CONFIGURED:
        return

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_format = (
        "%(asctime)s | %(levelname)s | %(name)s | "
        "%(filename)s:%(lineno)d | %(message)s"
    )

    formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=log_path / log_file,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _LOGGER_CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a configured logger.

    Example:
        logger = get_logger(__name__)
        logger.info("Indexing started", extra={"repo_id": repo_id})
    """
    configure_logging()
    return logging.getLogger(name or "agentic_rag")