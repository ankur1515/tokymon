#!/usr/bin/env bash
set -euo pipefail
DIR="/home/ankursharma/Projects/tokymon"
LOG_DIR="/var/log/tokymon"
LOG_FILE="$LOG_DIR/tokymon_session.log"
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

python3 main_session.py >> "$LOG_FILE" 2>&1

