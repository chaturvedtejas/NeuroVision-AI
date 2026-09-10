import React, { useState } from 'react'
import { Bell, Activity, Wifi, WifiOff, Clock } from 'lucide-react'
import { useNVStore } from '../../store'
import { clsx } from 'clsx'

export default function TopBar() {
  const { metrics, alerts, cameras } = useNVStore((s) => ({
    metrics: s.metrics,
    alerts: s.alerts,
    cameras: s.cameras,
  }))

  const [showAlerts, setShowAlerts] = useState(false)
  const activeAlerts = alerts.slice(0, 10)
  const onlineCams = cameras.filter((c) => c.status === 'online').length
  const now = new Date()

  return (
    <header className="flex items-center justify-between px-4 py-2.5 bg-nv-surface border-b border-nv-border flex-shrink-0">
      {/* Left: breadcrumb/title injected by pages */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-nv-accent" />
          <span className="text-xs font-mono text-nv-muted">
            {onlineCams}/{cameras.length} CAMERAS
          </span>
        </div>

        {metrics && (
          <>
            <div className="w-px h-4 bg-nv-border" />
            <div className="flex items-center gap-3 text-xs font-mono">
              <MetricChip label="CPU" value={metrics.cpu_percent} unit="%" />
              <MetricChip label="RAM" value={metrics.memory_percent} unit="%" />
              {metrics.gpu_percent !== null && (
                <MetricChip label="GPU" value={metrics.gpu_percent} unit="%" />
              )}
              <MetricChip label="FPS" value={metrics.avg_fps} unit="" noColor />
            </div>
          </>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {/* Clock */}
        <div className="flex items-center gap-1.5 text-xs font-mono text-nv-muted">
          <Clock className="w-3 h-3" />
          {now.toLocaleTimeString('en-US', { hour12: false })}
        </div>

        {/* Connection status */}
        <div className={clsx(
          'flex items-center gap-1.5 text-xs',
          metrics ? 'text-nv-accent' : 'text-nv-muted'
        )}>
          {metrics ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          <span className="font-mono">{metrics ? 'LIVE' : 'OFFLINE'}</span>
        </div>

        {/* Alert bell */}
        <div className="relative">
          <button
            onClick={() => setShowAlerts(!showAlerts)}
            className={clsx(
              'relative p-1.5 rounded-lg border transition-all',
              alerts.length > 0
                ? 'border-nv-red/30 bg-nv-red/10 text-nv-red'
                : 'border-nv-border text-nv-muted hover:text-nv-text'
            )}
          >
            <Bell className="w-4 h-4" />
            {alerts.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-nv-red text-white text-[9px] font-bold flex items-center justify-center">
                {alerts.length > 9 ? '9+' : alerts.length}
              </span>
            )}
          </button>

          {showAlerts && (
            <div className="absolute right-0 top-10 w-80 bg-nv-card border border-nv-border rounded-xl shadow-2xl z-50 animate-fade-in">
              <div className="flex items-center justify-between px-3 py-2 border-b border-nv-border">
                <span className="text-xs font-semibold text-nv-text">Recent Alerts</span>
                <button
                  onClick={() => useNVStore.getState().clearAlerts()}
                  className="text-[10px] text-nv-muted hover:text-nv-red transition-colors"
                >
                  Clear all
                </button>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-nv-border">
                {activeAlerts.length === 0 ? (
                  <div className="px-3 py-4 text-xs text-nv-muted text-center">No alerts</div>
                ) : (
                  activeAlerts.map((alert, i) => (
                    <div key={i} className="px-3 py-2.5 hover:bg-nv-surface transition-colors">
                      <div className="flex items-start gap-2">
                        <div className={clsx(
                          'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                          alert.severity === 'critical' ? 'bg-red-400' :
                          alert.severity === 'high' ? 'bg-orange-400' :
                          alert.severity === 'medium' ? 'bg-yellow-400' : 'bg-blue-400'
                        )} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-nv-text truncate">{alert.title}</p>
                          <p className="text-[10px] text-nv-muted mt-0.5 line-clamp-2">{alert.description}</p>
                          <p className="text-[9px] text-nv-muted mt-1 font-mono">{alert.camera_name}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

function MetricChip({ label, value, unit, noColor }: { label: string; value: number; unit: string; noColor?: boolean }) {
  const color = noColor ? 'text-nv-cyan' : value > 85 ? 'text-nv-red' : value > 65 ? 'text-nv-amber' : 'text-nv-accent'
  return (
    <span className={`${color}`}>
      {label} <span className="opacity-70">{Math.round(value)}{unit}</span>
    </span>
  )
}
