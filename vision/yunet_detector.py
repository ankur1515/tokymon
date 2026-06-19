"""YuNet-based face detector — pose-robust replacement for Haar Cascade.

Handles frontal, profile, and angled faces (±90° yaw, ±30° pitch).
Falls back to Haar Cascade gracefully when the YuNet ONNX model is absent
or when OpenCV DNN is unavailable.

Public API
----------
detect(frame, input_size=None) -> list[dict]
    Returns list of face dicts:
        {
            "bbox":       (x, y, w, h),          # int pixels
            "landmarks":  np.ndarray shape (5,2), # [x,y] per landmark
            "confidence": float                   # 0.0 – 1.0
        }

face_present(frame, context="unknown") -> bool
    Binary presence check — same contract as the legacy Haar API.

is_available() -> bool
    True if YuNet model loaded successfully.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

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

LOGGER = get_logger("yunet_detector")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

# Model paths (in priority order)
_MODEL_DIR = Path(__file__).parent / "models"
_YUNET_MODEL = _MODEL_DIR / "face_detection_yunet_2023mar.onnx"

# Detection thresholds
_SCORE_THRESHOLD = 0.6
_NMS_THRESHOLD = 0.3
_TOP_K = 5

# Global detector (loaded once)
_DETECTOR: Optional[Any] = None
_DETECTOR_LOADED: bool = False
_DETECTOR_IS_YUNET: bool = False


def _load_detector() -> Optional[Any]:
    """Load YuNet detector; fall back to Haar Cascade if model absent."""
    global _DETECTOR, _DETECTOR_LOADED, _DETECTOR_IS_YUNET

    if _DETECTOR_LOADED:
        return _DETECTOR

    _DETECTOR_LOADED = True

    if not CV2_AVAILABLE or cv2 is None:
        LOGGER.warning("OpenCV not available — face detection disabled.")
        return None

    # ── Try YuNet ────────────────────────────────────────────────────────────
    if _YUNET_MODEL.exists() and _YUNET_MODEL.stat().st_size > 1024:
        try:
            det = cv2.FaceDetectorYN.create(
                model=str(_YUNET_MODEL),
                config="",
                input_size=(640, 480),
                score_threshold=_SCORE_THRESHOLD,
                nms_threshold=_NMS_THRESHOLD,
                top_k=_TOP_K,
            )
            _DETECTOR = det
            _DETECTOR_IS_YUNET = True
            LOGGER.info("YuNet detector loaded from: %s", _YUNET_MODEL)
            return _DETECTOR
        except Exception as exc:
            LOGGER.warning("YuNet load failed (%s) — falling back to Haar Cascade.", exc)

    # ── Fall back to Haar Cascade ─────────────────────────────────────────────
    LOGGER.info("YuNet model not found — using Haar Cascade detector.")
    haar_candidates = [
        _MODEL_DIR / "haarcascade_frontalface_default.xml",
        Path("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"),
    ]
    if hasattr(cv2, "data"):
        haar_candidates.append(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")

    for candidate in haar_candidates:
        if candidate.exists():
            try:
                cascade = cv2.CascadeClassifier(str(candidate))
                if not cascade.empty():
                    _DETECTOR = cascade
                    _DETECTOR_IS_YUNET = False
                    LOGGER.info("Haar Cascade loaded from: %s", candidate)
                    return _DETECTOR
            except Exception as exc:
                LOGGER.warning("Haar load error: %s", exc)

    LOGGER.warning("No face detector available.")
    return None


def is_available() -> bool:
    """Return True if a detector (YuNet or Haar) loaded successfully."""
    if USE_SIM:
        return True
    return _load_detector() is not None


def is_yunet() -> bool:
    """Return True specifically if YuNet (not Haar fallback) is active."""
    _load_detector()
    return _DETECTOR_IS_YUNET


def _detect_yunet(detector: Any, frame: Any) -> List[Dict]:
    """Run YuNet inference; return list of face dicts."""
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    if faces is None:
        return []

    results = []
    for face in faces:
        # YuNet row: [x, y, w, h, lm0x, lm0y, lm1x, lm1y, ..., lm4x, lm4y, score]
        x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        landmarks = np.array(face[4:14], dtype=np.float32).reshape(5, 2)
        confidence = float(face[14])
        results.append({
            "bbox": (x, y, fw, fh),
            "landmarks": landmarks,
            "confidence": confidence,
        })
    return results


def _detect_haar(detector: Any, frame: Any) -> List[Dict]:
    """Run Haar Cascade inference; return list of face dicts (no landmarks)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
        maxSize=(400, 400),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    results = []
    if len(faces) == 0:
        return results

    img_area = gray.shape[0] * gray.shape[1]
    for (x, y, w, h) in faces:
        ar = w / h if h > 0 else 0
        area_ratio = (w * h) / img_area if img_area > 0 else 0
        if 0.5 <= ar <= 1.5 and 0.003 <= area_ratio <= 0.20:
            # Synthesise approximate landmarks from bbox centre
            cx, cy = x + w // 2, y + h // 2
            lm = np.array([
                [cx - w * 0.15, cy - h * 0.1],
                [cx + w * 0.15, cy - h * 0.1],
                [cx,            cy],
                [cx - w * 0.12, cy + h * 0.15],
                [cx + w * 0.12, cy + h * 0.15],
            ], dtype=np.float32)
            results.append({
                "bbox": (x, y, w, h),
                "landmarks": lm,
                "confidence": 0.7,   # Haar has no real score; use fixed value
            })
    return results


def detect(
    frame: Optional[Any],
    context: str = "unknown",
) -> List[Dict]:
    """Detect faces in a BGR frame.

    Args:
        frame:   numpy BGR array (H, W, 3).
        context: label used in log messages only.

    Returns:
        List of dicts with keys: ``bbox``, ``landmarks``, ``confidence``.
        Empty list when no faces found or detector unavailable.
    """
    if USE_SIM:
        return []

    if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
        return []

    if frame is None or (hasattr(frame, "size") and frame.size == 0):
        LOGGER.debug("detect (%s): empty frame", context)
        return []

    detector = _load_detector()
    if detector is None:
        return []

    try:
        if _DETECTOR_IS_YUNET:
            faces = _detect_yunet(detector, frame)
        else:
            faces = _detect_haar(detector, frame)

        LOGGER.debug(
            "detect (%s): %d face(s) via %s",
            context, len(faces), "YuNet" if _DETECTOR_IS_YUNET else "Haar",
        )
        return faces

    except Exception as exc:
        LOGGER.warning("detect error (%s): %s", context, exc)
        return []


def face_present(
    frame: Optional[Any],
    context: str = "unknown",
) -> bool:
    """Binary face presence check — same contract as legacy Haar detector.

    Args:
        frame:   BGR numpy array or None.
        context: label for logging.

    Returns:
        True if ≥1 face detected, False otherwise.
    """
    if USE_SIM:
        import random
        return random.random() > 0.3

    return len(detect(frame, context=context)) > 0
