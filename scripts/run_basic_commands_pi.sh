#!/usr/bin/env bash
# Quick script to run basic_commands on Raspberry Pi

cd /home/ankursharma/Projects/tokymon
source venv/bin/activate
export TOKY_ENV=prod
export PYTHONPATH=.

# Get Pi IP address
PI_IP=$(hostname -I | awk '{print $1}')

echo "Starting basic_commands session..."
echo "iPhone UI will be available at: http://${PI_IP}:8080"
echo ""

python3 -c "
from sessions import SessionOrchestrator
from control.safety import SafetyManager
import time

safety = SafetyManager()
safety.start()
orchestrator = SessionOrchestrator(safety_manager=safety, max_modules_per_session=1)
session_id = orchestrator.start_session(['basic_commands'])
print(f'Session started: {session_id}')

while orchestrator.is_session_active():
    orchestrator.run()
    time.sleep(0.1)

safety.stop()
print('Session completed')
"

