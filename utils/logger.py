"""
logger.py — Centralised structured logging.

Every module gets a logger via `get_logger(__name__)`. The format is
``timestamp | level | module | message`` so logs are easy to grep and
ship to log aggregators.

This replaces every `print(...)` call in the codebase.
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache

from config.settings import get_settings


_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@lru_cache(maxsize=1)
def _configure_root_logger() -> None:
    """Configure the root logger once per Python interpreter."""
    settings = get_settings()

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    # Avoid double-registration when Streamlit hot-reloads.
    if root.handlers:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Always call once at the top of each module::

        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("hello")
    """
    _configure_root_logger()
    return logging.getLogger(name)
