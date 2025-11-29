"""
IR sensor driver — EXACT behaviour of ir_detect_5s_led.py

- Uses sysfs GPIO (NOT RPi.GPIO)
- Automatically maps BCM → GLOBAL gpio numbers
- Active LOW: 0 = detection
- No debounce (same as working script)
"""

import os
import time
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("ir_sensor")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# BCM numbers from config
LEFT_BCM = CONFIG["pinmap"]["ir_left"]["out"]
RIGHT_BCM = CONFIG["pinmap"]["ir_right"]["out"]

# Convert BCM → GLOBAL like your working script:
# GLOBAL = 512 + BCM
LEFT_GLOBAL = 512 + LEFT_BCM
RIGHT_GLOBAL = 512 + RIGHT_BCM


def _export_sysfs(pin_global):
    """Ensure /sys/class/gpio/gpioX exists and is set to input."""
    base = f"/sys/class/gpio/gpio{pin_global}"

    if not os.path.exists(base):
        try:
            with open("/sys/class/gpio/export", "w") as f:
                f.write(str(pin_global))
            time.sleep(0.02)
        except PermissionError:
            LOGGER.error("Permission denied exporting GPIO %s. Need sudo.", pin_global)
            return False

    # set direction to input
    try:
        with open(f"{base}/direction", "w") as f:
            f.write("in")
    except Exception:
        pass

    return True


def _read_sysfs(pin_global):
    """Return raw sysfs value (0/1)."""
    try:
        with open(f"/sys/class/gpio/gpio{pin_global}/value") as f:
            return int(f.read().strip())
    except Exception:
        return 1  # fail-safe: HIGH = no detection


# Export at import time (same as working file)
_export_sysfs(LEFT_GLOBAL)
_export_sysfs(RIGHT_GLOBAL)


def read_left():
    """Return True if LEFT sensor detects an object (ACTIVE-LOW)."""
    if USE_SIM:
        from sensors import simulator
        return simulator.read_ir("left")

    raw = _read_sysfs(LEFT_GLOBAL)
    return raw == 0   # ACTIVE LOW


def read_right():
    """Return True if RIGHT sensor detects an object (ACTIVE-LOW)."""
    if USE_SIM:
        from sensors import simulator
        return simulator.read_ir("right")

    raw = _read_sysfs(RIGHT_GLOBAL)
    return raw == 0   # ACTIVE LOW


def read_both():
    return read_left(), read_right()