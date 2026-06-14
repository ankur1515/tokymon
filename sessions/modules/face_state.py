"""Shared face state file — cross-process IPC between session scripts and the
standalone face server.

State file location: /tmp/tokymon/face_state.json
  - /tmp is always writable, no root required, cleaned on reboot (fine for
    runtime state).
  - Written atomically via os.replace() so the face server never reads a
    partial write.

Public API
----------
write(mode)   — session scripts call this to change the displayed expression
read()        — face server calls this to get the current expression
reset()       — convenience: write("waiting")
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Optional

STATE_DIR = "/tmp/tokymon"
STATE_FILE = os.path.join(STATE_DIR, "face_state.json")

VALID_MODES = frozenset(
    ["waiting", "normal_smile", "greeting", "speaking", "moving", "stop"]
)


def _ensure_dir() -> None:
    """Create the state directory if it does not exist."""
    os.makedirs(STATE_DIR, exist_ok=True)


def write(mode: str) -> None:
    """Atomically write face_mode to the state file.

    Uses write-to-temp + os.replace() so the reader never sees a partial
    file.  Silently ignores unknown modes (logs a warning instead of raising
    so a bad mode can never crash a session).

    Args:
        mode: One of the six valid face_mode strings.
    """
    if mode not in VALID_MODES:
        # Don't crash the session — just fall back to waiting
        mode = "waiting"

    _ensure_dir()
    payload = json.dumps({"face_mode": mode, "ts": time.time()})

    # Atomic write: temp file in same directory → os.replace (rename) is atomic
    # on Linux (same filesystem, same /tmp partition).
    fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, STATE_FILE)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def read() -> str:
    """Read the current face_mode from the state file.

    Returns:
        face_mode string, or "waiting" if the file is missing / unreadable.
    """
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        mode = data.get("face_mode", "waiting")
        return mode if mode in VALID_MODES else "waiting"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "waiting"


def reset() -> None:
    """Reset the face to the calm waiting/idle state."""
    write("waiting")
