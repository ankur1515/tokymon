"""TB6612FNG motor driver (from raw_scripts/tb6612_Fix.py)."""
from __future__ import annotations

import time
import os

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("motors")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
TOKY_ENV = os.environ.get("TOKY_ENV", "dev").lower()

# Pin definitions - try CONFIG first, fallback to TB6612 defaults
try:
    PINS = CONFIG["pinmap"]["motors"]
    # TB6612 uses: PWMA, AIN1, AIN2 for motor A; PWMB, BIN1, BIN2 for motor B; STBY
    PWMA_PIN = PINS.get("motor_a", {}).get("pwm", 12)  # Default PWM pin for motor A
    AIN1_PIN = PINS.get("motor_a", {}).get("in1", 5)
    AIN2_PIN = PINS.get("motor_a", {}).get("in2", 6)
    PWMB_PIN = PINS.get("motor_b", {}).get("pwm", 13)  # Default PWM pin for motor B
    # For motor B: prefer in1/in2 (TB6612), fallback to in3/in4 (L298), then defaults
    motor_b = PINS.get("motor_b", {})
    BIN1_PIN = motor_b.get("in1", motor_b.get("in3", 20))
    BIN2_PIN = motor_b.get("in2", motor_b.get("in4", 21))
    STBY_PIN = PINS.get("standby", 22)
    # If we got L298 pins (in3/in4), use TB6612 defaults instead
    if BIN1_PIN in (12, 13) and BIN2_PIN in (12, 13):  # L298 structure detected
        LOGGER.warning("CONFIG has L298 structure; using TB6612 defaults for motor B")
        BIN1_PIN = 20
        BIN2_PIN = 21
    LOGGER.info("Using motor pins: PWMA=%s AIN1=%s AIN2=%s PWMB=%s BIN1=%s BIN2=%s STBY=%s",
                PWMA_PIN, AIN1_PIN, AIN2_PIN, PWMB_PIN, BIN1_PIN, BIN2_PIN, STBY_PIN)
except (KeyError, TypeError):
    # Fallback to TB6612 defaults (exact from working script)
    PWMA_PIN = 12
    AIN1_PIN = 5
    AIN2_PIN = 6
    PWMB_PIN = 13
    BIN1_PIN = 20
    BIN2_PIN = 21
    STBY_PIN = 22
    LOGGER.warning("Using fallback TB6612 pin defaults: PWMA=12 AIN1=5 AIN2=6 PWMB=13 BIN1=20 BIN2=21 STBY=22")

# Motor driver state
_h = None
_pwm_frequency = 1000
_initialized = False


def _init_driver():
    """Initialize motor driver (TB6612) - exact logic from tb6612_Fix.py."""
    global _h, _initialized
    if _initialized:
        return

    if USE_SIM:
        LOGGER.info("Motor driver: simulator mode (no hardware init)")
        _initialized = True
        return

    # Try lgpio first (required for Raspberry Pi 5 GPIO control with PWM)
    try:
        import lgpio as GPIO
        _h = GPIO.gpiochip_open(0)
        LOGGER.info("TB6612 driver initialized: GPIO Chip 0 opened (lgpio)")

        # List of all control pins (BCM numbering)
        output_pins = [PWMA_PIN, AIN1_PIN, AIN2_PIN, PWMB_PIN, BIN1_PIN, BIN2_PIN, STBY_PIN]

        # Claim all pins as OUTPUT
        for pin in output_pins:
            GPIO.gpio_claim_output(_h, pin)

        # Initialize STBY to HIGH to enable the motor driver
        GPIO.gpio_write(_h, STBY_PIN, GPIO.HIGH)
        LOGGER.info(f"Driver enabled: STBY (GPIO{STBY_PIN}) set HIGH")

        # Start PWM at 0% duty cycle (stopped)
        GPIO.tx_pwm(_h, PWMA_PIN, _pwm_frequency, 0)
        GPIO.tx_pwm(_h, PWMB_PIN, _pwm_frequency, 0)
        LOGGER.info(f"PWM ready on GPIO{PWMA_PIN} and GPIO{PWMB_PIN} at {_pwm_frequency}Hz")
        _initialized = True
        return
    except ImportError:
        LOGGER.warning("lgpio not available; using basic GPIO control (no PWM)")
    except Exception as e:
        LOGGER.warning("lgpio init failed: %s; using basic GPIO control", e)

    # Fallback to rpi_gpio (basic on/off, no PWM) - for simulator/dev
    from drivers import rpi_gpio
    for pin in [AIN1_PIN, AIN2_PIN, BIN1_PIN, BIN2_PIN, STBY_PIN]:
        rpi_gpio.setup(pin, "out")
    rpi_gpio.write(STBY_PIN, True)  # Enable driver
    LOGGER.info("TB6612 driver initialized: using basic GPIO (no PWM)")
    _initialized = True


