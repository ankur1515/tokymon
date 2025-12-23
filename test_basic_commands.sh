#!/usr/bin/env bash
# Simple test script for basic_commands module

cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
source venv/bin/activate
export TOKY_ENV=dev
export PYTHONPATH=.

echo "Starting basic_commands test..."
echo "iPhone UI will be available at: http://localhost:8080"
echo "Open that URL in your browser to see the face animation"
echo ""

python3 examples/test_basic_commands.py

