"""Basic Commands & Robot Interaction module."""
from __future__ import annotations

import random
import subprocess
import time
import threading
from pathlib import Path
from typing import Optional

from control import motors
from control.safety import SafetyManager
from display import expressions, max7219_driver
from sessions.modules.base import BaseModule, ModuleResult
from sensors.interface import get_ultrasonic_reader
from system.config import CONFIG
from system.logger import get_logger
from vision import camera
from vision import face_detector

LOGGER = get_logger("basic_commands")

# Global state for iPhone UI (simple in-memory state)
_ui_state = {
    "face_mode": "normal_smile",  # normal_smile, greeting, moving, stop, speaking
    "last_update": time.time(),
}
_ui_lock = threading.Lock()


def _update_ui_face(mode: str) -> None:
    """Update iPhone UI face state."""
    with _ui_lock:
        _ui_state["face_mode"] = mode
        _ui_state["last_update"] = time.time()


def _play_prompt(filename: str, safety: Optional[SafetyManager]) -> None:
    """Play WAV file with blocking playback and UI face updates."""
    # Set face to speaking
    _update_ui_face("speaking")
    
    # Construct path
    prompt_path = Path("voice_prompts/en_wav") / filename
    
    # Check simulator mode
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    if USE_SIM:
        LOGGER.info("Voice prompt (sim): %s", filename)
        _safe_sleep(1.0, safety)  # Simulate playback time
    else:
        # Use aplay via subprocess (blocking)
        try:
            SPEAKER_DEVICE = "plughw:3,0"
            cmd = ["aplay", "-D", SPEAKER_DEVICE, str(prompt_path)]
            # Send heartbeats during playback
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Monitor process and send heartbeats
            while proc.poll() is None:
                if safety:
                    safety.heartbeat()
                time.sleep(0.1)
            proc.wait()
            LOGGER.info("Voice prompt played: %s", filename)
        except FileNotFoundError:
            LOGGER.warning("aplay not found; falling back to simulated playback")
            _safe_sleep(1.0, safety)
        except Exception as exc:
            LOGGER.warning("Voice prompt playback failed: %s", exc)
            _safe_sleep(1.0, safety)  # Fallback to simulated time
    
    # Set face back to normal_smile
    _update_ui_face("normal_smile")


