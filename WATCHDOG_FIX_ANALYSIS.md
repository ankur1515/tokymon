# Watchdog Timeout Analysis & Fixes

## 🔍 Problem Analysis

### Root Cause
The safety watchdog has a **2-second timeout** (`safe_stop_timeout_s: 2.0`), but several operations were blocking for longer without sending heartbeats:

1. **Camera Capture** - `rpicam-still` can take up to **5 seconds** (timeout=5s), blocking the main thread
2. **LED Animation** - Long duration animations (2+ seconds) weren't sending heartbeats frequently enough
3. **`_safe_sleep()`** - Was checking every 250ms, which is borderline for a 2s timeout

### Evidence from Logs
```
18:30:31,133 | WARNING | safety | Watchdog timeout, stopping motors
18:30:33,234 | WARNING | safety | Watchdog timeout, stopping motors
18:30:35,335 | WARNING | safety | Watchdog timeout, stopping motors
```
Watchdog timeouts occurred during:
- Camera capture (initial face detection)
- Reposition movements (backward, forward, rotate)
- LED animation during greeting command

## ✅ Fixes Applied

### 1. Camera Capture with Heartbeats
**File:** `sessions/modules/basic_commands.py`

- Added `_capture_frame_with_heartbeat()` function
- Uses threading to run camera capture in background
- Sends heartbeats every 100ms while waiting for capture
- Prevents watchdog timeout during 5-second camera operations

### 2. Improved `_safe_sleep()`
**File:** `sessions/modules/basic_commands.py`

- Changed sleep interval from **250ms → 100ms**
- Now sends **10 heartbeats per second** (well above 2s timeout requirement)
- Ensures watchdog is fed every 0.1s during any sleep operation

### 3. Enhanced LED Animation
**File:** `sessions/modules/basic_commands.py`

- Sends heartbeat every 10 frames (~0.6s)
- Also sends heartbeat if duration > 1s
- Fallback: Uses `_safe_sleep()` if LED fails

### 4. Face Detection Heartbeats
**File:** `sessions/modules/basic_commands.py`

- Heartbeat before camera capture
- Heartbeats during capture (via `_capture_frame_with_heartbeat`)
- Heartbeat after capture
- Heartbeat after face detection

## 📊 Expected Behavior After Fix

| Operation | Before | After |
|-----------|--------|-------|
| Camera capture (5s) | ❌ Timeout | ✅ Heartbeats every 100ms |
| `_safe_sleep(2.0)` | ⚠️ 8 heartbeats | ✅ 20 heartbeats |
| LED animation (2s) | ⚠️ ~33 heartbeats | ✅ ~40+ heartbeats |
| Reposition sequence | ❌ Timeouts | ✅ Continuous heartbeats |

## 🧪 Testing Steps

1. **Run the test again:**
   ```bash
   python3 examples/test_basic_commands.py
   ```

2. **Expected results:**
   - ✅ No watchdog timeout warnings
   - ✅ No emergency stops during normal operation
   - ✅ Face detection completes successfully
   - ✅ Reposition sequence runs without interruption
   - ✅ Commands execute smoothly

3. **Monitor logs for:**
   - No "Watchdog timeout" warnings
   - No "Emergency stop triggered" during normal flow
   - Successful face detection
   - Smooth command execution

## 🔧 Configuration Check

Verify watchdog timeout in `configs/services.yaml`:
```yaml
runtime:
  safe_stop_timeout_s: 2.0  # 2 seconds timeout
```

With the fixes:
- Heartbeats sent every **100ms** (10 per second)
- Well within the 2-second safety margin
- No blocking operations without heartbeats

## 📝 Next Steps

1. **Test on Pi:**
   ```bash
   python3 examples/test_basic_commands.py
   ```

2. **If still seeing timeouts:**
   - Check if `safety.heartbeat()` is being called in all long operations
   - Verify SafetyManager is properly initialized
   - Check for any other blocking operations

3. **If working correctly:**
   - Proceed with full session testing
   - Test with multiple modules
   - Verify iPhone UI is accessible

## 🎯 Success Criteria

✅ **No watchdog timeouts** during normal operation  
✅ **Face detection** completes successfully  
✅ **Reposition sequence** runs without interruption  
✅ **Commands** execute smoothly  
✅ **Emergency stops** only on actual errors, not timeouts  

