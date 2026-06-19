"""MobileFaceNet face recognizer — 128-d L2-normalized embeddings via ONNX.

Produces a semantic embedding for any aligned 112×112 face crop.  Two photos
of the same person produce embeddings with cosine similarity > 0.4 regardless
of lighting or minor pose change.

Requirements
------------
    pip install onnxruntime        # CPU-only; no GPU needed

Public API
----------
MobileFaceNetRecognizer
    .align(frame, landmarks) -> np.ndarray   # 112×112 BGR crop
    .embed(aligned_face)     -> np.ndarray   # 128-d L2-normalised vector
    .is_available()          -> bool

Typical usage
-------------
    rec = MobileFaceNetRecognizer()
    if rec.is_available():
        aligned = rec.align(frame, face["landmarks"])
        embedding = rec.embed(aligned)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # type: ignore

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None  # type: ignore

try:
    import onnxruntime as ort
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False
    ort = None  # type: ignore

from system.logger import get_logger

LOGGER = get_logger("face_recognizer")

# Model path
_MODEL_DIR = Path(__file__).parent / "models"
_MODEL_PATH = _MODEL_DIR / "mobilefacenet.onnx"

# ArcFace standard reference landmarks for 112×112 canonical alignment
_REF_LANDMARKS = None  # lazy-initialised when numpy available

# Embedding dimension
EMBEDDING_DIM = 128


def _ref_landmarks() -> Any:
    """ArcFace 112×112 reference 5-point landmarks."""
    global _REF_LANDMARKS
    if _REF_LANDMARKS is None and NUMPY_AVAILABLE:
        _REF_LANDMARKS = np.float32([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ])
    return _REF_LANDMARKS


class MobileFaceNetRecognizer:
    """MobileFaceNet ONNX recognizer (CPU).

    Instantiate once and reuse — the ONNX session is created at init time.

    Args:
        model_path: Path to mobilefacenet.onnx.  Defaults to
                    ``vision/models/mobilefacenet.onnx``.
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self._session: Optional[Any] = None
        self._input_name: str = "data"

        path = Path(model_path) if model_path else _MODEL_PATH

        if not ORT_AVAILABLE:
            LOGGER.warning(
                "onnxruntime not installed — face recognition disabled. "
                "Install with: pip install onnxruntime"
            )
            return

        if not NUMPY_AVAILABLE or not CV2_AVAILABLE:
            LOGGER.warning("numpy/cv2 not available — face recognition disabled.")
            return

        if not path.exists() or path.stat().st_size < 512:
            LOGGER.warning(
                "MobileFaceNet model not found at %s — recognition disabled. "
                "Download from insightface model zoo or run: "
                "python3 vision/model_manager.py download",
                path,
            )
            return

        try:
            sess_opts = ort.SessionOptions()
            sess_opts.inter_op_num_threads = 2
            sess_opts.intra_op_num_threads = 2
            sess_opts.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            self._session = ort.InferenceSession(
                str(path),
                sess_options=sess_opts,
                providers=["CPUExecutionProvider"],
            )
            # Detect input name from model metadata
            self._input_name = self._session.get_inputs()[0].name
            LOGGER.info("MobileFaceNet loaded from: %s", path)
        except Exception as exc:
            LOGGER.error("Failed to load MobileFaceNet: %s", exc)
            self._session = None

    # ── Public helpers ────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """True if the ONNX session loaded successfully."""
        return self._session is not None

    def align(
        self,
        frame: Any,
        landmarks: Any,
    ) -> Optional[Any]:
        """Affine-warp face to canonical 112×112 ArcFace pose.

        Args:
            frame:     BGR numpy array (any size).
            landmarks: (5, 2) float32 array — five facial keypoints
                       [left-eye, right-eye, nose, left-mouth, right-mouth].

        Returns:
            112×112 BGR numpy array, or None on error.
        """
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            return None
        if frame is None or landmarks is None:
            return None

        try:
            src = np.float32(landmarks).reshape(5, 2)
            dst = _ref_landmarks()
            if dst is None:
                return None
            M, _ = cv2.estimateAffinePartial2D(src, dst)
            if M is None:
                return None
            aligned = cv2.warpAffine(frame, M, (112, 112))
            return aligned
        except Exception as exc:
            LOGGER.warning("align error: %s", exc)
            return None

    def embed(self, aligned_face: Any) -> Optional[Any]:
        """Compute 128-d L2-normalised embedding for an aligned face crop.

        Args:
            aligned_face: 112×112 BGR numpy array (from :meth:`align`).

        Returns:
            1-D float32 numpy array of length 128, L2-normalised, or None.
        """
        if self._session is None or not NUMPY_AVAILABLE:
            return None
        if aligned_face is None:
            return None

        try:
            # Normalise to [-1, 1] and convert to NCHW
            blob = (aligned_face.astype(np.float32) - 127.5) / 127.5
            blob = blob.transpose(2, 0, 1)[np.newaxis]   # (1, 3, 112, 112)

            result = self._session.run(None, {self._input_name: blob})
            emb = result[0][0].astype(np.float32)

            # L2 normalise — ensures cosine similarity == dot product
            norm = np.linalg.norm(emb)
            if norm > 1e-6:
                emb = emb / norm
            return emb

        except Exception as exc:
            LOGGER.warning("embed error: %s", exc)
            return None

    def embed_from_frame(
        self,
        frame: Any,
        landmarks: Any,
    ) -> Optional[Any]:
        """Convenience: align then embed in one call.

        Returns:
            128-d embedding or None.
        """
        aligned = self.align(frame, landmarks)
        if aligned is None:
            return None
        return self.embed(aligned)
