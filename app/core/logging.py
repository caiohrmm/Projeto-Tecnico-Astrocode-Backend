"""Logging configuration."""

import logging
import sys

from app.config.settings import get_settings


def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()

    level = logging.DEBUG if settings.debug else logging.INFO
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Suppress passlib bcrypt version warning (compatibility issue, but works fine)
    logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    return logging.getLogger(name)
