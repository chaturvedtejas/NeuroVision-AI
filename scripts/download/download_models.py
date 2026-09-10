#!/usr/bin/env python3
"""
NeuroVision AI — Model Download Script
Downloads all required AI models to the models/ directory
"""
import os
import sys
from pathlib import Path

MODELS_DIR = Path(os.environ.get("MODELS_DIR", "./models"))
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def download_yolo_models():
    """Download YOLO detection and pose models via ultralytics."""
    print("📥 Downloading YOLO models...")
    try:
        from ultralytics import YOLO

        models = [
            ("yolov8n.pt",      "YOLOv8 Nano — Object Detection"),
            ("yolov8s.pt",      "YOLOv8 Small — Object Detection (better accuracy)"),
            ("yolov8n-pose.pt", "YOLOv8 Nano Pose — Skeleton Estimation"),
            ("yolov8s-pose.pt", "YOLOv8 Small Pose — Skeleton Estimation (better)"),
        ]

        for model_file, description in models:
            dest = MODELS_DIR / model_file
            if dest.exists():
                print(f"  ✅ {model_file} already exists ({description})")
                continue
            print(f"  ⬇️  Downloading {model_file} — {description}")
            model = YOLO(model_file)
            # Move to models dir
            default_path = Path(model_file)
            if default_path.exists():
                default_path.rename(dest)
            print(f"  ✅ Saved to {dest}")

    except ImportError:
        print("❌ ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)
    except Exception as e:
        print(f"❌ YOLO download failed: {e}")
        sys.exit(1)


def verify_models():
    """Verify downloaded models are valid."""
    print("\n🔍 Verifying models...")
    required = ["yolov8n.pt", "yolov8n-pose.pt"]
    all_ok = True
    for model_file in required:
        path = MODELS_DIR / model_file
        if path.exists():
            size_mb = path.stat().st_size / 1e6
            print(f"  ✅ {model_file} ({size_mb:.1f} MB)")
        else:
            print(f"  ❌ {model_file} MISSING")
            all_ok = False
    return all_ok


def check_gpu():
    """Check CUDA availability."""
    print("\n🖥️  GPU Check...")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"  ✅ CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"  ✅ VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            print("  ⚠️  CUDA not available — will use CPU (slower)")
    except ImportError:
        print("  ❌ PyTorch not installed")


if __name__ == "__main__":
    print("=" * 50)
    print("  NeuroVision AI — Model Setup")
    print(f"  Models directory: {MODELS_DIR.absolute()}")
    print("=" * 50)

    check_gpu()
    download_yolo_models()
    ok = verify_models()

    print("\n" + ("=" * 50))
    if ok:
        print("🚀 All models ready! You can now start NeuroVision AI.")
    else:
        print("⚠️  Some models are missing. Check errors above.")
    print("=" * 50)
