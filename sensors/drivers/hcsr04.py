import time

from system.config import CONFIG
from system.logger import get_logger
from drivers import rpi_gpio

LOGGER = get_logger("hcsr04")

# Pin mapping: BCM → Global offset 559 (from raw_scripts/ultrasonic_test.py)
TRIG_BCM = 23
ECHO_BCM = 24

TRIG = TRIG_BCM + 559  # 582
ECHO = ECHO_BCM + 559  # 583

# Initialize pins
rpi_gpio.setup(TRIG, "out")
rpi_gpio.setup(ECHO, "in")
LOGGER.info(f"HC-SR04 driver loaded: TRIG={TRIG}, ECHO={ECHO}")

# Constants from raw_scripts/ultrasonic_test.py
TIMEOUT = 0.02  # seconds
POLL_SLEEP = 0.0001


def read_distance_cm() -> float:
    """
    Returns distance in cm using HC-SR04.
    Logic copied from raw_scripts/ultrasonic_test.py get_distance().
    Returns -1 on timeout or invalid reading.
    """
    # Ensure trig low
    rpi_gpio.write(TRIG, 0)
    time.sleep(0.05)

    # Pulse: HIGH for 10µs
    rpi_gpio.write(TRIG, 1)
    time.sleep(0.00001)
    rpi_gpio.write(TRIG, 0)

    # Wait for echo HIGH (start)
    start_deadline = time.time() + TIMEOUT
    while time.time() < start_deadline:
        if rpi_gpio.read(ECHO):
            pulse_start = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        LOGGER.warning("Ultrasonic timeout: no echo start")
        return -1

    # Wait for echo LOW (end)
    end_deadline = time.time() + TIMEOUT
    while time.time() < end_deadline:
        if not rpi_gpio.read(ECHO):
            pulse_end = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        LOGGER.warning("Ultrasonic timeout: no echo end")
        return -1

    duration = pulse_end - pulse_start
    dist = duration * 17150
    if dist < 2 or dist > 400:
        LOGGER.warning("Distance out of range: %.2f cm", dist)
        return -1
    return round(dist, 2)
