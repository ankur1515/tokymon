"""TB6612FNG motor driver (verbatim from raw_scripts/tb6612_Fix.py)."""
from __future__ import annotations

import time
import os

# lgpio is the required library for Raspberry Pi 5 GPIO control.
try:
    import lgpio as GPIO
    LGPIO_AVAILABLE = True
except ImportError:
    LGPIO_AVAILABLE = False
    GPIO = None

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("motors")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
TOKY_ENV = os.environ.get("TOKY_ENV", "dev").lower()

# --- Pin Definitions (BCM numbering scheme for Raspberry Pi 5) ---
# Motor A (Left Side Wheels) Control Pins
PWMA_PIN = 12  # Motor A speed (Hardware PWM0)
AIN2_PIN = 6   # Motor A direction 2 (Must be HIGH for Forward after fix)
AIN1_PIN = 5   # Motor A direction 1 (Must be LOW for Forward after fix)

# Motor B (Right Side Wheels) Control Pins
PWMB_PIN = 13  # Motor B speed (Hardware PWM1)
BIN1_PIN = 20  # Motor B direction 1 (HIGH for Forward)
BIN2_PIN = 21  # Motor B direction 2 (LOW for Forward)

# Standby Pin (Must be HIGH to enable the driver chip)
STBY_PIN = 22

