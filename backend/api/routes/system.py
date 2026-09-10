"""NeuroVision AI — System Route"""
import time
import psutil
from fastapi import APIRouter
from core.streaming.manager import stream_manager

router = APIRouter()

@router.get("/status")
async def system_status():
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    gpu_info = {}
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_info = {"name": gpus[0].name, "load": gpus[0].load * 100, "memory_util": gpus[0].memoryUtil * 100}
    except Exception:
        pass
    return {
        "timestamp": time.time(),
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_gb": round(mem.used / 1e9, 2),
        "gpu": gpu_info,
        "ai_pipeline_ready": stream_manager.is_initialized,
        "active_cameras": stream_manager.active_camera_count,
        "stream_statuses": stream_manager.get_stream_status(),
    }

@router.get("/info")
async def system_info():
    import platform, torch
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch_version": torch.__version__,
    }
