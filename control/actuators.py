"""High-level actuator primitives that wrap raw motor calls."""
from __future__ import annotations

import time
from typing import Literal

from control import motors
from system.logger import get_logger

LOGGER = get_logger("actuators")


Direction = Literal["forward", "backward"]


def move(direction: Direction, duration: float) -> None:
    LOGGER.info("Actuator move %s for %.2fs", direction, duration)
    if direction == "forward":
        motors.forward()
    else:
        motors.backward()
    time.sleep(max(duration, 0))
    motors.stop()


def stop() -> None:
    motors.stop()
