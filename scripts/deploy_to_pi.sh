#!/usr/bin/env bash
set -euo pipefail
TARGET="/home/ankursharma/Projects/tokymon"
rsync -avz \
  --exclude 'venv' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  ./ \
  pi@raspberrypi.local:"$TARGET"
