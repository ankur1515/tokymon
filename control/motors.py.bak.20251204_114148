"""L298N motor helpers (enable pins tied high)."""
from __future__ import annotations

from drivers import rpi_gpio
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("motors")
PINS = CONFIG["pinmap"]["motors"]

GLOBAL_OFFSET = 569
IN1 = CONFIG["pinmap"]["motors"]["motor_a"]["in1"] + GLOBAL_OFFSET
IN2 = CONFIG["pinmap"]["motors"]["motor_a"]["in2"] + GLOBAL_OFFSET
IN3 = CONFIG["pinmap"]["motors"]["motor_b"]["in3"] + GLOBAL_OFFSET
IN4 = CONFIG["pinmap"]["motors"]["motor_b"]["in4"] + GLOBAL_OFFSET

for pin in (IN1, IN2, IN3, IN4):
    rpi_gpio.setup(pin, "out")


def _set_motor(a_forward: bool, b_forward: bool) -> None:
    rpi_gpio.write(IN1, a_forward)
    rpi_gpio.write(IN2, not a_forward)
    rpi_gpio.write(IN3, b_forward)
    rpi_gpio.write(IN4, not b_forward)


def forward() -> None:
    LOGGER.info("Motors forward")
    _set_motor(True, True)


def backward() -> None:
    LOGGER.info("Motors backward")
    _set_motor(False, False)


def turn_left() -> None:
    LOGGER.info("Motors turn left")
    _set_motor(False, True)


def turn_right() -> None:
    LOGGER.info("Motors turn right")
    _set_motor(True, False)


def stop() -> None:
    LOGGER.info("Motors stop")
    rpi_gpio.write(IN1, False)
    rpi_gpio.write(IN2, False)
    rpi_gpio.write(IN3, False)
    rpi_gpio.write(IN4, False)
