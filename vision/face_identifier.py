"""Full face identification pipeline.

Combines YuNet detector → MobileFaceNet embeddings → FAISS gallery search →
temporal fusion into a single, easy-to-use class.

Pipeline (per frame)
--------------------
    1. YuNet detects faces + 5-point landmarks (pose-robust)
    2. MobileFaceNet aligns + embeds each face (128-d, L2-normalised)
    3. FAISS gallery finds nearest known identity by cosine similarity
    4. BboxTracker assigns stable track IDs across frames
    5. TemporalFusion smooths per-frame predictions (kills jitter)

Public API
----------
FaceIdentifier
    .identify(frame)     -> list[IdentificationResult]
    .enrol(name, frame)  -> bool
    .save_gallery()
    .load_gallery()
    .is_ready            -> bool   (True when all models loaded)

IdentificationResult (dataclass)
    .name        str    — identity label or "unknown" / "confirming..."
    .score       float  — cosine similarity 0–1
    .bbox        tuple  — (x, y, w, h) in pixels
    .track_id    int    — stable cross-frame ID
    .confirmed   bool   — False while temporal buffer is still filling

Usage
-----
    from vision.face_identifier import FaceIdentifier
    from vision.camera import capture_frame_np

    fi = FaceIdentifier()
    fi.load_gallery()

    frame = capture_frame_np()
    results = fi.identify(frame)
    for r in results:
        print(r.name, r.score, r.confirmed)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Any

from system.logger import get_logger
from system.config import CONFIG
from vision.yunet_detector import detect as _detect, face_present
from vision.face_recognizer import MobileFaceNetRecognizer
from vision.face_gallery import FaceGallery
from vision.temporal_fusion import TemporalFusion, BboxTracker

LOGGER = get_logger("face_identifier")

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)

_DEFAULT_GALLERY_PATH = Path(__file__).parent.parent / "data" / "face_gallery"
_CONFIRMING = "confirming..."


@dataclass
class IdentificationResult:
    """Result for a single detected face in a frame."""
    name: str          # identity label ("unknown" / "confirming..." / enrolled name)
    score: float       # cosine similarity [0, 1]; 0 when unrecognised
    bbox: tuple        # (x, y, w, h) in pixels
    track_id: int      # stable cross-frame track ID
    confirmed: bool    # True once temporal buffer has sufficient votes
    landmarks: Any = field(default=None, repr=False)  # (5,2) float32 or None


class FaceIdentifier:
    """End-to-end face identification pipeline.

    Args:
        gallery_path:  Base path for :class:`FaceGallery` persistence.
        sim_threshold: Cosine similarity threshold for gallery search.
        fusion_window: Temporal fusion rolling window size (frames).
        fusion_min_votes: Minimum votes to confirm an identity.
    """

    def __init__(
        self,
        gallery_path: Optional[Path] = None,
        sim_threshold: float = 0.40,
        fusion_window: int = 7,
        fusion_min_votes: int = 4,
    ) -> None:
        self._gallery_path = Path(gallery_path) if gallery_path else _DEFAULT_GALLERY_PATH
        self._recognizer = MobileFaceNetRecognizer()
        self._gallery = FaceGallery(threshold=sim_threshold)
        self._fusion = TemporalFusion(window=fusion_window, min_votes=fusion_min_votes)
        self._tracker = BboxTracker()

        if USE_SIM:
            LOGGER.info("FaceIdentifier: simulator mode active")
        else:
            rec_ok = self._recognizer.is_available()
            LOGGER.info(
                "FaceIdentifier ready: recognizer=%s, gallery_size=%d",
                "✓" if rec_ok else "✗ (model missing)",
                self._gallery.size,
            )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True when detector + recognizer are both loaded."""
        if USE_SIM:
            return True
        return self._recognizer.is_available()

    @property
    def gallery(self) -> FaceGallery:
        """Direct access to the identity gallery."""
        return self._gallery

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def identify(self, frame: Any) -> List[IdentificationResult]:
        """Run the full pipeline on a single BGR frame.

        Args:
            frame: numpy BGR array (H, W, 3) from :func:`vision.camera.capture_frame_np`.

        Returns:
            One :class:`IdentificationResult` per detected face (may be empty).
        """
        if USE_SIM:
            return []  # simulator: no real frames

        if frame is None:
            return []

        # Step 1: detect faces + landmarks
        faces = _detect(frame, context="identify")
        if not faces:
            return []

        # Step 2: assign stable track IDs
        bboxes = [f["bbox"] for f in faces]
        track_ids = self._tracker.update(bboxes)

        results: List[IdentificationResult] = []

        for face, tid in zip(faces, track_ids):
            name = "unknown"
            score = 0.0
            confirmed = False

            # Step 3: embed + search gallery (only if recognizer available)
            if self._recognizer.is_available():
                emb = self._recognizer.embed_from_frame(frame, face["landmarks"])
                if emb is not None:
                    name, score = self._gallery.search(emb)

            # Step 4: temporal fusion
            stable = self._fusion.update(tid, name)
            confirmed = stable not in (_CONFIRMING, "unknown")
            display_name = stable

            results.append(IdentificationResult(
                name=display_name,
                score=score,
                bbox=face["bbox"],
                track_id=tid,
                confirmed=confirmed,
                landmarks=face.get("landmarks"),
            ))

        return results

    # ── Enrolment ─────────────────────────────────────────────────────────────

    def enrol(self, name: str, frame: Any) -> bool:
        """Enrol a new identity from a single frame.

        Detects the largest face in *frame*, computes its embedding, and adds
        it to the gallery.  No model retraining required.

        Args:
            name:  Display name / ID for the identity.
            frame: BGR numpy array containing the person's face.

        Returns:
            True if enrolment succeeded.
        """
        if not self._recognizer.is_available():
            LOGGER.warning("enrol: recognizer not available")
            return False

        faces = _detect(frame, context="enrol")
        if not faces:
            LOGGER.warning("enrol '%s': no face detected in frame", name)
            return False

        # Use the largest face (highest confidence)
        best = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
        emb = self._recognizer.embed_from_frame(frame, best["landmarks"])
        if emb is None:
            LOGGER.warning("enrol '%s': embedding failed", name)
            return False

        self._gallery.add(name, emb)
        LOGGER.info("enrol: '%s' enrolled (gallery size=%d)", name, self._gallery.size)
        return True

    def enrol_from_embedding(self, name: str, embedding: Any) -> None:
        """Enrol a pre-computed embedding directly (useful for batch enrolment)."""
        self._gallery.add(name, embedding)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_gallery(self, path: Optional[Path] = None) -> None:
        """Persist the gallery to disk."""
        self._gallery.save(path or self._gallery_path)

    def load_gallery(self, path: Optional[Path] = None) -> bool:
        """Load a previously saved gallery from disk.

        Returns:
            True if gallery loaded successfully.
        """
        return self._gallery.load(path or self._gallery_path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def reset_temporal(self) -> None:
        """Clear all temporal fusion buffers (e.g., scene change)."""
        self._fusion.reset_all()
        self._tracker = BboxTracker()

    def __repr__(self) -> str:
        return (
            f"FaceIdentifier("
            f"ready={self.is_ready}, "
            f"gallery_size={self._gallery.size}, "
            f"active_tracks={self._tracker.active_count})"
        )
