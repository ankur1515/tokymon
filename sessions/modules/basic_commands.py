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


def _detect_face_binary(context: str, safety: Optional[SafetyManager], retries: int = 2) -> bool:
    """
    Binary face detection - returns True if face present, False otherwise.
    Uses real OpenCV Haar Cascade detection with retry logic.
    """
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    
    if USE_SIM:
        # Simulator: randomly return True/False for testing
        result = random.random() > 0.3  # 70% chance face visible
        LOGGER.info("Face visible (%s, sim): %s", context, result)
        return result
    
    # Production: real face detection with retries
    for attempt in range(retries + 1):
        try:
            # Heartbeat before camera capture
            if safety:
                safety.heartbeat()
            
            # Capture frame with periodic heartbeats during capture
            # Camera capture can take up to 5 seconds, so we need to send heartbeats
            frame = _capture_frame_with_heartbeat(context, safety)
            
            if frame is None:
                LOGGER.warning("Camera capture returned None (dependencies missing?)")
                if attempt < retries:
                    _safe_sleep(0.5, safety)  # Brief wait before retry
                    continue
                return False
            
            # Heartbeat after capture
            if safety:
                safety.heartbeat()
            
            # Detect face (should be fast, but send heartbeat just in case)
            face_visible = face_detector.face_present(frame, context=context)
            if safety:
                safety.heartbeat()
            
            if face_visible:
                LOGGER.info("Face visible (%s): True (attempt %d/%d)", context, attempt + 1, retries + 1)
                return True
            elif attempt < retries:
                # Retry if no face detected
                LOGGER.debug("Face not visible (%s), retrying (attempt %d/%d)", context, attempt + 1, retries + 1)
                _safe_sleep(0.5, safety)  # Brief wait before retry
            else:
                LOGGER.info("Face visible (%s): False (after %d attempts)", context, retries + 1)
                return False
            
        except Exception as exc:
            LOGGER.warning("Face detection error (%s, attempt %d/%d): %s", context, attempt + 1, retries + 1, exc)
            if attempt < retries:
                _safe_sleep(0.5, safety)  # Brief wait before retry
                continue
            return False
    
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
        # Play greeting prompt (first prompt)
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
        driver.forward(speed=100)  # Full speed (100%)
        if safety:
            safety.heartbeat()
        # Continuous distance monitoring with ultrasonic brake
        ultrasonic_reader = get_ultrasonic_reader()
        start_time = time.time()
        last_ultrasonic_time = 0
        distances_logged = []
        while time.time() - start_time < 3.0:  # 3 seconds duration
            if safety:
                safety.heartbeat()
            
            # Check distance (HC-SR04 needs ~60ms between readings)
            current_time = time.time()
            if current_time - last_ultrasonic_time >= 0.06:  # Minimum 60ms between readings
                distance = ultrasonic_reader()
                last_ultrasonic_time = current_time
                if distance > 0:
                    distances_logged.append(distance)
                    LOGGER.info("Ultrasonic distance during forward: %.1f cm", distance)
                elif distance == -1:
                    LOGGER.debug("Ultrasonic timeout during forward")
                if distance > 0 and distance < 20:  # Valid reading and too close
                    LOGGER.warning("Ultrasonic brake triggered: distance=%.1f cm", distance)
                    driver.brake()
                    break
            
            # Sleep in small chunks to allow frequent checks
            _safe_sleep(0.05, safety)  # Reduced to 50ms for more responsive checks
        else:
            # Normal completion after 3 seconds
            driver.brake()
        if safety:
            safety.heartbeat()
        
        # Log final distance after command
        final_distance = ultrasonic_reader()
        if final_distance > 0:
            LOGGER.info("Ultrasonic distance after forward: %.1f cm", final_distance)
        elif final_distance == -1:
            LOGGER.debug("Ultrasonic timeout after forward")
        if distances_logged:
            avg_distance = sum(distances_logged) / len(distances_logged)
            LOGGER.info("Average ultrasonic distance during forward: %.1f cm (from %d readings)", 
                       avg_distance, len(distances_logged))
        else:
            LOGGER.warning("No valid ultrasonic readings during forward command")
        
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
        driver.backward(speed=100)  # Full speed (100%)
        if safety:
            safety.heartbeat()
        # Continuous distance monitoring with ultrasonic brake
        ultrasonic_reader = get_ultrasonic_reader()
        start_time = time.time()
        last_ultrasonic_time = 0
        distances_logged = []
        while time.time() - start_time < 3.0:  # 3 seconds duration
            if safety:
                safety.heartbeat()
            
            # Check distance (HC-SR04 needs ~60ms between readings)
            current_time = time.time()
            if current_time - last_ultrasonic_time >= 0.06:  # Minimum 60ms between readings
                distance = ultrasonic_reader()
                last_ultrasonic_time = current_time
                if distance > 0:
                    distances_logged.append(distance)
                    LOGGER.info("Ultrasonic distance during backward: %.1f cm", distance)
                elif distance == -1:
                    LOGGER.debug("Ultrasonic timeout during backward")
                if distance > 0 and distance < 20:  # Valid reading and too close
                    LOGGER.warning("Ultrasonic brake triggered: distance=%.1f cm", distance)
                    driver.brake()
                    break
            
            # Sleep in small chunks to allow frequent checks
            _safe_sleep(0.05, safety)  # Reduced to 50ms for more responsive checks
        else:
            # Normal completion after 3 seconds
            driver.brake()
        if safety:
            safety.heartbeat()
        
        # Log final distance after command
        final_distance = ultrasonic_reader()
        if final_distance > 0:
            LOGGER.info("Ultrasonic distance after backward: %.1f cm", final_distance)
        elif final_distance == -1:
            LOGGER.debug("Ultrasonic timeout after backward")
        if distances_logged:
            avg_distance = sum(distances_logged) / len(distances_logged)
            LOGGER.info("Average ultrasonic distance during backward: %.1f cm (from %d readings)", 
                       avg_distance, len(distances_logged))
        else:
            LOGGER.warning("No valid ultrasonic readings during backward command")
        
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
        # Set direction for turn left, then override speed to 100%
        driver.set_direction('A', 'backward')
        driver.set_direction('B', 'forward')
        driver.set_motor_speed(100, 100)  # Full speed (100%)
        if safety:
            safety.heartbeat()
        # Send heartbeats continuously during movement
        _safe_sleep(3.0, safety)  # 3 seconds
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
        # Set direction for turn right, then override speed to 100%
        driver.set_direction('A', 'forward')
        driver.set_direction('B', 'backward')
        driver.set_motor_speed(100, 100)  # Full speed (100%)
        if safety:
            safety.heartbeat()
        # Send heartbeats continuously during movement
        _safe_sleep(3.0, safety)  # 3 seconds
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


