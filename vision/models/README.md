# Face Detection Models

## Phase 1 — YuNet Detector (pose-robust, replaces Haar Cascade)

**File:** `face_detection_yunet_2023mar.onnx` (337 KB)

Handles ±90° yaw, ±30° pitch. Returns 5-point landmarks per face.

**Download (on Raspberry Pi):**
```bash
cd vision/models
wget "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
```

If network is blocked, use `python3 vision/model_manager.py download`.

---

## Phase 2 — MobileFaceNet Recognizer (128-d embeddings)

**File:** `mobilefacenet.onnx` (~4 MB)

Zero-shot identity enrolment. No retraining required to add new people.

**Download (on Raspberry Pi):**
```bash
pip install insightface
python3 -c "
import insightface
m = insightface.app.FaceAnalysis(name='buffalo_s')
m.prepare(ctx_id=-1)
"
# Then copy the model:
cp ~/.insightface/models/buffalo_s/w600k_mbf.onnx vision/models/mobilefacenet.onnx
```

**Alternative direct download:**
```bash
wget https://github.com/foamliu/MobileFaceNet/releases/download/v1.0/mobilefacenet.onnx \
     -O vision/models/mobilefacenet.onnx
```

---

## Verify All Models

```bash
python3 vision/model_manager.py status    # check what's present
python3 vision/model_manager.py download  # auto-download missing
python3 vision/model_manager.py verify    # load-test via ONNX Runtime
```

---

## Fallback Behaviour

| YuNet model | MobileFaceNet model | Behaviour |
|---|---|---|
| ✓ present | ✓ present | Full pipeline: detection + recognition + gallery |
| ✗ missing | ✓ present | Falls back to Haar Cascade detection only |
| ✓ present | ✗ missing | YuNet detection only; face_present() works, enrol/identify disabled |
| ✗ missing | ✗ missing | Haar Cascade only; face_present() works (original behaviour) |

The existing `face_present()` API always works regardless of which models are present.

---

## Legacy Haar Cascade

**File:** `haarcascade_frontalface_default.xml`

Still used as automatic fallback when YuNet model is absent. Download:
```bash
# Option 1: auto-detected from system OpenCV
sudo apt-get install python3-opencv

# Option 2: manual download
wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml
```
