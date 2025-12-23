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


#def capture_frame() -> Image.Image:
def capture_frame(context: str = "unknown") -> Image.Image:    
    ts = int(time.time() * 1000)
    safe_context = context.replace(" ", "_").lower()
    img_path = FRAME_DIR / f"frame_{ts}_{safe_context}.jpg"
    LOGGER.info("Capturing frame from Pi camera (context=%s)", context)

    subprocess.run(
        [
            "rpicam-still",
            "-n",
            "--zsl",
            #"-t", "1",
            "--timeout", "200",
            "--rotation", "180",
            "--width", "640",
            "--height", "480",
            "-o", str(img_path)
        ],
        check=True
    )

    img = Image.open(img_path)

    #if CONFIG["vision"].get("save_frames", False):
    if CONFIG.get("vision", {}).get("save_frames", False):
        img.save(img_path)
        LOGGER.info("Saved camera frame: %s", img_path)
    else:
        img_path.unlink(missing_ok=True)

    return img