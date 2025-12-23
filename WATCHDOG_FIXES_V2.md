# Watchdog Fixes V2 - Critical Updates

## 🔧 Critical Fixes Applied

### 1. **LED Animation - Heartbeat Every Frame**
**Problem:** LED animation was sending heartbeats every 10 frames (~0.6s), which wasn't frequent enough.

**Fix:**
- Now sends heartbeat **EVERY frame** during LED animation
- Uses `_safe_sleep(0.06, safety)` instead of `time.sleep(0.06)` for frame delays
- Ensures watchdog is fed continuously during LED operations

### 2. **Motor Movements - Continuous Heartbeats**
**Problem:** Heartbeats were only sent before/after movements, not during.

**Fix:**
- All motor movements now use `_safe_sleep()` which sends heartbeats every 0.1s
- Removed redundant heartbeat calls (handled by `_safe_sleep`)
- Ensures watchdog is fed during entire movement duration

### 3. **Camera Capture - Improved Threading**
**Problem:** Camera capture threading wasn't sending heartbeats frequently enough.

**Fix:**
- Improved `_capture_frame_with_heartbeat()` to send heartbeats every 0.1s
- Heartbeats sent continuously while waiting for capture thread
- No gaps in heartbeat delivery during 5-second camera operations

### 4. **Camera Frames - Always Save**
**Problem:** Frames were being deleted when `save_frames` was False.

**Fix:**
- **Always save camera frames** to `data/camera_frames/` for debugging
- Removed conditional deletion
- All captured images are preserved

## 📊 Heartbeat Frequency Summary

| Operation | Heartbeat Frequency | Status |
|-----------|---------------------|--------|
| `_safe_sleep()` | Every 0.1s (10/sec) | ✅ Fixed |
| LED Animation | Every frame (~16/sec) | ✅ Fixed |
| Camera Capture | Every 0.1s (10/sec) | ✅ Fixed |
| Motor Movements | Every 0.1s during sleep | ✅ Fixed |
| Face Detection | Before/during/after | ✅ Fixed |

## 🎯 Expected Results

After these fixes:
- ✅ **No watchdog timeouts** during normal operation
- ✅ **No emergency stops** during LED animation
- ✅ **No emergency stops** during motor movements
- ✅ **No emergency stops** during camera capture
- ✅ **All camera frames saved** to `data/camera_frames/`

## 🧪 Test Again

```bash
python3 examples/test_basic_commands.py
```

**Check for:**
- No "Watchdog timeout" warnings
- No "Emergency stop triggered" during normal flow
- Camera frames saved in `data/camera_frames/`
- Smooth execution of all commands

## 📁 Camera Frames Location

All captured images are now saved to:
```
data/camera_frames/frame_<timestamp>_<context>.jpg
```

Example:
- `data/camera_frames/frame_1734972896_initial.jpg`
- `data/camera_frames/frame_1734972898_retry.jpg`
- `data/camera_frames/frame_1734972900_after_backward.jpg`

## 🔍 Key Changes

1. **LED Animation:** Heartbeat every frame + use `_safe_sleep()` for delays
2. **Motor Commands:** Use `_safe_sleep()` for all movement durations
3. **Camera Capture:** Continuous heartbeats every 0.1s during capture
4. **Camera Frames:** Always save, never delete

All operations now send heartbeats at least every 0.1s, well within the 2-second watchdog timeout.

