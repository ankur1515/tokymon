"""Camera access wrapper."""
from __future__ import annotations

import time
from pathlib import Path
from PIL import Image
import subprocess

from system.logger import get_logger
from system.config import CONFIG

LOGGER = get_logger("camera")

FRAME_DIR = Path("data/camera_frames")
FRAME_DIR.mkdir(parents=True, exist_ok=True)


def capture_frame() -> Image.Image:
    """
    Capture a single frame from Pi camera.
    Image is rotated 180° to fix upside-down mounting.
    Optionally saved to disk based on config.
    """
    ts = int(time.time() * 1000)
    img_path = FRAME_DIR / f"frame_{ts}.jpg"

    LOGGER.info("Capturing frame from Pi camera")

    subprocess.run(
        [
            "rpicam-still",
            "-n",
            "-t", "1",
            "-o", str(img_path)
        ],
        check=True
    )

    img = Image.open(img_path)
    img = img.rotate(180, expand=True)

    # Save rotated image if enabled
    if CONFIG["vision"].get("save_frames", False):
        img.save(img_path)
        LOGGER.info("Saved camera frame: %s", img_path)
    else:
        img_path.unlink(missing_ok=True)

    return img