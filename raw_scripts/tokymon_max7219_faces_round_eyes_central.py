#!/usr/bin/env python3
"""
tokymon_max7219_faces_minimal_v2.py
Three clean expressions for 4× MAX7219 (32×8), tuned for bold readability:

  1) Normal (natural blink)
  2) Listening (eye glances + level meter)
  3) Speaking (animated oval mouth + level meter)

Design rules:
- Big circular eyes (6×6) on panels 1 & 4; lightly filled with a crisp 2×2 pupil
- Blink uses half-lid → full-lid frames
- Nose 2×4 at rows 0..3, centered inside panels 2 & 3
- Guaranteed gap row 4 (empty)
- Mouth strictly in rows 5..7 and columns 8..23 (center window)

Requires:
  sudo apt install python3-luma.core python3-luma.led-matrix
"""

import time, math, argparse
from luma.core.interface.serial import spi, noop
from luma.led_matrix.device import max7219
from luma.core.render import canvas

# ===== Orientation (use your working values) =====
ROTATE       = 0
BLOCK_ORIENT = 90
REVERSED     = True
CASCADED     = 4
# ================================================

W, H = 8 * CASCADED, 8

# ----------------- OUTER EYES (full circle, lightly filled) -----------------
# Each eye sits in a 6×6 box: rows 0..5 (y), x in [1..6] (left) and [W-7..W-2] (right)
LBOX = (1, 0, 6, 5)
RBOX = (W - 7, 0, W - 2, 5)

def px_any(d, x, y, on=True):
    if on and 0 <= x < W and 0 <= y < H:
        d.point((x, y), fill=255)

def eye_full_circle(d, box, pupil="c", blink_stage=0):
    """
    Draw a bold, readable eye:
      - blink_stage: 0=none, 1=half-lid, 2=full-lid
      - lightly fill iris; keep a 2×2 pupil hole
    """
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    r  = 3  # 6×6 radius

    # Blink frames
    if blink_stage == 2:
        # full lid (two rows)
        for x in range(x1, x2 + 1):
            px_any(d, x, cy)
            px_any(d, x, min(H - 1, cy + 1))
        return
    elif blink_stage == 1:
        # half lid (one row)
        for x in range(x1, x2 + 1):
            px_any(d, x, cy)
        # continue to draw iris lightly below

    # Small interior fill for iris + ring
    r2 = r * r
    for x in range(x1, x2 + 1):
        for y in range(y1, y2 + 1):
            dist2 = (x - cx) ** 2 + (y - cy) ** 2
            # ring or just-inside ring for bolder look
            if (r2 - 2 <= dist2 <= r2 + 1) or (r2 - 5 <= dist2 <= r2 - 4):
                px_any(d, x, y)

    # Pupil (2×2) with directional offset
    ox = oy = 0
    if pupil == "l":   ox = -1
    elif pupil == "r": ox = +1
    elif pupil == "u": oy = -1
    elif pupil == "d": oy = +1
    # erase pupil hole by not drawing those 4 pixels (no-op here)
    # To ensure visibility, we draw iris first and leave the pupil "empty".
    # But MAX7219 has only on/off; so simulate hole by not overdrawing here.
    # To emphasize the pupil, we can 'erase' by skipping; done implicitly.

    # For clarity on LED: draw the 2×2 pupil explicitly (will look 'brighter')
    for dx in (0, 1):
        for dy in (0, 1):
            px_any(d, cx + ox + dx, cy + oy + dy)

def draw_eyes(d, pupil_dir="c", blink_phase=0):
    eye_full_circle(d, LBOX, pupil=pupil_dir, blink_stage=blink_phase)
    eye_full_circle(d, RBOX, pupil=pupil_dir, blink_stage=blink_phase)

# ------------------ CENTER WINDOW (panels 2 & 3 only) ------------------
CX1, CX2   = 8, 23
MARGIN     = 2
IN_X1, IN_X2 = CX1 + MARGIN, CX2 - MARGIN
MIDX       = (CX1 + CX2) // 2

def px_c(d, x, y, on=True):
    if on and CX1 <= x <= CX2 and 0 <= y < H:
        d.point((x, y), fill=255)

def hline_c(d, y, x1, x2):
    x1 = max(IN_X1, x1); x2 = min(IN_X2, x2)
    if x1 <= x2:
        for x in range(x1, x2 + 1):
            px_c(d, x, y)

