# NeuroVision AI — Backend Dockerfile
# Multi-stage build with CUDA support

# ── Base: CUDA + Python ────────────────────────────────────────────────────────
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 ffmpeg v4l-utils curl \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# ── Builder: install dependencies ─────────────────────────────────────────────
FROM base AS builder

WORKDIR /build

# Copy and install requirements
COPY requirements.txt .

# Install PyTorch with CUDA first (large, cache this layer)
RUN pip install torch==2.3.0 torchvision==0.18.0 \
    --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
RUN pip install --prefix=/install -r requirements.txt

# ── Final image ───────────────────────────────────────────────────────────────
FROM base AS final

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/models /app/data/uploads /app/data/recordings /app/data/reports

# Pre-download YOLO models (optional: comment out to download at runtime)
# RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); YOLO('yolov8n-pose.pt')"

# Non-root user
RUN useradd -m -u 1000 neurovision && chown -R neurovision:neurovision /app
USER neurovision

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--log-level", "info"]
