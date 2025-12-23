# Running Session Orchestrator on Mac

## 🚀 Quick Start

```bash
# 1. Navigate to project directory
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"

# 2. Activate virtual environment
source venv/bin/activate

# 3. Set development mode (enables simulator)
export TOKY_ENV=dev

# 4. Run Session Orchestrator
python3 main_session.py
```

## 📋 First Time Setup

If you haven't set up the environment yet:

```bash
# Navigate to project
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"

# Create virtual environment (if not exists)
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment (optional - for API keys)
cp .env .env.local  # Edit .env.local with your API keys if needed
```

## 🎯 Running Options

### Option 1: Full Session Orchestrator

```bash
export TOKY_ENV=dev
python3 main_session.py
```

This runs a complete session with modules selected from `configs/services.yaml`.

### Option 2: Example Sessions

```bash
export TOKY_ENV=dev
python3 examples/session_example.py
```

This runs example sessions (2 modules, 3 modules, emergency stop demo).

### Option 3: Interactive Testing

```bash
export TOKY_ENV=dev
python3 -i -c "
from sessions import SessionOrchestrator
from control.safety import SafetyManager

safety = SafetyManager()
safety.start()
orchestrator = SessionOrchestrator(safety_manager=safety, max_modules_per_session=2)
session_id = orchestrator.start_session(['object_identification', 'environment_orientation'])
print(f'Session started: {session_id}')

# Run manually
while orchestrator.is_session_active():
    result = orchestrator.run()
    print(f'State: {orchestrator.get_state().value}')
"
```

## ⚙️ Configuration

### Select Modules

Edit `configs/services.yaml`:

```yaml
sessions:
  max_modules_per_session: 3
  # Uncomment to select specific modules:
  # selected_modules: ["object_identification", "environment_orientation", "emotion_affect"]
```

### Simulator Mode

When `TOKY_ENV=dev` is set:
- ✅ Simulator mode is **automatically enabled**
- ✅ No hardware needed (motors, sensors simulated)
- ✅ MQTT uses mock client (logs to console)
- ✅ Safe to test without Raspberry Pi

## 📊 What You'll See

When running, you'll see:

```
2025-12-22 20:36:37,960 | INFO | main_session | Tokymon Session Orchestrator starting (simulator=True)
2025-12-22 20:36:37,960 | INFO | orchestrator | Initialized 10 modules
2025-12-22 20:36:37,960 | INFO | orchestrator | Starting session abc-123 with modules: ['object_identification', 'environment_orientation']
2025-12-22 20:36:37,960 | INFO | orchestrator | Session abc-123 started
2025-12-22 20:36:37,960 | INFO | orchestrator | Selected module: object_identification
2025-12-22 20:36:37,960 | INFO | module.object_identification | Entering object identification module
2025-12-22 20:36:37,960 | INFO | module.object_identification | Running object identification
...
```

## 🛑 Stopping

- Press `Ctrl+C` to stop gracefully
- The orchestrator will:
  - Stop current module
  - Perform safe shutdown
  - Clean up resources

## 🧪 Testing Individual Components

### Test Module Import

```bash
export TOKY_ENV=dev
python3 -c "from sessions import SessionOrchestrator; print('✓ Import successful')"
```

### Test Module Registry

```bash
export TOKY_ENV=dev
python3 -c "from sessions.modules import MODULE_REGISTRY; print(f'Found {len(MODULE_REGISTRY)} modules')"
```

### Run Unit Tests

```bash
export TOKY_ENV=dev
PYTHONPATH=. pytest tests/ -v
```

## 🔍 Debugging

### Enable Debug Logging

```bash
export TOKY_ENV=dev
export PYTHONPATH=.
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from main_session import main
main()
"
```

### Check Configuration

```bash
export TOKY_ENV=dev
python3 -c "
from system.config import CONFIG
print('Simulator mode:', CONFIG['services']['runtime']['use_simulator'])
print('Max modules:', CONFIG.get('sessions', {}).get('max_modules_per_session', 'not set'))
"
```

## 📝 Notes

- **Simulator Mode**: All hardware calls are mocked - safe to run on Mac
- **MQTT**: Uses mock client - no broker needed
- **Logs**: Output goes to console (stdout/stderr)
- **No Root Required**: Everything runs in user space

## 🆚 Mac vs Pi Differences

| Feature | Mac (dev) | Pi (prod) |
|---------|-----------|-----------|
| Simulator | ✅ Enabled | ❌ Disabled |
| Hardware | ❌ Mocked | ✅ Real |
| MQTT | Mock client | Real broker |
| Logs | Console | `/var/log/tokymon/` |
| Service | Manual run | Systemd |

## 🚨 Troubleshooting

### Import Errors

```bash
# Make sure you're in the project root
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"

# Check Python path
export PYTHONPATH=.

# Verify venv is activated
which python3  # Should show venv path
```

### Module Not Found

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### Configuration Issues

```bash
# Verify config loads
export TOKY_ENV=dev
python3 -c "from system.config import CONFIG; print(CONFIG['services']['runtime'])"
```

## 🎓 Next Steps

1. **Customize Modules**: Edit module `run()` methods in `sessions/modules/`
2. **Add Logging**: Check execution logs in console output
3. **Test Scenarios**: Use `examples/session_example.py` for different scenarios
4. **Deploy to Pi**: Once tested, deploy using `SESSION_DEPLOYMENT.md`

