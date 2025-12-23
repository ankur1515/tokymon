# Testing basic_commands Module on Mac

## Quick Test

### Option 1: Use the Test Script (Easiest)

```bash
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
./test_basic_commands.sh
```

### Option 2: Manual Run

```bash
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
source venv/bin/activate
export TOKY_ENV=dev  # Enables simulator mode
export PYTHONPATH=.  # Important: set Python path
python3 examples/test_basic_commands.py
```

### Step 2: Open iPhone UI in Browser

While the script is running, open your browser and go to:

```
http://localhost:8080
```

You should see:
- A simple face animation (eyes, nose, mouth)
- Face updates as robot demonstrates commands
- Face states: greeting → moving → normal

### Step 3: Watch the Console

You'll see logs like:
```
INFO | Module start: basic_commands
INFO | iPhone UI server started on port 8080
INFO | Demonstrating commands: ['greeting', 'forward', 'turn_left']
INFO | Face visible (initial): True
INFO | Command demonstrated: greeting
INFO | Command demonstrated: forward
INFO | Command demonstrated: turn_left
INFO | Module end: basic_commands
```

## What to Expect

### In Simulator Mode:
- ✅ Motor commands are logged (not executed)
- ✅ Face detection returns random True/False (for testing)
- ✅ LED matrix shows simulator messages
- ✅ iPhone UI server runs and serves face animation
- ✅ All safety checks pass

### Commands Demonstrated:
- **Greeting**: No movement, just face animation
- **Forward**: Slow forward movement (5-10cm)
- **Backward**: Slow backward movement (5-10cm)
- **Turn Left**: 10-15 degree rotation
- **Turn Right**: 10-15 degree rotation
- **Stop**: Immediate brake

### Face Detection:
- Initial check: 2 seconds
- If face not visible → ONE reposition attempt
- After each command: 2 seconds observation

## Testing iPhone UI

### Option 1: Browser on Mac
1. Run the test script
2. Open `http://localhost:8080` in any browser
3. Watch face animation update in real-time

### Option 2: iPhone 5s (Same Network)
1. Find your Mac's IP address:
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
2. On iPhone, open: `http://<your-mac-ip>:8080`
3. Face should sync with robot state

### Option 3: Test UI Server Directly

```bash
# Start UI server manually
python3 -c "
from sessions.modules.ui_server import start_ui_server
import time
start_ui_server(port=8080)
print('UI server running at http://localhost:8080')
time.sleep(60)  # Run for 60 seconds
"
```

Then open `http://localhost:8080` in browser.

## Troubleshooting

### Port 8080 Already in Use

If you get "Address already in use":
```bash
# Find what's using port 8080
lsof -i :8080

# Kill it (replace PID with actual process ID)
kill -9 <PID>
```

Or change the port in `basic_commands.py`:
```python
start_ui_server(port=8081)  # Use different port
```

### UI Not Updating

- Check browser console for errors (F12)
- Verify server is running: `curl http://localhost:8080/api/state`
- Check logs for UI server messages

### Module Crashes

- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify simulator mode: `export TOKY_ENV=dev`
- Check logs for specific error messages

## Expected Output

```
2025-12-22 22:20:00,000 | INFO | test_basic_commands | === Testing basic_commands Module ===
2025-12-22 22:20:00,100 | INFO | orchestrator | Initialized 10 modules
2025-12-22 22:20:00,100 | INFO | orchestrator | Starting session abc-123 with modules: ['basic_commands']
2025-12-22 22:20:00,100 | INFO | module.basic_commands | Module start: basic_commands
2025-12-22 22:20:00,200 | INFO | module.basic_commands | iPhone UI server started on port 8080
2025-12-22 22:20:00,200 | INFO | module.basic_commands | Demonstrating commands: ['greeting', 'forward', 'turn_left']
2025-12-22 22:20:00,200 | INFO | module.basic_commands | Face visible (initial): True
2025-12-22 22:20:00,200 | INFO | module.basic_commands | Reposition attempted: no
2025-12-22 22:20:00,200 | INFO | basic_commands | Command demonstrated: greeting
2025-12-22 22:20:02,200 | INFO | basic_commands | Command demonstrated: forward
2025-12-22 22:20:04,500 | INFO | basic_commands | Command demonstrated: turn_left
2025-12-22 22:20:06,500 | INFO | module.basic_commands | Module end: basic_commands
2025-12-22 22:20:06,600 | INFO | test_basic_commands | Session completed: session_end
```

## Next Steps

Once testing works on Mac:
1. Deploy to Raspberry Pi
2. Test with real hardware
3. Verify iPhone UI works on actual iPhone 5s
4. Test face detection with real camera

