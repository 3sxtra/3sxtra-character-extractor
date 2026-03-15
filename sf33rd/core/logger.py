"""Logging configuration for the sf33rd package."""

import logging


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configures the root logger."""
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")
