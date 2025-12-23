# Face Detection Tuning - Reducing False Positives

## 🔧 Changes Applied

### Problem
Face detector was producing false positives (detecting faces when none present), particularly on images with people in non-frontal poses or complex backgrounds.

### Solution
Made face detection **stricter** by:

1. **Increased `scaleFactor`**: 1.1 → 1.2
   - Less aggressive scaling = fewer false positives
   - Slightly slower but more accurate

2. **Increased `minNeighbors`**: 5 → 8
   - Requires more neighbor detections to confirm a face
   - Much stricter validation

3. **Increased `minSize`**: (30, 30) → (50, 50)
   - Filters out very small detections (likely noise)
   - Real faces are typically larger

4. **Added `maxSize`**: (300, 300)
   - Filters out very large detections (likely false positives)
   - Prevents detection of entire bodies as faces

5. **Added Aspect Ratio Validation**: 0.6 - 1.2
   - Real faces have width/height ratio around 0.7-1.0
   - Filters out elongated or square false positives

6. **Added Area Ratio Validation**: 0.5% - 15% of image
   - Faces should be a reasonable size relative to the image
   - Too small = noise, too large = likely not a face

## 📊 Detection Parameters

| Parameter | Old Value | New Value | Reason |
|-----------|-----------|-----------|--------|
| `scaleFactor` | 1.1 | 1.2 | Less aggressive = fewer false positives |
| `minNeighbors` | 5 | 8 | Stricter validation |
| `minSize` | (30, 30) | (50, 50) | Filter small noise |
| `maxSize` | None | (300, 300) | Filter large false positives |
| Aspect Ratio | None | 0.6-1.2 | Validate face proportions |
| Area Ratio | None | 0.5%-15% | Validate face size |

## 🎯 Expected Behavior

**Before:**
- False positives on non-face objects
- Detections on people's backs/sides
- Detections on complex backgrounds

**After:**
- Only detects actual frontal faces
- Filters out invalid detections
- More conservative (may miss some faces, but more accurate)

## 📝 Logging

The detector now logs:
- **INFO level**: When valid faces are detected (with count)
- **DEBUG level**: When detections are filtered out (with reason)
- **DEBUG level**: When no faces found

Example logs:
```
INFO | face_detector | Face detection (initial): True (found 1 valid faces out of 2 detections)
DEBUG | face_detector | Face detection (after_backward): filtered invalid detection - aspect=1.5, area_ratio=0.002
DEBUG | face_detector | Face detection (after_backward): False (found 1 detections, 0 valid)
```

## 🧪 Testing

Test with the problematic image:
```bash
python3 examples/test_basic_commands.py
```

Check logs for:
- Face detection results
- Filtered detections (if any)
- Validation reasons

## 🔍 Manual Verification

To verify detection on a specific image:
```python
import cv2
from vision import camera, face_detector

frame = camera.capture_frame_np(context="test")
result = face_detector.face_present(frame, context="manual_test")
print(f"Face detected: {result}")
```

## ⚠️ Trade-offs

**Pros:**
- ✅ Much fewer false positives
- ✅ More accurate detection
- ✅ Better validation

**Cons:**
- ⚠️ May miss some faces (more conservative)
- ⚠️ Slightly slower (more validation)
- ⚠️ Requires frontal face orientation

For POC use case (autism support robot), **accuracy over recall** is preferred - we'd rather miss a face than incorrectly detect one.

