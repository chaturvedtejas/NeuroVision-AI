# NeuroVision AI 🧠👁️
### Real-Time Predictive Surveillance & Behavior Understanding System

> **Production-grade AI surveillance platform** with real-time object detection, multi-object tracking, pose estimation, action recognition, trajectory prediction, crowd analytics, anomaly detection, and a futuristic React dashboard.

---

## ✨ Features

| Module | Description | Tech |
|--------|-------------|------|
| 🎯 **Object Detection** | Real-time multi-class detection (persons, bags, vehicles) | YOLOv8/v11 |
| 🔢 **Multi-Object Tracking** | Persistent IDs via Kalman filter + Hungarian algorithm | SORT + ByteTrack |
| 🦴 **Pose Estimation** | 17-keypoint COCO skeleton per person | YOLO-Pose |
| 🥊 **Action Recognition** | Fighting, falling, running, loitering, suspicious movement | Rule-based + ML |
| 📈 **Trajectory Prediction** | LSTM-based path prediction (15+ frames ahead) | PyTorch LSTM |
| 👥 **Crowd Analytics** | Density maps, heatmaps, flow vectors, congestion scoring | Gaussian kernels |
| 🚨 **Anomaly Detection** | Statistical + autoencoder-based unsupervised detection | PyOD + custom |
| 📋 **AI Incident Reports** | Auto-generated natural language incident summaries | Template + LLM-ready |
| ⚡ **Smart Alerts** | Zone intrusion, abandoned objects, crowd congestion | Rule engine |
| 🖥️ **Live Dashboard** | Futuristic React UI with WebSocket streaming | React + Recharts |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     NGINX Reverse Proxy                   │
│               Port 80/443 → :8000 / :3000               │
└──────────────────┬──────────────────┬────────────────────┘
                   │                  │
        ┌──────────▼──────┐  ┌───────▼──────────┐
        │  FastAPI Backend │  │  React Frontend   │
        │   (uvicorn)      │  │  (Vite + TS)      │
        │   Port 8000      │  │  Port 3000         │
        └──────────┬───────┘  └──────────────────┘
                   │
        ┌──────────▼─────────────────────────────┐
        │           AI Processing Pipeline         │
        │                                          │
        │  Camera Streams (RTSP / Webcam / File)  │
        │        ↓                                 │
        │  YOLOv8 Detection (CUDA/ONNX/CPU)       │
        │        ↓                                 │
        │  SORT Multi-Object Tracking              │
        │        ↓                                 │
        │  YOLO-Pose Skeleton Estimation           │
        │        ↓                                 │
        │  Action Recognition (Rules + LSTM)       │
        │        ↓                                 │
        │  LSTM Trajectory Prediction              │
        │        ↓                                 │
        │  Crowd Analytics + Heatmaps              │
        │        ↓                                 │
        │  Statistical Anomaly Detection           │
        │        ↓                                 │
        │  Smart Alert Engine → WebSocket Push    │
        └──────────┬─────────────────────────────┘
                   │
        ┌──────────▼──────────────────┐
        │  PostgreSQL  │  Redis Cache  │
        └─────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- NVIDIA GPU + CUDA 12.x *(optional but recommended)*

### 1. Clone & Setup

```bash
git clone https://github.com/your-org/neurovision-ai.git
cd neurovision-ai

# Copy environment config
cp .env.example .env
# Edit .env with your values (database passwords, etc.)
```

### 2. Download AI Models

```bash
cd backend
pip install ultralytics
python ../scripts/download/download_models.py
```

### 3A. Docker (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Access dashboard
open http://localhost:80
```

### 3B. Manual Development Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL and Redis first
docker-compose up -d postgres redis

# Initialize DB and run server
python main.py
# API docs: http://localhost:8000/api/docs
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Dashboard: http://localhost:3000
```

---

## 📁 Project Structure

