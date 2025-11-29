from __future__ import annotations
from drivers import rpi_gpio
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("ir_sensor")
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

LEFT_BCM = CONFIG["pinmap"]["ir_left"]["out"]
RIGHT_BCM = CONFIG["pinmap"]["ir_right"]["out"]

GLOBAL_OFFSET = 569
LEFT_GLOBAL = LEFT_BCM + GLOBAL_OFFSET
RIGHT_GLOBAL = RIGHT_BCM + GLOBAL_OFFSET

_initialized = False


def init():
    global _initialized
    if _initialized:
        return
    rpi_gpio.setup(LEFT_GLOBAL, "in")
    rpi_gpio.setup(RIGHT_GLOBAL, "in")
    _initialized = True


def read_left() -> bool:
    if USE_SIM:
        from sensors import simulator
        return simulator.read_ir("left")
    init()
    return rpi_gpio.read(LEFT_GLOBAL) == 0


def read_right() -> bool:
    if USE_SIM:
        from sensors import simulator
        return simulator.read_ir("right")
    init()
    return rpi_gpio.read(RIGHT_GLOBAL) == 0


def read_both():
    return read_left(), read_right()
