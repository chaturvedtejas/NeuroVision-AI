import React, { useEffect, useRef } from 'react'
import { X, AlertTriangle, ShieldAlert, Zap, Info } from 'lucide-react'
import { clsx } from 'clsx'
import { useNVStore, Alert } from '../../store'

const SEVERITY_CONFIG = {
  critical: { icon: Zap, bg: 'bg-red-500/10', border: 'border-red-500/40', text: 'text-red-400', dot: 'bg-red-400' },
  high: { icon: ShieldAlert, bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400', dot: 'bg-orange-400' },
  medium: { icon: AlertTriangle, bg: 'bg-yellow-500/10', border: 'border-yellow-500/40', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  low: { icon: Info, bg: 'bg-blue-500/10', border: 'border-blue-500/40', text: 'text-blue-400', dot: 'bg-blue-400' },
}

// Stateful toast queue — only show the latest few
const MAX_TOASTS = 3

export default function AlertToaster() {
  const alerts = useNVStore((s) => s.alerts)
  // Show only the newest MAX_TOASTS alerts that arrived in last 8 seconds
  const now = Date.now() / 1000
  const recentAlerts = alerts
    .filter((a) => now - a.timestamp < 8)
    .slice(0, MAX_TOASTS)

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {recentAlerts.map((alert, i) => (
        <AlertToast key={`${alert.timestamp}-${i}`} alert={alert} />
      ))}
    </div>
  )
}

function AlertToast({ alert }: { alert: Alert }) {
  const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low
  const Icon = cfg.icon

  return (
    <div className={clsx(
      'pointer-events-auto flex items-start gap-3 p-3 rounded-xl border backdrop-blur-sm',
      'min-w-72 max-w-sm animate-slide-in shadow-2xl',
      cfg.bg, cfg.border
    )}>
      <div className={clsx('w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5', cfg.bg)}>
        <Icon className={clsx('w-3.5 h-3.5', cfg.text)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={clsx('text-[10px] font-bold uppercase tracking-wider', cfg.text)}>
            {alert.severity}
          </span>
          <span className="text-[10px] text-nv-muted">{alert.camera_name}</span>
        </div>
        <p className="text-xs font-semibold text-nv-text leading-snug">{alert.title}</p>
        <p className="text-[10px] text-nv-muted mt-0.5 line-clamp-2">{alert.description}</p>
      </div>
      <div className={clsx('w-2 h-2 rounded-full flex-shrink-0 mt-1', cfg.dot, alert.severity === 'critical' && 'alert-pulse')} />
    </div>
  )
}
