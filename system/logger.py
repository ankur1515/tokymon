"""Shared logging configuration."""
import logging
from logging import Logger

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)


def get_logger(name: str) -> Logger:
    return logging.getLogger(name)
