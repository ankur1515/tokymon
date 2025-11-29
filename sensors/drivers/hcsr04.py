"""HC-SR04 ultrasonic sensor driver (extracted from raw_scripts/ultrasonic_test.py)."""
from __future__ import annotations

import time

from drivers import rpi_gpio
from sensors import simulator
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hcsr04")
PINS = CONFIG["pinmap"]["ultrasonic_hcsr04"]
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

TIMEOUT = 0.02
POLL_SLEEP = 0.0001

BCM_TRIG = CONFIG["pinmap"]["ultrasonic_hcsr04"]["trig"]
BCM_ECHO = CONFIG["pinmap"]["ultrasonic_hcsr04"]["echo"]

GLOBAL_OFFSET = 569
TRIG = BCM_TRIG + GLOBAL_OFFSET
ECHO = BCM_ECHO + GLOBAL_OFFSET

rpi_gpio.setup(TRIG, "out")
rpi_gpio.setup(ECHO, "in")

# Note: echo pin uses a 2k/1k resistor divider. Keep echo pin as input only.


def measure_distance_cm() -> float:
    """Measure distance using exact timing from ultrasonic_test.py."""
    if USE_SIM:
        return simulator.read_distance_cm()

    rpi_gpio.write(TRIG, False)
    time.sleep(0.05)

    rpi_gpio.write(TRIG, True)
    time.sleep(0.00001)
    rpi_gpio.write(TRIG, False)

    start_deadline = time.time() + TIMEOUT
    while time.time() < start_deadline:
        if rpi_gpio.read(ECHO):
            pulse_start = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        LOGGER.warning("Echo timeout waiting for HIGH")
        return -1.0

    end_deadline = time.time() + TIMEOUT
    while time.time() < end_deadline:
        if not rpi_gpio.read(ECHO):
            pulse_end = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        LOGGER.warning("Echo timeout waiting for LOW")
        return -1.0

    duration = pulse_end - pulse_start
    dist = duration * 17150
    if dist < 2 or dist > 400:
        LOGGER.warning("Distance out of range: %.2f cm", dist)
        return -1.0
    return round(dist, 2)
