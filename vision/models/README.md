# Face Detection Models

## Haar Cascade Model

Place the Haar Cascade model file here:

**File:** `haarcascade_frontalface_default.xml`

**Download from:**
- OpenCV GitHub: https://github.com/opencv/opencv/blob/master/data/haarcascades/haarcascade_frontalface_default.xml
- Or install OpenCV and copy from: `/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml`

**Installation on Raspberry Pi:**

```bash
# Option 1: Download directly
cd vision/models
wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml

# Option 2: Copy from system OpenCV (if installed)
cp /usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml vision/models/

# Option 3: Install OpenCV and use system path
sudo apt-get install python3-opencv
# Code will auto-detect from system path
```

The face detector will automatically find the model from:
1. `vision/models/haarcascade_frontalface_default.xml` (this directory)
2. `/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml` (system)
3. OpenCV data directory (if cv2.data available)

