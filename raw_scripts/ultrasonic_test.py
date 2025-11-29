#!/usr/bin/env python3
"""
Auto-detect global GPIO numbers for BCM pins and test HC-SR04.
TRIG_BCM and ECHO_BCM are BCM numbering for the header pins (usual values 23 & 24).
This script will:
 - try to parse /sys/kernel/debug/gpio for mapping (recommended)
 - otherwise scan /sys/class/gpio/gpiochip*/base and ngpio and attempt to export/verify
Run with sudo:
  sudo python3 detect_and_test_ultrasonic.py
"""

import os
import time
import re
import glob
import sys

TRIG_BCM = 23
ECHO_BCM = 24

TIMEOUT = 0.02  # seconds
POLL_SLEEP = 0.0001

def parse_debug_gpio():
    """Parse /sys/kernel/debug/gpio for lines that map 'GPIO23' etc and return global numbers."""
    path = "/sys/kernel/debug/gpio"
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = f.read()
    # The debug file contains lines like: "gpio-592 (GPIO23              )"
    found = {}
    for match in re.finditer(r"gpio-(\d+)\s+\(([^)]*)\)", data):
        gnum = int(match.group(1))
        label = match.group(2)
        # look for 'GPIO23' or 'GPIO24' in label
        if re.search(r"\bGPIO{}(\b|$)".format(TRIG_BCM), label):
            found['trig'] = gnum
        if re.search(r"\bGPIO{}(\b|$)".format(ECHO_BCM), label):
            found['echo'] = gnum
    if 'trig' in found and 'echo' in found:
        return found['trig'], found['echo']
    return None

def scan_chips_and_try_export(bcm_trig, bcm_echo):
    """Scan /sys/class/gpio/gpiochip* and compute candidate global = base + bcm.
       Try exporting candidate globals to verify operability.
    """
    for chip in sorted(glob.glob("/sys/class/gpio/gpiochip*")):
        try:
            with open(os.path.join(chip, "base")) as f:
                base = int(f.read().strip())
            with open(os.path.join(chip, "ngpio")) as f:
                ngpio = int(f.read().strip())
        except Exception:
            continue
        # candidate global numbers
        cand_trig = base + bcm_trig
        cand_echo = base + bcm_echo
        # only try this chip if both candidates fall in its range
        if not (base <= cand_trig <= base + ngpio - 1 and base <= cand_echo <= base + ngpio - 1):
            continue
        # try to export both (if already exported, that's okay)
        def try_export(g):
            p = f"/sys/class/gpio/gpio{g}"
            if os.path.exists(p):
                return True
            try:
                with open("/sys/class/gpio/export", "w") as ex:
                    ex.write(str(g))
                # small settle
                time.sleep(0.05)
                return os.path.exists(p)
            except Exception:
                return False
        ok1 = try_export(cand_trig)
        ok2 = try_export(cand_echo)
        if ok1 and ok2:
            return cand_trig, cand_echo
        # if export failed, try unexport any partially exported
        try:
            if os.path.exists(f"/sys/class/gpio/gpio{cand_trig}"):
                open("/sys/class/gpio/unexport","w").write(str(cand_trig))
            if os.path.exists(f"/sys/class/gpio/gpio{cand_echo}"):
                open("/sys/class/gpio/unexport","w").write(str(cand_echo))
        except Exception:
            pass
    return None

def export_gpio(global_num):
    p = f"/sys/class/gpio/gpio{global_num}"
    if not os.path.exists(p):
        with open("/sys/class/gpio/export", "w") as f:
            f.write(str(global_num))
        time.sleep(0.05)
    return p

def write_direction(global_num, direction):
    with open(f"/sys/class/gpio/gpio{global_num}/direction", "w") as f:
        f.write(direction)

def write_value(global_num, v):
    with open(f"/sys/class/gpio/gpio{global_num}/value", "w") as f:
        f.write("1" if v else "0")

def read_value(global_num):
    with open(f"/sys/class/gpio/gpio{global_num}/value", "r") as f:
        return f.read(1)

def find_and_prepare():
    # 1) try debug parsing
    parsed = parse_debug_gpio()
    if parsed:
        trig_g, echo_g = parsed
        print(f"Found via debug mapping: TRIG global={trig_g}, ECHO global={echo_g}")
    else:
        print("Debug mapping not usable; scanning gpiochips...")
        scanned = scan_chips_and_try_export(TRIG_BCM, ECHO_BCM)
        if scanned:
            trig_g, echo_g = scanned
            print(f"Found via chip scan: TRIG global={trig_g}, ECHO global={echo_g}")
        else:
            # last resort: try base+BCM for each chip where bcm < ngpio
            for chip in sorted(glob.glob("/sys/class/gpio/gpiochip*")):
                try:
                    base = int(open(os.path.join(chip,"base")).read().strip())
                    ngpio = int(open(os.path.join(chip,"ngpio")).read().strip())
                except Exception:
                    continue
                if TRIG_BCM < ngpio and ECHO_BCM < ngpio:
                    trig_g = base + TRIG_BCM
                    echo_g = base + ECHO_BCM
                    # try export and accept if works
                    try:
                        export_gpio(trig_g); export_gpio(echo_g)
                        print(f"Using fallback mapping: TRIG global={trig_g}, ECHO global={echo_g}")
                        break
                    except Exception:
                        continue
            else:
                raise RuntimeError("Unable to determine global gpio numbers for TRIG/ECHO.")
    # Export (idempotent) and set directions
    export_gpio(trig_g); export_gpio(echo_g)
    write_direction(trig_g, "out")
    write_direction(echo_g, "in")
    write_value(trig_g, 0)
    return trig_g, echo_g

def get_distance(trig_g, echo_g):
    # ensure trig low
    write_value(trig_g, 0)
    time.sleep(0.05)
    # pulse
    write_value(trig_g, 1)
    time.sleep(0.00001)
    write_value(trig_g, 0)
    # wait for echo high
    start_deadline = time.time() + TIMEOUT
    while time.time() < start_deadline:
        if read_value(echo_g) == '1':
            pulse_start = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        return None
    # wait for echo low
    end_deadline = time.time() + TIMEOUT
    while time.time() < end_deadline:
        if read_value(echo_g) == '0':
            pulse_end = time.time()
            break
        time.sleep(POLL_SLEEP)
    else:
        return None
    duration = pulse_end - pulse_start
    dist = duration * 17150
    if dist < 2 or dist > 400:
        return None
    return round(dist, 2)

def main():
    print("Tokymon: auto-detecting HC-SR04 pins...")
    trig_g, echo_g = find_and_prepare()
    print("Starting distance loop (CTRL+C to stop)...")
    try:
        while True:
            d = get_distance(trig_g, echo_g)
            if d is None:
                print("No valid reading")
            else:
                print(f"Distance: {d} cm")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        # optionally unexport if you want:
        # open("/sys/class/gpio/unexport","w").write(str(trig_g)); open("/sys/class/gpio/unexport","w").write(str(echo_g))
        pass

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Please run with sudo.")
        sys.exit(1)
    main()