class MotorDriver:
    """
    Controls two DC motors (driving four wheels in a differential setup) 
    via the TB6612FNG driver using lgpio.
    """
    def __init__(self, pwm_frequency=1000):
        self.pwm_frequency = pwm_frequency
        
        if USE_SIM:
            LOGGER.info("MotorDriver: simulator mode (no hardware init)")
            self.h = None
            return
        
        if not LGPIO_AVAILABLE:
            LOGGER.warning("lgpio not available; motor control disabled")
            self.h = None
            return
        
        # Open the GPIO chip
        try:
            self.h = GPIO.gpiochip_open(0) 
            LOGGER.info("Driver Initialized: GPIO Chip 0 opened successfully.")
        except Exception as e:
            LOGGER.error("Failed to open GPIO chip: %s", e)
            self.h = None
            return
        
        # List of all control pins
        self.output_pins = [PWMA_PIN, AIN1_PIN, AIN2_PIN, 
                            PWMB_PIN, BIN1_PIN, BIN2_PIN, STBY_PIN]
        
        # Claim all pins as OUTPUT
        for pin in self.output_pins:
            try:
                GPIO.gpio_claim_output(self.h, pin)
            except Exception as e:
                LOGGER.warning("Failed to claim pin %s: %s", pin, e)
        
        # Initialize STBY to HIGH to enable the motor driver
        GPIO.gpio_write(self.h, STBY_PIN, GPIO.HIGH)
        LOGGER.info(f"Driver enabled: STBY (GPIO{STBY_PIN}) set HIGH.")
        
        # Start PWM at 0% duty cycle (stopped)
        self.set_motor_speed(0, 0)
        LOGGER.info(f"PWM ready on GPIO{PWMA_PIN} and GPIO{PWMB_PIN} at {pwm_frequency}Hz.")

    def set_motor_speed(self, speed_a, speed_b):
        """Sets the duty cycle (speed) for both motors (0-100)."""
        if USE_SIM or self.h is None:
            LOGGER.debug("Motor speed (sim): A=%s%%, B=%s%%", speed_a, speed_b)
            return
        
        speed_a = max(0, min(100, speed_a))
        speed_b = max(0, min(100, speed_b))
        
        try:
            GPIO.tx_pwm(self.h, PWMA_PIN, self.pwm_frequency, speed_a)
            GPIO.tx_pwm(self.h, PWMB_PIN, self.pwm_frequency, speed_b)
        except Exception as e:
            LOGGER.warning("PWM set failed: %s", e)

    def set_direction(self, motor_side, direction):
        """
        Sets the direction or stop mode for a specific motor.
        Includes a polarity fix for Motor A (Left) to ensure 
        'forward' moves both motors in the same physical direction.
        """
        if USE_SIM or self.h is None:
            LOGGER.debug("Motor %s direction (sim): %s", motor_side, direction)
            return
        
        if motor_side == 'A':
            # --- Motor A Polarity Fix: Swapped Logic for AIN1/AIN2 ---
            pin1, pin2 = AIN1_PIN, AIN2_PIN
            if direction == 'forward':
                # Motor A: AIN1=LOW, AIN2=HIGH (Reverse of standard logic to match motor B)
                GPIO.gpio_write(self.h, pin1, GPIO.LOW)  
                GPIO.gpio_write(self.h, pin2, GPIO.HIGH) 
            elif direction == 'backward':
                # Motor A: AIN1=HIGH, AIN2=LOW (Reverse of standard logic to match motor B)
                GPIO.gpio_write(self.h, pin1, GPIO.HIGH) 
                GPIO.gpio_write(self.h, pin2, GPIO.LOW)  
            elif direction == 'coast':
                GPIO.gpio_write(self.h, pin1, GPIO.LOW)
                GPIO.gpio_write(self.h, pin2, GPIO.LOW)
            elif direction == 'brake':
                GPIO.gpio_write(self.h, pin1, GPIO.HIGH)
                GPIO.gpio_write(self.h, pin2, GPIO.HIGH)
            
        elif motor_side == 'B':
            # --- Motor B (Right) Logic (Standard Configuration) ---
            pin1, pin2 = BIN1_PIN, BIN2_PIN
            if direction == 'forward':
                # Motor B: BIN1=HIGH, BIN2=LOW
                GPIO.gpio_write(self.h, pin1, GPIO.HIGH)
                GPIO.gpio_write(self.h, pin2, GPIO.LOW)
            elif direction == 'backward':
                # Motor B: BIN1=LOW, BIN2=HIGH
                GPIO.gpio_write(self.h, pin1, GPIO.LOW)
                GPIO.gpio_write(self.h, pin2, GPIO.HIGH)
            elif direction == 'coast':
                GPIO.gpio_write(self.h, pin1, GPIO.LOW)
                GPIO.gpio_write(self.h, pin2, GPIO.LOW)
            elif direction == 'brake':
                GPIO.gpio_write(self.h, pin1, GPIO.HIGH)
                GPIO.gpio_write(self.h, pin2, GPIO.HIGH)
        
        else:
            LOGGER.warning(f"Invalid motor side: {motor_side}")

    def forward(self, speed=90):
        """Drives all four wheels forward (Left and Right)."""
        LOGGER.info(f"Action: Moving Forward (All 4 Wheels) at {speed}% speed.")
        self.set_direction('A', 'forward')
        self.set_direction('B', 'forward')
        self.set_motor_speed(speed, speed)

    def backward(self, speed=90):
        """Drives all four wheels backward (Left and Right)."""
        LOGGER.info(f"Action: Moving Backward (All 4 Wheels) at {speed}% speed.")
        self.set_direction('A', 'backward')
        self.set_direction('B', 'backward')
        self.set_motor_speed(speed, speed)

    def brake(self):
        """Brakes both motors quickly (quick stop/short brake)."""
        LOGGER.info("Action: Applying Quick Brake.")
        self.set_motor_speed(0, 0)
        self.set_direction('A', 'brake')
        self.set_direction('B', 'brake')
        if not USE_SIM:
            time.sleep(0.1) 
        self.set_direction('A', 'coast')
        self.set_direction('B', 'coast')

    def turn_left(self):
        """Pivot Turn Left: Left Motor Backward, Right Motor Forward (Now at 50% Speed)."""
        turn_speed = 70
        LOGGER.info(f"Action: Pivot Turn Left (Left Wheels Back {turn_speed}%, Right Wheels Forward {turn_speed}%)")
        
        # Left side (A) must pull backward
        self.set_direction('A', 'backward')
        
        # Right side (B) must push forward
        self.set_direction('B', 'forward')
        self.set_motor_speed(turn_speed, turn_speed) 

    def turn_right(self):
        """Pivot Turn Right: Left Motor Forward, Right Motor Backward (Now at 50% Speed)."""
        turn_speed = 70
        LOGGER.info(f"Action: Pivot Turn Right (Left Wheels Forward {turn_speed}%, Right Wheels Back {turn_speed}%)")
        
        # Left side (A) must push forward
        self.set_direction('A', 'forward')
        
        # Right side (B) must pull backward
        self.set_direction('B', 'backward')
        self.set_motor_speed(turn_speed, turn_speed) 
        
    def test_motor_a(self, speed=100):
        """Runs Motor A, testing both forward and backward directions for 2s each."""
        LOGGER.info(f"ISOLATED TEST: Motor A FORWARD at {speed}% for 2s.")
        self.set_direction('A', 'forward')
        self.set_direction('B', 'coast') 
        self.set_motor_speed(speed, 0) 
        if not USE_SIM:
            time.sleep(2)
        self.brake()
        if not USE_SIM:
            time.sleep(0.5)
        
        LOGGER.info(f"ISOLATED TEST: Motor A BACKWARD at {speed}% for 2s.")
        self.set_direction('A', 'backward')
        self.set_direction('B', 'coast') 
        self.set_motor_speed(speed, 0) 
        if not USE_SIM:
            time.sleep(2)
        self.brake()
        if not USE_SIM:
            time.sleep(0.5)


    def test_motor_b(self, speed=100):
        """Runs Motor B forward for a short test at high speed."""
        LOGGER.info(f"ISOLATED TEST: Motor B Forward at {speed}% for 2s.")
        self.set_direction('A', 'coast')
        self.set_direction('B', 'forward')
        self.set_motor_speed(0, speed) 
        if not USE_SIM:
            time.sleep(2)
        self.brake()
        if not USE_SIM:
            time.sleep(0.5)
        
    def cleanup(self):
        """Cleans up all GPIO settings, stops PWM, and closes the chip handle."""
        LOGGER.info("Cleaning up GPIO...")
        self.set_motor_speed(0, 0)
        
        if self.h is not None:
            try:
                GPIO.gpio_write(self.h, AIN1_PIN, GPIO.LOW)
                GPIO.gpio_write(self.h, AIN2_PIN, GPIO.LOW)
                GPIO.gpio_write(self.h, BIN1_PIN, GPIO.LOW)
                GPIO.gpio_write(self.h, BIN2_PIN, GPIO.LOW)
                GPIO.gpio_write(self.h, STBY_PIN, GPIO.LOW) 
                
                try:
                    GPIO.gpiochip_close(self.h) 
                except:
                    pass
                
                LOGGER.info("GPIO cleanup complete. Program terminated safely.")
            except Exception as e:
                LOGGER.warning("Cleanup error: %s", e)
        self.h = None


