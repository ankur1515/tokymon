"""HC-SR04 rear ultrasonic sensor driver using gpiozero (BCM pins 16/19).

Uses gpiozero instead of lgpio because the back sensor echo line is wired
directly to a 3.3 V-tolerant pin — no voltage divider required — and gpiozero
proved reliable on Pi 5 for this sensor in hardware tests.

Public API mirrors sensors/drivers/hcsr04.py so callers are interchangeable.
"""
from __future__ import annotations

import time

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("hcsr04_back")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Resolve BCM pins from CONFIG (pinmap_pi.yaml)
BCM_TRIG = int(CONFIG["pinmap"]["ultrasonic_hcsr04_back"]["trig"])  # 16
BCM_ECHO = int(CONFIG["pinmap"]["ultrasonic_hcsr04_back"]["echo"])  # 19

if not USE_SIM:
    try:
        from gpiozero import OutputDevice, DigitalInputDevice

        _trig = OutputDevice(BCM_TRIG)
        _echo = DigitalInputDevice(BCM_ECHO)
        LOGGER.info(
            "hcsr04_back: gpiozero initialised  TRIG=BCM%d  ECHO=BCM%d",
            BCM_TRIG,
            BCM_ECHO,
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("hcsr04_back: gpiozero init failed (%s) — falling back to sim", exc)
        USE_SIM = True
        _trig = None
        _echo = None
else:
    _trig = None
    _echo = None
    LOGGER.info("hcsr04_back: simulator mode — no GPIO access")


def read_distance_cm(timeout_s: float = 0.05) -> float:
    """Measure rear distance using HC-SR04 (gpiozero backend).

    Follows the same pulse-echo timing as the working raw script:
      - TRIG low for 50 ms to settle
      - 10 µs TRIG pulse
      - Poll ECHO for a rising edge within timeout_s
      - Returns distance in cm, or -1 on timeout / out-of-range

    Args:
        timeout_s: Maximum time (seconds) to wait for an echo. Default 0.05 s.

    Returns:
        Distance in cm (2–400), or -1 if no valid echo received.
    """
    if USE_SIM:
        # Return a plausible rear-side mock distance
        LOGGER.debug("hcsr04_back (sim): returning mock 60.0 cm")
        return 60.0

    # ── settle ──────────────────────────────────────────────────────────────
    _trig.off()
    time.sleep(0.05)

    # ── 10 µs trigger pulse ──────────────────────────────────────────────────
    _trig.on()
    time.sleep(0.00001)
    _trig.off()

    # ── wait for echo HIGH (pulse start) ────────────────────────────────────
    deadline = time.time() + timeout_s
    pulse_start: float | None = None
    while time.time() < deadline:
        if _echo.value == 1:
            pulse_start = time.time()
            break

    if pulse_start is None:
        LOGGER.debug("hcsr04_back: no echo detected (timeout)")
        return -1

    # ── wait for echo LOW (pulse end) ───────────────────────────────────────
    deadline = time.time() + timeout_s
    pulse_end: float | None = None
    while time.time() < deadline:
        if _echo.value == 0:
            pulse_end = time.time()
            break

    if pulse_end is None:
        LOGGER.debug("hcsr04_back: echo did not go LOW (timeout)")
        return -1

    # ── distance calculation ─────────────────────────────────────────────────
    duration = pulse_end - pulse_start
    dist = duration * 17150  # (speed-of-sound / 2) conversion → cm

    if dist < 2 or dist > 400:
        LOGGER.debug("hcsr04_back: out-of-range %.2f cm", dist)
        return -1

    LOGGER.debug("hcsr04_back: %.2f cm", dist)
    return round(dist, 2)


def cleanup() -> None:
    """Release gpiozero GPIO pins (BCM TRIG/ECHO).

    Must be called on app exit so the next session can claim the pins
    without hitting 'GPIO busy'. After cleanup, read_distance_cm falls
    back to sim mode for the remainder of this process run.
    """
    global _trig, _echo, USE_SIM
    if _trig is not None:
        try:
            _trig.close()
        except Exception:
            pass
        _trig = None
    if _echo is not None:
        try:
            _echo.close()
        except Exception:
            pass
        _echo = None
    USE_SIM = True
    LOGGER.info(
        "hcsr04_back: GPIO pins released (BCM%d, BCM%d)",
        BCM_TRIG, BCM_ECHO,
    )
