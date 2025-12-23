"""Camera access wrapper."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # type: ignore

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore

import subprocess

from system.logger import get_logger
from system.config import CONFIG

LOGGER = get_logger("camera")

FRAME_DIR = Path("data/camera_frames")
FRAME_DIR.mkdir(parents=True, exist_ok=True)

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)


def capture_frame(context: str = "unknown") -> Optional[object]:  # Image.Image when available
    """Capture frame and return PIL Image (legacy interface)."""
    if not PIL_AVAILABLE or Image is None:
        LOGGER.warning("PIL/Pillow not available - camera capture disabled")
        return None
    
    ts = int(time.time() * 1000)
    safe_context = context.replace(" ", "_").lower()
    img_path = FRAME_DIR / f"frame_{ts}_{safe_context}.jpg"
    LOGGER.info("Capturing frame from Pi camera (context=%s)", context)

    if USE_SIM:
        LOGGER.debug("Camera capture (simulator): returning blank image")
        return Image.new("RGB", (640, 480), color="black")

    subprocess.run(
        [
            "rpicam-still",
            "-n",
            "--zsl",
            "--timeout", "200",
            "--rotation", "180",
            "--width", "640",
            "--height", "480",
            "-o", str(img_path)
        ],
        check=True,
        timeout=5
    )

    img = Image.open(img_path)

    if CONFIG.get("vision", {}).get("save_frames", False):
        img.save(img_path)
        LOGGER.info("Saved camera frame: %s", img_path)
    else:
        img_path.unlink(missing_ok=True)

    return img


def capture_frame_np(context: str = "unknown") -> Optional[object]:  # np.ndarray when available
    """
    Capture frame and return as OpenCV-compatible numpy array.
    
    Returns:
        np.ndarray: BGR image array (shape: height, width, 3) or None if dependencies missing
    """
    if not NUMPY_AVAILABLE or np is None:
        LOGGER.warning("NumPy not available - camera capture disabled")
        return None
    
    if USE_SIM:
        LOGGER.debug("Camera capture (simulator): returning blank array")
        return np.zeros((480, 640, 3), dtype=np.uint8)
    
    try:
        # Capture using rpicam-still
        ts = int(time.time() * 1000)
        safe_context = context.replace(" ", "_").lower()
        img_path = FRAME_DIR / f"frame_{ts}_{safe_context}.jpg"
        
        LOGGER.debug("Capturing frame (context=%s)", context)
        
        subprocess.run(
            [
                "rpicam-still",
                "-n",
                "--zsl",
                "--timeout", "200",
                "--rotation", "180",  # Handle upside-down mounting
                "--width", "640",
                "--height", "480",
                "-o", str(img_path)
            ],
            check=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL
        )
        
        # Load image
        img = Image.open(img_path)
        
        # Convert PIL to numpy array (RGB)
        img_array = np.array(img)
        
        # Convert RGB to BGR for OpenCV compatibility
        if len(img_array.shape) == 3:
            img_bgr = img_array[:, :, ::-1]  # RGB to BGR
        else:
            # Grayscale - convert to 3-channel
            img_bgr = np.stack([img_array, img_array, img_array], axis=2)
        
        # Always save frames for debugging (user requested)
        img.save(img_path)
        LOGGER.debug("Saved camera frame: %s", img_path)
        
        return img_bgr
        
    except subprocess.TimeoutExpired:
        LOGGER.warning("Camera capture timeout")
        if np is not None:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        return None
    except FileNotFoundError:
        LOGGER.warning("rpicam-still not found (simulator mode?)")
        if np is not None:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        return None
    except Exception as exc:
        LOGGER.warning("Camera capture error: %s", exc)
        if np is not None:
            return np.zeros((480, 640, 3), dtype=np.uint8)
        return None
