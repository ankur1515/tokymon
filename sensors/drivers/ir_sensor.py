"""IR sensor driver (extracted from raw_scripts/ir_detect_5s_led.py)."""
from __future__ import annotations

from drivers import rpi_gpio
from sensors import simulator
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("ir_sensor")
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

LEFT_PIN = CONFIG["pinmap"]["ir_left"]["out"]
RIGHT_PIN = CONFIG["pinmap"]["ir_right"]["out"]

rpi_gpio.setup(LEFT_PIN, "in")
rpi_gpio.setup(RIGHT_PIN, "in")


def read_left() -> bool:
    """Read left IR sensor (active-low: 0 = detection)."""
    if USE_SIM:
        return simulator.read_ir("left")
    value = rpi_gpio.read(LEFT_PIN)
    return not value


def read_right() -> bool:
    """Read right IR sensor (active-low: 0 = detection)."""
    if USE_SIM:
        return simulator.read_ir("right")
    value = rpi_gpio.read(RIGHT_PIN)
    return not value


def read_both() -> tuple[bool, bool]:
    """Read both IR sensors, returns (left_detected, right_detected)."""
    return read_left(), read_right()

