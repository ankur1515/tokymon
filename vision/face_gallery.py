"""Face identity gallery — fast cosine-similarity search over 128-d embeddings.

Uses FAISS (CPU) when available for sub-millisecond search across thousands of
identities.  Falls back to a numpy linear scan when FAISS is not installed —
the API is identical in both cases.

Public API
----------
FaceGallery
    .add(name, embedding)        — enrol a new identity (zero-shot, no retrain)
    .search(embedding, threshold) -> (name, score)
    .remove(name)                — revoke an identity at runtime
    .save(path)                  — persist gallery to disk
    .load(path)                  — reload gallery from disk
    .known_names -> list[str]
    .size        -> int

Gallery file format
-------------------
    <path>.npz — numpy archive:  "embeddings" (N,128), "names" (N,)
    <path>.faiss — FAISS index   (written only when FAISS available)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple, List

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None  # type: ignore

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None  # type: ignore

from system.logger import get_logger

LOGGER = get_logger("face_gallery")

_DEFAULT_GALLERY = Path(__file__).parent.parent / "data" / "face_gallery"
EMBEDDING_DIM = 128
DEFAULT_THRESHOLD = 0.40   # cosine similarity; tuned per environment


class FaceGallery:
    """Identity gallery with FAISS-backed cosine search (numpy fallback).

    Args:
        dim:       Embedding dimension (128 for MobileFaceNet).
        threshold: Default cosine-similarity threshold for :meth:`search`.
    """

    def __init__(
        self,
        dim: int = EMBEDDING_DIM,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._dim = dim
        self._threshold = threshold
        self._names: List[str] = []
        self._embeddings: Optional[any] = None   # np.ndarray (N, dim)

        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(dim)   # inner product = cosine on L2-norm
            LOGGER.info("FaceGallery: using FAISS backend (fast, scalable)")
        else:
            self._index = None
            LOGGER.info("FaceGallery: using numpy backend (FAISS not installed)")

    # ── Enrolment ─────────────────────────────────────────────────────────────

    def add(self, name: str, embedding: any) -> None:
        """Enrol a new identity (or add another sample for an existing one).

        Args:
            name:      Display name / ID string.
            embedding: 128-d L2-normalised float32 numpy array.
        """
        if not NUMPY_AVAILABLE or embedding is None:
            LOGGER.warning("add: numpy unavailable or embedding is None")
            return

        vec = np.array(embedding, dtype=np.float32).flatten()
        if vec.shape[0] != self._dim:
            LOGGER.error(
                "add: embedding dim %d != expected %d", vec.shape[0], self._dim
            )
            return

        # Ensure L2-normalised
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm

        self._names.append(name)
        if self._embeddings is None:
            self._embeddings = vec[np.newaxis]
        else:
            self._embeddings = np.vstack([self._embeddings, vec[np.newaxis]])

        if FAISS_AVAILABLE and self._index is not None:
            v = vec[np.newaxis].copy()
            faiss.normalize_L2(v)
            self._index.add(v)

        LOGGER.debug("add: enrolled '%s' (gallery size=%d)", name, len(self._names))

    def remove(self, name: str) -> int:
        """Remove all embeddings for *name*.

        Returns:
            Number of entries removed.
        """
        if not NUMPY_AVAILABLE:
            return 0

        indices = [i for i, n in enumerate(self._names) if n == name]
        if not indices:
            return 0

        mask = np.ones(len(self._names), dtype=bool)
        for i in indices:
            mask[i] = False

        self._names = [n for n, keep in zip(self._names, mask) if keep]
        if self._embeddings is not None:
            self._embeddings = self._embeddings[mask]
            if self._embeddings.shape[0] == 0:
                self._embeddings = None

        # Rebuild FAISS index (IndexFlatIP has no remove)
        if FAISS_AVAILABLE and self._index is not None:
            self._index.reset()
            if self._embeddings is not None:
                v = self._embeddings.copy()
                faiss.normalize_L2(v)
                self._index.add(v)

        LOGGER.debug("remove: '%s' (%d entries removed)", name, len(indices))
        return len(indices)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        embedding: any,
        threshold: Optional[float] = None,
    ) -> Tuple[str, float]:
        """Find the closest identity by cosine similarity.

        Args:
            embedding: 128-d float32 query embedding.
            threshold: Override instance-level threshold.

        Returns:
            ``(name, score)`` where score ∈ [0, 1].
            Returns ``("unknown", 0.0)`` when gallery is empty or score < threshold.
        """
        if not NUMPY_AVAILABLE or embedding is None:
            return "unknown", 0.0
        if not self._names:
            return "unknown", 0.0

        thr = threshold if threshold is not None else self._threshold
        vec = np.array(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm

        if FAISS_AVAILABLE and self._index is not None and self._index.ntotal > 0:
            return self._search_faiss(vec, thr)
        return self._search_numpy(vec, thr)

    def _search_faiss(self, vec: any, thr: float) -> Tuple[str, float]:
        q = vec[np.newaxis].copy()
        faiss.normalize_L2(q)
        D, I = self._index.search(q, k=1)
        score = float(D[0][0])
        idx = int(I[0][0])
        if score < thr or idx < 0 or idx >= len(self._names):
            return "unknown", score
        return self._names[idx], score

    def _search_numpy(self, vec: any, thr: float) -> Tuple[str, float]:
        # Cosine similarity = dot product for L2-normalised vectors
        scores = self._embeddings @ vec   # shape (N,)
        idx = int(np.argmax(scores))
        score = float(scores[idx])
        if score < thr:
            return "unknown", score
        return self._names[idx], score

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: Optional[Path] = None) -> None:
        """Save gallery embeddings and names to disk.

        Args:
            path: Base path (without extension).  Defaults to
                  ``data/face_gallery``.
        """
        if not NUMPY_AVAILABLE:
            return

        base = Path(path) if path else _DEFAULT_GALLERY
        base.parent.mkdir(parents=True, exist_ok=True)

        names_arr = np.array(self._names, dtype=object)
        emb_arr = self._embeddings if self._embeddings is not None else np.zeros((0, self._dim), dtype=np.float32)
        np.savez(str(base) + ".npz", embeddings=emb_arr, names=names_arr)

        if FAISS_AVAILABLE and self._index is not None:
            faiss.write_index(self._index, str(base) + ".faiss")

        LOGGER.info("Gallery saved to %s.npz (%d identities)", base, len(self._names))

    def load(self, path: Optional[Path] = None) -> bool:
        """Load gallery from disk.

        Args:
            path: Base path used in :meth:`save`.

        Returns:
            True if loaded successfully, False if file not found.
        """
        if not NUMPY_AVAILABLE:
            return False

        base = Path(path) if path else _DEFAULT_GALLERY
        npz_path = Path(str(base) + ".npz")

        if not npz_path.exists():
            LOGGER.debug("Gallery file not found: %s", npz_path)
            return False

        try:
            data = np.load(str(npz_path), allow_pickle=True)
            self._embeddings = data["embeddings"].astype(np.float32)
            self._names = list(data["names"])

            if self._embeddings.shape[0] == 0:
                self._embeddings = None

            # Rebuild FAISS index
            if FAISS_AVAILABLE and self._index is not None:
                self._index.reset()
                if self._embeddings is not None:
                    v = self._embeddings.copy()
                    faiss.normalize_L2(v)
                    self._index.add(v)

            LOGGER.info(
                "Gallery loaded from %s (%d identities)", npz_path, len(self._names)
            )
            return True
        except Exception as exc:
            LOGGER.error("Gallery load error: %s", exc)
            return False

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Number of enrolled embeddings (not unique identities)."""
        return len(self._names)

    @property
    def known_names(self) -> List[str]:
        """Sorted list of unique enrolled names."""
        return sorted(set(self._names))

    def __repr__(self) -> str:
        backend = "FAISS" if FAISS_AVAILABLE else "numpy"
        return f"FaceGallery(size={self.size}, backend={backend}, dim={self._dim})"
