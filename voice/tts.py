"""Text-to-speech stub with caching placeholder."""
from __future__ import annotations

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("tts")
_CACHE: dict[str, bytes] = {}


def synthesize(text: str) -> bytes:
    if text in _CACHE:
        LOGGER.debug("TTS cache hit")
        return _CACHE[text]
    provider = CONFIG["services"]["tts"]["provider"]
    LOGGER.info("TTS provider=%s (placeholder)", provider)
    # TODO: Call ElevenLabs or preferred provider.
    audio = text.encode("utf-8")
    _CACHE[text] = audio
    return audio