```
neurovision-ai/
├── backend/
│   ├── main.py                      # FastAPI application entry
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── config/
│   │   └── settings.py              # All configuration (pydantic-settings)
│   ├── db/
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── repositories/            # Data access layer
│   ├── app/
│   │   ├── detection/
│   │   │   └── detector.py          # YOLOv8 object detection
│   │   ├── tracking/
│   │   │   └── tracker.py           # SORT + Kalman multi-object tracking
│   │   ├── pose/
│   │   │   └── estimator.py         # YOLO-Pose skeleton estimation
│   │   ├── action/
│   │   │   └── recognizer.py        # Action recognition (fight, fall, loiter…)
│   │   ├── trajectory/
│   │   │   └── predictor.py         # LSTM trajectory prediction
│   │   ├── crowd/
│   │   │   └── analytics.py         # Density maps, heatmaps, flow analysis
│   │   ├── anomaly/
│   │   │   └── detector.py          # Statistical + zone + abandoned object
│   │   ├── alerts/
│   │   │   └── engine.py            # Smart alert engine + incident reports
│   │   └── reporting/
│   ├── core/
│   │   └── streaming/
│   │       └── manager.py           # Camera stream orchestrator
│   └── api/
│       ├── routes/
│       │   ├── cameras.py           # Camera CRUD + stream control
│       │   ├── incidents.py         # Incident management
│       │   ├── alerts.py
│       │   ├── analytics.py         # Historical analytics
│       │   ├── zones.py             # Restricted zone management
│       │   └── system.py            # System status
│       └── websockets/
│           ├── stream_ws.py         # Per-camera live frame WebSocket
│           └── events_ws.py         # Global alerts/metrics WebSocket
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── store/index.ts           # Zustand global state
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts      # WebSocket hooks
│   │   ├── services/
│   │   │   └── api.ts               # Axios API client
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx        # Command center overview
│   │   │   ├── Cameras.tsx          # Camera management grid
│   │   │   ├── CameraDetail.tsx     # Live feed + analytics
│   │   │   ├── Incidents.tsx        # Incident log table
│   │   │   ├── Analytics.tsx        # Charts + heatmaps
│   │   │   └── Settings.tsx         # Configuration panel
│   │   └── components/
│   │       ├── dashboard/           # Layout, Sidebar, TopBar
│   │       └── alerts/              # AlertToaster
│   └── Dockerfile
│
├── docker/
│   ├── nginx/nginx.conf
│   ├── postgres/init.sql
│   └── redis/redis.conf
├── scripts/
│   └── download/download_models.py
├── docker-compose.yml
└── .env.example
```

---

## 🔌 API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health check |
| `GET` | `/api/v1/cameras` | List all cameras |
| `POST` | `/api/v1/cameras` | Create camera |
| `POST` | `/api/v1/cameras/{id}/start` | Start AI stream |
| `POST` | `/api/v1/cameras/{id}/stop` | Stop stream |
| `POST` | `/api/v1/cameras/{id}/upload-video` | Upload video file |
| `GET` | `/api/v1/cameras/{id}/heatmap` | Get crowd heatmap |
| `GET` | `/api/v1/incidents` | List incidents (filterable) |
| `POST` | `/api/v1/incidents/{id}/acknowledge` | Acknowledge incident |
| `GET` | `/api/v1/alerts` | List alerts |
| `GET` | `/api/v1/analytics/crowd/{camera_id}` | Crowd timeline |
| `GET` | `/api/v1/analytics/live/summary` | Live dashboard summary |
| `GET` | `/api/v1/system/status` | System + GPU metrics |
| `POST` | `/api/v1/zones` | Create restricted zone |

Interactive docs: **http://localhost:8000/api/docs**

### WebSocket Endpoints

| Path | Direction | Description |
|------|-----------|-------------|
| `ws://host/ws/stream/{camera_id}` | Server → Client | Annotated frames + detections |
| `ws://host/ws/events` | Server → Client | Global alerts + system metrics |

---

## ⚙️ Configuration

All settings are configured via environment variables (see `.env.example`):

