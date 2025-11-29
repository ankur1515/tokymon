"""Sysfs-based GPIO backend using /sys/class/gpio (raspi-gpio compatible)."""
from __future__ import annotations

import os
import subprocess
import time
from typing import Dict

from system.logger import get_logger

LOGGER = get_logger("sysfs_gpio")
_EXPORTED: Dict[int, bool] = {}


def _bcm_to_global(bcm_pin: int) -> int:
    """Convert BCM pin to global GPIO number using raspi-gpio or sysfs."""
    try:
        result = subprocess.run(
            ["raspi-gpio", "get", str(bcm_pin)],
            capture_output=True,
            text=True,
            check=True,
            timeout=1,
        )
        for line in result.stdout.splitlines():
            if "GPIO" in line and "func" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith("GPIO") and i + 1 < len(parts):
                        try:
                            return int(parts[i + 1])
                        except (ValueError, IndexError):
                            pass
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    base = 456
    return base + bcm_pin


def _export_gpio(global_num: int) -> None:
    if _EXPORTED.get(global_num):
        return
    path = f"/sys/class/gpio/gpio{global_num}"
    if not os.path.exists(path):
        try:
            with open("/sys/class/gpio/export", "w") as f:
                f.write(str(global_num))
            time.sleep(0.05)
        except PermissionError:
            LOGGER.warning("Permission denied exporting GPIO %s (need sudo?)", global_num)
            raise
    _EXPORTED[global_num] = True


def setup(bcm_pin: int, mode: str) -> None:
    global_num = _bcm_to_global(bcm_pin)
    _export_gpio(global_num)
    direction = "out" if mode == "out" else "in"
    try:
        with open(f"/sys/class/gpio/gpio{global_num}/direction", "w") as f:
            f.write(direction)
    except Exception as exc:
        LOGGER.warning("Failed to set direction for GPIO %s: %s", global_num, exc)


def write(bcm_pin: int, value: bool) -> None:
    global_num = _bcm_to_global(bcm_pin)
    if not _EXPORTED.get(global_num):
        setup(bcm_pin, "out")
    try:
        with open(f"/sys/class/gpio/gpio{global_num}/value", "w") as f:
            f.write("1" if value else "0")
    except Exception as exc:
        LOGGER.warning("Failed to write GPIO %s: %s", global_num, exc)


def read(bcm_pin: int) -> bool:
    global_num = _bcm_to_global(bcm_pin)
    if not _EXPORTED.get(global_num):
        setup(bcm_pin, "in")
    try:
        with open(f"/sys/class/gpio/gpio{global_num}/value", "r") as f:
            return f.read(1).strip() == "1"
    except Exception as exc:
        LOGGER.warning("Failed to read GPIO %s: %s", global_num, exc)
        return False


def cleanup() -> None:
    _EXPORTED.clear()

