"""GPIO abstraction that toggles between real hardware and simulator."""
from __future__ import annotations

try:
    from .safe_gpio import SafeGPIO
except ImportError:
    from .safe_gpio import setup as safe_setup, write as safe_write, read as safe_read, cleanup as safe_cleanup

    class SafeGPIO:
        def setup(self, pin, mode):
            safe_setup(pin, mode)

        def write(self, pin, val):
            safe_write(pin, val)

        def read(self, pin):
            return safe_read(pin)

        def cleanup(self):
            safe_cleanup()

try:
    import RPi.GPIO as _gpio

    class RpiBackend:
        def __init__(self):
            _gpio.setmode(_gpio.BCM)

        def setup(self, pin, mode):
            _gpio.setup(pin, _gpio.OUT if mode == "out" else _gpio.IN)

        def write(self, pin, val):
            _gpio.output(pin, _gpio.HIGH if val else _gpio.LOW)

        def read(self, pin):
            return _gpio.input(pin)

        def cleanup(self):
            _gpio.cleanup()

    BACKEND = RpiBackend()

except Exception:
    BACKEND = SafeGPIO()


def setup(pin: int, mode: str) -> None:
    BACKEND.setup(pin, mode)


def write(pin: int, value: bool) -> None:
    BACKEND.write(pin, value)


def read(pin: int) -> bool:
    return BACKEND.read(pin)


def cleanup() -> None:
    BACKEND.cleanup()
