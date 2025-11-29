"""
Unified GPIO backend for Tokymon.

Raspberry Pi 5 does NOT support RPi.GPIO → 
therefore always fall back to SafeGPIO backend.
"""

from .safe_gpio import (
    setup as safe_setup,
    write as safe_write,
    read as safe_read,
    cleanup as safe_cleanup,
)
from system.logger import get_logger

LOGGER = get_logger("rpi_gpio")


def setup(pin, mode):
    LOGGER.info("Using SafeGPIO backend")
    return safe_setup(pin, mode)


def write(pin, value):
    return safe_write(pin, value)


def read(pin):
    return safe_read(pin)


def cleanup():
    return safe_cleanup()
