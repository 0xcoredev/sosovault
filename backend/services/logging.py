"""
Structured logging for SoSoVault.

Provides a consistent logger across all backend services with
JSON-ready output for production and human-readable output for dev.
"""
import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for the given service module."""
    logger = logging.getLogger(f"sosovault.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level, logging.INFO))
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger
