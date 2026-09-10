import React, { useState } from 'react'
import {
  ShieldAlert, Filter, CheckCircle, Trash2, Search,
  AlertTriangle, Zap, Info, ChevronDown, Clock
} from 'lucide-react'
import { clsx } from 'clsx'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { incidentsApi } from '../services/api'

const SEVERITY_CFG: Record<string, { label: string; icon: any; cls: string; dot: string }> = {
  critical: { label: 'Critical', icon: Zap,           cls: 'nv-badge-critical', dot: 'bg-red-400' },
  high:     { label: 'High',     icon: ShieldAlert,   cls: 'nv-badge-high',     dot: 'bg-orange-400' },
  medium:   { label: 'Medium',   icon: AlertTriangle, cls: 'nv-badge-medium',   dot: 'bg-yellow-400' },
  low:      { label: 'Low',      icon: Info,          cls: 'nv-badge-low',      dot: 'bg-blue-400' },
}

const INCIDENT_TYPE_LABELS: Record<string, string> = {
  fighting:           '⚔️ Fighting',
  running:            '🏃 Running',
  falling:            '⬇️ Falling',
  fallen:             '🆘 Fallen',
  loitering:          '⏱️ Loitering',
  suspicious_movement:'👁️ Suspicious',
  abandoned_object:   '🎒 Abandoned Object',
  intrusion:          '🚫 Intrusion',
  crowd_congestion:   '👥 Crowd Congestion',
  anomaly:            '⚠️ Anomaly',
  object_detection:   '📦 Object Detected',
}

