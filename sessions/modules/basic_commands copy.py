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

# Global state for iPhone UI (simple in-memory state)
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


def _detect_face_binary() -> bool:
    """
    Binary face detection - returns True if face present, False otherwise.
    No confidence scores, no emotion, no identity.
    """
    # For POC: simple stub that returns True in simulator, calls real detection in production
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    if USE_SIM:
        # Simulator: randomly return True/False for testing
        return random.random() > 0.3  # 70% chance face visible
    
    # Production: use camera to detect face (binary only)
    try:
        frame = camera.capture_frame()
        # TODO: Add actual face detection here (OpenCV or similar)
        # For now, assume face present if camera works
        return len(frame) > 0
    except Exception as exc:
        LOGGER.warning("Face detection error: %s", exc)
        return False


def _show_face_led(mode: str, duration: float = 1.0) -> None:
    """Show face animation on LED matrix."""
    try:
        from luma.core.render import canvas
        device = max7219_driver.init_display()
        if device is None:
            LOGGER.debug("LED device not available (simulator)")
            return
        
        start_time = time.time()
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            with canvas(device) as draw:
                expressions.draw_face_frame(draw, device, mode, elapsed)
            time.sleep(0.06)  # ~16 FPS
    except ImportError:
        # luma not available - graceful degradation
        LOGGER.debug("LED display library not available (simulator/dev mode)")
    except Exception as exc:
        LOGGER.warning("LED face display error: %s", exc)


def _perform_safe_command(command: str, safety: Optional[SafetyManager]) -> None:
    """
    Perform a safe robot command.
    Commands: greeting, forward, backward, turn_left, turn_right, stop
    """
    LOGGER.info("Command demonstrated: %s", command)
    
    # Get singleton motor driver
    driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
    
    if command == "greeting":
        # No movement, just face animation
        _show_face_led("normal", duration=2.0)
        _update_ui_face("greeting")
        if safety:
            safety.heartbeat()
        time.sleep(2.0)
        return
    
    if command == "forward":
        _update_ui_face("moving")
        _show_face_led("normal", duration=2.0)
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.forward()
        if safety:
            safety.heartbeat()
        time.sleep(1.0)  # ~5-10cm at slow speed
        driver.brake()
        _update_ui_face("normal")
        _show_face_led("normal", duration=2.0)
        if safety:
            safety.heartbeat()
    
    elif command == "backward":
        _update_ui_face("moving")
        _show_face_led("normal", duration=2.0)
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.backward()
        if safety:
            safety.heartbeat()
        time.sleep(1.0)  # ~5-10cm at slow speed
        driver.brake()
        _update_ui_face("normal")
        _show_face_led("normal", duration=2.0)
        if safety:
            safety.heartbeat()
    
    elif command == "turn_left":
        _update_ui_face("moving")
        _show_face_led("normal", duration=2.0)
        driver.turn_left()
        if safety:
            safety.heartbeat()
        time.sleep(1.0)  # ~10-15 degrees
        driver.brake()
        _update_ui_face("normal")
        _show_face_led("normal", duration=2.0)
        if safety:
            safety.heartbeat()
    
    elif command == "turn_right":
        _update_ui_face("moving")
        _show_face_led("normal", duration=2.0)
        driver.turn_right()
        if safety:
            safety.heartbeat()
        time.sleep(1.0)  # ~10-15 degrees
        driver.brake()
        _update_ui_face("normal")
        _show_face_led("normal", duration=2.0)
        if safety:  
            safety.heartbeat()
    
    elif command == "stop":
        _update_ui_face("stop")
        driver.brake()
        _show_face_led("normal", duration=2.0)
        _update_ui_face("normal")
        if safety:
            safety.heartbeat()


class BasicCommandsModule(BaseModule):
    """Module 10: Basic Commands & Robot Interaction - Finalized for POC."""

    def __init__(self) -> None:
        super().__init__("basic_commands")
        self.safety: Optional[SafetyManager] = None
        self.reposition_attempted = False

    def enter(self) -> None:
        """Initialize basic commands and robot interaction."""
        self.logger.info("Module start: basic_commands")
        self.reposition_attempted = False
        
        # Start iPhone UI server
        try:
            from sessions.modules.ui_server import start_ui_server
            start_ui_server(port=8080)
            self.logger.info("iPhone UI server started on port 8080")
        except Exception as exc:
            self.logger.warning("Failed to start UI server: %s", exc)
        
        # Get safety manager from orchestrator context if available
        # For now, create a minimal one
        try:
            from control.safety import SafetyManager
            self.safety = SafetyManager()
            self.safety.start()
        except Exception:
            self.safety = None

    def run(self) -> ModuleResult:
        """Run basic commands - demonstrates ≤3 commands safely."""
        self._set_running(True)
        
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        
        # Available commands (max 3 per session)
        available_commands = ["greeting", "forward", "backward", "turn_left", "turn_right", "stop"]
        selected_commands = random.sample(available_commands, min(3, len(available_commands)))
        
        self.logger.info("Demonstrating commands: %s", selected_commands)
        
        # Initial face observation
        face_visible_initial = _detect_face_binary()
        self.logger.info("Face visible (initial): %s", face_visible_initial)
        
        # If face not visible, wait 2 seconds and check again
        if not face_visible_initial:
            time.sleep(4.0)
            face_visible_initial = _detect_face_binary()
        
        # ONE reposition attempt if face not visible
        if not face_visible_initial and not self.reposition_attempted:
            self.logger.info("Reposition attempted: yes")
            self.reposition_attempted = True
            
            # Rotate 10-15 degrees (random direction)
            direction = random.choice(["left", "right"])
            _update_ui_face("moving")
            driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
            if direction == "left":
                driver.turn_left()
            else:
                driver.turn_right()
            if self.safety:
                self.safety.heartbeat()
            time.sleep(1.0)  # ~10-15 degrees
            driver.brake()
            _update_ui_face("normal")
            if self.safety:
                self.safety.heartbeat()
            
            # Check again after reposition
            time.sleep(1.0)
            face_visible_after = _detect_face_binary()
            self.logger.info("Face visible (after reposition): %s", face_visible_after)
        else:
            self.logger.info("Reposition attempted: no")
            face_visible_after = face_visible_initial
        
        # Demonstrate commands
        for i, cmd in enumerate(selected_commands):
            if self._stop_requested:
                break
            
            _perform_safe_command(cmd, self.safety)
            
            # Observe for 2 seconds after each command
            # Send heartbeats during observation
            for _ in range(6):  # 4 heartbeats over 2 seconds
                if self.safety:
                    self.safety.heartbeat()
                time.sleep(0.5)
            face_during = _detect_face_binary()
            # Log observation (binary only, no interpretation)
            self.logger.debug("Face visible after command %s: %s", cmd, face_during)
        
        # Final state
        _update_ui_face("normal")
        _show_face_led("normal", duration=2.0)
        
        if self.safety:
            self.safety.heartbeat()
        
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup basic commands and robot interaction."""
        self.logger.info("Module end: basic_commands")
        try:
            driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
            driver.brake()
        except Exception:
            pass
        if self.safety:
            self.safety.stop()
        
        # Stop iPhone UI server
        try:
            from sessions.modules.ui_server import stop_ui_server
            stop_ui_server()
        except Exception:
            pass
