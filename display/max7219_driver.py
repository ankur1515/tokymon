# display/max7219_driver.py
from __future__ import annotations

import os
import time
import glob

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("max7219_driver")

# Config-driven defaults
CANDIDATE_CASCADE = CONFIG.get("board_options", {}).get("led_matrix_cascaded", 4)
DEFAULT_CONTRAST = CONFIG.get("board_options", {}).get("led_contrast", 8)
DEFAULT_BLOCK_ORIENTATION = 180
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Internal state
_DEVICE = None
_SERIAL = None
_DETECTED = {"port": None, "device": None, "cascaded": None, "orientation": None}


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


def _try_init(port, device, cascaded, orientation, contrast):
    """Try to init a device; returns device object or raises."""
    from luma.core.interface.serial import spi, noop
    from luma.led_matrix.device import max7219

    serial = spi(port=port, device=device, gpio=noop())
    dev = max7219(serial, cascaded=cascaded, block_orientation=orientation)
    dev.contrast(contrast)
    return dev


def _auto_detect_and_init():
    global _DEVICE, _SERIAL, _DETECTED
    if USE_SIM:
        LOGGER.info("Simulator mode - skipping hardware init")
        return None

    candidates = _list_spidev_nodes()
    if not candidates:
        LOGGER.warning("No spidev nodes found; skipping init")
        return None

    cascaded_options = [CANDIDATE_CASCADE] + list(range(1, 9))
    orientation_options = [DEFAULT_BLOCK_ORIENTATION, 0, 90, 180, 270]
    contrast = DEFAULT_CONTRAST

    for (port, device) in candidates:
        for casc in cascaded_options:
            for orient in orientation_options:
                try:
                    dev = _try_init(port, device, casc, orient, contrast)
                    # quick all-on test: draw a rectangle briefly to validate wiring
                    from luma.core.render import canvas
                    with canvas(dev) as draw:
                        draw.rectangle((0, 0, dev.width - 1, dev.height - 1), outline=255, fill=255)
                    # small pause to allow visual confirmation
                    time.sleep(0.05)
                    # success: keep this device
                    _DEVICE = dev
                    _DETECTED.update({"port": port, "device": device, "cascaded": casc, "orientation": orient})
                    LOGGER.info("MAX7219 init ok: port=%s device=%s cascaded=%s orient=%s", port, device, casc, orient)
                    return _DEVICE
                except Exception as e:
                    LOGGER.debug("max7219 try failed port=%s dev=%s casc=%s orient=%s -> %s", port, device, casc, orient, e)
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


def show_text(text: str, speed: float = 0.03):
    if USE_SIM:
        LOGGER.info("show_text(sim): %s", text)
        return
    dev = _require_device()
    # Port the horizontal text function from raw script
    from display.expressions import draw_text_horizontal
    draw_text_horizontal(dev, text, _DETECTED.get("orientation", DEFAULT_BLOCK_ORIENTATION), speed)


def clear():
    if USE_SIM:
        LOGGER.info("clear(sim)")
        return
    dev = _require_device()
    from luma.core.render import canvas
    with canvas(dev) as draw:
        draw.rectangle((0, 0, dev.width - 1, dev.height - 1), outline=0, fill=0)