export default function IncidentsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const params: any = { limit: 100 }
  if (filterSeverity) params.severity = filterSeverity
  if (filterType) params.incident_type = filterType
  if (filterStatus) params.status = filterStatus

  const { data: incidents = [], isLoading, refetch } = useQuery({
    queryKey: ['incidents', params],
    queryFn: () => incidentsApi.list(params),
    refetchInterval: 10000,
  })

  const ackMutation = useMutation({
    mutationFn: (id: string) => incidentsApi.acknowledge(id, { resolved_by: 'operator' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['incidents'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => incidentsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['incidents'] }),
  })

  const filtered = incidents.filter((inc: any) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      inc.title?.toLowerCase().includes(q) ||
      inc.description?.toLowerCase().includes(q) ||
      inc.camera_id?.toLowerCase().includes(q)
    )
  })

  const critCount = incidents.filter((i: any) => i.severity === 'critical').length
  const activeCount = incidents.filter((i: any) => i.status === 'active').length

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nv-text flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-nv-red" />
            Incident Log
          </h1>
          <p className="text-xs text-nv-muted">
            {activeCount} active · {critCount} critical · {incidents.length} total
          </p>
        </div>
        <button onClick={() => refetch()} className="nv-btn-secondary text-xs">Refresh</button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-2">
        {['critical', 'high', 'medium', 'low'].map((sev) => {
          const cfg = SEVERITY_CFG[sev]
          const count = incidents.filter((i: any) => i.severity === sev).length
          return (
            <button
              key={sev}
              onClick={() => setFilterSeverity(filterSeverity === sev ? '' : sev)}
              className={clsx(
                'nv-card p-3 text-left transition-all',
                filterSeverity === sev && 'border-nv-accent/30 bg-nv-accent/5'
              )}
            >
              <div className={clsx('text-xl font-bold font-mono', {
                critical: 'text-red-400', high: 'text-orange-400',
                medium: 'text-yellow-400', low: 'text-blue-400',
              }[sev])}>{count}</div>
              <div className="text-[10px] text-nv-muted mt-0.5">{cfg.label}</div>
            </button>
          )
        })}
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-nv-muted" />
          <input
            className="nv-input pl-8"
            placeholder="Search incidents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="nv-input w-auto text-xs"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All Types</option>
          {Object.entries(INCIDENT_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>

        <select
          className="nv-input w-auto text-xs"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
          <option value="false_positive">False Positive</option>
        </select>

        {(filterSeverity || filterType || filterStatus || search) && (
          <button
            onClick={() => { setFilterSeverity(''); setFilterType(''); setFilterStatus(''); setSearch('') }}
            className="text-xs text-nv-muted hover:text-nv-red transition-colors px-2 py-1.5"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-12 text-nv-muted text-sm">Loading incidents…</div>
      ) : (
        <div className="nv-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-nv-border">
                  {['Severity', 'Type', 'Title', 'Camera', 'Confidence', 'Status', 'Time', 'Actions'].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-[10px] font-semibold text-nv-muted uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-nv-border/50">
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3 py-12 text-center text-sm text-nv-muted">
                      No incidents found
                    </td>
                  </tr>
                )}
                {filtered.map((inc: any) => {
                  const cfg = SEVERITY_CFG[inc.severity] || SEVERITY_CFG.low
                  const isExpanded = expandedId === inc.id
                  return (
                    <React.Fragment key={inc.id}>
                      <tr
                        className="hover:bg-nv-surface/50 transition-colors cursor-pointer"
                        onClick={() => setExpandedId(isExpanded ? null : inc.id)}
                      >
                        {/* Severity */}
                        <td className="px-3 py-2.5">
                          <span className={clsx('nv-badge', cfg.cls)}>
                            {inc.severity}
                          </span>
                        </td>

                        {/* Type */}
                        <td className="px-3 py-2.5">
                          <span className="text-xs text-nv-text">
                            {INCIDENT_TYPE_LABELS[inc.incident_type] || inc.incident_type}
                          </span>
                        </td>

                        {/* Title */}
                        <td className="px-3 py-2.5 max-w-xs">
                          <div className="flex items-center gap-1.5">
                            <div className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', cfg.dot)} />
                            <span className="text-xs text-nv-text truncate">{inc.title}</span>
                          </div>
                        </td>

                        {/* Camera */}
                        <td className="px-3 py-2.5">
                          <span className="text-[10px] font-mono text-nv-muted">{inc.camera_id?.slice(0, 8)}…</span>
                        </td>

                        {/* Confidence */}
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <div className="w-12 h-1 bg-nv-border rounded overflow-hidden">
                              <div
                                className="h-full bg-nv-accent rounded"
                                style={{ width: `${inc.confidence_score * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] font-mono text-nv-muted">
                              {(inc.confidence_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-3 py-2.5">
                          <span className={clsx('text-[10px] font-mono px-2 py-0.5 rounded', {
                            'active':        'text-nv-red bg-nv-red/10',
                            'acknowledged':  'text-nv-amber bg-nv-amber/10',
                            'resolved':      'text-nv-accent bg-nv-accent/10',
                            'false_positive':'text-nv-muted bg-nv-border',
                          }[inc.status] || 'text-nv-muted')}>
                            {inc.status}
                          </span>
                        </td>

                        {/* Time */}
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1 text-[10px] font-mono text-nv-muted">
                            <Clock className="w-3 h-3" />
                            {new Date(inc.created_at).toLocaleTimeString('en-US', {
                              hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
                            })}
                          </div>
                        </td>

                        {/* Actions */}
                        <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center gap-1">
                            {inc.status === 'active' && (
                              <button
                                onClick={() => ackMutation.mutate(inc.id)}
                                disabled={ackMutation.isPending}
                                className="p-1 text-nv-muted hover:text-nv-accent border border-nv-border rounded transition-colors"
                                title="Acknowledge"
                              >
                                <CheckCircle className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <button
                              onClick={() => { if (confirm('Delete incident?')) deleteMutation.mutate(inc.id) }}
                              className="p-1 text-nv-muted hover:text-nv-red border border-nv-border rounded transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                            <ChevronDown className={clsx('w-3.5 h-3.5 text-nv-muted transition-transform', isExpanded && 'rotate-180')} />
                          </div>
                        </td>
                      </tr>

                      {/* Expanded row */}
                      {isExpanded && (
                        <tr className="bg-nv-surface/50">
                          <td colSpan={8} className="px-4 py-3">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                              <div>
                                <p className="text-nv-muted text-[10px] uppercase mb-1">Description</p>
                                <p className="text-nv-text">{inc.description || '—'}</p>
                              </div>
                              <div>
                                <p className="text-nv-muted text-[10px] uppercase mb-1">AI Summary</p>
                                <p className="text-nv-text">{inc.ai_summary || '—'}</p>
                              </div>
                              <div>
                                <p className="text-nv-muted text-[10px] uppercase mb-1">Incident ID</p>
                                <p className="font-mono text-nv-muted">{inc.id}</p>
                                <p className="text-nv-muted text-[10px] mt-1">
                                  {new Date(inc.created_at).toLocaleString()}
                                </p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>

          {filtered.length > 0 && (
            <div className="px-3 py-2 border-t border-nv-border flex items-center justify-between">
              <span className="text-[10px] text-nv-muted">
                Showing {filtered.length} of {incidents.length} incidents
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
