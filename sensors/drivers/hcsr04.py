from __future__ import annotations

import time

from drivers import rpi_gpio

from system.config import CONFIG

from system.logger import get_logger



LOGGER = get_logger("hcsr04")



# Correct Pi5 global GPIO numbers (sysfs)

TRIG = CONFIG["pinmap"]["ultrasonic_hcsr04"]["trig"]   # BCM → will map to global (582)

ECHO = CONFIG["pinmap"]["ultrasonic_hcsr04"]["echo"]   # BCM → will map to global (583)



# Setup GPIO

rpi_gpio.setup(TRIG, "out")

rpi_gpio.setup(ECHO, "in")



def read_distance_cm() -> float:

    """

    HC-SR04 measurement identical to working ultrasonic_test.py.

    Blocking, simple, reliable.

    Returns distance in cm or -1 on timeout.

    """



    # Ensure trigger low

    rpi_gpio.write(TRIG, 0)

    time.sleep(0.0002)



    # 10 microsecond pulse

    rpi_gpio.write(TRIG, 1)

    time.sleep(0.00001)

    rpi_gpio.write(TRIG, 0)



    # Wait for echo to go HIGH

    start_time = time.time()

    timeout = start_time + 0.03

    while rpi_gpio.read(ECHO) == 0:

        if time.time() > timeout:

            LOGGER.warning("Ultrasonic timeout: no echo start")

            return -1

    pulse_start = time.time()



    # Wait for echo to go LOW

    timeout = pulse_start + 0.03

    while rpi_gpio.read(ECHO) == 1:

        if time.time() > timeout:

            LOGGER.warning("Ultrasonic timeout: no echo end")

            return -1

    pulse_end = time.time()



    # Duration → distance

    duration = pulse_end - pulse_start

    distance = duration * 17150    # cm



    return round(distance, 2)