```bash
# Key settings
AI_DEVICE=cuda              # cuda or cpu
YOLO_MODEL=yolov8n.pt      # nano (fast) or yolov8s.pt (accurate)
CONF_THRESHOLD=0.45         # Detection confidence (0-1)
TARGET_FPS=25               # Processing rate
MAX_CAMERAS=16              # Concurrent camera limit
LOITER_TIME=60              # Seconds for loitering alert
ABANDONED_TIME=30           # Seconds for abandoned object alert
```

---

## 🔧 Performance Optimization

### GPU Mode (Recommended)
```bash
AI_DEVICE=cuda
AI_HALF_PRECISION=true      # FP16 — 2x faster, minimal accuracy loss
```

### CPU Mode
```bash
AI_DEVICE=cpu
AI_HALF_PRECISION=false
TARGET_FPS=10               # Reduce for CPU
```

### Model Size Trade-off

| Model | Speed | Accuracy | VRAM |
|-------|-------|----------|------|
| `yolov8n.pt` | ~120 FPS (GPU) | Good | ~1 GB |
| `yolov8s.pt` | ~80 FPS (GPU)  | Better | ~2 GB |
| `yolov8m.pt` | ~50 FPS (GPU)  | Best | ~4 GB |

### Multi-camera Scaling
- Each camera runs in a dedicated async task
- Frame processing is decoupled from capture via thread-safe queues
- Recommended: 1 GPU per 4–8 HD cameras at 25 FPS

---

## 🛡️ Supported Stream Types

| Type | Format | Example |
|------|--------|---------|
| Webcam | Integer index | `0`, `1`, `2` |
| RTSP IP Camera | RTSP URL | `rtsp://admin:pass@192.168.1.100/stream` |
| Video File | File path | `/data/uploads/video.mp4` |
| HTTP Stream | HTTP URL | `http://example.com/stream.mjpg` |

---

## 🔬 Action Recognition Reference

| Action | Detection Method | Severity |
|--------|-----------------|----------|
| **Fighting** | Proximity + high speed variance of 2+ persons | 🔴 Critical |
| **Fallen** | Bounding box aspect ratio + pose geometry | 🔴 Critical |
| **Falling** | Rapid height ratio change + velocity spike | 🔴 High |
| **Loitering** | Low displacement > threshold time | 🟡 Medium |
| **Running** | Speed above walking threshold | 🟡 Medium |
| **Suspicious** | High speed variance / erratic movement | 🟡 Medium |
| **Intrusion** | Point-in-polygon zone check | 🔴 High |
| **Abandoned Object** | Object unattended > time threshold | 🔴 High |
| **Crowd Congestion** | Person count / density > threshold | 🔴 High |

---

## 📊 Database Schema (Key Tables)

```
cameras          — registered camera sources
zones            — restricted/monitoring polygons per camera
tracked_objects  — persistent tracking history + trajectories
detections       — per-frame detection records
incidents        — security incidents with AI summaries
alerts           — dispatched notifications
crowd_analytics  — crowd density time-series
system_metrics   — CPU/GPU/FPS monitoring history
```

---

## 🐳 Production Deployment

### Enable GPU in Docker

Uncomment in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

Requires `nvidia-container-toolkit` installed on host.

### Scale Horizontally

For large deployments, separate services:
```bash
# Run AI workers on GPU machines
docker-compose up backend

# Run frontend + nginx separately
docker-compose up frontend nginx
```

---

## 🧪 Development

```bash
# Backend with hot reload
cd backend && uvicorn main:app --reload --port 8000

# Frontend with HMR
cd frontend && npm run dev

# Type checking
cd frontend && npx tsc --noEmit

# API testing (Swagger)
open http://localhost:8000/api/docs
```

---

## 📄 License

MIT License — Copyright © 2024 NeuroVision AI

---

*Built with ❤️ using PyTorch, FastAPI, React, and cutting-edge computer vision*
"# NeuroVision-AI" 
