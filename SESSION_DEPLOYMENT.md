# Session Orchestrator Deployment Guide

This guide explains how to run the Session Orchestrator on the Raspberry Pi.

## Quick Start

### Option 1: Run Manually (Testing)

```bash
# SSH into Raspberry Pi
ssh pi@raspberrypi.local

# Navigate to project directory
cd /home/ankursharma/Projects/tokymon

# Activate virtual environment
source venv/bin/activate

# Run session orchestrator
python3 main_session.py
```

### Option 2: Run as Systemd Service (Production)

```bash
# SSH into Raspberry Pi
ssh pi@raspberrypi.local
cd /home/ankursharma/Projects/tokymon

# Make script executable
chmod +x scripts/run_session.sh

# Install systemd service
sudo cp scripts/tokymon_session.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tokymon_session.service
sudo systemctl start tokymon_session.service

# Check status
sudo systemctl status tokymon_session.service

# View logs
tail -f /var/log/tokymon/tokymon_session.log
```

## Configuration

### Module Selection

Edit `configs/services.yaml` to configure which modules run:

```yaml
sessions:
  max_modules_per_session: 3
  # Uncomment to select specific modules:
  # selected_modules: ["object_identification", "environment_orientation", "emotion_affect"]
```

If `selected_modules` is not set, the orchestrator will use the first `max_modules_per_session` modules in the registry.

### Available Modules (in execution order)

1. `object_identification` - Object Identification
2. `environment_orientation` - Environment Orientation
3. `emotion_affect` - Emotion & Affect Recognition
4. `body_movement` - Body Movement & Gesture Imitation
5. `joint_attention` - Joint Attention & Engagement
6. `obstacle_course` - Obstacle Course & Motor Planning
7. `academic_foundation` - Academic Foundation
8. `sensory_response` - Sensory Response Observation
9. `parent_collaboration` - Parent & Therapist Collaboration
10. `basic_commands` - Basic Commands & Robot Interaction

## Service Management

### Start Service
```bash
sudo systemctl start tokymon_session.service
```

### Stop Service
```bash
sudo systemctl stop tokymon_session.service
```

### Restart Service
```bash
sudo systemctl restart tokymon_session.service
```

### View Logs
```bash
# Real-time log viewing
tail -f /var/log/tokymon/tokymon_session.log

# Last 100 lines
tail -n 100 /var/log/tokymon/tokymon_session.log

# Search for errors
grep -i error /var/log/tokymon/tokymon_session.log
```

### Check Service Status
```bash
sudo systemctl status tokymon_session.service
```

## Emergency Stop

The Session Orchestrator supports emergency stop from any state:

1. **Via Systemd**: `sudo systemctl stop tokymon_session.service`
2. **Via Signal**: Send SIGTERM or SIGINT to the process
3. **Via SafetyManager**: If integrated with hardware safety systems

## MQTT Integration

The orchestrator publishes session events to MQTT:

- `session/start` - When session starts (contains session_id)
- `session/state` - Periodic state updates
- `session/end` - When session ends (contains session_id)
- `session/results` - Final session results (JSON)

Subscribe to these topics to monitor sessions remotely.

## Development/Testing

### Test on Mac (Simulator Mode)

```bash
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
export TOKY_ENV=dev  # Enables simulator mode
source venv/bin/activate
python3 main_session.py
```

### Test Individual Modules

```bash
python3 examples/session_example.py
```

## Troubleshooting

### Service Won't Start

1. Check logs: `sudo journalctl -u tokymon_session.service -n 50`
2. Verify virtual environment exists: `ls -la venv/bin/activate`
3. Check Python path: `which python3`
4. Verify permissions: `ls -la scripts/run_session.sh`

### Module Execution Errors

1. Check module logs in `/var/log/tokymon/tokymon_session.log`
2. Verify all modules are properly initialized
3. Check hardware connections (if not in simulator mode)

### Emergency Stop Not Working

1. Verify SafetyManager is properly initialized
2. Check that motors are connected and responding
3. Review safety timeout settings in `configs/services.yaml`

## Logging

All session execution is logged with:
- `session_id` - Unique session identifier
- `module_name` - Name of module executed
- `start_time` - Module start timestamp
- `end_time` - Module end timestamp
- `completed` - Whether module completed successfully
- `child_engagement` - Binary engagement signal
- `duration_seconds` - Module execution duration

Logs are written to `/var/log/tokymon/tokymon_session.log` when running as a service.

## Next Steps

1. **Customize Modules**: Implement actual logic in each module's `run()` method
2. **Add Audio Prompts**: Integrate pre-recorded MP3 files for child-facing audio
3. **Vision Integration**: Connect vision models for observation-only signals
4. **Parent Interface**: Build UI for parent/therapist to select modules and view results

