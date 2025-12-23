# Run basic_commands on Raspberry Pi

## Quick Start

```bash
# SSH into Pi
ssh pi@raspberrypi.local

# Navigate and run
cd /home/ankursharma/Projects/tokymon
source venv/bin/activate
export TOKY_ENV=prod  # Production mode (real hardware)
export PYTHONPATH=.

# Run session with basic_commands only
python3 -c "
from sessions import SessionOrchestrator
from control.safety import SafetyManager
import time
import subprocess

safety = SafetyManager()
safety.start()
orchestrator = SessionOrchestrator(safety_manager=safety, max_modules_per_session=1)
session_id = orchestrator.start_session(['basic_commands'])
ip = subprocess.check_output(['hostname', '-I']).decode().strip().split()[0]
print(f'Session: {session_id}')
print(f'iPhone UI: http://{ip}:8080')

while orchestrator.is_session_active():
    orchestrator.run()
    time.sleep(0.1)

safety.stop()
"
```

## Or Use Test Script

```bash
cd /home/ankursharma/Projects/tokymon
source venv/bin/activate
export TOKY_ENV=prod
export PYTHONPATH=.
python3 examples/test_basic_commands.py
```

## Access iPhone UI

While running, open on iPhone 5s:
```
http://<pi-ip-address>:8080
```

Find Pi IP:
```bash
hostname -I
```

## As Systemd Service

```bash
# Edit config to select basic_commands
nano configs/services.yaml
# Set: selected_modules: ["basic_commands"]

# Start service
sudo systemctl start tokymon_session.service

# View logs
tail -f /var/log/tokymon/tokymon_session.log
```

## Stop

- Press `Ctrl+C` if running manually
- `sudo systemctl stop tokymon_session.service` if service

