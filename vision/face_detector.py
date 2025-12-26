"""Face detection using OpenCV Haar Cascade."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # type: ignore

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("face_detector")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Haar Cascade model path
_MODEL_PATH = Path(__file__).parent.parent / "vision" / "models" / "haarcascade_frontalface_default.xml"
_FALLBACK_MODEL_PATH = Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")

# Global detector instance (loaded once)
_DETECTOR: Optional[object] = None  # cv2.CascadeClassifier when available


def _load_detector() -> Optional[object]:  # cv2.CascadeClassifier when available
    """Load Haar Cascade detector (loads once, reuses)."""
    global _DETECTOR
    
    if _DETECTOR is not None:
        return _DETECTOR
    
    if not CV2_AVAILABLE:
        LOGGER.warning("OpenCV (cv2) not installed. Face detection disabled.")
        LOGGER.warning("Install with: sudo apt-get install python3-opencv")
        return None
    
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
            if cv2 is not None and hasattr(cv2, 'data'):
                model_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
                if not model_path.exists():
                    model_path = None
                else:
                    pass  # model_path is set
            else:
                model_path = None
        except Exception:
            model_path = None
    
    if model_path is None:
        LOGGER.warning("Haar Cascade model not found. Face detection disabled.")
        LOGGER.warning("Download from: https://github.com/opencv/opencv/blob/master/data/haarcascades/haarcascade_frontalface_default.xml")
        return None
    
    try:
        if cv2 is None:
            return None
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


def face_present(frame: Optional[object], context: str = "unknown") -> bool:  # np.ndarray when available
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
    
    if not CV2_AVAILABLE or cv2 is None:
        LOGGER.warning("OpenCV not available - face detection disabled")
        return False
    
    if not NUMPY_AVAILABLE or np is None:
        LOGGER.warning("NumPy not available - face detection disabled")
        return False
    
    if frame is None:
        LOGGER.debug("Face detection: empty frame")
        return False
    
    try:
        # Check if frame has size attribute (numpy array)
        if hasattr(frame, 'size') and frame.size == 0:
            LOGGER.debug("Face detection: empty frame")
            return False
    except Exception:
        pass
    
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
        
        # Detect faces with balanced parameters (more sensitive than before, but still validated)
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,  # More sensitive than 1.2 - better detection of faces
            minNeighbors=5,   # Reduced from 8 - less strict, more sensitive
            minSize=(40, 40),  # Reduced from 50x50 - can detect smaller faces
            maxSize=(400, 400),  # Increased from 300x300 - can detect larger faces
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Additional validation: filter faces by aspect ratio and size (more lenient)
        # Real faces typically have aspect ratio around 0.7-1.0 (width/height)
        valid_faces = []
        for (x, y, w, h) in faces:
            aspect_ratio = w / h if h > 0 else 0
            face_area = w * h
            image_area = gray.shape[0] * gray.shape[1]
            area_ratio = face_area / image_area if image_area > 0 else 0
            
            # Validate: reasonable aspect ratio (0.5-1.5) and reasonable size (0.3%-20% of image)
            # More lenient than before to catch more real faces
            if 0.5 <= aspect_ratio <= 1.5 and 0.003 <= area_ratio <= 0.20:
                valid_faces.append((x, y, w, h))
            else:
                LOGGER.debug(
                    "Face detection (%s): filtered invalid detection - aspect=%.2f, area_ratio=%.3f",
                    context, aspect_ratio, area_ratio
                )
        
        # Binary result: face present or not (only count validated faces)
        face_visible = len(valid_faces) > 0
        
        if face_visible:
            LOGGER.info(
                "Face detection (%s): True (found %d valid faces out of %d detections)",
                context, len(valid_faces), len(faces)
            )
        else:
            LOGGER.debug(
                "Face detection (%s): False (found %d detections, %d valid)",
                context, len(faces), len(valid_faces)
            )
        
        return face_visible
        
    except Exception as exc:
        LOGGER.warning("Face detection error (%s): %s", context, exc)
        return False

