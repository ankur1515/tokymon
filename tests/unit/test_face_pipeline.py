"""Unit tests for the face identification pipeline.

Tests are structured to run in CI without camera hardware or real ONNX models.
All tests that require a real model file check availability first and skip
gracefully if the model is a stub / not present.

Coverage
--------
1.  YuNetDetector       — detect(), face_present(), fallback behaviour
2.  MobileFaceNetRecognizer — align(), embed(), is_available()
3.  FaceGallery         — add(), search(), remove(), save/load roundtrip
4.  TemporalFusion      — window vote, min_votes threshold, reset
5.  BboxTracker         — track ID assignment, IoU matching, track retirement
6.  FaceIdentifier      — pipeline wiring, enrol, identify, gallery persistence
7.  face_detector       — public face_present() API backward compatibility
8.  model_manager       — check_model(), ensure_models()
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import onnxruntime  # noqa: F401
    ORT_AVAILABLE = True
except ImportError:
    ORT_AVAILABLE = False

try:
    import faiss  # noqa: F401
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# Paths
_VISION_DIR = Path(__file__).parent.parent.parent / "vision"
_MODEL_DIR = _VISION_DIR / "models"
_YUNET_PATH = _MODEL_DIR / "face_detection_yunet_2023mar.onnx"
_MFN_PATH = _MODEL_DIR / "mobilefacenet.onnx"
_YUNET_REAL = _YUNET_PATH.exists() and _YUNET_PATH.stat().st_size > 300_000
_MFN_REAL = _MFN_PATH.exists() and _MFN_PATH.stat().st_size > 3_000_000

requires_numpy = pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
requires_cv2 = pytest.mark.skipif(not CV2_AVAILABLE, reason="opencv not installed")
requires_ort = pytest.mark.skipif(not ORT_AVAILABLE, reason="onnxruntime not installed")
requires_real_yunet = pytest.mark.skipif(not _YUNET_REAL, reason="Real YuNet model not downloaded")
requires_real_mfn = pytest.mark.skipif(not _MFN_REAL, reason="Real MobileFaceNet model not downloaded")


def _blank_frame(h=480, w=640) -> Any:
    """Return a black BGR frame."""
    if NUMPY_AVAILABLE:
        return np.zeros((h, w, 3), dtype=np.uint8)
    return None


def _random_embedding(dim=128) -> Any:
    """Return a random L2-normalised embedding."""
    if not NUMPY_AVAILABLE:
        return None
    v = np.random.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def _face_frame(h=480, w=640) -> Any:
    """Return a frame with a simple bright rectangle simulating a face region."""
    if not NUMPY_AVAILABLE:
        return None
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    # A bright rectangle in the centre — won't fool a real detector, but
    # used for geometry / alignment tests
    cx, cy = w // 2, h // 2
    frame[cy - 60:cy + 60, cx - 50:cx + 50] = 200
    return frame


# ── 1. YuNet Detector ─────────────────────────────────────────────────────────

class TestYuNetDetector:

    def test_import_succeeds(self):
        from vision import yunet_detector  # noqa: F401

    @requires_numpy
    @requires_cv2
    def test_detect_empty_frame_returns_empty(self):
        from vision.yunet_detector import detect
        assert detect(None) == []
        assert detect(_blank_frame()) == []

    @requires_numpy
    @requires_cv2
    def test_face_present_returns_bool(self):
        from vision.yunet_detector import face_present
        result = face_present(_blank_frame())
        assert isinstance(result, bool)

    @requires_numpy
    @requires_cv2
    def test_face_present_none_frame(self):
        from unittest.mock import patch
        import vision.yunet_detector as yd
        with patch.object(yd, "USE_SIM", False):
            assert yd.face_present(None) is False

    @requires_numpy
    @requires_cv2
    def test_detect_returns_list(self):
        from vision.yunet_detector import detect
        result = detect(_blank_frame())
        assert isinstance(result, list)

    @requires_numpy
    @requires_cv2
    def test_detect_result_has_required_keys(self):
        from vision.yunet_detector import detect
        # Create a frame with detectable content (may or may not trigger)
        frame = _blank_frame()
        results = detect(frame)
        for r in results:
            assert "bbox" in r
            assert "landmarks" in r
            assert "confidence" in r
            assert len(r["bbox"]) == 4
            assert r["landmarks"].shape == (5, 2)

    def test_is_available_returns_bool(self):
        from vision.yunet_detector import is_available
        assert isinstance(is_available(), bool)

    @requires_real_yunet
    @requires_numpy
    @requires_cv2
    def test_yunet_is_active_when_model_present(self):
        from vision.yunet_detector import is_yunet
        assert is_yunet() is True


# ── 2. MobileFaceNet Recognizer ───────────────────────────────────────────────

class TestMobileFaceNetRecognizer:

    def test_import_succeeds(self):
        from vision.face_recognizer import MobileFaceNetRecognizer  # noqa

    @requires_numpy
    @requires_cv2
    def test_align_returns_112x112(self):
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        frame = _blank_frame()
        # Provide five synthetic landmarks
        lm = np.float32([
            [280, 180], [360, 180], [320, 230], [290, 280], [350, 280]
        ])
        aligned = rec.align(frame, lm)
        if aligned is not None:   # only if cv2 is available
            assert aligned.shape == (112, 112, 3)

    @requires_numpy
    @requires_cv2
    def test_align_none_returns_none(self):
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        assert rec.align(None, None) is None

    def test_is_available_returns_bool(self):
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        assert isinstance(rec.is_available(), bool)

    @requires_numpy
    @requires_cv2
    @requires_ort
    def test_embed_on_stub_model(self):
        """Stub model returns zeros; just test shape + type."""
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        if not rec.is_available():
            pytest.skip("MobileFaceNet model (even stub) not loadable")
        aligned = np.zeros((112, 112, 3), dtype=np.uint8)
        emb = rec.embed(aligned)
        # Stub returns zeros → norm == 0 → embed returns zero vector (safe)
        if emb is not None:
            assert emb.shape == (128,)
            assert emb.dtype == np.float32

    @requires_real_mfn
    @requires_numpy
    @requires_cv2
    @requires_ort
    def test_embed_is_l2_normalised(self):
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        aligned = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        emb = rec.embed(aligned)
        assert emb is not None
        norm = float(np.linalg.norm(emb))
        assert abs(norm - 1.0) < 1e-5, f"Embedding not L2-normalised: norm={norm}"

    @requires_real_mfn
    @requires_numpy
    @requires_cv2
    @requires_ort
    def test_same_frame_yields_similar_embeddings(self):
        from vision.face_recognizer import MobileFaceNetRecognizer
        rec = MobileFaceNetRecognizer()
        aligned = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        e1 = rec.embed(aligned)
        e2 = rec.embed(aligned.copy())
        assert e1 is not None and e2 is not None
        sim = float(np.dot(e1, e2))
        assert sim > 0.99, f"Same frame produced divergent embeddings: sim={sim}"


# ── 3. Face Gallery ───────────────────────────────────────────────────────────

class TestFaceGallery:

    def test_import_succeeds(self):
        from vision.face_gallery import FaceGallery  # noqa

    @requires_numpy
    def test_empty_gallery_returns_unknown(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery()
        name, score = g.search(_random_embedding())
        assert name == "unknown"
        assert score == 0.0

    @requires_numpy
    def test_add_and_search_known_identity(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery(threshold=0.0)   # always match above threshold
        emb = _random_embedding()
        g.add("alice", emb)
        name, score = g.search(emb)
        assert name == "alice"
        assert score > 0.99   # cosine of identical vectors ≈ 1.0

    @requires_numpy
    def test_threshold_blocks_low_similarity(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery(threshold=0.99)  # very strict
        g.add("bob", _random_embedding())
        # An unrelated random embedding will have low similarity
        name, score = g.search(_random_embedding())
        assert name == "unknown"

    @requires_numpy
    def test_multiple_identities_nearest_wins(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery(threshold=0.0)
        alice = _random_embedding()
        bob = _random_embedding()
        g.add("alice", alice)
        g.add("bob", bob)
        # Query alice's own embedding
        name, _ = g.search(alice)
        assert name == "alice"
        name, _ = g.search(bob)
        assert name == "bob"

    @requires_numpy
    def test_remove_identity(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery(threshold=0.0)
        emb = _random_embedding()
        g.add("carol", emb)
        assert g.size == 1
        removed = g.remove("carol")
        assert removed == 1
        assert g.size == 0
        name, _ = g.search(emb)
        assert name == "unknown"

    @requires_numpy
    def test_known_names_sorted(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery()
        g.add("zebra", _random_embedding())
        g.add("alpha", _random_embedding())
        assert g.known_names == ["alpha", "zebra"]

    @requires_numpy
    def test_save_and_load_roundtrip(self):
        from vision.face_gallery import FaceGallery
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "gallery"
            g1 = FaceGallery(threshold=0.0)
            emb = _random_embedding()
            g1.add("dave", emb)
            g1.save(base)

            g2 = FaceGallery(threshold=0.0)
            ok = g2.load(base)
            assert ok is True
            assert g2.size == 1
            name, score = g2.search(emb)
            assert name == "dave"
            assert score > 0.99

    @requires_numpy
    def test_load_missing_file_returns_false(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery()
        assert g.load(Path("/nonexistent/path/gallery")) is False

    @requires_numpy
    def test_size_property(self):
        from vision.face_gallery import FaceGallery
        g = FaceGallery()
        assert g.size == 0
        g.add("eve", _random_embedding())
        assert g.size == 1
        g.add("eve", _random_embedding())   # second sample same person
        assert g.size == 2

    def test_repr(self):
        from vision.face_gallery import FaceGallery
        r = repr(FaceGallery())
        assert "FaceGallery" in r


# ── 4. Temporal Fusion ────────────────────────────────────────────────────────

class TestTemporalFusion:

    def test_import_succeeds(self):
        from vision.temporal_fusion import TemporalFusion  # noqa

    def test_insufficient_votes_returns_confirming(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        # Push 3 votes (< min_votes=4)
        for _ in range(3):
            result = tf.update(0, "alice")
        assert result == "confirming..."

    def test_sufficient_votes_returns_winner(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        for _ in range(4):
            tf.update(0, "alice")
        result = tf.update(0, "alice")
        assert result == "alice"

    def test_majority_vote_over_noise(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        votes = ["alice", "alice", "alice", "unknown", "alice", "unknown", "alice"]
        for v in votes:
            result = tf.update(0, v)
        # alice has 5/7 votes → should win
        assert result == "alice"

    def test_window_is_rolling(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=3, min_votes=2)
        # Fill window with "alice"
        for _ in range(3):
            tf.update(0, "alice")
        # Now push 3 "bob" — alice falls out of window
        for _ in range(3):
            result = tf.update(0, "bob")
        assert result == "bob"

    def test_reset_clears_buffer(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        for _ in range(5):
            tf.update(0, "alice")
        tf.reset(0)
        assert tf.buffer_for(0) == []
        result = tf.update(0, "alice")
        assert result == "confirming..."

    def test_reset_all(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        tf.update(1, "alice")
        tf.update(2, "bob")
        tf.reset_all()
        assert tf.active_tracks == []

    def test_independent_tracks(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion(window=7, min_votes=4)
        for _ in range(5):
            tf.update(10, "alice")
        for _ in range(5):
            tf.update(20, "bob")
        assert tf.update(10, "alice") == "alice"
        assert tf.update(20, "bob") == "bob"

    def test_invalid_window_raises(self):
        from vision.temporal_fusion import TemporalFusion
        with pytest.raises(ValueError):
            TemporalFusion(window=0)

    def test_invalid_min_votes_raises(self):
        from vision.temporal_fusion import TemporalFusion
        with pytest.raises(ValueError):
            TemporalFusion(window=5, min_votes=6)

    def test_buffer_for_returns_list(self):
        from vision.temporal_fusion import TemporalFusion
        tf = TemporalFusion()
        tf.update(1, "alice")
        buf = tf.buffer_for(1)
        assert isinstance(buf, list)
        assert "alice" in buf

    def test_repr(self):
        from vision.temporal_fusion import TemporalFusion
        r = repr(TemporalFusion(window=5, min_votes=3))
        assert "TemporalFusion" in r
        assert "window=5" in r


# ── 5. BboxTracker ────────────────────────────────────────────────────────────

class TestBboxTracker:

    def test_import_succeeds(self):
        from vision.temporal_fusion import BboxTracker  # noqa

    def test_empty_update_returns_empty(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker()
        assert t.update([]) == []

    def test_new_bbox_gets_new_id(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker()
        ids = t.update([(100, 100, 80, 80)])
        assert len(ids) == 1
        assert isinstance(ids[0], int)

    def test_same_bbox_keeps_same_id(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker()
        ids1 = t.update([(100, 100, 80, 80)])
        ids2 = t.update([(100, 100, 80, 80)])   # same bbox
        assert ids1[0] == ids2[0]

    def test_two_distinct_bboxes_get_different_ids(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker()
        ids = t.update([(100, 100, 80, 80), (400, 300, 80, 80)])
        assert len(set(ids)) == 2

    def test_track_retired_after_max_lost(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker(max_lost=2)
        t.update([(100, 100, 80, 80)])
        # Let it go missing for max_lost+1 frames
        for _ in range(3):
            t.update([])
        assert t.active_count == 0

    def test_id_monotonically_increases(self):
        from vision.temporal_fusion import BboxTracker
        t = BboxTracker()
        all_ids = []
        for i in range(5):
            ids = t.update([(i * 200, 100, 80, 80)])
            all_ids.extend(ids)
        assert all_ids == sorted(all_ids)


# ── 6. FaceIdentifier ─────────────────────────────────────────────────────────

class TestFaceIdentifier:

    def test_import_succeeds(self):
        from vision.face_identifier import FaceIdentifier  # noqa

    def test_instantiation(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        assert fi is not None

    def test_is_ready_returns_bool(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        assert isinstance(fi.is_ready, bool)

    @requires_numpy
    def test_identify_none_returns_empty(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        assert fi.identify(None) == []

    @requires_numpy
    def test_identify_blank_frame_returns_empty(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        results = fi.identify(_blank_frame())
        assert isinstance(results, list)

    @requires_numpy
    def test_enrol_without_face_returns_false(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        ok = fi.enrol("ghost", _blank_frame())
        assert ok is False

    @requires_numpy
    def test_enrol_from_embedding_adds_to_gallery(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        emb = _random_embedding()
        fi.enrol_from_embedding("frank", emb)
        assert fi.gallery.size == 1
        assert "frank" in fi.gallery.known_names

    @requires_numpy
    def test_gallery_save_and_load(self):
        from vision.face_identifier import FaceIdentifier
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "gallery"
            fi1 = FaceIdentifier(gallery_path=base)
            fi1.enrol_from_embedding("grace", _random_embedding())
            fi1.save_gallery()

            fi2 = FaceIdentifier(gallery_path=base)
            ok = fi2.load_gallery()
            assert ok is True
            assert "grace" in fi2.gallery.known_names

    @requires_numpy
    def test_reset_temporal_clears_state(self):
        from vision.face_identifier import FaceIdentifier
        fi = FaceIdentifier()
        fi.reset_temporal()   # should not raise

    def test_repr(self):
        from vision.face_identifier import FaceIdentifier
        r = repr(FaceIdentifier())
        assert "FaceIdentifier" in r


# ── 7. face_detector backward compatibility ───────────────────────────────────

class TestFaceDetectorBackwardCompat:
    """Ensure the original face_present() API is fully preserved."""

    def test_import_face_present(self):
        from vision.face_detector import face_present  # noqa: F401

    def test_face_present_accepts_none(self):
        from vision.face_detector import face_present
        result = face_present(None)
        assert isinstance(result, bool)

    @requires_numpy
    @requires_cv2
    def test_face_present_accepts_blank_frame(self):
        from vision.face_detector import face_present
        result = face_present(_blank_frame())
        assert isinstance(result, bool)

    @requires_numpy
    @requires_cv2
    def test_face_present_accepts_context_kwarg(self):
        from vision.face_detector import face_present
        # Verify the function signature still accepts context=
        result = face_present(_blank_frame(), context="test_suite")
        assert isinstance(result, bool)

    @requires_numpy
    @requires_cv2
    def test_face_present_returns_false_on_blank(self):
        from unittest.mock import patch
        import vision.face_detector as fd
        import vision.yunet_detector as yd
        # Patch USE_SIM=False in both modules so real detection runs
        with patch.object(fd, "USE_SIM", False), patch.object(yd, "USE_SIM", False):
            result = fd.face_present(_blank_frame())
        assert result is False

    @requires_numpy
    @requires_cv2
    def test_face_present_empty_array_is_false(self):
        from unittest.mock import patch
        import vision.face_detector as fd
        import vision.yunet_detector as yd
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        with patch.object(fd, "USE_SIM", False), patch.object(yd, "USE_SIM", False):
            result = fd.face_present(empty)
        assert result is False


# ── 8. Model Manager ──────────────────────────────────────────────────────────

class TestModelManager:

    def test_import_succeeds(self):
        from vision.model_manager import check_model, ensure_models  # noqa: F401

    def test_check_model_returns_dict(self):
        from vision.model_manager import check_model, MODELS
        for name in MODELS:
            result = check_model(name)
            assert isinstance(result, dict)
            assert "valid" in result
            assert "exists" in result
            assert "size" in result

    def test_ensure_models_returns_bool(self):
        from vision.model_manager import ensure_models
        result = ensure_models()
        assert isinstance(result, bool)

    def test_model_dir_exists(self):
        from vision.model_manager import _MODEL_DIR
        assert _MODEL_DIR.exists()

    def test_models_dict_has_required_keys(self):
        from vision.model_manager import MODELS
        for name, spec in MODELS.items():
            assert "min_size_bytes" in spec
            assert "urls" in spec
            assert "install_hint" in spec


# ── 9. IoU helper ─────────────────────────────────────────────────────────────

class TestIoU:

    def test_identical_boxes_iou_is_1(self):
        from vision.temporal_fusion import _iou
        assert abs(_iou((10, 10, 50, 50), (10, 10, 50, 50)) - 1.0) < 1e-6

    def test_non_overlapping_boxes_iou_is_0(self):
        from vision.temporal_fusion import _iou
        assert _iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0

    def test_partial_overlap(self):
        from vision.temporal_fusion import _iou
        iou = _iou((0, 0, 10, 10), (5, 0, 10, 10))
        assert 0.0 < iou < 1.0

    def test_contained_box(self):
        from vision.temporal_fusion import _iou
        # Small box fully inside large box
        iou = _iou((0, 0, 100, 100), (25, 25, 50, 50))
        expected = (50 * 50) / (100 * 100)   # intersection / union
        assert abs(iou - expected) < 1e-4
