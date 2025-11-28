"""GPIO abstraction that toggles between real hardware and simulator."""
from __future__ import annotations

try:
    from typing import Protocol
except ImportError:  # pragma: no cover - py<3.8 fallback
    Protocol = object  # type: ignore

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("gpio")


class _GpioBackend(Protocol):
    def setup(self, pin: int, mode: str) -> None: ...
    def write(self, pin: int, value: bool) -> None: ...
    def read(self, pin: int) -> bool: ...
    def cleanup(self) -> None: ...


if CONFIG["services"]["runtime"]["use_simulator"]:
    from drivers import safe_gpio as backend
else:  # pragma: no cover - requires real hardware
    try:
        import RPi.GPIO as GPIO
    except ImportError:  # pragma: no cover - tests/dev fallback
        from drivers import safe_gpio as backend  # type: ignore
        LOGGER.warning("RPi.GPIO unavailable, falling back to safe GPIO")
    else:

        class _RealBackend:
            def __init__(self) -> None:
                GPIO.setmode(GPIO.BCM)

            def setup(self, pin: int, mode: str) -> None:
                gpio_mode = GPIO.OUT if mode == "out" else GPIO.IN
                GPIO.setup(pin, gpio_mode)

            def write(self, pin: int, value: bool) -> None:
                GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)

            def read(self, pin: int) -> bool:
                return bool(GPIO.input(pin))

            def cleanup(self) -> None:
                GPIO.cleanup()

        backend = _RealBackend()


BACKEND: _GpioBackend = backend


def setup(pin: int, mode: str) -> None:
    LOGGER.debug("setup pin %s mode %s", pin, mode)
    BACKEND.setup(pin, mode)


def write(pin: int, value: bool) -> None:
    BACKEND.write(pin, value)


def read(pin: int) -> bool:
    return BACKEND.read(pin)


def cleanup() -> None:
    BACKEND.cleanup()
