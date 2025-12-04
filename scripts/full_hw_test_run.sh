#!/bin/bash
# Full hardware auto-test runner for Tokymon
# Usage: ./scripts/full_hw_test_run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load .env if it exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Run the full hardware test
# Note: Requires TOKY_ENV=prod and sudo for full GPIO/PWM/camera access
echo "Running full hardware auto-test..."
echo "Note: This test requires TOKY_ENV=prod and may need sudo for GPIO/PWM/camera access"
echo ""

PYTHONPATH=. TOKY_ENV=prod python3 examples/full_hw_test.py

