"""Helper utilities for Tokymon hardware tests."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from display import max7219_driver
from system.logger import get_logger
from voice import audio, tts, stt
from vision import camera

LOGGER = get_logger("hw_test_helpers")


def timestamp_slug() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def led_show_short(expression: str) -> None:
    try:
        max7219_driver.show_expression(expression)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("LED expression failed: %s", exc)


def safe_tts(message: str) -> None:
    try:
        audio_buffer = tts.synthesize(message)
        audio.play_audio(audio_buffer)
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("TTS failed: %s", exc)


def safe_stt_or_fallback(prompt: str, timeout_s: float, fallback_input: Callable[[str], str] | None = None) -> str:
    safe_tts(prompt)
    try:
        transcript = stt.transcribe()
        if transcript:
            return transcript
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("STT unavailable: %s", exc)
    fallback = fallback_input or (lambda msg: input(msg))
    return fallback("(Fallback) %s\n> " % prompt)


def safe_camera_capture(target_dir: Path, filename_prefix: str = "hw_test") -> Path | None:
    ensure_dir(target_dir)
    try:
        frame = camera.capture_frame()
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Camera capture failed: %s", exc)
        return None
    photo_path = target_dir / f"{filename_prefix}_{timestamp_slug()}.jpg"
    try:
        photo_path.write_bytes(frame)
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Unable to write photo: %s", exc)
        return None
    LOGGER.info("Photo saved to %s", photo_path)
    return photo_path


def write_report(report_path: Path, payload: dict) -> None:
    ensure_dir(report_path.parent)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
