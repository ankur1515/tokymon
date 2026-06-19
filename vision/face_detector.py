"""Face detection — public API wrapper.

Internally delegates to :mod:`vision.yunet_detector` which uses YuNet (pose-
robust, ±90° yaw) with automatic fallback to Haar Cascade when the YuNet ONNX
model is not yet present on disk.

Public API (UNCHANGED — all callers work without modification)
--------------------------------------------------------------
face_present(frame, context="unknown") -> bool
    Binary presence check: True if ≥1 face detected.

All existing call-sites continue to work identically.  The upgrade is
transparent — callers never need to import yunet_detector directly.
"""
from __future__ import annotations

from typing import Optional

from system.config import CONFIG
from system.logger import get_logger

# Import the new detector; fall back to legacy Haar path if import fails
try:
    from vision.yunet_detector import face_present as _fp
    from vision.yunet_detector import detect as _detect
    _YUNET_IMPORTED = True
except Exception:
    _YUNET_IMPORTED = False

LOGGER = get_logger("face_detector")
USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# ── Legacy Haar path (kept verbatim as fallback) ──────────────────────────────

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

from pathlib import Path

_MODEL_PATH = Path(__file__).parent.parent / "vision" / "models" / "haarcascade_frontalface_default.xml"
_FALLBACK_MODEL_PATH = Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")
_HAAR_DETECTOR: Optional[object] = None


def _load_haar() -> Optional[object]:
    """Load Haar Cascade (legacy fallback — used only when YuNet unavailable)."""
    global _HAAR_DETECTOR
    if _HAAR_DETECTOR is not None:
        return _HAAR_DETECTOR
    if not CV2_AVAILABLE or cv2 is None:
        return None

    candidates = [_MODEL_PATH, _FALLBACK_MODEL_PATH]
    if hasattr(cv2, "data"):
        candidates.append(
            Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        )
    for p in candidates:
        if p.exists():
            try:
                det = cv2.CascadeClassifier(str(p))
                if not det.empty():
                    _HAAR_DETECTOR = det
                    LOGGER.info("Haar Cascade loaded from: %s", p)
                    return _HAAR_DETECTOR
            except Exception:
                pass
    LOGGER.warning("Haar Cascade model not found. Face detection disabled.")
    return None


def _haar_face_present(frame: Optional[object], context: str) -> bool:
    """Legacy Haar Cascade face_present (exact original logic, preserved)."""
    if not CV2_AVAILABLE or cv2 is None:
        LOGGER.warning("OpenCV not available - face detection disabled")
        return False
    if not NUMPY_AVAILABLE or np is None:
        LOGGER.warning("NumPy not available - face detection disabled")
        return False
    if frame is None:
        return False
    try:
        if hasattr(frame, "size") and frame.size == 0:
            return False
    except Exception:
        pass

    detector = _load_haar()
    if detector is None:
        return False

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
            maxSize=(400, 400),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        valid_faces = []
        for (x, y, w, h) in faces:
            aspect_ratio = w / h if h > 0 else 0
            face_area = w * h
            image_area = gray.shape[0] * gray.shape[1]
            area_ratio = face_area / image_area if image_area > 0 else 0
            if 0.5 <= aspect_ratio <= 1.5 and 0.003 <= area_ratio <= 0.20:
                valid_faces.append((x, y, w, h))
            else:
                LOGGER.debug(
                    "Face detection (%s): filtered invalid detection - aspect=%.2f, area_ratio=%.3f",
                    context, aspect_ratio, area_ratio,
                )
        face_visible = len(valid_faces) > 0
        if face_visible:
            LOGGER.info(
                "Face detection (%s): True (found %d valid faces out of %d detections)",
                context, len(valid_faces), len(faces),
            )
        else:
            LOGGER.debug(
                "Face detection (%s): False (found %d detections, %d valid)",
                context, len(faces), len(valid_faces),
            )
        return face_visible
    except Exception as exc:
        LOGGER.warning("Face detection error (%s): %s", context, exc)
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def face_present(frame: Optional[object], context: str = "unknown") -> bool:  # np.ndarray when available
    """
    Detect if face is present in frame (binary only).

    Internally uses YuNet (pose-robust) when available; silently falls back to
    Haar Cascade — callers never need to change.

    Args:
        frame:   BGR image array (from capture_frame_np())
        context: Optional context string for logging

    Returns:
        bool: True if ≥1 face detected, False otherwise
    """
    if USE_SIM:
        import random
        return random.random() > 0.3

    if _YUNET_IMPORTED:
        return _fp(frame, context=context)

    # Last-resort: legacy Haar path
    return _haar_face_present(frame, context)

