#!/usr/bin/env python3
"""
ir_detect_5s_led.py — patched (orientation-aware horizontal scrolling)

- LEFT global gpio = 586 (BCM17)
- RIGHT global gpio = 596 (BCM27)
- Active LOW sensors: 0 = detect
- Latches detection for LATCH_SECONDS (default 5s)
- Prints raw lines and shows messages on LED matrix horizontally (tries several orientations)
Run:
    sudo python3 ir_detect_5s_led.py
If text still looks vertical, edit DEVICE_ORIENTATION (0,90,180,270) near the top.
"""

import time, os, sys

# ----------------- USER TUNABLES -----------------
LEFT_GLOBAL = 586
RIGHT_GLOBAL = 596
POLL_INTERVAL = 0.06
LATCH_SECONDS = 5.0

# Default orientation - if the automatic test doesn't match your hardware,
# set this to 0, 90, 180 or 270 manually.
DEVICE_ORIENTATION = 180  # None = run quick visual test on startup and keep last orientation
# -------------------------------------------------

# --- LED init (optional) ---
USE_LED = True
device = None
font = None
try:
    from luma.core.interface.serial import spi, noop
    from luma.led_matrix.device import max7219
    from luma.core.render import canvas
    from PIL import ImageFont, ImageDraw, Image
    try:
        serial = spi(port=0, device=0, gpio=noop())
        # set cascaded equal to your chained 8x8 matrices; common values: 4, 8, etc
        device = max7219(serial, cascaded=4, block_orientation=0)
        device.contrast(8)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
    except Exception:
        USE_LED = False
        device = None
except Exception:
    USE_LED = False
    device = None

# ----------------- text measurement helpers -----------------
def measure_text(text, font_obj):
    """Return (w, h) of text in pixels using robust Pillow fallbacks."""
    try:
        tmp_img = Image.new("1", (1,1))
        draw = ImageDraw.Draw(tmp_img)
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0,0), text, font=font_obj)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
        if hasattr(draw, "textsize"):
            return draw.textsize(text, font=font_obj)
    except Exception:
        pass

    try:
        if hasattr(font_obj, "getbbox"):
            bbox = font_obj.getbbox(text)
            return (bbox[2]-bbox[0], bbox[3]-bbox[1])
    except Exception:
        pass

    try:
        if hasattr(font_obj, "getmask"):
            mask = font_obj.getmask(text)
            return mask.size
    except Exception:
        pass

    return (len(text) * 6, 8)

# ----------------- horizontal display with rotation -----------------
def show_text_horizontal(text, device_orientation, speed=0.03, font_obj=None):
    """
    Draw text horizontally (left->right) into a wide image, then rotate it
    so the physical device receives pixels in the correct orientation.
    device_orientation: 0, 90, 180, 270 degrees (how the device expects the image)
    """
    if not USE_LED or device is None:
        print("[LED-FALLBACK]", text)
        return

    f = font_obj or font or ImageFont.load_default()
    w, h = measure_text(text, f)
    dev_w, dev_h = device.width, device.height

    # create a horizontal canvas image: wider than device width by text width
    horiz_img = Image.new("1", (w + dev_w, max(dev_h, h)), "black")
    draw = ImageDraw.Draw(horiz_img)
    draw.text((dev_w, (horiz_img.height - h) // 2), text, font=f, fill=255)

    # rotate to match device orientation
    if device_orientation == 0:
        out_img = horiz_img
    elif device_orientation == 90:
        out_img = horiz_img.rotate(-90, expand=True)
    elif device_orientation == 180:
        out_img = horiz_img.rotate(180, expand=True)
    elif device_orientation == 270:
        out_img = horiz_img.rotate(90, expand=True)
    else:
        out_img = horiz_img

    # scroll horizontally across out_img's width
    total = out_img.width - dev_w
    if total <= 0:
        # text fits — center and show briefly
        with canvas(device) as drawc:
            x = (dev_w - w) // 2
            y = (dev_h - h) // 2
            drawc.text((x, y), text, font=f, fill=255)
        time.sleep(1.0)
        return

    # Scroll window across the rotated image
    for x in range(0, total + 1):
        with canvas(device) as drawc:
            segment = out_img.crop((x, 0, x + dev_w, out_img.height))
            drawc.bitmap((0, 0), segment, fill=255)
        time.sleep(speed)

# ----------------- auto orientation visual test -----------------
def run_orientation_test():
    """Quick visual test: show short labels for each orientation so user can see which is correct."""
    if not USE_LED or device is None:
        print("LED device not present — skipping orientation test.")
        return None

    orientations = [0, 90, 180, 270]
    chosen = None
    print("Orientation test: cycling through 0,90,180,270 (watch the matrix)...")
    for o in orientations:
        show_text_horizontal(f"OR{o}", o, speed=0.02)
        time.sleep(0.25)
        # we cannot auto-detect visually; we pick last tried if DEVICE_ORIENTATION unset.
        chosen = o
    print("Orientation test complete. If text still looks vertical, edit DEVICE_ORIENTATION near the top.")
    return chosen

# ----------------- sysfs helpers -----------------
def export_gpio(n):
    p = f"/sys/class/gpio/gpio{n}"
    if not os.path.exists(p):
        try:
            with open("/sys/class/gpio/export", "w") as f:
                f.write(str(n))
            time.sleep(0.02)
        except PermissionError:
            print("Permission error exporting gpio. Run script with sudo.")
            sys.exit(1)
    try:
        with open(f"/sys/class/gpio/gpio{n}/direction", "w") as f:
            f.write("in")
    except Exception:
        pass

def read_gpio_value(n):
    try:
        return int(open(f"/sys/class/gpio/gpio{n}/value").read().strip())
    except Exception:
        return 1

# ----------------- main -----------------
def main():
    global DEVICE_ORIENTATION

    export_gpio(LEFT_GLOBAL)
    export_gpio(RIGHT_GLOBAL)

    # orientation test if not explicitly set
    if DEVICE_ORIENTATION is None and USE_LED and device is not None:
        detected = run_orientation_test()
        if detected is not None:
            DEVICE_ORIENTATION = detected
    if DEVICE_ORIENTATION is None:
        DEVICE_ORIENTATION = 0  # fallback

    print("Using DEVICE_ORIENTATION =", DEVICE_ORIENTATION)
    print("Starting IR monitor (active-low). Ctrl+C to stop.")
    left_until = right_until = centre_until = 0.0

    try:
        while True:
            now = time.time()
            lv = read_gpio_value(LEFT_GLOBAL)
            rv = read_gpio_value(RIGHT_GLOBAL)
            ts = time.strftime("%H:%M:%S")
            print(f"{ts} LEFT={lv} RIGHT={rv}")

            # active-low: 0 == detection
            if lv == 0 and rv == 0:
                centre_until = now + LATCH_SECONDS
                left_until = right_until = 0.0
                msg = "CENTRE"
                print(msg)
                show_text_horizontal(msg, DEVICE_ORIENTATION, speed=0.03)
            elif lv == 0:
                left_until = now + LATCH_SECONDS
                centre_until = 0.0
                msg = "LEFT SENSOR"
                print(msg)
                show_text_horizontal(msg, DEVICE_ORIENTATION, speed=0.03)
            elif rv == 0:
                right_until = now + LATCH_SECONDS
                centre_until = 0.0
                msg = "RIGHT SENSOR"
                print(msg)
                show_text_horizontal(msg, DEVICE_ORIENTATION, speed=0.03)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()