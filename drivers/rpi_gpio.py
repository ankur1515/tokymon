# Tokymon – Raspberry Pi 5 Safe GPIO Backend (sysfs only)
# -------------------------------------------------------
# This backend never loads RPi.GPIO (unsupported on Pi5)
# and uses ONLY sysfs GPIO — same as your working scripts.

import os
import time

SYSFS = "/sys/class/gpio"


class SysfsGPIO:
    def __init__(self):
        pass

    def _export(self, pin):
        if not os.path.exists(f"{SYSFS}/gpio{pin}"):
            try:
                with open(f"{SYSFS}/export", "w") as f:
                    f.write(str(pin))
                time.sleep(0.05)
            except Exception:
                pass

    def setup(self, pin, mode):
        self._export(pin)
        try:
            with open(f"{SYSFS}/gpio{pin}/direction", "w") as f:
                f.write("out" if mode == "out" else "in")
        except Exception:
            pass

    def write(self, pin, val):
        try:
            with open(f"{SYSFS}/gpio{pin}/value", "w") as f:
                f.write("1" if val else "0")
        except Exception:
            pass

    def read(self, pin):
        try:
            with open(f"{SYSFS}/gpio{pin}/value", "r") as f:
                return f.read().strip() == "1"
        except Exception:
            return False

    def cleanup(self):
        pass


# Always use sysfs backend (Pi 5 safe)
BACKEND = SysfsGPIO()