# ------------------ Nose 2×4 (rows 0..3) ------------------
def nose_block(d):
    x1, x2 = max(IN_X1, MIDX - 1), min(IN_X2, MIDX)
    for y in (0, 1, 2, 3):
        px_c(d, x1, y); px_c(d, x2, y)

# ------------------ Mouths in rows 5..7 only ------------------
def mouth_neutral_round(d):
    """Shallow round 'rest' mouth using an arc; strictly rows 5..7."""
    R  = 6
    cy = 9  # below bottom to get a shallow arc
    for x in range(IN_X1, IN_X2 + 1):
        dx = x - MIDX
        val = R * R - dx * dx
        if val >= 0:
            y = int(cy - math.sqrt(val))
            if 5 <= y <= 7: px_c(d, x, y)
            if 5 <= y + 1 <= 7: px_c(d, x, y + 1)  # thicken

def mouth_oval_talk(d, t):
    """Animated oval; height 2–3 rows, centered at row ~6."""
    a  = max(4, (IN_X2 - IN_X1) // 2 - 1)
    b  = 2 if (math.sin(t * 6) > 0) else 1   # toggle 1↔2 (rows each side)
    cy = 6
    for x in range(IN_X1, IN_X2 + 1):
        dx = (x - MIDX) / a
        t2 = 1 - dx * dx
        if t2 >= 0:
            dy = b * math.sqrt(t2)
            y1 = int(cy - dy); y2 = int(cy + dy)
            # clamp to 5..7
            y1 = max(5, min(7, y1))
            y2 = max(5, min(7, y2))
            px_c(d, x, y1); px_c(d, x, y2)

def level_meter(d, t):
    span = IN_X2 - IN_X1
    n = 2 + int((math.sin(t * 5) + 1) / 2 * span)
    for x in range(IN_X1, IN_X1 + n):
        px_c(d, x, 7)

# ------------------ FACE COMPOSER ------------------
def face(device, sec, mode="normal"):
    """
    mode: 'normal' | 'listening' | 'speaking'
    """
    t0 = time.time()
    # blink timing
    next_blink = t0 + 1.2
    blink_frame = 0  # 0 none, 1 half, 2 full

    while time.time() - t0 < sec:
        now = time.time()

        # eye direction
        if mode == "listening":
            s = math.sin(now * 2.0)
            pupil_dir = "l" if s < -0.35 else ("r" if s > 0.35 else "c")
        else:
            pupil_dir = "c"

        # blink state machine
        if next_blink <= now < next_blink + 0.08:
            blink_frame = 1
        elif next_blink + 0.08 <= now < next_blink + 0.16:
            blink_frame = 2
        else:
            blink_frame = 0
        if now >= next_blink + 0.6:  # reopen window
            next_blink = now + 1.2 + 0.6 * math.sin(now)

        with canvas(device) as d:
            # Eyes
            draw_eyes(d, pupil_dir=pupil_dir, blink_phase=blink_frame)

            # Nose rows 0..3
            nose_block(d)

            # Gap rows 4 is empty (and 3 naturally unused by mouth)
            # Mouth rows 5..7
            if mode == "speaking":
                mouth_oval_talk(d, now - t0)
                level_meter(d, now - t0)
            elif mode == "listening":
                mouth_neutral_round(d)
                level_meter(d, now - t0)
            else:
                mouth_neutral_round(d)

        time.sleep(0.06)

# ------------------ DEVICE + MAIN ------------------
def make_device(contrast):
    serial = spi(port=0, device=0, gpio=noop())
    dev = max7219(serial,
                  cascaded=CASCADED,
                  rotate=ROTATE,
                  block_orientation=BLOCK_ORIENT,
                  blocks_arranged_in_reverse_order=REVERSED)
    dev.contrast(contrast)
    return dev

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--each", type=float, default=3.0)
    ap.add_argument("--contrast", type=int, default=9)
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args()

    dev = make_device(args.contrast)
    try:
        while True:
            print("[Tokymon] Normal")
            face(dev, args.each, mode="normal")

            print("[Tokymon] Listening")
            face(dev, args.each, mode="listening")

            print("[Tokymon] Speaking")
            face(dev, args.each, mode="speaking")

            if not args.loop:
                break
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()