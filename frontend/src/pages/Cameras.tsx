// Cameras page
import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, Plus, Play, Square, Trash2, Wifi, WifiOff, ChevronRight } from 'lucide-react'
import { clsx } from 'clsx'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { camerasApi } from '../services/api'
import { useNVStore } from '../store'

export default function CamerasPage() {
  const qc = useQueryClient()
  const { data: cameras = [], isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.list,
    refetchInterval: 5000,
  })
  const frameData = useNVStore((s) => s.frameData)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', location: '', stream_url: '0' })

  const createMutation = useMutation({
    mutationFn: camerasApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cameras'] }); setShowAdd(false) },
  })

  const startMutation = useMutation({
    mutationFn: (id: string) => camerasApi.start(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  })

  const stopMutation = useMutation({
    mutationFn: (id: string) => camerasApi.stop(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => camerasApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  })

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nv-text">Camera Management</h1>
          <p className="text-xs text-nv-muted">{cameras.length} cameras registered</p>
        </div>
        <button onClick={() => setShowAdd(!showAdd)} className="nv-btn-primary flex items-center gap-2">
          <Plus className="w-3.5 h-3.5" /> Add Camera
        </button>
      </div>

      {/* Add camera form */}
      {showAdd && (
        <div className="nv-card p-4 border border-nv-accent/20 animate-fade-in">
          <h3 className="text-sm font-semibold text-nv-text mb-3">Add New Camera</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className="nv-input" placeholder="Camera name *"
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="nv-input" placeholder="Location (optional)"
              value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            <input className="nv-input" placeholder="Stream URL or webcam index (0)"
              value={form.stream_url} onChange={(e) => setForm({ ...form, stream_url: e.target.value })} />
          </div>
          <p className="text-[10px] text-nv-muted mt-2">
            Webcam: enter 0 (or 1, 2…) | RTSP: rtsp://user:pass@ip/stream | File: /path/to/video.mp4
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => createMutation.mutate(form)}
              disabled={!form.name || createMutation.isPending}
              className="nv-btn-primary"
            >
              {createMutation.isPending ? 'Creating…' : 'Create Camera'}
            </button>
            <button onClick={() => setShowAdd(false)} className="nv-btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Camera grid */}
      {isLoading ? (
        <div className="text-center py-12 text-nv-muted text-sm">Loading cameras…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cameras.map((cam: any) => (
            <CameraCard
              key={cam.id}
              camera={cam}
              frame={frameData[cam.id]}
              onStart={() => startMutation.mutate(cam.id)}
              onStop={() => stopMutation.mutate(cam.id)}
              onDelete={() => { if (confirm('Delete this camera?')) deleteMutation.mutate(cam.id) }}
            />
          ))}
          {cameras.length === 0 && (
            <div className="col-span-3 py-16 text-center">
              <Camera className="w-12 h-12 text-nv-muted mx-auto mb-3 opacity-30" />
              <p className="text-nv-muted text-sm">No cameras yet</p>
              <button onClick={() => setShowAdd(true)} className="nv-btn-primary mt-3">
                <Plus className="w-3.5 h-3.5 inline mr-1" /> Add your first camera
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function CameraCard({ camera, frame, onStart, onStop, onDelete }: any) {
  const isOnline = camera.status === 'online'
  return (
    <div className="nv-card-glow overflow-hidden">
      {/* Thumbnail */}
      <div className="relative aspect-video bg-nv-bg">
        {frame?.frame ? (
          <img src={`data:image/jpeg;base64,${frame.frame}`} className="w-full h-full object-cover" alt={camera.name} />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Camera className="w-8 h-8 text-nv-muted opacity-20" />
          </div>
        )}
        <div className={clsx('absolute top-2 left-2 flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono',
          isOnline ? 'bg-nv-accent/20 text-nv-accent' : 'bg-nv-muted/20 text-nv-muted'
        )}>
          {isOnline ? <Wifi className="w-2.5 h-2.5" /> : <WifiOff className="w-2.5 h-2.5" />}
          {camera.status.toUpperCase()}
        </div>
        {frame && (
          <div className="absolute top-2 right-2 text-[10px] font-mono bg-nv-bg/80 px-1.5 py-0.5 rounded text-nv-accent">
            {frame.fps.toFixed(0)} FPS
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <div className="flex items-start justify-between mb-1">
          <div>
            <h3 className="text-sm font-semibold text-nv-text">{camera.name}</h3>
            {camera.location && <p className="text-[10px] text-nv-muted">{camera.location}</p>}
          </div>
          {frame && (
            <div className="flex items-center gap-1 text-[10px] font-mono text-nv-muted bg-nv-bg px-1.5 py-0.5 rounded">
              👁 {frame.person_count}
            </div>
          )}
        </div>

        <p className="text-[10px] font-mono text-nv-muted/50 mb-3 truncate">{camera.stream_url}</p>

        <div className="flex items-center gap-2">
          {!isOnline ? (
            <button onClick={onStart} className="nv-btn-primary flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5">
              <Play className="w-3 h-3" /> Start
            </button>
          ) : (
            <button onClick={onStop} className="nv-btn-danger flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5">
              <Square className="w-3 h-3" /> Stop
            </button>
          )}
          <Link to={`/cameras/${camera.id}`}
            className="nv-btn-secondary flex items-center justify-center gap-1 text-xs py-1.5 px-3">
            View <ChevronRight className="w-3 h-3" />
          </Link>
          <button onClick={onDelete} className="p-1.5 text-nv-muted hover:text-nv-red border border-nv-border rounded-lg transition-colors">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
