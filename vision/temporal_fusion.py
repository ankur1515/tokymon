"""Temporal fusion — stabilise per-frame identity predictions.

Eliminates label jitter caused by single-frame misclassifications by keeping a
rolling window of the last N predictions per tracked entity and returning the
majority-vote winner only when it exceeds a minimum vote count.

Zero external dependencies — pure Python standard library.

Public API
----------
TemporalFusion
    .update(track_id, candidate) -> str
    .reset(track_id)
    .reset_all()
    .buffer_for(track_id)        -> list[str]

BboxTracker
    .update(bboxes)              -> list[int]   — assigns stable track IDs

Typical usage
-------------
    fusion  = TemporalFusion(window=7, min_votes=4)
    tracker = BboxTracker()

    # Per frame:
    faces = detector.detect(frame)
    track_ids = tracker.update([f["bbox"] for f in faces])
    for face, tid in zip(faces, track_ids):
        name, score = gallery.search(recognizer.embed_from_frame(frame, face["landmarks"]))
        stable_name = fusion.update(tid, name)   # "confirming..." until stable
"""
from __future__ import annotations

from collections import deque, Counter
from typing import Dict, List, Tuple, Optional

from system.logger import get_logger

LOGGER = get_logger("temporal_fusion")

_CONFIRMING = "confirming..."


class TemporalFusion:
    """Rolling-window majority-vote smoother for identity predictions.

    Args:
        window:    Number of recent frames to keep per track.
        min_votes: Minimum occurrences of the winner to emit it.
                   Before this threshold is met, returns ``"confirming..."``.
    """

    def __init__(self, window: int = 7, min_votes: int = 4) -> None:
        if window < 1:
            raise ValueError(f"window must be ≥ 1, got {window}")
        if min_votes < 1 or min_votes > window:
            raise ValueError(
                f"min_votes must be in [1, window], got {min_votes} (window={window})"
            )
        self._window = window
        self._min_votes = min_votes
        self._buffers: Dict[int, deque] = {}

    # ── Core API ──────────────────────────────────────────────────────────────

    def update(self, track_id: int, candidate: str) -> str:
        """Push a new prediction for *track_id* and return the stable label.

        Args:
            track_id:  Integer track identifier (from :class:`BboxTracker`).
            candidate: Raw identity label from the gallery (e.g. ``"alice"``
                       or ``"unknown"``).

        Returns:
            Majority-vote winner if it has ≥ ``min_votes`` in the window;
            otherwise ``"confirming..."``.
        """
        if track_id not in self._buffers:
            self._buffers[track_id] = deque(maxlen=self._window)

        buf = self._buffers[track_id]
        buf.append(candidate)

        winner, votes = Counter(buf).most_common(1)[0]
        if votes >= self._min_votes:
            LOGGER.debug(
                "fusion track=%d: '%s' (%d/%d votes)",
                track_id, winner, votes, len(buf),
            )
            return winner

        LOGGER.debug(
            "fusion track=%d: confirming... (top='%s' %d/%d votes needed %d)",
            track_id, winner, votes, len(buf), self._min_votes,
        )
        return _CONFIRMING

    def reset(self, track_id: int) -> None:
        """Clear the buffer for a single track (e.g., person left frame)."""
        self._buffers.pop(track_id, None)

    def reset_all(self) -> None:
        """Clear all buffers."""
        self._buffers.clear()

    def buffer_for(self, track_id: int) -> List[str]:
        """Return a copy of the current prediction buffer for *track_id*."""
        return list(self._buffers.get(track_id, []))

    @property
    def active_tracks(self) -> List[int]:
        """Track IDs that currently have buffered predictions."""
        return list(self._buffers.keys())

    def __repr__(self) -> str:
        return (
            f"TemporalFusion(window={self._window}, "
            f"min_votes={self._min_votes}, "
            f"tracks={len(self._buffers)})"
        )


# ── Simple centroid-IoU bbox tracker ─────────────────────────────────────────

class BboxTracker:
    """Lightweight single-class centroid tracker using IoU matching.

    Assigns a stable integer track_id to each detected face across frames.
    Tracks are retired after ``max_lost`` consecutive frames without a match.

    No external dependencies — pure Python + optional numpy (for IoU).

    Args:
        max_lost:    Frames before a track is retired.
        iou_threshold: Minimum IoU to associate a detection with a track.
    """

    def __init__(self, max_lost: int = 10, iou_threshold: float = 0.3) -> None:
        self._max_lost = max_lost
        self._iou_threshold = iou_threshold
        self._tracks: Dict[int, Dict] = {}   # id → {bbox, lost}
        self._next_id: int = 0

    def update(self, bboxes: List[Tuple[int, int, int, int]]) -> List[int]:
        """Match detections to existing tracks; create new tracks as needed.

        Args:
            bboxes: List of ``(x, y, w, h)`` tuples for the current frame.

        Returns:
            List of track IDs in the same order as *bboxes*.
        """
        # Increment lost counter for all existing tracks
        for tid in list(self._tracks):
            self._tracks[tid]["lost"] += 1

        assigned_ids: List[int] = []
        used_tracks: set = set()

        for bbox in bboxes:
            best_tid = self._best_match(bbox, used_tracks)
            if best_tid is not None:
                self._tracks[best_tid]["bbox"] = bbox
                self._tracks[best_tid]["lost"] = 0
                used_tracks.add(best_tid)
                assigned_ids.append(best_tid)
            else:
                new_id = self._next_id
                self._next_id += 1
                self._tracks[new_id] = {"bbox": bbox, "lost": 0}
                assigned_ids.append(new_id)

        # Retire lost tracks
        for tid in list(self._tracks):
            if self._tracks[tid]["lost"] > self._max_lost:
                del self._tracks[tid]

        return assigned_ids

    def _best_match(
        self,
        bbox: Tuple[int, int, int, int],
        used: set,
    ) -> Optional[int]:
        """Return the track ID with highest IoU above threshold, or None."""
        best_tid, best_iou = None, self._iou_threshold
        for tid, track in self._tracks.items():
            if tid in used:
                continue
            iou = _iou(bbox, track["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_tid = tid
        return best_tid

    @property
    def active_count(self) -> int:
        return len(self._tracks)


def _iou(
    a: Tuple[int, int, int, int],
    b: Tuple[int, int, int, int],
) -> float:
    """Compute Intersection-over-Union for two (x,y,w,h) boxes."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0

    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0
