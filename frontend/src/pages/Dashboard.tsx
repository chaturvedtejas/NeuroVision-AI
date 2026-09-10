import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Camera, ShieldAlert, Activity, Users, AlertTriangle,
  TrendingUp, Eye, Cpu, Zap, ChevronRight
} from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis,
  Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'
import { clsx } from 'clsx'
import { useNVStore } from '../store'
import { analyticsApi, incidentsApi } from '../services/api'
import { useQuery } from '@tanstack/react-query'

export default function DashboardPage() {
  const { metrics, cameras, alerts, frameData } = useNVStore((s) => ({
    metrics: s.metrics,
    cameras: s.cameras,
    alerts: s.alerts,
    frameData: s.frameData,
  }))

  const { data: liveSummary } = useQuery({
    queryKey: ['live-summary'],
    queryFn: analyticsApi.liveSummary,
    refetchInterval: 5000,
  })

  const { data: incidentSummary } = useQuery({
    queryKey: ['incident-summary'],
    queryFn: () => incidentsApi.summary(),
    refetchInterval: 30000,
  })

  const { data: incidentTimeline } = useQuery({
    queryKey: ['incident-timeline'],
    queryFn: () => analyticsApi.incidentTimeline(undefined, 24),
    refetchInterval: 15000,
  })

  // Compute live stats
  const totalPersons = Object.values(frameData).reduce((sum, fd) => sum + fd.person_count, 0)
  const totalTracks = Object.values(frameData).reduce((sum, fd) => sum + fd.active_tracks, 0)
  const criticalAlerts = alerts.filter((a) => a.severity === 'critical').length
  const onlineCams = cameras.filter((c) => c.status === 'online').length

  // Build FPS sparkline from live frame data
  const fpsHistory = Object.values(frameData).flatMap((fd) =>
    [{ time: new Date(fd.timestamp * 1000).toLocaleTimeString(), fps: fd.fps }]
  )

  // Incident type breakdown for bar chart
  const incidentBreakdown = React.useMemo(() => {
    if (!incidentSummary) return []
    const map: Record<string, number> = {}
    incidentSummary.forEach((row: any) => {
      map[row.incident_type] = (map[row.incident_type] || 0) + row.count
    })
    return Object.entries(map).map(([type, count]) => ({
      type: type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      count,
    }))
  }, [incidentSummary])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nv-text">Command Center</h1>
          <p className="text-xs text-nv-muted">Real-time surveillance intelligence</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-nv-accent/10 border border-nv-accent/20">
          <div className="w-1.5 h-1.5 rounded-full bg-nv-accent animate-pulse" />
          <span className="text-xs font-mono text-nv-accent">LIVE MONITORING</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          icon={Camera}
          label="Active Cameras"
          value={`${onlineCams}/${cameras.length}`}
          sub={`${cameras.length - onlineCams} offline`}
          color="cyan"
        />
        <KpiCard
          icon={Users}
          label="People Detected"
          value={totalPersons}
          sub={`${totalTracks} active tracks`}
          color="accent"
        />
        <KpiCard
          icon={AlertTriangle}
          label="Active Alerts"
          value={alerts.length}
          sub={`${criticalAlerts} critical`}
          color={criticalAlerts > 0 ? 'red' : 'accent'}
          pulse={criticalAlerts > 0}
        />
        <KpiCard
          icon={Activity}
          label="Avg FPS"
          value={metrics ? `${metrics.avg_fps.toFixed(1)}` : '—'}
          sub={`${metrics?.active_cameras || 0} streams processing`}
          color="purple"
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Camera grid preview */}
        <div className="lg:col-span-2 nv-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2">
              <Eye className="w-4 h-4 text-nv-cyan" /> Live Feeds
            </h2>
            <Link to="/cameras" className="text-xs text-nv-muted hover:text-nv-accent flex items-center gap-1 transition-colors">
              View all <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {cameras.slice(0, 4).map((cam) => (
              <CameraThumb key={cam.id} camera={cam} frameData={frameData[cam.id]} />
            ))}
            {cameras.length === 0 && (
              <div className="col-span-2 py-12 text-center">
                <Camera className="w-8 h-8 text-nv-muted mx-auto mb-2" />
                <p className="text-sm text-nv-muted">No cameras configured</p>
                <Link to="/cameras" className="text-xs text-nv-accent mt-1 block hover:underline">
                  Add a camera →
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* System metrics */}
          {metrics && (
            <div className="nv-card p-4">
              <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
                <Cpu className="w-4 h-4 text-nv-purple" /> System Resources
              </h2>
              <div className="space-y-2.5">
                <ResourceBar label="CPU" value={metrics.cpu_percent} />
                <ResourceBar label="Memory" value={metrics.memory_percent}
                  sub={`${metrics.memory_used_gb.toFixed(1)} / ${metrics.memory_total_gb.toFixed(1)} GB`} />
                {metrics.gpu_percent !== null && (
                  <ResourceBar label="GPU" value={metrics.gpu_percent} color="purple" />
                )}
                {metrics.gpu_memory_percent !== null && (
                  <ResourceBar label="VRAM" value={metrics.gpu_memory_percent} color="purple" />
                )}
              </div>
            </div>
          )}

          {/* Alert severity breakdown */}
          <div className="nv-card p-4">
            <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-nv-red" /> Alert Breakdown
            </h2>
            {[
              { label: 'Critical', key: 'critical', color: '#ff3366' },
              { label: 'High', key: 'high', color: '#f97316' },
              { label: 'Medium', key: 'medium', color: '#f59e0b' },
              { label: 'Low', key: 'low', color: '#3b82f6' },
            ].map(({ label, key, color }) => {
              const count = alerts.filter((a) => a.severity === key).length
              const pct = alerts.length > 0 ? (count / alerts.length) * 100 : 0
              return (
                <div key={key} className="flex items-center gap-2 mb-1.5">
                  <span className="text-[11px] text-nv-muted w-14">{label}</span>
                  <div className="flex-1 h-1.5 bg-nv-border rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, backgroundColor: color }} />
                  </div>
                  <span className="text-[11px] font-mono text-nv-text w-6 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Incident type bar chart */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <ShieldAlert className="w-4 h-4 text-nv-amber" /> Incident Types (24h)
          </h2>
          {incidentBreakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={incidentBreakdown} margin={{ left: -20, bottom: 20 }}>
                <XAxis dataKey="type" tick={{ fontSize: 9, fill: '#6b7280' }} angle={-25} textAnchor="end" />
                <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="count" fill="#00ff88" radius={[3, 3, 0, 0]} opacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-xs text-nv-muted">
              No incident data
            </div>
          )}
        </div>

        {/* Recent incident timeline */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-nv-cyan" /> Recent Incidents
          </h2>
          <div className="space-y-1.5 max-h-40 overflow-y-auto">
            {(incidentTimeline || []).slice(0, 8).map((inc: any, i: number) => (
              <div key={i} className="flex items-center gap-2 py-1 border-b border-nv-border/50">
                <div className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0',
                  inc.severity === 'critical' ? 'bg-red-400' :
                  inc.severity === 'high' ? 'bg-orange-400' :
                  inc.severity === 'medium' ? 'bg-yellow-400' : 'bg-blue-400'
                )} />
                <span className="text-[11px] text-nv-text flex-1 truncate">{inc.title}</span>
                <span className="text-[10px] font-mono text-nv-muted flex-shrink-0">
                  {new Date(inc.created_at).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
            {(!incidentTimeline || incidentTimeline.length === 0) && (
              <p className="text-xs text-nv-muted text-center py-6">No incidents in last 24h</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Sub-components ────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, label, value, sub, color, pulse }: any) {
  const colors: any = {
    accent: { text: 'text-nv-accent', bg: 'bg-nv-accent/10', border: 'border-nv-accent/20' },
    cyan: { text: 'text-nv-cyan', bg: 'bg-nv-cyan/10', border: 'border-nv-cyan/20' },
    red: { text: 'text-nv-red', bg: 'bg-nv-red/10', border: 'border-nv-red/20' },
    purple: { text: 'text-purple-400', bg: 'bg-purple-400/10', border: 'border-purple-400/20' },
  }
  const c = colors[color] || colors.accent
  return (
    <div className={clsx('nv-card p-4 border', c.border)}>
      <div className="flex items-start justify-between mb-2">
        <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', c.bg)}>
          <Icon className={clsx('w-4 h-4', c.text, pulse && 'animate-pulse')} />
        </div>
        {pulse && <div className="w-2 h-2 rounded-full bg-nv-red animate-pulse" />}
      </div>
      <div className={clsx('text-2xl font-bold font-mono', c.text)}>{value}</div>
      <div className="text-xs text-nv-text font-medium mt-0.5">{label}</div>
      <div className="text-[10px] text-nv-muted mt-0.5">{sub}</div>
    </div>
  )
}

function CameraThumb({ camera, frameData }: any) {
  const isOnline = camera.status === 'online'
  return (
    <Link to={`/cameras/${camera.id}`} className="block">
      <div className="aspect-video bg-nv-bg rounded-lg border border-nv-border overflow-hidden relative group hover:border-nv-accent/30 transition-colors">
        {frameData?.frame ? (
          <img
            src={`data:image/jpeg;base64,${frameData.frame}`}
            alt={camera.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Camera className="w-6 h-6 text-nv-muted" />
          </div>
        )}

        {/* Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-nv-bg/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

        {/* Status dot */}
        <div className={clsx(
          'absolute top-1.5 left-1.5 w-2 h-2 rounded-full',
          isOnline ? 'bg-nv-accent' : 'bg-nv-muted',
          isOnline && 'animate-pulse'
        )} />

        {/* FPS badge */}
        {frameData && (
          <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 bg-nv-bg/80 rounded text-[9px] font-mono text-nv-accent">
            {frameData.fps.toFixed(0)} FPS
          </div>
        )}

        {/* Person count */}
        {frameData && (
          <div className="absolute bottom-1.5 left-1.5 flex items-center gap-1 px-1.5 py-0.5 bg-nv-bg/80 rounded">
            <Users className="w-2.5 h-2.5 text-nv-accent" />
            <span className="text-[9px] font-mono text-nv-text">{frameData.person_count}</span>
          </div>
        )}

        <div className="absolute bottom-1.5 right-1.5 text-[9px] font-medium text-nv-muted bg-nv-bg/80 px-1.5 py-0.5 rounded truncate max-w-[60%]">
          {camera.name}
        </div>
      </div>
    </Link>
  )
}

function ResourceBar({ label, value, sub, color = 'accent' }: any) {
  const colors: any = {
    accent: value > 85 ? '#ff3366' : value > 65 ? '#f59e0b' : '#00ff88',
    purple: '#7c3aed',
  }
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[11px] text-nv-muted">{label}</span>
        <span className="text-[11px] font-mono text-nv-text">{Math.round(value)}%{sub ? ` · ${sub}` : ''}</span>
      </div>
      <div className="h-1.5 bg-nv-border rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${value}%`, backgroundColor: colors[color] }}
        />
      </div>
    </div>
  )
}
