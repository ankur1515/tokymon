"""HC-SR04 ultrasonic sensor driver."""
from __future__ import annotations

import time

from drivers import rpi_gpio
from sensors import simulator
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hcsr04")
PINS = CONFIG["pinmap"]["ultrasonic_hcsr04"]
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

rpi_gpio.setup(PINS["trig"], "out")
rpi_gpio.setup(PINS["echo"], "in")

# Note: echo pin uses a 2k/1k resistor divider. Keep echo pin as input only.


def _pulse_trigger() -> None:
    rpi_gpio.write(PINS["trig"], False)
    time.sleep(0.0002)
    rpi_gpio.write(PINS["trig"], True)
    time.sleep(0.00001)
    rpi_gpio.write(PINS["trig"], False)


def measure_distance_cm() -> float:
    if USE_SIM:
        return simulator.read_distance_cm()

    _pulse_trigger()

    timeout = time.time() + 1
    while not rpi_gpio.read(PINS["echo"]):
        if time.time() > timeout:
            LOGGER.warning("Echo timeout waiting for HIGH")
            return -1.0

    start = time.time()
    while rpi_gpio.read(PINS["echo"]):
        if time.time() > timeout:
            LOGGER.warning("Echo timeout waiting for LOW")
            return -1.0
    end = time.time()

    duration = end - start
    distance_cm = (duration * 34300) / 2
    return round(distance_cm, 2)
