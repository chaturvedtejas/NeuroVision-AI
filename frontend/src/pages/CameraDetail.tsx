import React, { useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Play, Square, Upload, Users, Activity,
  Shield, Target, AlertTriangle, MapPin, BarChart2
} from 'lucide-react'
import { clsx } from 'clsx'
import { useNVStore } from '../store'
import { camerasApi } from '../services/api'
import { useCameraStream } from '../hooks/useWebSocket'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

export default function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const frameData = useNVStore((s) => s.frameData[id!])
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTab, setActiveTab] = useState<'detections' | 'tracks' | 'actions' | 'crowd'>('detections')
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: camera, isLoading } = useQuery({
    queryKey: ['camera', id],
    queryFn: () => camerasApi.get(id!),
    enabled: !!id,
  })

  // Connect WebSocket stream when streaming is active
  useCameraStream(isStreaming && id ? id : null)

  const startMutation = useMutation({
    mutationFn: () => camerasApi.start(id!),
    onSuccess: () => { setIsStreaming(true); qc.invalidateQueries({ queryKey: ['camera', id] }) },
  })

  const stopMutation = useMutation({
    mutationFn: () => camerasApi.stop(id!),
    onSuccess: () => { setIsStreaming(false); qc.invalidateQueries({ queryKey: ['camera', id] }) },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => camerasApi.uploadVideo(id!, file),
    onSuccess: () => alert('Video uploaded! Start stream to analyze.'),
  })

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadMutation.mutate(file)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-nv-muted text-sm">Loading camera…</div>
      </div>
    )
  }

  if (!camera) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <p className="text-nv-muted text-sm">Camera not found</p>
        <Link to="/cameras" className="nv-btn-primary nv-btn">← Back to cameras</Link>
      </div>
    )
  }

  const TABS = [
    { key: 'detections', label: 'Detections', icon: Target, count: frameData?.total_detections },
    { key: 'tracks', label: 'Tracks', icon: Users, count: frameData?.active_tracks },
    { key: 'actions', label: 'Actions', icon: Activity, count: frameData?.actions?.length },
    { key: 'crowd', label: 'Crowd', icon: BarChart2, count: null },
  ] as const

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/cameras" className="p-1.5 rounded-lg border border-nv-border text-nv-muted hover:text-nv-text transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-bold text-nv-text">{camera.name}</h1>
            <div className="flex items-center gap-2 text-xs text-nv-muted">
              {camera.location && <><MapPin className="w-3 h-3" /><span>{camera.location}</span></>}
              <span className="font-mono opacity-50">ID: {camera.id.slice(0, 8)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" accept="video/*" className="hidden" onChange={handleFileUpload} />
          <button
            onClick={() => fileRef.current?.click()}
            className="nv-btn-secondary flex items-center gap-2"
            disabled={uploadMutation.isPending}
          >
            <Upload className="w-3.5 h-3.5" />
            {uploadMutation.isPending ? 'Uploading…' : 'Upload Video'}
          </button>
          {!isStreaming ? (
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
              className="nv-btn-primary flex items-center gap-2"
            >
              <Play className="w-3.5 h-3.5" />
              {startMutation.isPending ? 'Starting…' : 'Start Stream'}
            </button>
          ) : (
            <button
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
              className="nv-btn-danger flex items-center gap-2"
            >
              <Square className="w-3.5 h-3.5" />
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Video feed */}
        <div className="lg:col-span-2">
          <div className="nv-card overflow-hidden">
            {/* Stream header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-nv-border">
              <div className="flex items-center gap-2">
                <div className={clsx('w-2 h-2 rounded-full', isStreaming ? 'bg-nv-accent animate-pulse' : 'bg-nv-muted')} />
                <span className="text-xs font-mono text-nv-muted">{isStreaming ? 'LIVE' : 'OFFLINE'}</span>
              </div>
              {frameData && (
                <div className="flex items-center gap-4 text-[10px] font-mono text-nv-muted">
                  <span className="text-nv-accent">{frameData.fps.toFixed(1)} FPS</span>
                  <span>{frameData.inference_ms.toFixed(0)}ms latency</span>
                  <span>{frameData.total_detections} obj</span>
                  <span>{frameData.person_count} persons</span>
                </div>
              )}
            </div>

            {/* Video frame */}
            <div className="relative bg-nv-bg aspect-video">
              {frameData?.frame ? (
                <img
                  src={`data:image/jpeg;base64,${frameData.frame}`}
                  alt="Live feed"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center scanline">
                  <div className="w-16 h-16 rounded-full border-2 border-nv-border flex items-center justify-center mb-3">
                    <Shield className="w-8 h-8 text-nv-muted opacity-30" />
                  </div>
                  <p className="text-xs text-nv-muted">
                    {isStreaming ? 'Connecting to stream…' : 'Stream not started'}
                  </p>
                  <p className="text-[10px] text-nv-muted/50 mt-1 font-mono">{camera.stream_url}</p>
                </div>
              )}

              {/* Alert overlay */}
              {frameData?.alerts && frameData.alerts.length > 0 && (
                <div className="absolute top-2 left-2 right-2 flex flex-col gap-1">
                  {frameData.alerts.slice(0, 2).map((a: any, i: number) => (
                    <div key={i} className={clsx(
                      'flex items-center gap-2 px-2 py-1 rounded text-xs backdrop-blur-sm',
                      a.severity === 'critical' ? 'bg-red-500/30 text-red-300' :
                      a.severity === 'high' ? 'bg-orange-500/30 text-orange-300' :
                      'bg-yellow-500/30 text-yellow-300'
                    )}>
                      <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                      {a.title}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Analytics panel */}
        <div className="space-y-3">
          {/* Live stats */}
          <div className="nv-card p-3">
            <h3 className="text-xs font-semibold text-nv-muted mb-2 uppercase tracking-wider">Live Analytics</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Persons', value: frameData?.person_count ?? '—', color: 'text-nv-accent' },
                { label: 'Tracks', value: frameData?.active_tracks ?? '—', color: 'text-nv-cyan' },
                { label: 'Actions', value: frameData?.actions?.length ?? '—', color: 'text-nv-amber' },
                { label: 'Anomalies', value: frameData?.anomalies?.length ?? '—', color: 'text-nv-red' },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-nv-bg rounded-lg p-2 border border-nv-border">
                  <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
                  <div className="text-[10px] text-nv-muted">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Crowd metrics */}
          {frameData?.crowd && (
            <div className="nv-card p-3">
              <h3 className="text-xs font-semibold text-nv-muted mb-2 uppercase tracking-wider">Crowd</h3>
              <CrowdMeter label="Density" value={frameData.crowd.density_score} />
              <CrowdMeter label="Congestion" value={frameData.crowd.congestion_score} />
              <div className="flex justify-between mt-2">
                <span className="text-[10px] text-nv-muted">Avg velocity</span>
                <span className="text-[10px] font-mono text-nv-cyan">
                  {(frameData.crowd.avg_velocity * 100).toFixed(2)} u/s
                </span>
              </div>
            </div>
          )}

          {/* Tabs: detections/tracks/actions */}
          <div className="nv-card overflow-hidden">
            <div className="flex border-b border-nv-border">
              {TABS.map(({ key, label, icon: Icon, count }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key as any)}
                  className={clsx(
                    'flex-1 flex items-center justify-center gap-1 py-2 text-[10px] font-medium transition-colors',
                    activeTab === key
                      ? 'text-nv-accent border-b-2 border-nv-accent bg-nv-accent/5'
                      : 'text-nv-muted hover:text-nv-text'
                  )}
                >
                  <Icon className="w-3 h-3" />
                  <span className="hidden sm:inline">{label}</span>
                  {count !== null && count !== undefined && count > 0 && (
                    <span className="bg-nv-accent/20 text-nv-accent rounded-full px-1">{count}</span>
                  )}
                </button>
              ))}
            </div>

            <div className="p-2 max-h-60 overflow-y-auto">
              {activeTab === 'detections' && (
                <DetectionList detections={frameData?.detections || []} />
              )}
              {activeTab === 'tracks' && (
                <TrackList tracks={frameData?.tracks || []} />
              )}
              {activeTab === 'actions' && (
                <ActionList actions={frameData?.actions || []} />
              )}
              {activeTab === 'crowd' && frameData?.crowd && (
                <div className="space-y-1 text-[11px]">
                  {frameData.crowd.hotspots?.map((hs: any, i: number) => (
                    <div key={i} className="flex justify-between px-1 py-1 rounded bg-nv-bg">
                      <span className="text-nv-muted">Hotspot {i + 1}</span>
                      <span className="font-mono text-nv-cyan">
                        ({hs.x.toFixed(2)}, {hs.y.toFixed(2)}) · {(hs.intensity * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CrowdMeter({ label, value }: { label: string; value: number }) {
  const color = value > 0.8 ? '#ff3366' : value > 0.5 ? '#f59e0b' : '#00ff88'
  return (
    <div className="mb-2">
      <div className="flex justify-between mb-1">
        <span className="text-[10px] text-nv-muted">{label}</span>
        <span className="text-[10px] font-mono" style={{ color }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-nv-border rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${value * 100}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

function DetectionList({ detections }: { detections: any[] }) {
  if (!detections.length) return <p className="text-[10px] text-nv-muted text-center py-4">No detections</p>
  return (
    <div className="space-y-1">
      {detections.slice(0, 15).map((d: any, i: number) => (
        <div key={i} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-nv-bg transition-colors">
          <span className="text-[10px] text-nv-accent font-mono w-12 truncate">{d.class_name}</span>
          <div className="flex-1 h-1 bg-nv-border rounded overflow-hidden">
            <div className="h-full bg-nv-accent/50 rounded" style={{ width: `${d.confidence * 100}%` }} />
          </div>
          <span className="text-[9px] font-mono text-nv-muted">{(d.confidence * 100).toFixed(0)}%</span>
          {d.track_id && <span className="text-[9px] font-mono text-nv-cyan">#{d.track_id}</span>}
        </div>
      ))}
    </div>
  )
}

function TrackList({ tracks }: { tracks: any[] }) {
  if (!tracks.length) return <p className="text-[10px] text-nv-muted text-center py-4">No active tracks</p>
  return (
    <div className="space-y-1">
      {tracks.map((t: any) => (
        <div key={t.track_id} className="flex items-center gap-2 px-1 py-1.5 rounded hover:bg-nv-bg border border-transparent hover:border-nv-border transition-all">
          <span className="text-[10px] font-mono text-nv-cyan w-8">#{t.track_id}</span>
          <span className="text-[10px] text-nv-text flex-1">{t.class_name}</span>
          <span className="text-[9px] text-nv-muted">{t.trajectory?.length || 0} pts</span>
          <span className="text-[9px] font-mono text-nv-muted">{t.age}f</span>
        </div>
      ))}
    </div>
  )
}

function ActionList({ actions }: { actions: any[] }) {
  if (!actions.length) return <p className="text-[10px] text-nv-muted text-center py-4">No actions detected</p>
  const ACTION_COLORS: Record<string, string> = {
    fighting: 'text-nv-red', falling: 'text-nv-red', fallen: 'text-nv-red',
    running: 'text-nv-amber', loitering: 'text-nv-amber',
    suspicious_movement: 'text-orange-400', walking: 'text-nv-accent',
    standing: 'text-nv-cyan',
  }
  return (
    <div className="space-y-1">
      {actions.map((a: any, i: number) => (
        <div key={i} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-nv-bg">
          <span className="text-[9px] font-mono text-nv-cyan w-6">#{a.track_id}</span>
          <span className={`text-[10px] font-medium flex-1 ${ACTION_COLORS[a.action] || 'text-nv-text'}`}>
            {a.action.replace(/_/g, ' ')}
          </span>
          <span className="text-[9px] font-mono text-nv-muted">{(a.confidence * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  )
}
