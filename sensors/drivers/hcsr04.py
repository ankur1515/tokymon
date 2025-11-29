"""
HC-SR04 ultrasonic distance driver.

Works on Raspberry Pi 5 using SafeGPIO backend.

"""

from __future__ import annotations

GLOBAL_OFFSET = 559

import time

from drivers import rpi_gpio
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hcsr04")

# Load pins from config and convert BCM to GLOBAL
BCM_TRIG = CONFIG["pinmap"]["ultrasonic_hcsr04"]["trig"]
BCM_ECHO = CONFIG["pinmap"]["ultrasonic_hcsr04"]["echo"]

TRIG = BCM_TRIG + GLOBAL_OFFSET
ECHO = BCM_ECHO + GLOBAL_OFFSET

# Setup GPIO directions
rpi_gpio.setup(TRIG, "out")
rpi_gpio.setup(ECHO, "in")

# Constants
MAX_WAIT = 0.02          # 20 ms timeout
SPEED_OF_SOUND = 34300   # cm/s


def read_distance_cm() -> float:
    """
    Returns distance in cm using HC-SR04.
    Returns -1 on timeout.
    """
    # Ensure trigger LOW
    rpi_gpio.write(TRIG, 0)
    time.sleep(0.0002)

    # Send 10µs trigger pulse
    rpi_gpio.write(TRIG, 1)
    time.sleep(0.00001)
    rpi_gpio.write(TRIG, 0)

    # Wait for echo HIGH (start)
    start_time = time.time()
    while rpi_gpio.read(ECHO) == 0:
        if time.time() - start_time > MAX_WAIT:
            LOGGER.warning("Ultrasonic timeout: no echo start")
            return -1

    pulse_start = time.time()

    # Wait for echo LOW (end)
    while rpi_gpio.read(ECHO) == 1:
        if time.time() - pulse_start > MAX_WAIT:
            LOGGER.warning("Ultrasonic timeout: no echo end")
            return -1

    pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = (pulse_duration * SPEED_OF_SOUND) / 2
    return round(distance, 2)


LOGGER.info(f"HC-SR04 driver loaded: TRIG={TRIG}, ECHO={ECHO}")
