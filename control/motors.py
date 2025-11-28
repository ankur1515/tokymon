"""L298N motor helpers (enable pins tied high)."""
from __future__ import annotations

from drivers import rpi_gpio
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("motors")
PINS = CONFIG["pinmap"]["motors"]

A_IN1 = PINS["motor_a"]["in1"]
A_IN2 = PINS["motor_a"]["in2"]
B_IN3 = PINS["motor_b"]["in3"]
B_IN4 = PINS["motor_b"]["in4"]

for pin in (A_IN1, A_IN2, B_IN3, B_IN4):
    rpi_gpio.setup(pin, "out")


def _set_motor(a_forward: bool, b_forward: bool) -> None:
    rpi_gpio.write(A_IN1, a_forward)
    rpi_gpio.write(A_IN2, not a_forward)
    rpi_gpio.write(B_IN3, b_forward)
    rpi_gpio.write(B_IN4, not b_forward)


def forward() -> None:
    LOGGER.info("Motors forward")
    _set_motor(True, True)


def backward() -> None:
    LOGGER.info("Motors backward")
    _set_motor(False, False)


def stop() -> None:
    LOGGER.info("Motors stop")
    rpi_gpio.write(A_IN1, False)
    rpi_gpio.write(A_IN2, False)
    rpi_gpio.write(B_IN3, False)
    rpi_gpio.write(B_IN4, False)
