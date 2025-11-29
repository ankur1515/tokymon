"""
drivers.rpi_gpio — clean & stable GPIO shim

Provides module-level functions:
    setup(pin, mode)
    write(pin, val)
    read(pin)
    cleanup()

Uses real RPi.GPIO on the Pi.
Falls back to SafeGPIO in dev/simulator mode.
"""

from .safe_gpio import SafeGPIO


# ---------------------------------------------------------
# Select backend: RPi.GPIO → fallback to SafeGPIO
# ---------------------------------------------------------
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
            try:
                _gpio.cleanup()
            except Exception:
                pass

    BACKEND = RpiBackend()

except Exception:
    # Dev/simulator environment
    BACKEND = SafeGPIO()


# ---------------------------------------------------------
# Module-level functions expected everywhere in Tokymon
# ---------------------------------------------------------
def setup(pin, mode):
    return BACKEND.setup(pin, mode)

def write(pin, value):
    return BACKEND.write(pin, value)

def read(pin):
    return BACKEND.read(pin)

def cleanup():
    return BACKEND.cleanup()