# Singleton instance for module-level API
_driver = None

def _get_driver():
    """Get or create the singleton MotorDriver instance."""
    global _driver
    if _driver is None:
        _driver = MotorDriver()
    return _driver


# Module-level API (matches existing codebase expectations)
def forward():
    """Drive all wheels forward."""
    _get_driver().forward(90)

def backward():
    """Drive all wheels backward."""
    _get_driver().backward(90)

def turn_left():
    """Pivot turn left."""
    _get_driver().turn_left()

def turn_right():
    """Pivot turn right."""
    _get_driver().turn_right()

def stop():
    """Stop motors (brake then coast)."""
    _get_driver().brake()

def cleanup():
    """Clean up GPIO and close handles."""
    global _driver
    if _driver is not None:
        _driver.cleanup()
        _driver = None


# --- Test Routine (Using High Speeds and Pivot Turns) ---
if __name__ == "__main__" and os.environ.get("TOKY_ENV") != "dev":
    driver = None
    try:
        driver = MotorDriver()
        test_duration = 3.0 
        
        LOGGER.info("\n--- Starting Full Movement Test Sequence (Corrected Polarity/Pivot) ---")
        
        # 1. Forward (90% Power) - Both motors should now move forward
        driver.forward(90)
        time.sleep(test_duration)
        driver.brake()
        time.sleep(1)

        # 2. Backward (90% Power) - Both motors should now move backward
        driver.backward(90)
        time.sleep(test_duration)
        driver.brake()
        time.sleep(1)

        # 3. Pivot Turn Left (50% Speed)
        driver.turn_left()
        time.sleep(test_duration * 1.2) 
        driver.brake()
        time.sleep(1)
        
        # 4. Pivot Turn Right (50% Speed)
        driver.turn_right()
        time.sleep(test_duration * 1.2) 
        driver.brake()
        time.sleep(1)
        
        LOGGER.info("\n--- Test Sequence Complete ---")
        
    except KeyboardInterrupt:
        LOGGER.info("\nTest sequence interrupted by user.")
    except Exception as e:
        LOGGER.error(f"\nAn error occurred during testing: {e}")
    finally:
        if driver:
            driver.cleanup()
