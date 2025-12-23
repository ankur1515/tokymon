"""Face detection using OpenCV Haar Cascade."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("face_detector")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Haar Cascade model path
_MODEL_PATH = Path(__file__).parent.parent / "vision" / "models" / "haarcascade_frontalface_default.xml"
_FALLBACK_MODEL_PATH = Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")

# Global detector instance (loaded once)
_DETECTOR: Optional[cv2.CascadeClassifier] = None


def _load_detector() -> Optional[cv2.CascadeClassifier]:
    """Load Haar Cascade detector (loads once, reuses)."""
    global _DETECTOR
    
    if _DETECTOR is not None:
        return _DETECTOR
    
    if USE_SIM:
        LOGGER.debug("Face detector (simulator): returning None")
        return None
    
    # Try to find model file
    model_path = None
    if _MODEL_PATH.exists():
        model_path = _MODEL_PATH
    elif _FALLBACK_MODEL_PATH.exists():
        model_path = _FALLBACK_MODEL_PATH
    else:
        # Try OpenCV data directory
        try:
            import cv2.data
            model_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            if not model_path.exists():
                model_path = None
        except Exception:
            pass
    
    if model_path is None:
        LOGGER.warning("Haar Cascade model not found. Face detection disabled.")
        LOGGER.warning("Download from: https://github.com/opencv/opencv/blob/master/data/haarcascades/haarcascade_frontalface_default.xml")
        return None
    
    try:
        _DETECTOR = cv2.CascadeClassifier(str(model_path))
        if _DETECTOR.empty():
            LOGGER.error("Failed to load Haar Cascade model from %s", model_path)
            _DETECTOR = None
            return None
        LOGGER.info("Face detector loaded from: %s", model_path)
        return _DETECTOR
    except Exception as exc:
        LOGGER.error("Error loading face detector: %s", exc)
        _DETECTOR = None
        return None


def face_present(frame: np.ndarray, context: str = "unknown") -> bool:
    """
    Detect if face is present in frame (binary only).
    
    Args:
        frame: BGR image array (from capture_frame_np())
        context: Optional context string for logging
    
    Returns:
        bool: True if ≥1 face detected, False otherwise
    """
    if USE_SIM:
        # Simulator: random for testing
        import random
        return random.random() > 0.3
    
    if frame is None or frame.size == 0:
        LOGGER.debug("Face detection: empty frame")
        return False
    
    detector = _load_detector()
    if detector is None:
        LOGGER.debug("Face detector not available")
        return False
    
    try:
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Detect faces
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Binary result: face present or not
        face_visible = len(faces) > 0
        
        LOGGER.debug("Face detection (%s): %s (found %d faces)", context, face_visible, len(faces))
        
        return face_visible
        
    except Exception as exc:
        LOGGER.warning("Face detection error (%s): %s", context, exc)
        return False