def _safe_sleep(seconds: float, safety: Optional[SafetyManager]) -> None:
    """
    Sleep while continuously feeding the watchdog.
    Prevents watchdog timeout during long operations.
    Sends heartbeats every 0.05s to ensure watchdog never times out (timeout is 2s).
    """
    if seconds <= 0:
        return
    
    end_time = time.time() + seconds
    while time.time() < end_time:
        if safety:
            safety.heartbeat()
        # Sleep in smaller chunks to ensure frequent heartbeats
        sleep_time = min(0.05, end_time - time.time())  # Max 50ms, or remaining time
        if sleep_time > 0:
            time.sleep(sleep_time)


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
    # Check every 50ms and send heartbeat to ensure watchdog is fed
    while capture_thread.is_alive():
        if safety:
            safety.heartbeat()
        capture_thread.join(timeout=0.05)  # Check every 50ms
    
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
            # Send heartbeat at least every 0.3s (well within 2s timeout)
            # More frequent heartbeats to prevent watchdog timeouts
            current_time = time.time()
            if safety and (current_time - last_heartbeat >= 0.3 or frame_count % 5 == 0):
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
        # Play greeting prompt
        _play_prompt("bc_01_greeting_hello.wav", safety)
        # No movement, just face animation
        _update_ui_face("greeting")
        _show_face_led("normal", duration=2.0, safety=safety)
        _update_ui_face("normal_smile")
        return
    
    if command == "forward":
        # Play forward demo prompt
        _play_prompt("bc_05_demo_forward.wav", safety)
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.2, safety=safety)
        if safety:
            safety.heartbeat()
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.forward()
        if safety:
            safety.heartbeat()
        # Continuous distance monitoring with ultrasonic brake
        ultrasonic_reader = get_ultrasonic_reader()
        start_time = time.time()
        last_ultrasonic_time = 0
        while time.time() - start_time < 5.0:
            if safety:
                safety.heartbeat()
            
            # Check distance (HC-SR04 needs ~60ms between readings)
            current_time = time.time()
            if current_time - last_ultrasonic_time >= 0.06:  # Minimum 60ms between readings
                distance = ultrasonic_reader()
                last_ultrasonic_time = current_time
                if distance > 0 and distance < 10:  # Valid reading and too close
                    LOGGER.warning("Ultrasonic brake triggered: distance=%.1f cm", distance)
                    driver.brake()
                    break
            
            # Sleep in small chunks to allow frequent checks
            _safe_sleep(0.05, safety)  # Reduced to 50ms for more responsive checks
        else:
            # Normal completion after 5 seconds
            driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal_smile")
        _show_face_led("normal", duration=0.2, safety=safety)
        # Play positive feedback
        _play_prompt("bc_10_demo_positive.wav", safety)
    
    elif command == "backward":
        # Play backward demo prompt
        _play_prompt("bc_06_demo_backward.wav", safety)
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.2, safety=safety)
        if safety:
            safety.heartbeat()
        driver.set_motor_speed(50, 50)  # Slow speed (50%)
        driver.backward()
        if safety:
            safety.heartbeat()
        # Continuous distance monitoring with ultrasonic brake
        ultrasonic_reader = get_ultrasonic_reader()
        start_time = time.time()
        last_ultrasonic_time = 0
        while time.time() - start_time < 5.0:
            if safety:
                safety.heartbeat()
            
            # Check distance (HC-SR04 needs ~60ms between readings)
            current_time = time.time()
            if current_time - last_ultrasonic_time >= 0.06:  # Minimum 60ms between readings
                distance = ultrasonic_reader()
                last_ultrasonic_time = current_time
                if distance > 0 and distance < 10:  # Valid reading and too close
                    LOGGER.warning("Ultrasonic brake triggered: distance=%.1f cm", distance)
                    driver.brake()
                    break
            
            # Sleep in small chunks to allow frequent checks
            _safe_sleep(0.05, safety)  # Reduced to 50ms for more responsive checks
        else:
            # Normal completion after 5 seconds
            driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal_smile")
        _show_face_led("normal", duration=0.2, safety=safety)
        # Play positive feedback
        _play_prompt("bc_10_demo_positive.wav", safety)
    
    elif command == "turn_left":
        # Play turn left demo prompt
        _play_prompt("bc_07_demo_turn_left.wav", safety)
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.15, safety=safety)
        if safety:
            safety.heartbeat()
        driver.turn_left()
        if safety:
            safety.heartbeat()
        # Send heartbeats continuously during movement
        _safe_sleep(5.0, safety)  # 5 seconds
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal_smile")
        _show_face_led("normal", duration=0.2, safety=safety)
        # Play positive feedback
        _play_prompt("bc_10_demo_positive.wav", safety)
    
    elif command == "turn_right":
        # Play turn right demo prompt
        _play_prompt("bc_08_demo_turn_right.wav", safety)
        _update_ui_face("moving")
        _show_face_led("normal", duration=0.15, safety=safety)
        if safety:
            safety.heartbeat()
        driver.turn_right()
        if safety:
            safety.heartbeat()
        # Send heartbeats continuously during movement
        _safe_sleep(5.0, safety)  # 5 seconds
        driver.brake()
        if safety:
            safety.heartbeat()
        _update_ui_face("normal_smile")
        _show_face_led("normal", duration=0.2, safety=safety)
        # Play positive feedback
        _play_prompt("bc_10_demo_positive.wav", safety)
    
    elif command == "stop":
        # Play stop demo prompt
        _play_prompt("bc_09_demo_stop.wav", safety)
        _update_ui_face("stop")
        driver.brake()
        if safety:
            safety.heartbeat()
        # Hold state for 5 seconds
        _safe_sleep(5.0, safety)
        _show_face_led("normal", duration=1.0, safety=safety)
        _update_ui_face("normal_smile")
        # Play positive feedback
        _play_prompt("bc_10_demo_positive.wav", safety)


