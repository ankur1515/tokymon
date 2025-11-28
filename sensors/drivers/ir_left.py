"""Left IR sensor driver."""
from __future__ import annotations

from drivers import rpi_gpio
from sensors import simulator
from system.config import CONFIG

PIN = CONFIG["pinmap"]["ir_left"]["out"]
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

rpi_gpio.setup(PIN, "in")


def read_state() -> bool:
    if USE_SIM:
        return simulator.read_ir("left")
    return rpi_gpio.read(PIN)
