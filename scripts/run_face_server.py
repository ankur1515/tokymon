#!/usr/bin/env python3
"""Standalone always-on Tokymon face server.

Run this once at boot (via systemd tokymon-face.service).  It:

  1. Starts the HTTP face server on port 8080  (ui_server.py, unchanged)
  2. Runs a background file-watcher thread that polls
     /tmp/tokymon/face_state.json every 50 ms and updates the server's
     in-process _ui_state dict when the mode changes.  The SSE endpoint in
     ui_server.py then pushes the change to the browser within ~10 ms.

Session scripts (basic_commands, future modules, etc.) update the face by
writing to /tmp/tokymon/face_state.json via sessions.modules.face_state.
This server picks up those writes and reflects them on the touchscreen
without any coupling between the session process and this process.

Usage
-----
  # Development (manual):
  TOKY_ENV=dev PYTHONPATH=. python3 scripts/run_face_server.py

  # Production (via systemd):
  systemctl start tokymon-face
"""
from __future__ import annotations

import os
import signal
import sys
import threading
import time

# Ensure project root is on the path when run directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sessions.modules import face_state
from sessions.modules.ui_server import start_ui_server, stop_ui_server
import sessions.modules.ui_server as _ui_srv

PORT = int(os.environ.get("TOKYMON_FACE_PORT", "8080"))
POLL_INTERVAL = 0.05   # 50 ms — face change reaches browser in ≤ 60 ms total


def _file_watcher() -> None:
    """Background thread: poll state file, update ui_server's in-process dict.

    ui_server.py's SSE loop already watches _ui_state every 10 ms and pushes
    on change — so all we need to do here is keep that dict in sync with the
    file written by session scripts.
    """
    last_mode: str = "waiting"

    while _running:
        try:
            mode = face_state.read()
            if mode != last_mode:
                with _ui_srv._ui_lock:
                    _ui_srv._ui_state["face_mode"] = mode
                    _ui_srv._ui_state["last_update"] = time.time()
                last_mode = mode
        except Exception:
            pass   # Log nothing — tight loop, errors are transient
        time.sleep(POLL_INTERVAL)


def main() -> None:
    global _running

    # ── Initialise state file to waiting ──────────────────────────────────────
    face_state.reset()

    # ── Start HTTP face server ────────────────────────────────────────────────
    start_ui_server(port=PORT)
    print(f"[tokymon-face] Face server running on http://0.0.0.0:{PORT}")
    print(f"[tokymon-face] State file: {face_state.STATE_FILE}")
    print("[tokymon-face] Press Ctrl+C to stop")

    # ── Start file-watcher thread ─────────────────────────────────────────────
    _running = True
    watcher = threading.Thread(target=_file_watcher, daemon=True, name="face-watcher")
    watcher.start()

    # ── Signal handlers for clean shutdown ────────────────────────────────────
    def _handle_signal(signum, _frame):
        print(f"\n[tokymon-face] Signal {signum} received, shutting down…")
        _shutdown()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # ── Keep main thread alive ────────────────────────────────────────────────
    try:
        while _running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()


def _shutdown() -> None:
    global _running
    _running = False
    face_state.reset()   # Return to waiting face on server stop
    stop_ui_server()
    print("[tokymon-face] Stopped.")
    sys.exit(0)


_running: bool = False

if __name__ == "__main__":
    main()
