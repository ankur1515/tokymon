"""
Unified SafeGPIO backend for Raspberry Pi 5.

This backend removes:
- RPi.GPIO
- gpiod
- sysfs GPIO
- backend auto-detection

Everything goes through SafeGPIO for 100% Pi5 compatibility.
"""

from __future__ import annotations
from drivers import safe_gpio as SafeGPIO

from system.logger import get_logger

LOGGER = get_logger("rpi_gpio")


# Always use SafeGPIO backend – it is Pi5-safe and consistent
class RpiBackend:

    def __init__(self):
        LOGGER.info("Using SafeGPIO backend")
        self.backend = SafeGPIO

    def setup(self, pin: int, mode: str) -> None:
        return self.backend.setup(pin, mode)

    def write(self, pin: int, value: bool) -> None:
        return self.backend.write(pin, value)

    def read(self, pin: int) -> bool:
        return self.backend.read(pin)

    def cleanup(self) -> None:
        return self.backend.cleanup()


# Instantiate global backend
BACKEND = RpiBackend()


# Public API wrappers
def setup(pin: int, mode: str) -> None:
    return BACKEND.setup(pin, mode)


def write(pin: int, value: bool) -> None:
    return BACKEND.write(pin, value)


def read(pin: int) -> bool:
    return BACKEND.read(pin)


def cleanup() -> None:
    return BACKEND.cleanup()
