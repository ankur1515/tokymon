#!/usr/bin/env bash
set -euo pipefail
DIR="/home/ankursharma/Projects/tokymon"
LOG_DIR="/var/log/tokymon"
LOG_FILE="$LOG_DIR/hw_test.log"
mkdir -p "$LOG_DIR"

if [ -f "$DIR/.env" ]; then
  set -a
  source "$DIR/.env"
  set +a
fi
if [ -f "$DIR/.env.local" ]; then
  set -a
  source "$DIR/.env.local"
  set +a
fi

source "$DIR/venv/bin/activate"
cd "$DIR"
TOKY_ENV=prod python3 examples/hw_test.py --run-hw "$@" >> "$LOG_FILE" 2>&1
