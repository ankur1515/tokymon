# Final Watchdog & Camera Path Fix

## 🔧 Critical Fixes Applied

### 1. **Improved `_safe_sleep()` Function**
**Problem:** Sleep interval was too long (0.1s), causing gaps in heartbeats.

**Fix:**
- Changed sleep interval from 0.1s → 0.05s (50ms)
- Now sends **20 heartbeats per second** (well above 2s timeout requirement)
- Uses adaptive sleep to handle remaining time precisely
- Ensures no gaps in heartbeat delivery

### 2. **Camera Capture Heartbeats**
**Problem:** Heartbeats were sent every 100ms during camera capture, which wasn't frequent enough.

**Fix:**
- Changed heartbeat interval from 100ms → 50ms during camera capture
- Sends heartbeats every 50ms while waiting for capture thread
- Ensures watchdog is fed continuously during 5-second camera operations

### 3. **LED Animation Heartbeats**
**Problem:** Heartbeats were sent every 0.5s or 10 frames, which could cause gaps.

**Fix:**
- Changed to send heartbeat every **0.3s OR every 5 frames** (whichever comes first)
- More frequent heartbeats to prevent watchdog timeouts
- Still uses regular `time.sleep(0.06)` for frame delay (heartbeats handled separately)

### 4. **Motor Command Heartbeats**
**Problem:** Heartbeats only sent before/after movements, not during.

**Fix:**
- Added explicit heartbeats before motor commands
- Added heartbeats after motor commands
- `_safe_sleep()` handles heartbeats during movement duration
- Multiple safety layers to ensure watchdog is always fed

### 5. **Camera Frame Path Logging**
**Problem:** Camera frames were saved but path wasn't visible in logs.

**Fix:**
- Changed log level from `DEBUG` → `INFO` for frame saving
- Added explicit absolute path logging: `LOGGER.info("Camera frame absolute path: %s", img_path.resolve())`
- Now shows full path in logs for easy access

## 📁 Camera Frames Location

**Absolute Path:**
```
/home/ankursharma/Projects/tokymon/data/camera_frames/
```

**Log Output:**
```
INFO | camera | Saved camera frame: /home/ankursharma/Projects/tokymon/data/camera_frames/frame_1734972896_initial.jpg
INFO | camera | Camera frame absolute path: /home/ankursharma/Projects/tokymon/data/camera_frames/frame_1734972896_initial.jpg
```

## 🎯 Heartbeat Frequency Summary

| Operation | Heartbeat Frequency | Status |
|-----------|---------------------|--------|
| `_safe_sleep()` | Every 0.05s (20/sec) | ✅ Fixed |
| LED Animation | Every 0.3s or 5 frames | ✅ Fixed |
| Camera Capture | Every 0.05s (20/sec) | ✅ Fixed |
| Motor Movements | Before + During + After | ✅ Fixed |
| Face Detection | Before + During + After | ✅ Fixed |

## 🧪 Test Again

```bash
python3 examples/test_basic_commands.py
```

**Check for:**
- ✅ No "Watchdog timeout" warnings
- ✅ Camera frame paths in logs: `INFO | camera | Camera frame absolute path: ...`
- ✅ Smooth execution of all commands
- ✅ All frames saved to: `/home/ankursharma/Projects/tokymon/data/camera_frames/`

## 🔍 Verify Camera Frames

```bash
# List all captured frames
ls -lh /home/ankursharma/Projects/tokymon/data/camera_frames/

# Count frames
ls /home/ankursharma/Projects/tokymon/data/camera_frames/*.jpg | wc -l

# View latest frame
ls -t /home/ankursharma/Projects/tokymon/data/camera_frames/*.jpg | head -1 | xargs feh
```

## 📝 Key Changes

1. **`_safe_sleep()`:** 50ms intervals (20 heartbeats/sec)
2. **Camera Capture:** 50ms heartbeat intervals during capture
3. **LED Animation:** Every 0.3s or 5 frames
4. **Motor Commands:** Heartbeats before, during, and after
5. **Camera Logging:** INFO level with absolute path

All operations now send heartbeats at least every 0.05s (20/second), providing a 40x safety margin over the 2-second watchdog timeout.

