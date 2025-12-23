# Installing OpenCV on Raspberry Pi

## Quick Install

```bash
# Update package list
sudo apt-get update

# Install OpenCV for Python 3
sudo apt-get install python3-opencv

# Verify installation
python3 -c "import cv2; print(cv2.__version__)"
```

## Alternative: Install via pip (if apt version is outdated)

```bash
# Install dependencies
sudo apt-get install python3-pip python3-dev libopencv-dev python3-numpy

# Install OpenCV via pip
pip3 install opencv-python

# Verify
python3 -c "import cv2; print(cv2.__version__)"
```

## Download Haar Cascade Model

After installing OpenCV, download the face detection model:

```bash
cd /home/ankursharma/Projects/tokymon/vision/models
wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml
```

Or copy from system path (if OpenCV is installed):

```bash
# Check if model exists in system path
ls /usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml

# If it exists, copy it
cp /usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml vision/models/
```

## Verify Installation

```bash
# Test OpenCV import
python3 -c "import cv2; print('OpenCV version:', cv2.__version__)"

# Test numpy import
python3 -c "import numpy; print('NumPy version:', numpy.__version__)"

# Test PIL import
python3 -c "from PIL import Image; print('PIL available')"
```

## Troubleshooting

### If `cv2` import fails:
- Make sure you installed `python3-opencv` (not just `opencv`)
- Try: `sudo apt-get install --reinstall python3-opencv`

### If model file not found:
- The code will auto-detect from multiple paths
- Or manually download to `vision/models/haarcascade_frontalface_default.xml`

### If still having issues:
- Check Python version: `python3 --version` (should be 3.7+)
- Check pip: `pip3 --version`
- Try virtual environment: `python3 -m venv venv && source venv/bin/activate`

## Note

The code now handles missing OpenCV gracefully - it will log warnings but won't crash. However, face detection will be disabled until OpenCV is installed.

