"""MAX7219 LED matrix driver (extracted from raw_scripts/tokymon_max7219_faces_round_eyes_central.py)."""
from __future__ import annotations

import math
import time
from typing import Literal

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("max7219")
SPI = CONFIG["pinmap"]["led_matrix"]["spi"]
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

CASCADED = 4
W, H = 8 * CASCADED, 8
_device = None


def _make_device(contrast: int = 9):
    """Initialize MAX7219 device (luma.led_matrix)."""
    global _device
    if USE_SIM or _device is not None:
        return _device
    try:
        from luma.core.interface.serial import spi as luma_spi, noop
        from luma.led_matrix.device import max7219 as luma_max7219

        serial = luma_spi(port=0, device=0, gpio=noop())
        _device = luma_max7219(
            serial,
            cascaded=CASCADED,
            rotate=0,
            block_orientation=90,
            blocks_arranged_in_reverse_order=True,
        )
        _device.contrast(contrast)
        LOGGER.info("MAX7219 initialized (MOSI=%s CLK=%s CS=%s)", SPI["mosi"], SPI["clk"], SPI["cs"])
    except ImportError:
        LOGGER.warning("luma.led_matrix not installed; display will be mocked")
    except Exception as exc:
        LOGGER.warning("MAX7219 init failed: %s", exc)
    return _device


def init_display(contrast: int = 9) -> None:
    """Initialize the LED matrix display."""
    _make_device(contrast)
    if USE_SIM:
        LOGGER.info("MAX7219 simulator mode (no hardware)")


def _px_any(draw, x: int, y: int, on: bool = True) -> None:
    if on and 0 <= x < W and 0 <= y < H:
        draw.point((x, y), fill=255)


def _eye_full_circle(draw, box: tuple[int, int, int, int], pupil: str = "c", blink_stage: int = 0) -> None:
    """Draw eye with blink animation (from raw_scripts)."""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    r = 3

    if blink_stage == 2:
        for x in range(x1, x2 + 1):
            _px_any(draw, x, cy)
            _px_any(draw, x, min(H - 1, cy + 1))
        return
    elif blink_stage == 1:
        for x in range(x1, x2 + 1):
            _px_any(draw, x, cy)

    r2 = r * r
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            dist2 = (x - cx) ** 2 + (y - cy) ** 2
            if (r2 - 2 <= dist2 <= r2 + 1) or (r2 - 5 <= dist2 <= r2 - 4):
                _px_any(draw, x, y)

    ox = oy = 0
    if pupil == "l":
        ox = -1
    elif pupil == "r":
        ox = +1
    elif pupil == "u":
        oy = -1
    elif pupil == "d":
        oy = +1

    for dx in (0, 1):
        for dy in (0, 1):
            _px_any(draw, cx + ox + dx, cy + oy + dy)


def _draw_eyes(draw, pupil_dir: str = "c", blink_phase: int = 0) -> None:
    LBOX = (1, 0, 6, 5)
    RBOX = (W - 7, 0, W - 2, 5)
    _eye_full_circle(draw, LBOX, pupil=pupil_dir, blink_stage=blink_phase)
    _eye_full_circle(draw, RBOX, pupil=pupil_dir, blink_stage=blink_phase)


def _nose_block(draw) -> None:
    CX1, CX2 = 8, 23
    MARGIN = 2
    IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
    MIDX = (CX1 + CX2) // 2
    x1, x2 = max(IN_X1, MIDX - 1), min(IN_X2, MIDX)
    for y in (0, 1, 2, 3):
        _px_any(draw, x1, y)
        _px_any(draw, x2, y)


def _mouth_neutral_round(draw) -> None:
    CX1, CX2 = 8, 23
    MARGIN = 2
    IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
    MIDX = (CX1 + CX2) // 2
    R = 6
    cy = 9
    for x in range(IN_X1, IN_X2 + 1):
        dx = x - MIDX
        val = R * R - dx * dx
        if val >= 0:
            y = int(cy - math.sqrt(val))
            if 5 <= y <= 7:
                _px_any(draw, x, y)
            if 5 <= y + 1 <= 7:
                _px_any(draw, x, y + 1)


def _mouth_oval_talk(draw, t: float) -> None:
    CX1, CX2 = 8, 23
    MARGIN = 2
    IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
    MIDX = (CX1 + CX2) // 2
    a = max(4, (IN_X2 - IN_X1) // 2 - 1)
    b = 2 if (math.sin(t * 6) > 0) else 1
    cy = 6
    for x in range(IN_X1, IN_X2 + 1):
        dx = (x - MIDX) / a
        t2 = 1 - dx * dx
        if t2 >= 0:
            dy = b * math.sqrt(t2)
            y1 = int(cy - dy)
            y2 = int(cy + dy)
            y1 = max(5, min(7, y1))
            y2 = max(5, min(7, y2))
            _px_any(draw, x, y1)
            _px_any(draw, x, y2)


def _level_meter(draw, t: float) -> None:
    CX1, CX2 = 8, 23
    MARGIN = 2
    IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
    span = IN_X2 - IN_X1
    n = 2 + int((math.sin(t * 5) + 1) / 2 * span)
    for x in range(IN_X1, IN_X1 + n):
        _px_any(draw, x, 7)


def show_expression(name: str, duration: float = 2.0) -> None:
    """Show face expression (normal/listening/speaking) with animation."""
    device = _make_device()
    if device is None and not USE_SIM:
        LOGGER.warning("Display not initialized; skipping expression %s", name)
        return

    mode: Literal["normal", "listening", "speaking"] = "normal"
    if name in ("listening", "alert"):
        mode = "listening"
    elif name in ("speaking", "happy"):
        mode = "speaking"

    t0 = time.time()
    next_blink = t0 + 1.2
    blink_frame = 0

    if USE_SIM:
        LOGGER.debug("Display expression %s (simulator)", name)
        return

    try:
        from luma.core.render import canvas

        while time.time() - t0 < duration:
            now = time.time()

            if mode == "listening":
                s = math.sin(now * 2.0)
                pupil_dir = "l" if s < -0.35 else ("r" if s > 0.35 else "c")
            else:
                pupil_dir = "c"

            if next_blink <= now < next_blink + 0.08:
                blink_frame = 1
            elif next_blink + 0.08 <= now < next_blink + 0.16:
                blink_frame = 2
            else:
                blink_frame = 0
            if now >= next_blink + 0.6:
                next_blink = now + 1.2 + 0.6 * math.sin(now)

            with canvas(device) as draw:
                _draw_eyes(draw, pupil_dir=pupil_dir, blink_phase=blink_frame)
                _nose_block(draw)
                if mode == "speaking":
                    _mouth_oval_talk(draw, now - t0)
                    _level_meter(draw, now - t0)
                elif mode == "listening":
                    _mouth_neutral_round(draw)
                    _level_meter(draw, now - t0)
                else:
                    _mouth_neutral_round(draw)

            time.sleep(0.06)
    except Exception as exc:
        LOGGER.warning("Display expression failed: %s", exc)


def show_text(text: str, speed: float = 0.03) -> None:
    """Show scrolling text (placeholder; full implementation requires PIL font rendering)."""
    LOGGER.info("Display text: %s (speed=%.2f)", text, speed)
    if USE_SIM:
        return
    device = _make_device()
    if device is None:
        return
    try:
        from luma.core.render import canvas

        with canvas(device) as draw:
            draw.text((0, 0), text[:16], fill=255)
        time.sleep(1.0)
    except Exception as exc:
        LOGGER.warning("Display text failed: %s", exc)
