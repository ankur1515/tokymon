"""Text-to-speech (extracted from raw_scripts/toky_voice.py using espeak)."""
from __future__ import annotations

import os
import subprocess

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("tts")
_CACHE: dict[str, bytes] = {}
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)


def synthesize(text: str) -> bytes:
    """Synthesize text to speech using espeak + aplay (from toky_voice.py)."""
    if USE_SIM:
        LOGGER.info("TTS (simulator): %s", text)
        return text.encode("utf-8")

    if text in _CACHE:
        LOGGER.debug("TTS cache hit")
        return _CACHE[text]

    try:
        espeak_cmd = ["espeak", text, "--stdout"]
        aplay_cmd = ["aplay", "-D", "plughw:2,0"]
        espeak_proc = subprocess.Popen(espeak_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        aplay_proc = subprocess.Popen(
            aplay_cmd, stdin=espeak_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        espeak_proc.stdout.close()
        audio_data, _ = aplay_proc.communicate()
        LOGGER.info("TTS synthesized: %s", text[:50])
        _CACHE[text] = audio_data
        return audio_data
    except FileNotFoundError:
        LOGGER.warning("espeak or aplay not found; falling back to print")
        print(f"Speaking: {text}")
        audio_data = text.encode("utf-8")
        _CACHE[text] = audio_data
        return audio_data
    except Exception as exc:
        LOGGER.warning("TTS failed: %s", exc)
        return text.encode("utf-8")
