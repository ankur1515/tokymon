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
    
    # Fixed audio devices
    MIC_DEVICE = "plughw:1,0"
    SPEAKER_DEVICE = "plughw:3,0"
    
    # Check simulator mode
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    TOKY_ENV = os.environ.get("TOKY_ENV", "dev").lower()
    is_sim = USE_SIM or (TOKY_ENV == "dev")
    
    if is_sim:
        print("[SIM] Audio test (simulator mode - skipping actual recording/playback)")
        print(f"[SIM] Would record 5s to data/temp/Audio/tokymon_test.wav using mic: {MIC_DEVICE}")
        print(f"[SIM] Would play on speaker: {SPEAKER_DEVICE}")
        return
    
    # Use data/temp/Audio directory for audio files
    audio_dir = Path(CONFIG.get("runtime", {}).get("root_path", ".")) / "data" / "temp" / "Audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    outfile = str(audio_dir / "tokymon_test.wav")
    
    record_dev = MIC_DEVICE
    record_seconds = 5
    
    print(f"Using mic: {record_dev}")
    print(f"Using speaker: {SPEAKER_DEVICE}")
    print(f"Recording for {record_seconds} seconds...")
    
    # Record with fixed device
    try:
        cmd = ["arecord", "-D", record_dev, "-d", str(record_seconds), "-f", "cd", outfile]
        rc = subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        if rc == 0 and Path(outfile).exists() and Path(outfile).stat().st_size > 0:
            file_size = Path(outfile).stat().st_size
            print(f"Recording successful (size: {file_size} bytes)")
            print(f"Audio file saved to: {outfile}")
        else:
            print("[FAIL] Could not record audio.")
            print("Try: arecord -l  # to list devices")
            return
    except Exception as e:
        print(f"[FAIL] Recording failed: {e}")
        return
    
    # Playback with fixed device
    playback_dev = SPEAKER_DEVICE
    print("Playing recorded audio (5 seconds)...")
    
    try:
        cmd = ["aplay", "-D", playback_dev, outfile]
        rc = subprocess.call(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
        if rc == 0:
            print(f"[OK] Playback successful")
            print("[OK] Audio test passed (5s record + playback).")
        else:
            print("[WARN] Playback failed.")
            print("Try: aplay -l  # to list available devices")
            print(f"Audio file saved at: {outfile}")
    except subprocess.TimeoutExpired:
        print("[WARN] Playback timeout")
    except Exception as e:
        print(f"[WARN] Playback error: {e}")


# ------------------------------------------------------------
# Test 3 — CAMERA PHOTO (CSI) - Capture and Show
# ------------------------------------------------------------
def test_camera():
    header("TEST 3 — CAMERA (capture and show)")
    
    # Check simulator mode
    USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)
    TOKY_ENV = os.environ.get("TOKY_ENV", "dev").lower()
    is_sim = USE_SIM or (TOKY_ENV == "dev")
    
    if is_sim:
        print("[SIM] Camera test (simulator mode - skipping actual capture)")
        print("[SIM] Would capture to data/temp/tokymon_photo.jpg")
        return
    
    # Use data/temp for camera photos
    camera_dir = Path(CONFIG.get("runtime", {}).get("root_path", ".")) / "data" / "temp"
    camera_dir.mkdir(parents=True, exist_ok=True)
    out_photo = str(camera_dir / "tokymon_photo.jpg")
    
    print(f"Capturing photo to: {out_photo}")
    
    # Check camera status first
    print("Checking camera status...")
    try:
        result = subprocess.run(["vcgencmd", "get_camera"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            print(f"Camera status: {result.stdout.strip()}")
    except:
        print("Could not check camera status (vcgencmd not available)")
    
    # Check for video devices
    try:
        video_devices = list(Path("/dev").glob("video*"))
        if video_devices:
            print(f"Found video devices: {[str(d) for d in video_devices]}")
        else:
            print("No /dev/video* devices found")
    except:
        pass
    
    # Use rpicam-still/rpicam-hello detection, fallback to libcamera-still
    captured = False
    last_error = None
    
    if which("rpicam-still"):
        print("Trying rpicam-still...")
        try:
            result = subprocess.run(["rpicam-still", "-o", out_photo, "-t", "1000"], 
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, timeout=10)
            if result.returncode == 0 and Path(out_photo).exists() and Path(out_photo).stat().st_size > 0:
                file_size = Path(out_photo).stat().st_size
                print(f"[OK] Camera capture successful!")
                print(f"     File: {out_photo}")
                print(f"     Size: {file_size} bytes")
                print(f"     Using: rpicam-still")
                captured = True
            else:
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore').strip()
                    if error_msg:
                        last_error = error_msg
                        print(f"  Error: {error_msg[:100]}")
        except subprocess.TimeoutExpired:
            print("  Timeout waiting for camera")
        except Exception as e:
            last_error = str(e)
            print(f"  Exception: {e}")
    elif which("libcamera-still"):
        print("Trying libcamera-still...")
        try:
            result = subprocess.run(["libcamera-still", "-o", out_photo, "-t", "1000"], 
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, timeout=10)
            if result.returncode == 0 and Path(out_photo).exists() and Path(out_photo).stat().st_size > 0:
                file_size = Path(out_photo).stat().st_size
                print(f"[OK] Camera capture successful!")
                print(f"     File: {out_photo}")
                print(f"     Size: {file_size} bytes")
                print(f"     Using: libcamera-still")
                captured = True
            else:
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore').strip()
                    if error_msg:
                        last_error = error_msg
                        print(f"  Error: {error_msg[:100]}")
        except subprocess.TimeoutExpired:
            print("  Timeout waiting for camera")
        except Exception as e:
            last_error = str(e)
            print(f"  Exception: {e}")
    else:
        print("No camera capture binary found (rpicam-still/libcamera-still). Skipping camera test.")
        return
    
    if captured:
        # Rotate image 180 degrees
        try:
            from PIL import Image
            img = Image.open(out_photo)
            img = img.rotate(180)
            img.save(out_photo)
            print("Image rotated 180°")
        except ImportError:
            print("PIL not available - skipping rotation")
        except Exception as e:
            print(f"Rotation failed: {e}")
        
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
    else:
        print("[FAIL] Camera capture failed.")
        if last_error:
            print(f"Last error: {last_error}")
        print("\nTroubleshooting steps:")
        print("1. Check camera status: vcgencmd get_camera")
        print("   Should show: supported=1 detected=1")
        print("\n2. For Raspberry Pi 5 / newer OS:")
        print("   Camera interface may need to be enabled in /boot/firmware/config.txt")
        print("   Add or uncomment: camera_auto_detect=1")
        print("   Or edit: sudo nano /boot/firmware/config.txt")
        print("   Then reboot: sudo reboot")
        print("\n3. For older Pi models:")
        print("   Enable via: sudo raspi-config -> Interface Options -> Camera -> Enable")
        print("   Or add to /boot/config.txt: start_x=1")
        print("\n4. Check camera connection:")
        print("   ls -la /dev/video*")
        print("   Should show /dev/video0 or /dev/video10+")
        print("\n5. Test manually:")
        print("   rpicam-still -o /tmp/test.jpg  or  libcamera-still -o /tmp/test.jpg")
        print("\n6. Install/update camera tools:")
        print("   sudo apt-get update")
        print("   sudo apt-get install -y libcamera-apps")
        print(f"\nFiles will be saved to: {camera_dir}")


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