def _perform_360_rotation(safety: Optional[SafetyManager]) -> bool:
    """
    Perform 360 degree rotation, stopping if face becomes visible.
    Returns True if face becomes visible, False otherwise.
    """
    driver = motors._get_driver() if hasattr(motors, '_get_driver') else motors.MotorDriver()
    
    LOGGER.info("Starting 360 degree rotation to find face")
    _update_ui_face("moving")
    
    # Set direction for continuous left rotation at 100% speed
    # Calculate time for 360 degrees: approximately 12 seconds at 70% speed
    # At 100% speed, it should be faster, estimate ~8-10 seconds for full rotation
    driver.set_direction('A', 'backward')
    driver.set_direction('B', 'forward')
    driver.set_motor_speed(100, 100)  # Full speed (100%)
    
    if safety:
        safety.heartbeat()
    
    # Rotate and check for face continuously
    start_time = time.time()
    last_face_check = 0
    rotation_duration = 10.0  # Maximum rotation time for 360 degrees at 100% speed
    
    while time.time() - start_time < rotation_duration:
        if safety:
            safety.heartbeat()
        
        # Check for face every 0.5 seconds during rotation
        current_time = time.time()
        if current_time - last_face_check >= 0.5:
            if _detect_face_binary("during_360_rotation", safety):
                LOGGER.info("Face visible during 360 rotation: True")
                driver.brake()
                _update_ui_face("normal_smile")
                return True
            last_face_check = current_time
        
        _safe_sleep(0.1, safety)
    
    # Complete rotation without finding face
    driver.brake()
    if safety:
        safety.heartbeat()
    
    # Final face check after rotation
    _safe_sleep(0.5, safety)
    face_visible = _detect_face_binary("after_360_rotation", safety)
    LOGGER.info("Face visible after 360 rotation: %s", face_visible)
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
        
        # Start iPhone UI server first
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
        
        # Wait 5 seconds before starting greeting
        _safe_sleep(5.0, self.safety)

    def run(self) -> ModuleResult:
        """Run basic commands - always starts with greeting, then 2 other commands, then face detection."""
        self._set_running(True)
        
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        
        # Step 1: Always start with greeting command (first prompt)
        self.logger.info("Demonstrating commands: greeting (always first)")
        _perform_safe_command("greeting", self.safety)
        
        # Step 2: Play session intro prompt (second prompt)
        _play_prompt("bc_02_session_intro.wav", self.safety)
        
        # Step 3: Select 2 other commands (excluding greeting)
        available_commands = ["forward", "backward", "turn_left", "turn_right", "stop"]
        selected_commands = random.sample(available_commands, min(2, len(available_commands)))
        
        self.logger.info("Demonstrating additional commands: %s", selected_commands)
        
        # Step 4: Demonstrate the 2 other commands
        for i, cmd in enumerate(selected_commands):
            if self._stop_requested:
                break
            
            _perform_safe_command(cmd, self.safety)
        
        # Step 5: Face detection logic after all commands
        # Initial face observation
        face_visible_initial = _detect_face_binary("initial", self.safety)
        
        # If face not visible, perform 360 degree rotation
        if not face_visible_initial and not self.reposition_attempted:
            self.logger.info("Face not visible, starting 360 degree rotation")
            self.reposition_attempted = True
            
            # Play reposition start prompt
            _play_prompt("bc_12_reposition_start.wav", self.safety)
            
            # Perform 360 degree rotation, stopping if face becomes visible
            face_visible_after = _perform_360_rotation(self.safety)
            
            # Play reposition done prompt
            _play_prompt("bc_13_reposition_done.wav", self.safety)
            
            self.logger.info("Face visible (after 360 rotation): %s", face_visible_after)
        else:
            self.logger.info("Face visible or rotation already attempted")
            face_visible_after = face_visible_initial
        
        # Observe for 2 seconds after face detection/rotation
        # Play observation waiting prompt
        _play_prompt("bc_11_observe_waiting.wav", self.safety)
        # Send heartbeats during observation (safe_sleep handles this)
        if self.safety:
            self.safety.heartbeat()
        _safe_sleep(2.0, self.safety)
        if self.safety:
            self.safety.heartbeat()
        face_during = _detect_face_binary("after_all_commands", self.safety)
        # Log observation (binary only, no interpretation)
        self.logger.debug("Face visible after all commands: %s", face_during)
        
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
