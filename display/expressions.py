"""Expression drawing primitives for MAX7219 LED matrix."""
from __future__ import annotations

import math
import time
from typing import Callable

try:
    from PIL import ImageFont, ImageDraw, Image
except ImportError:
    ImageFont = ImageDraw = Image = None  # type: ignore

# Constants from raw_scripts/tokymon_max7219_faces_round_eyes_central.py
CASCADED = 4
W, H = 8 * CASCADED, 8

# Eye boxes
LBOX = (1, 0, 6, 5)
RBOX = (W - 7, 0, W - 2, 5)

# Center window (panels 2 & 3)
CX1, CX2 = 8, 23
MARGIN = 2
IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
MIDX = (CX1 + CX2) // 2


def px_any(draw, x: int, y: int, on: bool = True) -> None:
    """Draw a point if within bounds."""
    if on and 0 <= x < W and 0 <= y < H:
        draw.point((x, y), fill=255)


def px_c(draw, x: int, y: int, on: bool = True) -> None:
    """Draw a point in center window."""
    if on and CX1 <= x <= CX2 and 0 <= y < H:
        draw.point((x, y), fill=255)


def eye_full_circle(draw, box: tuple[int, int, int, int], pupil: str = "c", blink_stage: int = 0) -> None:
    """Draw a bold, readable eye with blink animation."""
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    r = 3  # 6×6 radius

    # Blink frames
    if blink_stage == 2:
        # full lid (two rows)
        for x in range(x1, x2 + 1):
            px_any(draw, x, cy)
            px_any(draw, x, min(H - 1, cy + 1))
        return
    elif blink_stage == 1:
        # half lid (one row)
        for x in range(x1, x2 + 1):
            px_any(draw, x, cy)

    # Small interior fill for iris + ring
    r2 = r * r
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            dist2 = (x - cx) ** 2 + (y - cy) ** 2
            # ring or just-inside ring for bolder look
            if (r2 - 2 <= dist2 <= r2 + 1) or (r2 - 5 <= dist2 <= r2 - 4):
                px_any(draw, x, y)

    # Pupil (2×2) with directional offset
    ox = oy = 0
    if pupil == "l":
        ox = -1
    elif pupil == "r":
        ox = +1
    elif pupil == "u":
        oy = -1
    elif pupil == "d":
        oy = +1

    # Draw the 2×2 pupil explicitly
    for dx in (0, 1):
        for dy in (0, 1):
            px_any(draw, cx + ox + dx, cy + oy + dy)


def draw_eyes(draw, pupil_dir: str = "c", blink_phase: int = 0) -> None:
    """Draw both eyes."""
    eye_full_circle(draw, LBOX, pupil=pupil_dir, blink_stage=blink_phase)
    eye_full_circle(draw, RBOX, pupil=pupil_dir, blink_stage=blink_phase)


def nose_block(draw) -> None:
    """Nose 2×4 (rows 0..3)."""
    x1, x2 = max(IN_X1, MIDX - 1), min(IN_X2, MIDX)
    for y in (0, 1, 2, 3):
        px_c(draw, x1, y)
        px_c(draw, x2, y)


def mouth_neutral_round(draw) -> None:
    """Shallow round 'rest' mouth using an arc; strictly rows 5..7."""
    R = 6
    cy = 9  # below bottom to get a shallow arc
    for x in range(IN_X1, IN_X2 + 1):
        dx = x - MIDX
        val = R * R - dx * dx
        if val >= 0:
            y = int(cy - math.sqrt(val))
            if 5 <= y <= 7:
                px_c(draw, x, y)
            if 5 <= y + 1 <= 7:
                px_c(draw, x, y + 1)  # thicken


def mouth_oval_talk(draw, t: float) -> None:
    """Animated oval; height 2–3 rows, centered at row ~6."""
    a = max(4, (IN_X2 - IN_X1) // 2 - 1)
    b = 2 if (math.sin(t * 6) > 0) else 1  # toggle 1↔2 (rows each side)
    cy = 6
    for x in range(IN_X1, IN_X2 + 1):
        dx = (x - MIDX) / a
        t2 = 1 - dx * dx
        if t2 >= 0:
            dy = b * math.sqrt(t2)
            y1 = int(cy - dy)
            y2 = int(cy + dy)
            # clamp to 5..7
            y1 = max(5, min(7, y1))
            y2 = max(5, min(7, y2))
            px_c(draw, x, y1)
            px_c(draw, x, y2)


def level_meter(draw, t: float) -> None:
    """Animated level meter at bottom."""
    span = IN_X2 - IN_X1
    n = 2 + int((math.sin(t * 5) + 1) / 2 * span)
    for x in range(IN_X1, IN_X1 + n):
        px_c(draw, x, 7)


def draw_face_frame(draw, device, mode: str, elapsed: float) -> None:
    """
    Draw a single frame of the face animation.
    mode: 'normal' | 'listening' | 'speaking'
    """
    # Eye direction
    if mode == "listening":
        s = math.sin(elapsed * 2.0)
        pupil_dir = "l" if s < -0.35 else ("r" if s > 0.35 else "c")
    else:
        pupil_dir = "c"

    # Blink state machine
    next_blink_base = int(elapsed / 1.8) * 1.8
    blink_offset = elapsed - next_blink_base
    if 0 <= blink_offset < 0.08:
        blink_frame = 1
    elif 0.08 <= blink_offset < 0.16:
        blink_frame = 2
    else:
        blink_frame = 0

    # Draw components
    draw_eyes(draw, pupil_dir=pupil_dir, blink_phase=blink_frame)
    nose_block(draw)

    # Mouth rows 5..7
    if mode == "speaking":
        mouth_oval_talk(draw, elapsed)
        level_meter(draw, elapsed)
    elif mode == "listening":
        mouth_neutral_round(draw)
        level_meter(draw, elapsed)
    else:
        mouth_neutral_round(draw)


def draw_text_horizontal(device, text: str, device_orientation: int, speed: float = 0.03) -> None:
    """
    Draw text horizontally (left->right) with rotation support.
    Ported from raw_scripts/ir_detect_5s_led.py
    """
    if ImageFont is None or ImageDraw is None or Image is None:
        from system.logger import get_logger
        get_logger("expressions").warning("PIL not available; cannot render text")
        return

    from luma.core.render import canvas

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

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
    w, h = measure_text(text, f)
    dev_w, dev_h = device.width, device.height

    # Create horizontal canvas image
    horiz_img = Image.new("1", (w + dev_w, max(dev_h, h)), "black")
    draw = ImageDraw.Draw(horiz_img)
    draw.text((dev_w, (horiz_img.height - h) // 2), text, font=f, fill=255)

    # Rotate to match device orientation
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

    # Scroll horizontally
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


# Expression name mappings (for backward compatibility)
EXPRESSIONS = {
    "idle": "normal",
    "happy": "speaking",
    "alert": "listening",
    "hello": "normal",
    "smile": "normal",
    "forward": "normal",
    "back": "normal",
    "left": "normal",
    "right": "normal",
    "listening": "listening",
    "success": "normal",
    "error": "listening",
}
