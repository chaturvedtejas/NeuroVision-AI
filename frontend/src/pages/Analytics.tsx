import React, { useState } from 'react'
import { BarChart2, TrendingUp, Users, Activity, Clock } from 'lucide-react'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, PieChart, Pie, Cell
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '../services/api'
import { useNVStore } from '../store'
import { clsx } from 'clsx'

const COLORS = ['#00ff88', '#00d4ff', '#7c3aed', '#f59e0b', '#ff3366', '#10b981']

export default function AnalyticsPage() {
  const cameras = useNVStore((s) => s.cameras)
  const [selectedCamera, setSelectedCamera] = useState<string>(cameras[0]?.id || '')
  const [timeWindow, setTimeWindow] = useState(24)
  const frameData = useNVStore((s) => s.frameData)

  const { data: incidentTimeline = [] } = useQuery({
    queryKey: ['incident-timeline', selectedCamera, timeWindow],
    queryFn: () => analyticsApi.incidentTimeline(selectedCamera || undefined, timeWindow),
    refetchInterval: 30000,
  })

  const { data: crowdData = [] } = useQuery({
    queryKey: ['crowd', selectedCamera],
    queryFn: () => analyticsApi.crowd(selectedCamera, 1),
    enabled: !!selectedCamera,
    refetchInterval: 15000,
  })

  const { data: sysMetrics = [] } = useQuery({
    queryKey: ['sys-metrics'],
    queryFn: () => analyticsApi.systemMetrics(1),
    refetchInterval: 10000,
  })

  const { data: incidentSummary = [] } = useQuery({
    queryKey: ['incident-summary-analytics'],
    queryFn: () => import('../services/api').then(({ incidentsApi }) => incidentsApi.summary()),
    refetchInterval: 60000,
  })

  // Build incident type pie data
  const pieData = incidentSummary.reduce((acc: any[], row: any) => {
    const existing = acc.find((a) => a.name === row.incident_type)
    if (existing) existing.value += row.count
    else acc.push({ name: row.incident_type.replace(/_/g, ' '), value: row.count })
    return acc
  }, [])

  // Format crowd data for chart
  const crowdChartData = crowdData.map((d: any) => ({
    time: new Date(d.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
    persons: d.person_count,
    congestion: Math.round(d.congestion_score * 100),
  }))

  // Format system metrics
  const sysChartData = sysMetrics.slice(-60).map((m: any) => ({
    time: new Date(m.timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
    cpu: Math.round(m.cpu_percent),
    ram: Math.round(m.memory_percent),
    gpu: m.gpu_percent ? Math.round(m.gpu_percent) : null,
    fps: Math.round(m.total_fps * 10) / 10,
    cameras: m.active_cameras,
  }))

  // Incident hourly breakdown
  const incidentsByHour = Array.from({ length: 24 }, (_, h) => ({
    hour: `${String(h).padStart(2, '0')}:00`,
    count: incidentTimeline.filter((i: any) => new Date(i.created_at).getHours() === h).length,
  }))

  const CUSTOM_TOOLTIP = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-nv-card border border-nv-border rounded-lg px-3 py-2 text-xs shadow-xl">
        <p className="font-mono text-nv-muted mb-1">{label}</p>
        {payload.map((p: any) => (
          <p key={p.dataKey} style={{ color: p.color }}>{p.name}: {p.value}</p>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nv-text flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-nv-cyan" /> Analytics
          </h1>
          <p className="text-xs text-nv-muted">Historical insights and trend analysis</p>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="nv-input w-auto text-xs"
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(e.target.value)}
          >
            <option value="">All Cameras</option>
            {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>

          <div className="flex rounded-lg overflow-hidden border border-nv-border">
            {[1, 6, 24, 168].map((h) => (
              <button key={h} onClick={() => setTimeWindow(h)}
                className={clsx('px-3 py-1.5 text-xs transition-colors',
                  timeWindow === h ? 'bg-nv-accent text-nv-bg font-semibold' : 'text-nv-muted hover:text-nv-text'
                )}>
                {h === 1 ? '1h' : h === 6 ? '6h' : h === 24 ? '24h' : '7d'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Top row: system metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-nv-purple" /> System Performance (1h)
          </h2>
          {sysChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={sysChartData} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6b7280' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} domain={[0, 100]} />
                <Tooltip content={<CUSTOM_TOOLTIP />} />
                <Legend iconSize={8} iconType="circle" wrapperStyle={{ fontSize: 10 }} />
                <Line dataKey="cpu" name="CPU %" stroke="#00ff88" dot={false} strokeWidth={1.5} />
                <Line dataKey="ram" name="RAM %" stroke="#00d4ff" dot={false} strokeWidth={1.5} />
                {sysChartData.some((d: any) => d.gpu !== null) && (
                  <Line dataKey="gpu" name="GPU %" stroke="#7c3aed" dot={false} strokeWidth={1.5} />
                )}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>

        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-nv-accent" /> Processing FPS (1h)
          </h2>
          {sysChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={sysChartData} margin={{ left: -20 }}>
                <defs>
                  <linearGradient id="fpsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00ff88" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6b7280' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} />
                <Tooltip content={<CUSTOM_TOOLTIP />} />
                <Area dataKey="fps" name="FPS" stroke="#00ff88" fill="url(#fpsGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>
      </div>

      {/* Middle row: crowd + incident hourly */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Users className="w-4 h-4 text-nv-cyan" /> Crowd Density (1h)
          </h2>
          {crowdChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={crowdChartData} margin={{ left: -20 }}>
                <defs>
                  <linearGradient id="crowdGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="congGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff3366" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ff3366" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#6b7280' }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} />
                <Tooltip content={<CUSTOM_TOOLTIP />} />
                <Legend iconSize={8} iconType="circle" wrapperStyle={{ fontSize: 10 }} />
                <Area dataKey="persons" name="Persons" stroke="#00d4ff" fill="url(#crowdGrad)" strokeWidth={2} dot={false} />
                <Area dataKey="congestion" name="Congestion %" stroke="#ff3366" fill="url(#congGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No crowd data yet" />
          )}
        </div>

        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-nv-amber" /> Incidents by Hour
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={incidentsByHour} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="hour" tick={{ fontSize: 8, fill: '#6b7280' }} interval={3} />
              <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} />
              <Tooltip content={<CUSTOM_TOOLTIP />} />
              <Bar dataKey="count" name="Incidents" fill="#f59e0b" radius={[2, 2, 0, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom row: incident type breakdown pie + live snapshot */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text mb-3">Incident Type Distribution</h2>
          {pieData.length > 0 ? (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="50%" height={180}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70}
                    paddingAngle={3} dataKey="value">
                    {pieData.map((_: any, i: number) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<CUSTOM_TOOLTIP />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-1.5">
                {pieData.slice(0, 6).map((d: any, i: number) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                    <span className="text-[10px] text-nv-text flex-1 truncate">{d.name}</span>
                    <span className="text-[10px] font-mono text-nv-muted">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyChart message="No incident data" />
          )}
        </div>

        {/* Live snapshot table */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text mb-3">Live Camera Snapshot</h2>
          <div className="space-y-2">
            {Object.entries(frameData).length === 0 && (
              <p className="text-xs text-nv-muted text-center py-8">No live cameras running</p>
            )}
            {Object.entries(frameData).map(([camId, fd]) => (
              <div key={camId} className="flex items-center gap-3 px-3 py-2 bg-nv-bg rounded-lg border border-nv-border">
                <div className="w-2 h-2 rounded-full bg-nv-accent animate-pulse flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] font-mono text-nv-muted truncate">{camId.slice(0, 16)}…</p>
                </div>
                <div className="flex items-center gap-4 text-[10px] font-mono">
                  <span className="text-nv-accent">{fd.fps.toFixed(0)} FPS</span>
                  <span className="text-nv-cyan">{fd.person_count} 👤</span>
                  <span className="text-nv-muted">{fd.inference_ms.toFixed(0)}ms</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function EmptyChart({ message = 'Waiting for data…' }: { message?: string }) {
  return (
    <div className="h-44 flex items-center justify-center">
      <p className="text-xs text-nv-muted">{message}</p>
    </div>
  )
}
