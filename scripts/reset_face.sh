#!/usr/bin/env bash
# reset_face.sh — reset Tokymon face to calm "waiting" state
# Run this any time a session script crashes and leaves the face stuck.
#
# Usage:
#   bash scripts/reset_face.sh

PYTHONPATH="${PYTHONPATH:-$(dirname "$(dirname "$(realpath "$0")")")}"
export PYTHONPATH

python3 - <<'EOF'
import sys, os
sys.path.insert(0, os.environ.get("PYTHONPATH", "."))
from sessions.modules.face_state import reset
reset()
print("[reset_face] face_mode → waiting")
EOF
