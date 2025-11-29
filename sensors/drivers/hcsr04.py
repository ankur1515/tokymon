from __future__ import annotations

import time

from drivers import rpi_gpio
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hcsr04")

# Resolve BCM pins from CONFIG
BCM_TRIG = int(CONFIG["pinmap"]["ultrasonic_hcsr04"]["trig"])   # usually 23
BCM_ECHO = int(CONFIG["pinmap"]["ultrasonic_hcsr04"]["echo"])   # usually 24

# Raspberry Pi 5 sysfs global GPIO offset discovered from working tests
GLOBAL_OFFSET = 559

# Convert BCM → global GPIO numbering used in /sys/class/gpio
TRIG = BCM_TRIG + GLOBAL_OFFSET   # 23 + 559 = 582
ECHO = BCM_ECHO + GLOBAL_OFFSET   # 24 + 559 = 583

# Setup GPIO
rpi_gpio.setup(TRIG, "out")
rpi_gpio.setup(ECHO, "in")


def read_distance_cm(timeout_s=0.03) -> float:
    """
    Measure distance using HC-SR04.
    Returns:
        distance in cm, or -1 on timeout
    """
    # Trigger low
    rpi_gpio.write(TRIG, 0)
    time.sleep(0.0002)

    # Send 10µs pulse
    rpi_gpio.write(TRIG, 1)
    time.sleep(0.00001)
    rpi_gpio.write(TRIG, 0)

    # Wait for echo start
    start_time = time.time()
    while rpi_gpio.read(ECHO) == 0:
        if time.time() - start_time > timeout_s:
            LOGGER.warning("Ultrasonic timeout: no echo start")
            return -1

    pulse_start = time.time()

    # Wait for echo end
    while rpi_gpio.read(ECHO) == 1:
        if time.time() - pulse_start > timeout_s:
            LOGGER.warning("Ultrasonic timeout: echo too long")
            return -1

    pulse_end = time.time()

    duration = pulse_end - pulse_start
    distance = duration * 17150  # speed of sound conversion
    return round(distance, 2)
