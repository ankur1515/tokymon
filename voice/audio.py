"""Audio helpers for microphone and speaker pipeline."""
from __future__ import annotations

from system.logger import get_logger

LOGGER = get_logger("audio")


def capture_microphone(seconds: int = 3) -> bytes:
    LOGGER.info("Capturing %ss of audio (stub)", seconds)
    return b""


def play_audio(buffer: bytes) -> None:
    LOGGER.info("Playing %d bytes (stub)", len(buffer))
