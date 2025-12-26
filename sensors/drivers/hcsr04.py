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
GLOBAL_OFFSET = 569

# Convert BCM → global GPIO numbering used in /sys/class/gpio
TRIG = BCM_TRIG + GLOBAL_OFFSET   # 23 + 559 = 582
ECHO = BCM_ECHO + GLOBAL_OFFSET   # 24 + 559 = 583

# Setup GPIO
rpi_gpio.setup(TRIG, "out")
rpi_gpio.setup(ECHO, "in")


def read_distance_cm(timeout_s=0.02) -> float:
    """
    Measure distance using HC-SR04.
    Based on working code from raw_scripts/ultrasonic_test.py
    Returns:
        distance in cm, or -1 on timeout
    """
    POLL_SLEEP = 0.0001
    
    # Ensure trig low with longer delay (from working code)
    rpi_gpio.write(TRIG, 0)
    time.sleep(0.05)

    # Send 10µs pulse
    rpi_gpio.write(TRIG, 1)
    time.sleep(0.00001)
    rpi_gpio.write(TRIG, 0)

    # Wait for echo start (with polling like working code)
    start_deadline = time.time() + timeout_s
    pulse_start = None
    while time.time() < start_deadline:
        if rpi_gpio.read(ECHO) == 1:
            pulse_start = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        # Timeout - no echo start
        return -1

    # Wait for echo end
    end_deadline = time.time() + timeout_s
    pulse_end = None
    while time.time() < end_deadline:
        if rpi_gpio.read(ECHO) == 0:
            pulse_end = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        # Timeout - echo too long
        return -1

    duration = pulse_end - pulse_start
    dist = duration * 17150  # speed of sound conversion
    
    # Validate range (from working code)
    if dist < 2 or dist > 400:
        return -1
    
    return round(dist, 2)
