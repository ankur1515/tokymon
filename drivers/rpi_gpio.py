# drivers/rpi_gpio.py
"""
Sysfs GPIO backend (Pi5) + SafeGPIO fallback.
"""

from __future__ import annotations
import os, time, errno
from system.logger import get_logger
from . import safe_gpio

LOGGER = get_logger("rpi_gpio")

TOKY_ENV = os.environ.get("TOKY_ENV", "dev").lower()
SYSFS_ROOT = "/sys/class/gpio"
USE_SYSFS = (TOKY_ENV == "prod") and os.path.isdir(SYSFS_ROOT)


class SysfsBackend:

    def __init__(self):
        if not os.path.isdir(SYSFS_ROOT):
            raise RuntimeError("sysfs gpio not available")
        LOGGER.info("SysfsBackend initialized")

    def _export(self, gnum: int):
        base = f"{SYSFS_ROOT}/gpio{gnum}"
        if not os.path.exists(base):
            try:
                with open(f"{SYSFS_ROOT}/export", "w") as f:
                    f.write(str(gnum))
                time.sleep(0.02)
            except PermissionError:
                raise PermissionError(f"Need sudo for gpio {gnum}")
            except OSError as e:
                if e.errno != errno.EBUSY:
                    raise

    def setup(self, gnum: int, mode: str):
        self._export(gnum)
        try:
            with open(f"{SYSFS_ROOT}/gpio{gnum}/direction", "w") as f:
                f.write("out" if mode == "out" else "in")
        except Exception:
            LOGGER.debug("Failed direction for gpio%s", gnum)

    def write(self, gnum: int, value: bool):
        try:
            with open(f"{SYSFS_ROOT}/gpio{gnum}/value", "w") as f:
                f.write("1" if value else "0")
        except Exception as e:
            LOGGER.error("sysfs write fail gpio%s: %s", gnum, e)

    def read(self, gnum: int) -> int:
        try:
            with open(f"{SYSFS_ROOT}/gpio{gnum}/value", "r") as f:
                return int(f.read().strip() or "1")
        except Exception:
            return 1

    def cleanup(self):
        pass


if USE_SYSFS:
    try:
        BACKEND = SysfsBackend()
        LOGGER.info("Using SysfsBackend for GPIO")
    except Exception as e:
        LOGGER.warning("Sysfs failed: %s — using SafeGPIO", e)
        BACKEND = None
else:
    BACKEND = None
    LOGGER.info("Using SafeGPIO")


def setup(pin, mode):
    if BACKEND:
        return BACKEND.setup(pin, mode)
    return safe_gpio.setup(pin, mode)


def write(pin, value):
    if BACKEND:
        return BACKEND.write(pin, value)
    return safe_gpio.write(pin, value)


def read(pin):
    if BACKEND:
        return BACKEND.read(pin)
    return safe_gpio.read(pin)


def cleanup():
    if BACKEND:
        return BACKEND.cleanup()
    return safe_gpio.cleanup()
