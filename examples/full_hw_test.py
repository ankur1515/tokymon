#!/usr/bin/env python3
"""
FULL HARDWARE AUTO-TEST FOR TOKYMON (with MIC + CAMERA)
------------------------------------------------------
Tests: LED Matrix → Audio (mic record+play) → Camera photo → IR → Ultrasonic → Motors → Final Display
Requires: TOKY_ENV=prod and sudo for full GPIO/PWM/camera access
"""

import time
import os
import sys
import subprocess
from pathlib import Path
from shutil import which

from display import max7219_driver as disp
from sensors.drivers.ir_sensor import read_left, read_right
from sensors.drivers.hcsr04 import read_distance_cm
from control import motors


# ------------------------------------------------------------
# Helper: safe print
# ------------------------------------------------------------
def header(title: str):
    print("\n" + "=" * 60)
    print(">>> " + title)
    print("=" * 60)


# ------------------------------------------------------------
# Test 1 — LED MATRIX
# ------------------------------------------------------------
def test_led():
    header("TEST 1 — LED MATRIX")
    try:
        disp.init_display()
        disp.show_text("TOKYMON")
        time.sleep(1)
        disp.show_expression("hello")
        time.sleep(1)
        disp.clear()
        print("[OK] LED Matrix test passed.")
    except Exception as e:
        print("[FAIL] LED test:", e)


# ------------------------------------------------------------
# Test 2 — AUDIO (MIC RECORD + SPEAKER PLAY)
# ------------------------------------------------------------
def test_audio():
    header("TEST 2 — AUDIO (mic record + playback)")
    outfile = "/tmp/tokymon_test.wav"
    
    # try default capture device; user can adapt device if needed
    print("Recording 1.5s to", outfile)
    try:
        # prefer arecord; record 1.5s wav at CD quality
        rc = subprocess.call(["arecord", "-d", "1", "-f", "cd", outfile])
        if rc != 0 or not Path(outfile).exists():
            print("arecord failed or file missing (rc=%s), attempting plughw:2,0" % rc)
            subprocess.call(["arecord", "-D", "plughw:2,0", "-d", "1", "-f", "cd", outfile])
    except FileNotFoundError:
        print("arecord not installed.")
    except Exception as e:
        print("Audio record error:", e)

    if not Path(outfile).exists():
        print("[FAIL] Could not record audio.")
        return

    print("Playing recorded audio...")
    try:
        subprocess.call(["aplay", outfile])
        print("[OK] Audio test passed.")
    except FileNotFoundError:
        print("aplay not installed — unable to play.")
    except Exception as e:
        print("[FAIL] Audio playback error:", e)


# ------------------------------------------------------------
# Test 3 — CAMERA PHOTO (CSI)
# ------------------------------------------------------------
def test_camera():
    header("TEST 3 — CAMERA (capture)")
    out_photo = "/tmp/tokymon_photo.jpg"
    
    # Try libcamera-still first, then raspistill as fallback
    try:
        if which("libcamera-still"):
            cmd = ["libcamera-still", "-o", out_photo, "-t", "1000"]
            print("Capturing with libcamera-still...")
            rc = subprocess.call(cmd)
        elif which("raspistill"):
            cmd = ["raspistill", "-o", out_photo, "-t", "1000"]
            print("Capturing with raspistill...")
            rc = subprocess.call(cmd)
        else:
            print("No camera capture binary found (libcamera-still/raspistill). Skipping camera test.")
            return

        if Path(out_photo).exists():
            print("[OK] Camera capture saved to", out_photo)
        else:
            print("[FAIL] Camera capture failed or file not created.")
    except Exception as e:
        print("[FAIL] Camera test exception:", e)


# ------------------------------------------------------------
# Test 4 — IR SENSORS
# ------------------------------------------------------------
def test_ir():
    header("TEST 4 — IR SENSORS (Active-low: 0=Detect)")
    try:
        l = read_left()
        r = read_right()
        print(f"Left IR:  {l}")
        print(f"Right IR: {r}")
        print("[OK] IR test done.")
    except Exception as e:
        print("[FAIL] IR test:", e)


# ------------------------------------------------------------
# Test 5 — ULTRASONIC SENSOR
# ------------------------------------------------------------
def test_ultrasonic():
    header("TEST 5 — ULTRASONIC HC-SR04")
    try:
        d = read_distance_cm()
        print(f"Distance: {d} cm")
        print("[OK] Ultrasonic test done.")
    except Exception as e:
        print("[FAIL] Ultrasonic test:", e)


# ------------------------------------------------------------
# Test 6 — MOTORS (TB6612)
# ------------------------------------------------------------
def test_motors():
    header("TEST 6 — MOTORS (TB6612)")
    try:
        print("Forward 1s...")
        motors.forward()
        time.sleep(1)

        print("Backward 1s...")
        motors.backward()
        time.sleep(1)

        print("Turn Left 1s...")
        motors.turn_left()
        time.sleep(1)

        print("Turn Right 1s...")
        motors.turn_right()
        time.sleep(1)

        print("STOP")
        motors.stop()
        time.sleep(0.3)

        print("[OK] Motors test done.")
    except Exception as e:
        print("[FAIL] Motor test:", e)
        try:
            motors.stop()
        except:
            pass


# ------------------------------------------------------------
# Final
# ------------------------------------------------------------
def final_ok():
    header("ALL TESTS COMPLETED")
    try:
        disp.show_text("OK")
        time.sleep(1)
        disp.clear()
    except:
        pass


# ------------------------------------------------------------
# RUN ALL
# ------------------------------------------------------------
if __name__ == "__main__":
    print("\nTOKYMON — FULL HARDWARE AUTO-TEST (MIC + CAMERA INCLUDED)")
    print("Starting...\n")

    test_led()
    test_audio()
    test_camera()
    test_ir()
    test_ultrasonic()
    test_motors()
    final_ok()

    print("\nDONE.\n")

