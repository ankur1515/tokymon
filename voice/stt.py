"""Speech-to-text wrapper."""
from __future__ import annotations

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("stt")


def transcribe(audio_blob: bytes | None = None) -> str:
    provider = CONFIG["services"]["stt"]["provider"]
    LOGGER.info("STT provider=%s (placeholder)", provider)
    # TODO: Implement Whisper or other provider call.
    return "move forward"
