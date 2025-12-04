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
from system.config import CONFIG


# ------------------------------------------------------------
# Helper: Get reliable temp directory
# ------------------------------------------------------------
def get_temp_dir():
    """Get a writable temp directory, creating if needed."""
    temp_dirs = [
        Path("/tmp"),
        Path.home() / "tmp",
        Path(CONFIG.get("runtime", {}).get("root_path", ".")) / "data" / "temp",
        Path(".") / "data" / "temp",
    ]
    
    for temp_dir in temp_dirs:
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            # Test write
            test_file = temp_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            return temp_dir
        except (PermissionError, OSError):
            continue
    
    # Last resort: current directory
    return Path(".")

TEMP_DIR = get_temp_dir()
print(f"[INFO] Using temp directory: {TEMP_DIR}")


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
# Test 2 — AUDIO (MIC RECORD 5s + SPEAKER PLAY)
# ------------------------------------------------------------
def test_audio():
    header("TEST 2 — AUDIO (mic record 5s + playback)")
    outfile = str(TEMP_DIR / "tokymon_test.wav")
    
    # Ensure parent directory exists
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Recording 5 seconds to {outfile}")
    
    # Try recording with different devices
    record_devs = [None, "plughw:2,0", "plughw:1,0", "hw:2,0"]
    recorded = False
    
    for dev in record_devs:
        try:
            cmd = ["arecord", "-d", "5", "-f", "cd", outfile]  # 5 seconds
            if dev:
                cmd.insert(1, "-D")
                cmd.insert(2, dev)
            print(f"Trying recording device: {dev or 'default'}...")
            rc = subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            if rc == 0 and Path(outfile).exists() and Path(outfile).stat().st_size > 0:
                file_size = Path(outfile).stat().st_size
                print(f"Recording successful (device: {dev or 'default'}, size: {file_size} bytes)")
                recorded = True
                break
        except Exception as e:
            print(f"Recording attempt failed: {e}")
            continue
    
    if not recorded:
        print("[FAIL] Could not record audio from any device.")
        print("Try: arecord -l  # to list devices")
        return
    
    # Try playback with different devices
    print("Playing recorded audio (5 seconds)...")
    playback_devs = [None, "plughw:0,0", "plughw:1,0", "sysdefault", "default"]
    played = False
    
    for dev in playback_devs:
        try:
            cmd = ["aplay", outfile]
            if dev:
                cmd.insert(1, "-D")
                cmd.insert(2, dev)
            rc = subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            if rc == 0:
                print(f"[OK] Playback successful (device: {dev or 'default'})")
                played = True
                break
        except Exception as e:
            continue
    
    if not played:
        print("[WARN] Playback failed. Check 'aplay -l' for available devices.")
    else:
        print("[OK] Audio test passed (5s record + playback).")


# ------------------------------------------------------------
# Test 3 — CAMERA PHOTO (CSI) - Capture and Show
# ------------------------------------------------------------
def test_camera():
    header("TEST 3 — CAMERA (capture and show)")
    out_photo = str(TEMP_DIR / "tokymon_photo.jpg")
    
    # Ensure parent directory exists
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Capturing photo to: {out_photo}")
    
    # Try different camera binaries and paths
    camera_commands = [
        (["libcamera-still", "-o", out_photo, "-t", "1000"], "libcamera-still"),
        (["/usr/bin/libcamera-still", "-o", out_photo, "-t", "1000"], "/usr/bin/libcamera-still"),
        (["raspistill", "-o", out_photo, "-t", "1000"], "raspistill"),
        (["/usr/bin/raspistill", "-o", out_photo, "-t", "1000"], "/usr/bin/raspistill"),
    ]
    
    captured = False
    for cmd, name in camera_commands:
        binary_name = cmd[0].split('/')[-1]
        if not which(binary_name) and not Path(cmd[0]).exists():
            continue
        try:
            print(f"Trying {name}...")
            rc = subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            if rc == 0 and Path(out_photo).exists() and Path(out_photo).stat().st_size > 0:
                file_size = Path(out_photo).stat().st_size
                print(f"[OK] Camera capture successful!")
                print(f"     File: {out_photo}")
                print(f"     Size: {file_size} bytes")
                print(f"     Using: {name}")
                
                # Show confirmation on LED display
                try:
                    disp.show_text("PHOTO")
                    time.sleep(1)
                    disp.show_expression("success")
                    time.sleep(1)
                    disp.clear()
                except Exception as e:
                    print(f"LED display warning: {e}")
                
                # Try to show image (if viewer available)
                try:
                    if which("feh"):
                        print(f"Opening image with feh...")
                        subprocess.Popen(["feh", out_photo], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                    elif which("xdg-open"):
                        print(f"Opening image with xdg-open...")
                        subprocess.Popen(["xdg-open", out_photo], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                    else:
                        print(f"Image saved. View with: feh {out_photo}  or  xdg-open {out_photo}")
                except:
                    print(f"Image saved. View with: feh {out_photo}  or  xdg-open {out_photo}")
                
                captured = True
                break
        except Exception as e:
            print(f"Camera attempt failed: {e}")
            continue
    
    if not captured:
        print("[FAIL] Camera capture failed.")
        print("Install: sudo apt-get install -y libcamera-apps")
        print("Or check: ls -la /dev/video*")
        print(f"Files will be saved to: {TEMP_DIR}")


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
