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
from vision import face_detector

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


def _safe_sleep(seconds: float, safety: Optional[SafetyManager]) -> None:
    """
    Sleep while continuously feeding the watchdog.
    Prevents watchdog timeout during long operations.
    Sends heartbeats every 0.1s to ensure watchdog never times out (timeout is 2s).
    """
    end_time = time.time() + seconds
    while time.time() < end_time:
        if safety:
            safety.heartbeat()
        time.sleep(0.1)  # Check every 100ms (10 heartbeats per second)


def _detect_face_binary(context: str, safety: Optional[SafetyManager]) -> bool:
    """
    Binary face detection - returns True if face present, False otherwise.
    Uses real OpenCV Haar Cascade detection.
    """
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    
    if USE_SIM:
        # Simulator: randomly return True/False for testing
        result = random.random() > 0.3  # 70% chance face visible
        LOGGER.info("Face visible (%s, sim): %s", context, result)
        return result
    
    # Production: real face detection
    try:
        # Heartbeat before camera capture
        if safety:
            safety.heartbeat()
        
        # Capture frame with periodic heartbeats during capture
        # Camera capture can take up to 5 seconds, so we need to send heartbeats
        frame = _capture_frame_with_heartbeat(context, safety)
        
        if frame is None:
            LOGGER.warning("Camera capture returned None (dependencies missing?)")
            return False
        
        # Heartbeat after capture
        if safety:
            safety.heartbeat()
        
        # Detect face (should be fast, but send heartbeat just in case)
        face_visible = face_detector.face_present(frame, context=context)
        if safety:
            safety.heartbeat()
        
        LOGGER.info("Face visible (%s): %s", context, face_visible)
        return face_visible
        
    except Exception as exc:
        LOGGER.warning("Face detection error (%s): %s", context, exc)
        return False


def _capture_frame_with_heartbeat(context: str, safety: Optional[SafetyManager]) -> Optional[object]:
    """
    Capture frame while sending heartbeats during the blocking operation.
    Uses threading to monitor camera capture and send heartbeats.
    """
    import threading
    
    frame_result = [None]
    capture_error = [None]
    
    def capture_worker():
        """Worker thread to capture frame."""
        try:
            frame_result[0] = camera.capture_frame_np(context=context)
        except Exception as exc:
            capture_error[0] = exc
    
    # Start capture in thread
    capture_thread = threading.Thread(target=capture_worker, daemon=True)
    capture_thread.start()
    
    # Send heartbeats while waiting for capture to complete
    capture_thread.join(timeout=0.1)  # Check every 100ms
    while capture_thread.is_alive():
        if safety:
            safety.heartbeat()
        capture_thread.join(timeout=0.1)
    
    # Final heartbeat
    if safety:
        safety.heartbeat()
    
    if capture_error[0]:
        raise capture_error[0]
    
    return frame_result[0]


def _show_face_led(mode: str, duration: float = 1.0, safety: Optional[SafetyManager] = None) -> None:
    """Show face animation on LED matrix with watchdog heartbeats."""
    try:
        from luma.core.render import canvas
        device = max7219_driver.init_display()
        if device is None:
            LOGGER.debug("LED device not available (simulator)")
            # Still send heartbeats during LED duration even if LED unavailable
            if safety:
                _safe_sleep(duration, safety)
            return
        
        start_time = time.time()
        frame_count = 0
        last_heartbeat = time.time()
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            with canvas(device) as draw:
                expressions.draw_face_frame(draw, device, mode, elapsed)
            
            frame_count += 1
            # Send heartbeat at least every 0.5s (well within 2s timeout)
            # Send every 10 frames (~0.6s) to avoid overhead
            current_time = time.time()
            if safety and (current_time - last_heartbeat >= 0.5 or frame_count % 10 == 0):
                safety.heartbeat()
                last_heartbeat = current_time
            
            # Use regular sleep for frame delay (we're already heartbeating)
            time.sleep(0.06)  # ~16 FPS
    except ImportError:
        # luma not available - graceful degradation
        LOGGER.debug("LED display library not available (simulator/dev mode)")
        # Still send heartbeats during LED duration even if LED unavailable
        if safety:
            _safe_sleep(duration, safety)
    except Exception as exc:
        LOGGER.warning("LED face display error: %s", exc)
        # Fallback: use safe_sleep if LED fails
        if safety:
            _safe_sleep(duration, safety)


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
        _update_ui_face("greeting")
        _show_face_led("normal", duration=2.0, safety=safety)
        _update_ui_face("normal")
        return
    
    if command == "forward":
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.3, safety=safety)
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.forward()
        # Send heartbeats continuously during movement
        _safe_sleep(0.6, safety)  # ~5-10cm at slow speed
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal")
        _show_face_led("normal", duration=0.3, safety=safety)
    
    elif command == "backward":
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.3, safety=safety)
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.backward()
        # Send heartbeats continuously during movement
        _safe_sleep(0.6, safety)  # ~5-10cm at slow speed
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal")
        _show_face_led("normal", duration=0.3, safety=safety)
    
    elif command == "turn_left":
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.2, safety=safety)
        driver.turn_left()
        # Send heartbeats continuously during movement
        _safe_sleep(0.6, safety)  # ~10-15 degrees
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal")
        _show_face_led("normal", duration=0.3, safety=safety)
    
    elif command == "turn_right":
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.2, safety=safety)
        driver.turn_right()
        # Send heartbeats continuously during movement
        _safe_sleep(0.6, safety)  # ~10-15 degrees
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal")
        _show_face_led("normal", duration=0.3, safety=safety)
    
    elif command == "stop":
        _update_ui_face("stop")
        driver.brake()
        if safety:
            safety.heartbeat()
        _show_face_led("normal", duration=1.0, safety=safety)
        _update_ui_face("normal")


