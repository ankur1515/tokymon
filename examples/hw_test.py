"""Tokymon hardware verification flow."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

from brain import policy_engine
from control import actuators
from control.safety import SafetyManager
from display import max7219_driver
from examples.hw_test_helpers import (
    ensure_dir,
    led_show_short,
    safe_camera_capture,
    safe_stt_or_fallback,
    safe_tts,
    timestamp_slug,
    write_report,
)
from sensors import interface
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hw_test")
ROOT_PATH = Path(CONFIG["runtime"]["root_path"])
DATA_DIR = ROOT_PATH / "data"
PHOTOS_DIR = DATA_DIR / "photos"
REPORTS_DIR = DATA_DIR / "reports"
TESTS_CFG = CONFIG.get("tests", {})
MOVEMENT_CFG = TESTS_CFG.get("movement_durations", {})
MIN_SAFE_CM = TESTS_CFG.get("ultrasonic_min_safe_cm", 15)
STT_TIMEOUT = TESTS_CFG.get("stt_timeout_s", 4)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tokymon hardware flow")
    parser.add_argument("--run-hw", action="store_true", help="Allow running the test flow")
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Skip interactive ENTER confirmation (useful for tests)",
    )
    return parser.parse_args(argv)


def _require_permission(run_hw: bool) -> None:
    env_name = os.getenv("TOKY_ENV", "dev")
    if env_name != "prod" and not run_hw:
        raise SystemExit(
            "Hardware test requires TOKY_ENV=prod or passing --run-hw when simulating"
        )


def _hardware_enabled() -> bool:
    env_name = os.getenv("TOKY_ENV", "dev")
    sim_flag = CONFIG["services"]["runtime"].get("use_simulator", env_name != "prod")
    return env_name == "prod" and not sim_flag


def _confirm_ready(auto_confirm: bool) -> None:
    if auto_confirm:
        LOGGER.info("Auto-confirm enabled; skipping prompt")
        return
    input("Ensure area is clear and Tokymon is on blocks. Press ENTER to continue...")


def _movement_duration(key: str) -> float:
    return float(MOVEMENT_CFG.get(key, 1.0))


def _perform_motion(kind: str, duration: float, ir_left, ir_right, safety: SafetyManager, hw_enabled: bool) -> None:
    led_show_short(kind)
    LOGGER.info("Motion %s for %.2fs", kind, duration)
    if not hw_enabled:
        LOGGER.info("Simulator mode: skipping GPIO motion")
        return
    if ir_left() or ir_right():
        raise RuntimeError("IR sensors blocked; aborting motion")
    try:
        if kind == "forward":
            actuators.move("forward", duration)
        elif kind == "back":
            actuators.move("backward", duration)
        elif kind == "left":
            actuators.turn_left(duration)
        elif kind == "right":
            actuators.turn_right(duration)
        else:
            LOGGER.warning("Unknown motion %s", kind)
    finally:
        actuators.stop()
        safety.heartbeat()


def run_hw_flow(run_hw: bool, auto_confirm: bool = False) -> Dict:
    _require_permission(run_hw)
    hw_enabled = _hardware_enabled()
    safety = SafetyManager()
    safety.start()
    report = {
        "timestamp": timestamp_slug(),
        "env": os.getenv("TOKY_ENV", "dev"),
        "hardware_enabled": hw_enabled,
        "steps": [],
    }
    ultrasonic_reader = interface.get_ultrasonic_reader()
    ir_left_reader = interface.get_ir_left_reader()
    ir_right_reader = interface.get_ir_right_reader()

    ensure_dir(DATA_DIR)
    try:
        _confirm_ready(auto_confirm)
        max7219_driver.init_display()

        # Greeting
        led_show_short("hello")
        safe_tts("Hello, I am Tokymon. How can I help you?")
        report["steps"].append({"greeting": True})

        # Motors test
        motions = [
            ("forward", _movement_duration("forward")),
            ("back", _movement_duration("backward")),
            ("right", _movement_duration("turn")),
            ("left", _movement_duration("turn")),
        ]
        for kind, duration in motions:
            _perform_motion(kind, duration, ir_left_reader, ir_right_reader, safety, hw_enabled)
            report["steps"].append({"motion": kind, "duration": duration})

        # Camera test
        photo_path = safe_camera_capture(PHOTOS_DIR)
        safe_tts("Photo captured." if photo_path else "Camera unavailable.")
        report["steps"].append({"camera": str(photo_path) if photo_path else None})

        # Audio Q/A test
        led_show_short("listening")
        name = safe_stt_or_fallback("What is your name?", STT_TIMEOUT)
        led_show_short("happy")
        report["steps"].append({"stt_name": name})

        # Ultrasonic test
        distance = ultrasonic_reader()
        report["steps"].append({"ultrasonic_cm": distance})
        if distance < MIN_SAFE_CM:
            led_show_short("error")
            safe_tts("Obstacle detected. Stopping all motion.")
            hw_enabled = False
        else:
            safe_tts(f"Distance is {distance:.1f} centimeters.")

        # IR sensors test
        ir_state = {"left": bool(ir_left_reader()), "right": bool(ir_right_reader())}
        led_show_short("alert" if any(ir_state.values()) else "success")
        report["steps"].append({"ir": ir_state})

        # Integrated scenario
        response = safe_stt_or_fallback(
            "Shall I move forward for two seconds? Say yes or no.", STT_TIMEOUT
        ).lower()
        decision = response.strip()
        led_show_short("listening")
        if "yes" in decision:
            intent = {"action": "move", "params": {"dir": "forward", "duration": 2.0}}
            approved = False
            try:
                policy_engine.enforce(intent)
                approved = True
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("Policy blocked movement: %s", exc)
            if approved and hw_enabled:
                _perform_motion("forward", 2.0, ir_left_reader, ir_right_reader, safety, hw_enabled)
                safe_tts("Moving forward now.")
            else:
                LOGGER.info("Movement skipped (approved=%s hw=%s)", approved, hw_enabled)
        else:
            safe_tts("Canceled.")
        report["steps"].append({"integrated_response": decision, "hw_enabled": hw_enabled})

        safe_tts("Hardware test completed. Shutting down.")
        led_show_short("success")
        safety.heartbeat()
        return report
    finally:
        try:
            actuators.stop()
        finally:
            safety.stop()
        report_path = REPORTS_DIR / f"hw_test_report_{timestamp_slug()}.json"
        write_report(report_path, report)
        LOGGER.info("Report saved to %s", report_path)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_hw_flow(run_hw=args.run_hw, auto_confirm=args.auto_confirm)
    except SystemExit as exc:
        LOGGER.error(str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - top-level guard
        LOGGER.exception("Hardware test failed: %s", exc)
        return 2
    LOGGER.info("Hardware test completed: %s", report.get("timestamp"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
