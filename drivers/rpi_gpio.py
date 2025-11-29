"""
Unified GPIO backend for Raspberry Pi.

Priority:
1. RPi.GPIO
2. fallback to safe_gpio (simulator)
"""

from system.logger import get_logger
LOGGER = get_logger("rpi_gpio")

# Try to import real RPi.GPIO
try:
    import RPi.GPIO as _gpio

    class RpiBackend:
        def __init__(self):
            _gpio.setmode(_gpio.BCM)

        def setup(self, pin, mode):
            _gpio.setup(pin, _gpio.OUT if mode == "out" else _gpio.IN)

        def write(self, pin, value):
            _gpio.output(pin, _gpio.HIGH if value else _gpio.LOW)

        def read(self, pin):
            return _gpio.input(pin)

        def cleanup(self):
            _gpio.cleanup()

    BACKEND = RpiBackend()
    LOGGER.info("Using RPi.GPIO backend")

except Exception as e:
    LOGGER.warning("RPi.GPIO unavailable → using SafeGPIO fallback (%s)", e)

    # Import module functions directly
    from . import safe_gpio

    class SafeWrapper:
        def setup(self, pin, mode):
            safe_gpio.setup(pin, mode)

        def write(self, pin, value):
            safe_gpio.write(pin, value)

        def read(self, pin):
            return safe_gpio.read(pin)

        def cleanup(self):
            safe_gpio.cleanup()

    BACKEND = SafeWrapper()
    LOGGER.info("Using SafeGPIO fallback backend")


# Public API
def setup(pin, mode): return BACKEND.setup(pin, mode)
def write(pin, value): return BACKEND.write(pin, value)
def read(pin): return BACKEND.read(pin)
def cleanup(): return BACKEND.cleanup()