def _set_motor_speed(speed_a: int, speed_b: int):
    """Set PWM duty cycle for both motors (0-100) - exact from tb6612_Fix.py."""
    if USE_SIM:
        LOGGER.debug("Motor speed (sim): A=%s%%, B=%s%%", speed_a, speed_b)
        return

    speed_a = max(0, min(100, speed_a))
    speed_b = max(0, min(100, speed_b))

    if _h is not None:
        try:
            import lgpio as GPIO
            GPIO.tx_pwm(_h, PWMA_PIN, _pwm_frequency, speed_a)
            GPIO.tx_pwm(_h, PWMB_PIN, _pwm_frequency, speed_b)
        except Exception as e:
            LOGGER.warning("PWM set failed: %s", e)
    else:
        # Basic GPIO mode: speed not supported, just on/off
        from drivers import rpi_gpio
        rpi_gpio.write(PWMA_PIN, speed_a > 0)
        rpi_gpio.write(PWMB_PIN, speed_b > 0)


def _set_direction(motor_side: str, direction: str):
    """
    Set motor direction - exact logic from tb6612_Fix.py.
    Includes Motor A polarity fix (AIN1=LOW, AIN2=HIGH for forward).
    """
    if USE_SIM:
        LOGGER.debug("Motor %s direction (sim): %s", motor_side, direction)
        return

    if _h is not None:
        try:
            import lgpio as GPIO
            if motor_side == 'A':
                # Motor A Polarity Fix: Swapped Logic for AIN1/AIN2
                pin1, pin2 = AIN1_PIN, AIN2_PIN
                if direction == 'forward':
                    # Motor A: AIN1=LOW, AIN2=HIGH (Reverse of standard logic)
                    GPIO.gpio_write(_h, pin1, GPIO.LOW)
                    GPIO.gpio_write(_h, pin2, GPIO.HIGH)
                elif direction == 'backward':
                    # Motor A: AIN1=HIGH, AIN2=LOW
                    GPIO.gpio_write(_h, pin1, GPIO.HIGH)
                    GPIO.gpio_write(_h, pin2, GPIO.LOW)
                elif direction == 'coast':
                    GPIO.gpio_write(_h, pin1, GPIO.LOW)
                    GPIO.gpio_write(_h, pin2, GPIO.LOW)
                elif direction == 'brake':
                    GPIO.gpio_write(_h, pin1, GPIO.HIGH)
                    GPIO.gpio_write(_h, pin2, GPIO.HIGH)
            elif motor_side == 'B':
                # Motor B (Right) Logic (Standard Configuration)
                pin1, pin2 = BIN1_PIN, BIN2_PIN
                if direction == 'forward':
                    # Motor B: BIN1=HIGH, BIN2=LOW
                    GPIO.gpio_write(_h, pin1, GPIO.HIGH)
                    GPIO.gpio_write(_h, pin2, GPIO.LOW)
                elif direction == 'backward':
                    # Motor B: BIN1=LOW, BIN2=HIGH
                    GPIO.gpio_write(_h, pin1, GPIO.LOW)
                    GPIO.gpio_write(_h, pin2, GPIO.HIGH)
                elif direction == 'coast':
                    GPIO.gpio_write(_h, pin1, GPIO.LOW)
                    GPIO.gpio_write(_h, pin2, GPIO.LOW)
                elif direction == 'brake':
                    GPIO.gpio_write(_h, pin1, GPIO.HIGH)
                    GPIO.gpio_write(_h, pin2, GPIO.HIGH)
        except Exception as e:
            LOGGER.warning("Direction set failed: %s", e)
    else:
        # Fallback to rpi_gpio
        from drivers import rpi_gpio
        if motor_side == 'A':
            if direction == 'forward':
                rpi_gpio.write(AIN1_PIN, False)
                rpi_gpio.write(AIN2_PIN, True)
            elif direction == 'backward':
                rpi_gpio.write(AIN1_PIN, True)
                rpi_gpio.write(AIN2_PIN, False)
            elif direction == 'coast':
                rpi_gpio.write(AIN1_PIN, False)
                rpi_gpio.write(AIN2_PIN, False)
            elif direction == 'brake':
                rpi_gpio.write(AIN1_PIN, True)
                rpi_gpio.write(AIN2_PIN, True)
        elif motor_side == 'B':
            if direction == 'forward':
                rpi_gpio.write(BIN1_PIN, True)
                rpi_gpio.write(BIN2_PIN, False)
            elif direction == 'backward':
                rpi_gpio.write(BIN1_PIN, False)
                rpi_gpio.write(BIN2_PIN, True)
            elif direction == 'coast':
                rpi_gpio.write(BIN1_PIN, False)
                rpi_gpio.write(BIN2_PIN, False)
            elif direction == 'brake':
                rpi_gpio.write(BIN1_PIN, True)
                rpi_gpio.write(BIN2_PIN, True)