def _perform_reposition(safety: Optional[SafetyManager]) -> bool:
    """
    Perform reposition sequence: backward → forward → rotate.
    Returns True if face becomes visible, False otherwise.
    """
    driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
    ultrasonic_reader = get_ultrasonic_reader()
    
    # Step 1: Move backward
    LOGGER.info("Reposition step: moving backward")
    _update_ui_face("moving")
    driver.set_motor_speed(50, 50)
    driver.backward()
    if safety:
        safety.heartbeat()
    # Continuous distance monitoring with ultrasonic brake
    start_time = time.time()
    last_ultrasonic_time = 0
    while time.time() - start_time < 0.6:
        if safety:
            safety.heartbeat()
        # Check distance (HC-SR04 needs ~60ms between readings)
        current_time = time.time()
        if current_time - last_ultrasonic_time >= 0.06:
            distance = ultrasonic_reader()
            last_ultrasonic_time = current_time
            if distance > 0 and distance < 10:
                LOGGER.warning("Ultrasonic brake triggered during reposition backward: distance=%.1f cm", distance)
                driver.brake()
                break
        _safe_sleep(0.05, safety)
    else:
        driver.brake()
    if safety:
        safety.heartbeat()
    
    # Check face after backward
    _safe_sleep(0.5, safety)  # Brief pause before detection
    if _detect_face_binary("after_backward", safety):
        LOGGER.info("Face visible after backward: True")
        _update_ui_face("normal_smile")
        return True
    
    # Step 2: Move forward
    LOGGER.info("Reposition step: moving forward")
    _update_ui_face("moving")
    driver.set_motor_speed(50, 50)
    driver.forward()
    if safety:
        safety.heartbeat()
    # Continuous distance monitoring with ultrasonic brake
    start_time = time.time()
    last_ultrasonic_time = 0
    while time.time() - start_time < 0.8:
        if safety:
            safety.heartbeat()
        # Check distance (HC-SR04 needs ~60ms between readings)
        current_time = time.time()
        if current_time - last_ultrasonic_time >= 0.06:
            distance = ultrasonic_reader()
            last_ultrasonic_time = current_time
            if distance > 0 and distance < 10:
                LOGGER.warning("Ultrasonic brake triggered during reposition forward: distance=%.1f cm", distance)
                driver.brake()
                break
        _safe_sleep(0.05, safety)
    else:
        driver.brake()
    if safety:
        safety.heartbeat()
    
    # Check face after forward
    _safe_sleep(0.5, safety)
    if _detect_face_binary("after_forward", safety):
        LOGGER.info("Face visible after forward: True")
        _update_ui_face("normal_smile")
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
    _update_ui_face("normal_smile")
    
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
        
        # Play session intro prompt
        _play_prompt("bc_02_session_intro.wav", self.safety)

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
        
        # If face not visible, play attention prompt and wait
        if not face_visible_initial:
            _play_prompt("bc_03_attention_look_at_me.wav", self.safety)
            # Use safe_sleep to ensure heartbeats during wait
            _safe_sleep(2.0, self.safety)
            _play_prompt("bc_04_calm_wait.wav", self.safety)
            face_visible_initial = _detect_face_binary("retry", self.safety)
        
        # ONE reposition attempt if face not visible
        if not face_visible_initial and not self.reposition_attempted:
            self.logger.info("Reposition attempted: yes")
            self.reposition_attempted = True
            
            # Play reposition start prompt
            _play_prompt("bc_12_reposition_start.wav", self.safety)
            
            # Perform full reposition sequence: backward → forward → rotate
            face_visible_after = _perform_reposition(self.safety)
            
            # Play reposition done prompt
            _play_prompt("bc_13_reposition_done.wav", self.safety)
            
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
            # Play observation waiting prompt
            _play_prompt("bc_11_observe_waiting.wav", self.safety)
            # Send heartbeats during observation (safe_sleep handles this)
            if self.safety:
                self.safety.heartbeat()
            _safe_sleep(2.0, self.safety)
            if self.safety:
                self.safety.heartbeat()
            face_during = _detect_face_binary(f"after_{cmd}", self.safety)
            # Log observation (binary only, no interpretation)
            self.logger.debug("Face visible after command %s: %s", cmd, face_during)
        
        # Play session closing prompt
        _play_prompt("bc_14_session_closing.wav", self.safety)
        
        # Final state
        _update_ui_face("normal_smile")
        _show_face_led("normal", duration=1.0, safety=self.safety)
        
        if self.safety:
            self.safety.heartbeat()
        
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup basic commands and robot interaction."""
        self.logger.info("Module end: basic_commands")
        
        # Play goodbye prompt
        _play_prompt("bc_15_session_goodbye.wav", self.safety)
        
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
