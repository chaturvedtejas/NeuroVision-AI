import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
})

// ─── Cameras ──────────────────────────────────────────────────────────────

export const camerasApi = {
  list: () => api.get('/cameras').then((r) => r.data),
  get: (id: string) => api.get(`/cameras/${id}`).then((r) => r.data),
  create: (data: any) => api.post('/cameras', data).then((r) => r.data),
  update: (id: string, data: any) => api.patch(`/cameras/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/cameras/${id}`),
  start: (id: string) => api.post(`/cameras/${id}/start`).then((r) => r.data),
  stop: (id: string) => api.post(`/cameras/${id}/stop`).then((r) => r.data),
  status: (id: string) => api.get(`/cameras/${id}/status`).then((r) => r.data),
  heatmap: (id: string) => api.get(`/cameras/${id}/heatmap`).then((r) => r.data),
  uploadVideo: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/cameras/${id}/upload-video`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data)
  },
}

// ─── Incidents ────────────────────────────────────────────────────────────

export const incidentsApi = {
  list: (params?: any) => api.get('/incidents', { params }).then((r) => r.data),
  get: (id: string) => api.get(`/incidents/${id}`).then((r) => r.data),
  create: (data: any) => api.post('/incidents', data).then((r) => r.data),
  acknowledge: (id: string, data: any) =>
    api.post(`/incidents/${id}/acknowledge`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/incidents/${id}`),
  summary: (cameraId?: string) =>
    api.get('/incidents/stats/summary', { params: { camera_id: cameraId } }).then((r) => r.data),
}

// ─── Alerts ───────────────────────────────────────────────────────────────

export const alertsApi = {
  list: (params?: any) => api.get('/alerts', { params }).then((r) => r.data),
  acknowledge: (id: string) => api.post(`/alerts/${id}/acknowledge`).then((r) => r.data),
}

// ─── Analytics ────────────────────────────────────────────────────────────

export const analyticsApi = {
  crowd: (cameraId: string, hours = 1) =>
    api.get(`/analytics/crowd/${cameraId}`, { params: { hours } }).then((r) => r.data),
  detectionHeatmap: (cameraId?: string, hours = 6) =>
    api.get('/analytics/detections/heatmap', { params: { camera_id: cameraId, hours } }).then((r) => r.data),
  systemMetrics: (hours = 1) =>
    api.get('/analytics/system/metrics', { params: { hours } }).then((r) => r.data),
  incidentTimeline: (cameraId?: string, hours = 24) =>
    api.get('/analytics/incidents/timeline', { params: { camera_id: cameraId, hours } }).then((r) => r.data),
  liveSummary: () => api.get('/analytics/live/summary').then((r) => r.data),
}

// ─── System ───────────────────────────────────────────────────────────────

export const systemApi = {
  status: () => api.get('/system/status').then((r) => r.data),
  info: () => api.get('/system/info').then((r) => r.data),
  health: () => axios.get('/health').then((r) => r.data),
}

// ─── Zones ────────────────────────────────────────────────────────────────

export const zonesApi = {
  list: (cameraId: string) => api.get(`/zones/${cameraId}`).then((r) => r.data),
  create: (data: any) => api.post('/zones', data).then((r) => r.data),
  delete: (id: string) => api.delete(`/zones/${id}`),
}

export default api
