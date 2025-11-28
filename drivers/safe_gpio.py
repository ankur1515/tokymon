"""No-op GPIO helpers for simulator mode."""
from __future__ import annotations

from system.logger import get_logger

LOGGER = get_logger("safe_gpio")
_STATE = {}


def setup(pin: int, mode: str) -> None:  # pragma: no cover - trivial
    LOGGER.debug("SAFE setup pin %s -> %s", pin, mode)


def write(pin: int, value: bool) -> None:
    LOGGER.debug("SAFE write pin %s = %s", pin, value)
    _STATE[pin] = value


def read(pin: int) -> bool:
    value = _STATE.get(pin, False)
    LOGGER.debug("SAFE read pin %s -> %s", pin, value)
    return value


def cleanup() -> None:
    LOGGER.info("SAFE cleanup")
    _STATE.clear()