def _perform_reposition(safety: Optional[SafetyManager]) -> bool:
    """
    Perform reposition sequence: backward → forward → rotate.
    Returns True if face becomes visible, False otherwise.
    """
    driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
    
    # Step 1: Move backward
    LOGGER.info("Reposition step: moving backward")
    _update_ui_face("moving")
    driver.set_motor_speed(50, 50)
    driver.backward()
    if safety:
        safety.heartbeat()
    _safe_sleep(0.6, safety)
    driver.brake()
    if safety:
        safety.heartbeat()
    
    # Check face after backward
    _safe_sleep(0.5, safety)  # Brief pause before detection
    if _detect_face_binary("after_backward", safety):
        LOGGER.info("Face visible after backward: True")
        _update_ui_face("normal")
        return True
    
    # Step 2: Move forward
    LOGGER.info("Reposition step: moving forward")
    _update_ui_face("moving")
    driver.set_motor_speed(50, 50)
    driver.forward()
    if safety:
        safety.heartbeat()
    _safe_sleep(0.8, safety)  # Slightly longer forward
    driver.brake()
    if safety:
        safety.heartbeat()
    
    # Check face after forward
    _safe_sleep(0.5, safety)
    if _detect_face_binary("after_forward", safety):
        LOGGER.info("Face visible after forward: True")
        _update_ui_face("normal")
        return True
    
    # Step 3: Rotate (random direction)
    LOGGER.info("Reposition step: rotating")
    _update_ui_face("moving")
    direction = random.choice(["left", "right"])
    if direction == "left":
        driver.turn_left()
    else:
        driver.turn_right()
    if safety:
        safety.heartbeat()
    _safe_sleep(0.6, safety)
    driver.brake()
    if safety:
        safety.heartbeat()
    
    # Check face after rotation
    _safe_sleep(0.5, safety)
    face_visible = _detect_face_binary("after_rotate", safety)
    LOGGER.info("Face visible after rotate: %s", face_visible)
    _update_ui_face("normal")
    
    return face_visible


class BasicCommandsModule(BaseModule):
    """Module 10: Basic Commands & Robot Interaction - Finalized for POC."""

    def __init__(self) -> None:
        super().__init__("basic_commands")
        self.safety: Optional[SafetyManager] = None
        self.reposition_attempted = False
    
    def set_safety_manager(self, safety_manager: SafetyManager) -> None:
        """Set the SafetyManager instance from orchestrator."""
        self.safety = safety_manager

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
        
        # Safety manager should be set by orchestrator before enter() is called
        # If not set, create a fallback (shouldn't happen in normal flow)
        if self.safety is None:
            self.logger.warning("SafetyManager not provided by orchestrator, creating fallback")
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
        face_visible_initial = _detect_face_binary("initial", self.safety)
        
        # If face not visible, wait and check again (with heartbeats)
        if not face_visible_initial:
            # Use safe_sleep to ensure heartbeats during wait
            _safe_sleep(2.0, self.safety)
            face_visible_initial = _detect_face_binary("retry", self.safety)
        
        # ONE reposition attempt if face not visible
        if not face_visible_initial and not self.reposition_attempted:
            self.logger.info("Reposition attempted: yes")
            self.reposition_attempted = True
            
            # Perform full reposition sequence: backward → forward → rotate
            face_visible_after = _perform_reposition(self.safety)
            
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
            # Send heartbeats during observation (safe_sleep handles this)
            _safe_sleep(2.0, self.safety)
            face_during = _detect_face_binary(f"after_{cmd}", self.safety)
            # Log observation (binary only, no interpretation)
            self.logger.debug("Face visible after command %s: %s", cmd, face_during)
        
        # Final state
        _update_ui_face("normal")
        _show_face_led("normal", duration=1.0, safety=self.safety)
        
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
