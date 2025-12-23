#!/usr/bin/env bash
# Quick script to run Session Orchestrator on Mac

cd "/Users/ankursharma/Documents/Dev Projects/tokymon"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    # Activate existing venv
    source venv/bin/activate
fi

# Set dev environment (enables simulator)
export TOKY_ENV=dev

# Run Session Orchestrator
python3 main_session.py

