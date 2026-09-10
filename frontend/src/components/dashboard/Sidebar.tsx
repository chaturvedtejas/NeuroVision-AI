import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Camera, ShieldAlert, BarChart3,
  Settings, Activity, Eye, ChevronLeft, ChevronRight, Cpu
} from 'lucide-react'
import { clsx } from 'clsx'
import { useNVStore } from '../../store'

const NAV_ITEMS = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard',  badge: null },
  { to: '/cameras',    icon: Camera,          label: 'Cameras',    badge: null },
  { to: '/incidents',  icon: ShieldAlert,     label: 'Incidents',  badge: 'alerts' },
  { to: '/analytics',  icon: BarChart3,       label: 'Analytics',  badge: null },
  { to: '/settings',   icon: Settings,        label: 'Settings',   badge: null },
]

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar, alerts, metrics } = useNVStore((s) => ({
    sidebarOpen: s.sidebarOpen,
    toggleSidebar: s.toggleSidebar,
    alerts: s.alerts,
    metrics: s.metrics,
  }))

  const activeAlerts = alerts.filter((a) => a.severity === 'critical' || a.severity === 'high').length

  return (
    <aside
      className={clsx(
        'flex flex-col bg-nv-surface border-r border-nv-border transition-all duration-300 relative z-10',
        sidebarOpen ? 'w-56' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-nv-border">
        <div className="relative flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-nv-accent/10 border border-nv-accent/30 flex items-center justify-center">
            <Eye className="w-4 h-4 text-nv-accent" />
          </div>
          <div className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-nv-accent animate-pulse" />
        </div>
        {sidebarOpen && (
          <div>
            <div className="text-sm font-bold text-gradient-accent leading-tight">NeuroVision</div>
            <div className="text-[10px] text-nv-muted font-mono">AI SURVEILLANCE</div>
          </div>
        )}
      </div>

      {/* System status pill */}
      {sidebarOpen && metrics && (
        <div className="mx-3 mt-3 px-3 py-2 rounded-lg bg-nv-bg border border-nv-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-nv-muted font-mono">SYSTEM</span>
            <Cpu className="w-3 h-3 text-nv-muted" />
          </div>
          <div className="flex gap-3">
            <StatPill label="CPU" value={metrics.cpu_percent} />
            <StatPill label="RAM" value={metrics.memory_percent} />
            {metrics.gpu_percent !== null && (
              <StatPill label="GPU" value={metrics.gpu_percent} />
            )}
          </div>
        </div>
      )}

      {/* Nav links */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label, badge }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 group relative',
                isActive
                  ? 'bg-nv-accent/10 text-nv-accent border border-nv-accent/20'
                  : 'text-nv-muted hover:text-nv-text hover:bg-nv-border/50'
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={clsx('w-4 h-4 flex-shrink-0', isActive && 'drop-shadow-[0_0_6px_rgba(0,255,136,0.8)]')} />
                {sidebarOpen && (
                  <span className="text-sm font-medium flex-1">{label}</span>
                )}
                {badge === 'alerts' && activeAlerts > 0 && (
                  <span className={clsx(
                    'flex-shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-nv-red text-white',
                    !sidebarOpen && 'absolute -top-1 -right-1 w-4 h-4 flex items-center justify-center p-0'
                  )}>
                    {activeAlerts > 99 ? '99+' : activeAlerts}
                  </span>
                )}
                {!sidebarOpen && (
                  <div className="absolute left-full ml-2 px-2 py-1 bg-nv-card border border-nv-border rounded text-xs text-nv-text opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                    {label}
                  </div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center w-8 h-8 mx-auto mb-4 rounded-lg border border-nv-border text-nv-muted hover:text-nv-text hover:border-nv-accent/30 transition-all"
      >
        {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>
    </aside>
  )
}

function StatPill({ label, value }: { label: string; value: number }) {
  const color = value > 80 ? 'text-nv-red' : value > 60 ? 'text-nv-amber' : 'text-nv-accent'
  return (
    <div className="flex flex-col items-center">
      <span className={`text-[10px] font-bold font-mono ${color}`}>{Math.round(value)}%</span>
      <span className="text-[9px] text-nv-muted">{label}</span>
    </div>
  )
}
