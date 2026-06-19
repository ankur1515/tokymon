"""Model manager — download and verify face pipeline ONNX models.

Run on first deployment to fetch the required model files:

    python3 vision/model_manager.py download       # download all models
    python3 vision/model_manager.py status         # check what's present
    python3 vision/model_manager.py verify         # check file sizes

Models required
---------------
1. face_detection_yunet_2023mar.onnx  (337 KB)
   Source: https://github.com/opencv/opencv_zoo
   Alternative: ships with some opencv-python wheels

2. mobilefacenet.onnx  (~4 MB)
   Source: https://github.com/deepinsight/insightface  (model zoo)
   Alternative: https://github.com/cavalleria/cavaface.pytorch (export)

Usage
-----
    # On Raspberry Pi / target robot:
    cd /path/to/tokymon
    python3 vision/model_manager.py download

    # From Python:
    from vision.model_manager import ensure_models
    ok = ensure_models()   # True if all models present
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

_MODEL_DIR = Path(__file__).parent / "models"

MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "min_size_bytes": 300_000,
        "description": "YuNet face detector (pose-robust, 337 KB)",
        "urls": [
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        ],
        "install_hint": (
            "pip install opencv-contrib-python\n"
            "  or download manually from:\n"
            "  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet"
        ),
    },
    "mobilefacenet.onnx": {
        "min_size_bytes": 3_000_000,
        "description": "MobileFaceNet recognizer (128-d embeddings, ~4 MB)",
        "urls": [
            # insightface model zoo buffalo_s pack
            "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip",
        ],
        "install_hint": (
            "Download from insightface model zoo:\n"
            "  pip install insightface\n"
            "  python3 -c \"import insightface; m = insightface.app.FaceAnalysis(); m.prepare(ctx_id=-1)\"\n"
            "  # Then copy ~/.insightface/models/buffalo_s/w600k_mbf.onnx to vision/models/mobilefacenet.onnx\n"
            "\n"
            "  Alternative (direct download):\n"
            "  wget https://github.com/foamliu/MobileFaceNet/releases/download/v1.0/mobilefacenet.onnx \\\n"
            "       -O vision/models/mobilefacenet.onnx"
        ),
    },
}


def check_model(name: str) -> dict:
    """Return status dict for a model file."""
    path = _MODEL_DIR / name
    spec = MODELS[name]
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    valid = exists and size >= spec["min_size_bytes"]
    return {
        "name": name,
        "path": path,
        "exists": exists,
        "size": size,
        "valid": valid,
        "description": spec["description"],
    }


def status() -> None:
    """Print model status table."""
    print("\n── Face Pipeline Model Status ──────────────────────────────")
    all_ok = True
    for name in MODELS:
        s = check_model(name)
        icon = "✓" if s["valid"] else ("⚠ stub/empty" if s["exists"] else "✗ missing")
        size_str = f"{s['size']:,} bytes" if s["exists"] else "not found"
        print(f"  {icon}  {name}")
        print(f"       {s['description']}")
        print(f"       path: {s['path']}")
        print(f"       size: {size_str}")
        print()
        if not s["valid"]:
            all_ok = False
    if all_ok:
        print("  All models present — pipeline ready.\n")
    else:
        print("  Some models missing — run: python3 vision/model_manager.py download\n")


def download() -> bool:
    """Attempt to download missing models.  Returns True if all valid after."""
    import urllib.request

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    all_ok = True

    for name, spec in MODELS.items():
        s = check_model(name)
        if s["valid"]:
            print(f"  ✓  {name} already present ({s['size']:,} bytes)")
            continue

        print(f"  ↓  Downloading {name} ...")
        downloaded = False
        for url in spec["urls"]:
            try:
                dest = _MODEL_DIR / name
                urllib.request.urlretrieve(url, str(dest))
                s2 = check_model(name)
                if s2["valid"]:
                    print(f"     ✓  Downloaded ({s2['size']:,} bytes)")
                    downloaded = True
                    break
                else:
                    print(f"     ⚠  Downloaded but file seems too small ({s2['size']} bytes)")
            except Exception as exc:
                print(f"     ✗  Failed from {url[:60]}...: {exc}")

        if not downloaded:
            print(f"\n  Manual install needed for {name}:")
            print(f"  {spec['install_hint']}\n")
            all_ok = False

    return all_ok


def ensure_models() -> bool:
    """Return True if all required models are present and valid."""
    return all(check_model(name)["valid"] for name in MODELS)


def verify() -> bool:
    """Verify all models by loading them with ONNX Runtime.  Returns True if all pass."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("onnxruntime not installed — cannot verify")
        return False

    all_ok = True
    for name in MODELS:
        s = check_model(name)
        if not s["valid"]:
            print(f"  ✗  {name}: file invalid/missing")
            all_ok = False
            continue
        try:
            sess = ort.InferenceSession(str(s["path"]), providers=["CPUExecutionProvider"])
            inputs = [i.name for i in sess.get_inputs()]
            print(f"  ✓  {name}: loaded OK (inputs={inputs})")
        except Exception as exc:
            print(f"  ✗  {name}: ONNX load error: {exc}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        status()
    elif cmd == "download":
        ok = download()
        status()
        sys.exit(0 if ok else 1)
    elif cmd == "verify":
        ok = verify()
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 vision/model_manager.py [status|download|verify]")
        sys.exit(1)
