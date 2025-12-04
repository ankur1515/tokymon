# display/max7219_driver.py
from __future__ import annotations

import os
import time
import glob

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("max7219_driver")

# Config-driven defaults (read safely)
LED_CONFIG = CONFIG.get("board_options", {}).get("led_matrix", {})
CASCADED = LED_CONFIG.get("cascaded", 4)
ORIENTATION = LED_CONFIG.get("orientation", 0)
SCROLL_SPEED = LED_CONFIG.get("scroll_speed", 0.03)
X_OFFSET = LED_CONFIG.get("x_offset", 0)
DEFAULT_CONTRAST = CONFIG.get("board_options", {}).get("led_contrast", 8)

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Internal state
_DEVICE = None
_SERIAL = None
_DETECTED = {"port": None, "device": None, "cascaded": None}


def _list_spidev_nodes():
    """Returns list of tuples (port, device) for /dev/spidevX.Y"""
    nodes = glob.glob("/dev/spidev*")
    out = []
    for n in nodes:
        try:
            base = os.path.basename(n)  # e.g. spidev0.0 or spidev10.0
            parts = base.replace("spidev", "").split(".")
            port = int(parts[0])
            device = int(parts[1])
            out.append((port, device))
        except Exception:
            continue
    return sorted(set(out))


def _try_init(port, device, cascaded, contrast):
    """Try to init a device; returns device object or raises."""
    from luma.core.interface.serial import spi, noop
    from luma.led_matrix.device import max7219

    serial = spi(port=port, device=device, gpio=noop())
    # Use block_orientation=0 always - we handle rotation via image rotation
    dev = max7219(serial, cascaded=cascaded, block_orientation=0)
    dev.contrast(contrast)
    return dev


def _auto_detect_and_init():
    """Auto-detect SPI device and initialize."""
    global _DEVICE, _SERIAL, _DETECTED
    if USE_SIM:
        LOGGER.info("Simulator mode - skipping hardware init")
        return None

    candidates = _list_spidev_nodes()
    if not candidates:
        LOGGER.warning("No spidev nodes found; skipping init")
        return None

    cascaded_options = [CASCADED] + list(range(1, 9))
    contrast = DEFAULT_CONTRAST

    for (port, device) in candidates:
        for casc in cascaded_options:
            try:
                dev = _try_init(port, device, casc, contrast)
                # quick all-on test: draw a rectangle briefly to validate wiring
                from luma.core.render import canvas
                with canvas(dev) as draw:
                    draw.rectangle((0, 0, dev.width - 1, dev.height - 1), outline=255, fill=255)
                # small pause to allow visual confirmation
                time.sleep(0.05)
                # success: keep this device
                _DEVICE = dev
                _DETECTED.update({"port": port, "device": device, "cascaded": casc})
                LOGGER.info("MAX7219 init ok: port=%s device=%s cascaded=%s", port, device, casc)
                return _DEVICE
            except Exception as e:
                LOGGER.debug("max7219 try failed port=%s dev=%s casc=%s -> %s", port, device, casc, e)
                # try next combination
                continue
    LOGGER.error("Auto-detect failed for MAX7219; no working combination found")
    return None


# Public API:


def init_display(force=False):
    """
    Initialize display device. If already initialized and not forced, return existing.
    In dev mode this is a no-op (logs only).
    """
    global _DEVICE
    if _DEVICE is not None and not force:
        return _DEVICE
    if USE_SIM:
        LOGGER.info("init_display: simulator mode, no hardware init")
        return None
    _DEVICE = _auto_detect_and_init()
    return _DEVICE


def _require_device():
    if USE_SIM:
        raise RuntimeError("Simulator mode: display not available")
    if _DEVICE is None:
        raise RuntimeError("Display not initialized; call init_display() first")
    return _DEVICE


def show_text(text: str, speed: float = None):
    """
    Show text with robust rendering: create horizontal image, rotate by ORIENTATION, scroll.
    """
    if USE_SIM:
        LOGGER.info("show_text(sim): %s", text)
        return
    
    if speed is None:
        speed = SCROLL_SPEED
    
    dev = _require_device()
    
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        LOGGER.warning("PIL not available; cannot render text")
        return
    
    from luma.core.render import canvas
    
    # Get device dimensions
    dev_w, dev_h = dev.width, dev.height
    
    # Load font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    
    # Measure text
    def measure_text(txt, font_obj):
        """Return (w, h) of text in pixels."""
        try:
            tmp_img = Image.new("1", (1, 1))
            draw = ImageDraw.Draw(tmp_img)
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), txt, font=font_obj)
                return (bbox[2] - bbox[0], bbox[3] - bbox[1])
            if hasattr(draw, "textsize"):
                return draw.textsize(txt, font=font_obj)
        except Exception:
            pass
        return (len(txt) * 6, 8)
    
    f = font or ImageFont.load_default()
    text_w, text_h = measure_text(text, f)
    
    # Create large horizontal image with text
    # Text origin = (device_width + X_OFFSET, centered vertically)
    canvas_w = dev_w + X_OFFSET + text_w + dev_w  # space before, text, space after
    canvas_h = max(dev_h, text_h)
    horiz_img = Image.new("1", (canvas_w, canvas_h), "black")
    draw = ImageDraw.Draw(horiz_img)
    
    # Draw text at (dev_w + X_OFFSET, centered vertically)
    text_x = dev_w + X_OFFSET
    text_y = (canvas_h - text_h) // 2
    draw.text((text_x, text_y), text, font=f, fill=255)
    
    # Rotate entire image by ORIENTATION before displaying
    if ORIENTATION != 0:
        rotated_img = horiz_img.rotate(ORIENTATION, expand=True)
    else:
        rotated_img = horiz_img
    
    # Scroll the rotated image across the display
    total_scroll = rotated_img.width - dev_w
    if total_scroll <= 0:
        # Text fits - center and show briefly
        with canvas(dev) as drawc:
            x = (dev_w - rotated_img.width) // 2
            y = (dev_h - rotated_img.height) // 2
            drawc.bitmap((x, y), rotated_img, fill=255)
        time.sleep(1.0)
        return
    
    # Scroll window across the rotated image
    for x in range(0, total_scroll + 1):
        with canvas(dev) as drawc:
            segment = rotated_img.crop((x, 0, x + dev_w, rotated_img.height))
            drawc.bitmap((0, 0), segment, fill=255)
        time.sleep(speed)


def show_expression(name: str, duration_s: float = 1.2):
    """
    Show a named expression. Use the expression map from the raw script.
    In dev mode, log and return.
    """
    if USE_SIM:
        LOGGER.info("show_expression(sim): %s", name)
        return
    dev = _require_device()

    # Use expressions from display.expressions module
    from display.expressions import draw_face_frame
    from luma.core.render import canvas

    # Map expression names to modes
    mode_map = {
        "normal": "normal",
        "listening": "listening",
        "alert": "listening",
        "speaking": "speaking",
        "happy": "speaking",
        "hello": "normal",
        "smile": "normal",
    }
    mode = mode_map.get(name, "normal")

    t0 = time.time()
    while time.time() - t0 < duration_s:
        with canvas(dev) as draw:
            draw_face_frame(draw, dev, mode, time.time() - t0)
        time.sleep(0.06)


def clear():
    """Clear the display."""
    if USE_SIM:
        LOGGER.info("clear(sim)")
        return
    dev = _require_device()
    from luma.core.render import canvas
    with canvas(dev) as draw:
        draw.rectangle((0, 0, dev.width - 1, dev.height - 1), outline=0, fill=0)
