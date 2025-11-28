"""Deterministic sensor outputs for tests and dev."""
from __future__ import annotations

import itertools

_FAKE_DISTANCES_CM = [30.0, 45.0, 50.0]
DISTANCE_SEQ = itertools.cycle(_FAKE_DISTANCES_CM)


def read_distance_cm() -> float:
    return next(DISTANCE_SEQ)


def read_ir(channel: str) -> bool:
    return channel == "left"
