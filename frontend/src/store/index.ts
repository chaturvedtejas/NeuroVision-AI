import { create } from 'zustand'

export interface Camera {
  id: string
  name: string
  location?: string
  stream_url: string
  status: 'online' | 'offline' | 'error' | 'paused' | 'recording'
  fps: number
  detection_enabled: boolean
  tracking_enabled: boolean
  pose_enabled: boolean
}

export interface Alert {
  id?: string
  camera_id: string
  camera_name: string
  alert_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  description: string
  track_ids: number[]
  confidence: number
  timestamp: number
  metadata?: Record<string, unknown>
}

export interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  memory_used_gb: number
  memory_total_gb: number
  gpu_percent: number | null
  gpu_memory_percent: number | null
  active_cameras: number
  total_cameras: number
  avg_fps: number
  ws_clients: number
}

export interface FrameData {
  camera_id: string
  frame_number: number
  timestamp: number
  fps: number
  inference_ms: number
  person_count: number
  total_detections: number
  active_tracks: number
  frame: string   // base64 JPEG
  detections: Detection[]
  tracks: Track[]
  actions: Action[]
  anomalies: Anomaly[]
  crowd: CrowdMetrics | null
  alerts: Alert[]
}

export interface Detection {
  x1: number; y1: number; x2: number; y2: number
  confidence: number
  class_id: number
  class_name: string
  track_id: number | null
  center: [number, number]
}

export interface Track {
  track_id: number
  class_name: string
  bbox: Detection
  trajectory: { x: number; y: number }[]
  age: number
}

export interface Action {
  track_id: number
  action: string
  confidence: number
  timestamp: number
  evidence: Record<string, unknown>
}

export interface Anomaly {
  camera_id: string
  track_id: number
  anomaly_score: number
  is_anomaly: boolean
  anomaly_type: string
  details: Record<string, unknown>
  timestamp: number
}

export interface CrowdMetrics {
  camera_id: string
  person_count: number
  density_score: number
  congestion_score: number
  avg_velocity: number
  flow_direction: [number, number] | null
  hotspots: { x: number; y: number; intensity: number }[]
}

export interface Incident {
  id: string
  camera_id: string
  incident_type: string
  severity: string
  status: string
  title: string
  description?: string
  ai_summary?: string
  confidence_score: number
  created_at: string
}

interface NVStore {
  // Camera registry
  cameras: Camera[]
  setCameras: (cameras: Camera[]) => void
  updateCamera: (id: string, patch: Partial<Camera>) => void

  // Live frame data per camera
  frameData: Record<string, FrameData>
  setFrameData: (cameraId: string, data: FrameData) => void

  // Global alerts queue
  alerts: Alert[]
  addAlert: (alert: Alert) => void
  clearAlerts: () => void

  // System metrics
  metrics: SystemMetrics | null
  setMetrics: (m: SystemMetrics) => void

  // Incidents
  incidents: Incident[]
  setIncidents: (i: Incident[]) => void
  addIncident: (i: Incident) => void

  // UI state
  selectedCameraId: string | null
  setSelectedCamera: (id: string | null) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useNVStore = create<NVStore>((set, get) => ({
  cameras: [],
  setCameras: (cameras) => set({ cameras }),
  updateCamera: (id, patch) =>
    set((s) => ({ cameras: s.cameras.map((c) => (c.id === id ? { ...c, ...patch } : c)) })),

  frameData: {},
  setFrameData: (cameraId, data) =>
    set((s) => ({ frameData: { ...s.frameData, [cameraId]: data } })),

  alerts: [],
  addAlert: (alert) =>
    set((s) => ({ alerts: [alert, ...s.alerts].slice(0, 200) })),
  clearAlerts: () => set({ alerts: [] }),

  metrics: null,
  setMetrics: (metrics) => set({ metrics }),

  incidents: [],
  setIncidents: (incidents) => set({ incidents }),
  addIncident: (incident) =>
    set((s) => ({ incidents: [incident, ...s.incidents].slice(0, 500) })),

  selectedCameraId: null,
  setSelectedCamera: (id) => set({ selectedCameraId: id }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))
