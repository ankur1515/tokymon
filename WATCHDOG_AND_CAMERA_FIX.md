# Watchdog & Camera Frames Fix

## 🔧 Critical Fixes Applied

### 1. **SafetyManager Instance Sharing**
**Problem:** Module was creating its own SafetyManager instead of using the orchestrator's instance, causing heartbeat mismatches.

**Fix:**
- Added `set_safety_manager()` method to `BasicCommandsModule`
- Orchestrator now passes its SafetyManager to the module before calling `enter()`
- Module uses the same SafetyManager instance as the orchestrator
- Ensures all heartbeats go to the same watchdog

### 2. **LED Animation Heartbeat Optimization**
**Problem:** Using `_safe_sleep(0.06)` was inefficient and could cause timing issues.

**Fix:**
- Send heartbeat every 0.5s OR every 10 frames (whichever comes first)
- Use regular `time.sleep(0.06)` for frame delay (we're already heartbeating)
- Reduces overhead while ensuring watchdog is fed frequently enough

### 3. **Camera Frames Path - Absolute Path**
**Problem:** Camera frames were saved to relative path, making it hard to find.

**Fix:**
- Changed to absolute path based on project root
- Path: `<project_root>/data/camera_frames/`
- Directory is created automatically if it doesn't exist
- Logs the absolute path on startup for easy reference

## 📁 Camera Frames Location

**Absolute Path:**
```
/home/ankursharma/Projects/tokymon/data/camera_frames/
```

**Frame Naming:**
```
frame_<timestamp>_<context>.jpg
```

**Examples:**
- `frame_1734972896_initial.jpg`
- `frame_1734972898_retry.jpg`
- `frame_1734972900_after_backward.jpg`
- `frame_1734972902_after_forward.jpg`
- `frame_1734972904_after_rotate.jpg`
- `frame_1734972906_after_turn_right.jpg`
- `frame_1734972908_after_greeting.jpg`

## 🎯 Expected Results

After these fixes:
- ✅ **No watchdog timeouts** - Module uses orchestrator's SafetyManager
- ✅ **Camera frames saved** to absolute path: `<project_root>/data/camera_frames/`
- ✅ **LED animation** runs smoothly with optimized heartbeats
- ✅ **All heartbeats** go to the same SafetyManager instance

## 🧪 Test Again

```bash
python3 examples/test_basic_commands.py
```

**Check for:**
- No "Watchdog timeout" warnings
- Camera frames in: `/home/ankursharma/Projects/tokymon/data/camera_frames/`
- Log message: "Camera frames directory: /home/ankursharma/Projects/tokymon/data/camera_frames"
- Smooth execution of all commands

## 🔍 Verify Camera Frames

```bash
# List all captured frames
ls -lh /home/ankursharma/Projects/tokymon/data/camera_frames/

# View a specific frame
feh /home/ankursharma/Projects/tokymon/data/camera_frames/frame_*.jpg
```

## 📝 Key Changes

1. **Orchestrator:** Passes SafetyManager to module before `enter()`
2. **Module:** Added `set_safety_manager()` method, uses orchestrator's instance
3. **LED Animation:** Optimized heartbeat frequency (every 0.5s or 10 frames)
4. **Camera Path:** Absolute path based on project root, logged on startup

