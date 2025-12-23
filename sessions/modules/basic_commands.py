"""Basic Commands & Robot Interaction module."""
from __future__ import annotations

import random
import time
import threading
from typing import Optional

from control import motors
from control.safety import SafetyManager
from display import expressions, max7219_driver
from sessions.modules.base import BaseModule, ModuleResult
from system.config import CONFIG
from system.logger import get_logger
from vision import camera

LOGGER = get_logger("basic_commands")

# ──────────────────────────────────────────────
# 🔹 GLOBAL UI STATE (iPhone UI)
# ──────────────────────────────────────────────
_ui_state = {
    "face_mode": "normal",  # normal, greeting, moving, stop
    "last_update": time.time(),
}
_ui_lock = threading.Lock()


def _update_ui_face(mode: str) -> None:
    """Update iPhone UI face state."""
    with _ui_lock:
        _ui_state["face_mode"] = mode
        _ui_state["last_update"] = time.time()


# ──────────────────────────────────────────────
# ✅ NEW: WATCHDOG-SAFE SLEEP
# ──────────────────────────────────────────────
def _safe_sleep(seconds: float, safety: Optional[SafetyManager]) -> None:
    """
    Sleep while continuously feeding the watchdog.
    """
    end_time = time.time() + seconds
    while time.time() < end_time:
        if safety:
            safety.heartbeat()
        time.sleep(0.3)


# ──────────────────────────────────────────────
# ✅ UPDATED: CAMERA + HEARTBEAT
# ──────────────────────────────────────────────
def _capture_face(context: str, safety: Optional[SafetyManager]) -> bool:
    """
    Capture a frame safely.
    Returns True if capture succeeded.
    """
    try:
        if safety:
            safety.heartbeat()

        camera.capture_frame()

        if safety:
            safety.heartbeat()

        return True
    except Exception as exc:
        LOGGER.warning("Camera capture failed (%s): %s", context, exc)
        return False


# ──────────────────────────────────────────────
# ✅ UPDATED: FACE CHECK (NO BLOCKING)
# ──────────────────────────────────────────────
def _detect_face_binary(safety: Optional[SafetyManager], context: str) -> bool:
    """
    Binary face detection (POC-safe).
    """
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

    if USE_SIM:
        return random.random() > 0.3

    return _capture_face(context=context, safety=safety)


# ──────────────────────────────────────────────
# ✅ UPDATED: LED FACE WITH HEARTBEAT
# ──────────────────────────────────────────────
def _show_face_led(
    mode: str,
    duration: float,
    safety: Optional[SafetyManager],
) -> None:
    """Show face animation on LED matrix safely."""
    try:
        from luma.core.render import canvas
        device = max7219_driver.init_display()
        if device is None:
            return

        start_time = time.time()
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            with canvas(device) as draw:
                expressions.draw_face_frame(draw, device, mode, elapsed)

            if safety:
                safety.heartbeat()

            time.sleep(0.06)
    except Exception as exc:
        LOGGER.warning("LED face display error: %s", exc)


# ──────────────────────────────────────────────
# ✅ UPDATED: SAFE COMMAND EXECUTION
# ──────────────────────────────────────────────
def _perform_safe_command(command: str, safety: Optional[SafetyManager]) -> None:
    LOGGER.info("Command demonstrated: %s", command)

    driver = motors._get_driver() if hasattr(motors, "_get_driver") else motors.MotorDriver()

    if command == "greeting":
        _update_ui_face("greeting")
        _show_face_led("normal", 2.0, safety)
        _safe_sleep(2.0, safety)
        return

    _update_ui_face("moving")
    _show_face_led("normal", 1.5, safety)

    if command == "forward":
        driver.set_motor_speed(50, 50)
        driver.forward()
    elif command == "backward":
        driver.set_motor_speed(50, 50)
        driver.backward()
    elif command == "turn_left":
        driver.turn_left()
    elif command == "turn_right":
        driver.turn_right()
    elif command == "stop":
        driver.brake()
        _update_ui_face("stop")
        _safe_sleep(1.0, safety)
        _update_ui_face("normal")
        return

    _safe_sleep(1.0, safety)
    driver.brake()

    _update_ui_face("normal")
    _show_face_led("normal", 1.5, safety)


# ──────────────────────────────────────────────
# 🧠 MODULE CLASS
# ──────────────────────────────────────────────
class BasicCommandsModule(BaseModule):
    """Basic Commands Module (watchdog-safe)."""

    def __init__(self) -> None:
        super().__init__("basic_commands")
        self.safety: Optional[SafetyManager] = None
        self.reposition_attempted = False

    def enter(self) -> None:
        self.logger.info("Module start: basic_commands")

        try:
            from sessions.modules.ui_server import start_ui_server
            start_ui_server(port=8080)
        except Exception:
            pass

        try:
            self.safety = SafetyManager()
            self.safety.start()
        except Exception:
            self.safety = None

    def run(self) -> ModuleResult:
        self._set_running(True)

        commands = random.sample(
            ["greeting", "forward", "backward", "turn_left", "turn_right", "stop"],
            3,
        )

        self.logger.info("Demonstrating commands: %s", commands)

        face_visible = _detect_face_binary(self.safety, "initial")

        if not face_visible:
            _safe_sleep(3.0, self.safety)
            face_visible = _detect_face_binary(self.safety, "retry")

        if not face_visible and not self.reposition_attempted:
            self.reposition_attempted = True
            driver = motors._get_driver()
            driver.turn_left()
            _safe_sleep(1.0, self.safety)
            driver.brake()
            _safe_sleep(1.0, self.safety)

        for cmd in commands:
            if self._stop_requested:
                break

            _perform_safe_command(cmd, self.safety)
            _safe_sleep(2.0, self.safety)
            _detect_face_binary(self.safety, f"after_{cmd}")

        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        self.logger.info("Module end: basic_commands")

        try:
            motors._get_driver().brake()
        except Exception:
            pass

        if self.safety:
            self.safety.stop()

        try:
            from sessions.modules.ui_server import stop_ui_server
            stop_ui_server()
        except Exception:
            pass