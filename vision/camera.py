"""Camera access wrapper."""
from __future__ import annotations

from system.logger import get_logger

LOGGER = get_logger("camera")


def capture_frame() -> bytes:
    LOGGER.info("Capturing frame from Pi camera (stub)")
    return b"frame"