# Public API (preserved from original - no duration params, actuators.py handles timing)
def forward() -> None:
    """Drive all wheels forward at 90% speed (exact from tb6612_Fix.py)."""
    _init_driver()
    LOGGER.info("Motors forward (90%% speed)")
    _set_direction('A', 'forward')
    _set_direction('B', 'forward')
    _set_motor_speed(90, 90)


def backward() -> None:
    """Drive all wheels backward at 90% speed (exact from tb6612_Fix.py)."""
    _init_driver()
    LOGGER.info("Motors backward (90%% speed)")
    _set_direction('A', 'backward')
    _set_direction('B', 'backward')
    _set_motor_speed(90, 90)


def turn_left() -> None:
    """Pivot turn left: left backward, right forward at 70% speed (exact from tb6612_Fix.py)."""
    _init_driver()
    LOGGER.info("Motors turn left (70%% speed)")
    _set_direction('A', 'backward')
    _set_direction('B', 'forward')
    _set_motor_speed(70, 70)


def turn_right() -> None:
    """Pivot turn right: left forward, right backward at 70% speed (exact from tb6612_Fix.py)."""
    _init_driver()
    LOGGER.info("Motors turn right (70%% speed)")
    _set_direction('A', 'forward')
    _set_direction('B', 'backward')
    _set_motor_speed(70, 70)


def stop() -> None:
    """Stop motors (brake then coast) - exact from tb6612_Fix.py brake()."""
    _init_driver()
    LOGGER.info("Motors stop (brake)")
    _set_motor_speed(0, 0)
    _set_direction('A', 'brake')
    _set_direction('B', 'brake')
    if not USE_SIM:
        time.sleep(0.1)
    _set_direction('A', 'coast')
    _set_direction('B', 'coast')


def cleanup() -> None:
    """Clean up GPIO and close handles - exact from tb6612_Fix.py cleanup()."""
    global _h, _initialized
    if USE_SIM:
        LOGGER.info("Motor cleanup (sim)")
        return
    stop()
    if _h is not None:
        try:
            import lgpio as GPIO
            GPIO.gpio_write(_h, AIN1_PIN, GPIO.LOW)
            GPIO.gpio_write(_h, AIN2_PIN, GPIO.LOW)
            GPIO.gpio_write(_h, BIN1_PIN, GPIO.LOW)
            GPIO.gpio_write(_h, BIN2_PIN, GPIO.LOW)
            GPIO.gpio_write(_h, STBY_PIN, GPIO.LOW)
            GPIO.gpiochip_close(_h)
            LOGGER.info("Motor driver cleanup complete")
        except Exception as e:
            LOGGER.warning("Cleanup error: %s", e)
    _h = None
    _initialized = False
