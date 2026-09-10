import React, { useState } from 'react'
import { Settings, Cpu, Video, Bell, Shield, Save, RotateCcw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '../services/api'

export default function SettingsPage() {
  const { data: sysInfo } = useQuery({ queryKey: ['sys-info'], queryFn: systemApi.info })
  const { data: sysStatus } = useQuery({ queryKey: ['sys-status'], queryFn: systemApi.status })

  const [settings, setSettings] = useState({
    confidence_threshold: 0.45,
    iou_threshold: 0.45,
    target_fps: 25,
    jpeg_quality: 85,
    loiter_time: 60,
    abandoned_time: 30,
    crowd_threshold: 0.7,
    max_persons: 50,
    half_precision: true,
    pose_enabled: true,
    trajectory_enabled: true,
    anomaly_enabled: true,
  })

  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // In production, POST to /api/v1/system/settings
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const S = ({ label, id, type = 'number', min, max, step, value, onChange, unit }: any) => (
    <div className="flex items-center justify-between py-2 border-b border-nv-border/50 last:border-0">
      <label htmlFor={id} className="text-xs text-nv-text">{label}</label>
      <div className="flex items-center gap-2">
        {type === 'checkbox' ? (
          <button
            onClick={() => onChange(!value)}
            className={`w-10 h-5 rounded-full transition-colors relative ${value ? 'bg-nv-accent' : 'bg-nv-border'}`}
          >
            <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow ${value ? 'left-5' : 'left-0.5'}`} />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <input
              id={id}
              type="number"
              min={min} max={max} step={step}
              value={value}
              onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) : e.target.value)}
              className="nv-input w-20 text-right text-xs font-mono"
            />
            {unit && <span className="text-[10px] text-nv-muted w-8">{unit}</span>}
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-nv-text flex items-center gap-2">
            <Settings className="w-5 h-5 text-nv-muted" /> Settings
          </h1>
          <p className="text-xs text-nv-muted">Configure AI pipeline and system parameters</p>
        </div>
        <button
          onClick={handleSave}
          className={`nv-btn flex items-center gap-2 transition-all ${saved ? 'bg-nv-accent/20 text-nv-accent border border-nv-accent/30' : 'nv-btn-primary'}`}
        >
          <Save className="w-3.5 h-3.5" />
          {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* AI Detection */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Cpu className="w-4 h-4 text-nv-accent" /> Detection Settings
          </h2>
          <S label="Confidence Threshold" id="conf" min={0.1} max={0.99} step={0.05}
            value={settings.confidence_threshold} unit="ratio"
            onChange={(v: number) => setSettings({ ...settings, confidence_threshold: v })} />
          <S label="IoU Threshold" id="iou" min={0.1} max={0.99} step={0.05}
            value={settings.iou_threshold} unit="ratio"
            onChange={(v: number) => setSettings({ ...settings, iou_threshold: v })} />
          <S label="Half Precision (FP16)" id="half" type="checkbox"
            value={settings.half_precision}
            onChange={(v: boolean) => setSettings({ ...settings, half_precision: v })} />
          <S label="Pose Estimation" id="pose" type="checkbox"
            value={settings.pose_enabled}
            onChange={(v: boolean) => setSettings({ ...settings, pose_enabled: v })} />
          <S label="Trajectory Prediction" id="traj" type="checkbox"
            value={settings.trajectory_enabled}
            onChange={(v: boolean) => setSettings({ ...settings, trajectory_enabled: v })} />
          <S label="Anomaly Detection" id="anom" type="checkbox"
            value={settings.anomaly_enabled}
            onChange={(v: boolean) => setSettings({ ...settings, anomaly_enabled: v })} />
        </div>

        {/* Streaming */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Video className="w-4 h-4 text-nv-cyan" /> Streaming Settings
          </h2>
          <S label="Target FPS" id="fps" min={1} max={60} step={1}
            value={settings.target_fps} unit="fps"
            onChange={(v: number) => setSettings({ ...settings, target_fps: v })} />
          <S label="JPEG Quality" id="jpeg" min={50} max={100} step={5}
            value={settings.jpeg_quality} unit="%"
            onChange={(v: number) => setSettings({ ...settings, jpeg_quality: v })} />
        </div>

        {/* Alert thresholds */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Bell className="w-4 h-4 text-nv-amber" /> Alert Thresholds
          </h2>
          <S label="Loitering Time" id="loiter" min={10} max={600} step={10}
            value={settings.loiter_time} unit="sec"
            onChange={(v: number) => setSettings({ ...settings, loiter_time: v })} />
          <S label="Abandoned Object Time" id="aband" min={10} max={300} step={10}
            value={settings.abandoned_time} unit="sec"
            onChange={(v: number) => setSettings({ ...settings, abandoned_time: v })} />
          <S label="Crowd Congestion Threshold" id="crowd" min={0.1} max={1.0} step={0.05}
            value={settings.crowd_threshold} unit="ratio"
            onChange={(v: number) => setSettings({ ...settings, crowd_threshold: v })} />
          <S label="Max Persons Threshold" id="maxp" min={5} max={500} step={5}
            value={settings.max_persons} unit="persons"
            onChange={(v: number) => setSettings({ ...settings, max_persons: v })} />
        </div>

        {/* System info */}
        <div className="nv-card p-4">
          <h2 className="text-sm font-semibold text-nv-text flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-nv-purple" /> System Information
          </h2>
          {sysInfo ? (
            <div className="space-y-2 text-xs font-mono">
              {[
                ['Platform', sysInfo.platform?.split(' ')[0]],
                ['Python', sysInfo.python],
                ['PyTorch', sysInfo.torch_version],
                ['CUDA', sysInfo.cuda_available ? '✅ Available' : '❌ Not available'],
                ['GPU', sysInfo.cuda_device || 'N/A'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between py-1 border-b border-nv-border/50 last:border-0">
                  <span className="text-nv-muted">{k}</span>
                  <span className="text-nv-text truncate ml-4 max-w-[60%] text-right">{v}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-nv-muted">Loading system info…</p>
          )}

          {sysStatus && (
            <div className="mt-3 pt-3 border-t border-nv-border">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${sysStatus.ai_pipeline_ready ? 'bg-nv-accent' : 'bg-nv-red'}`} />
                <span className="text-xs text-nv-text">
                  AI Pipeline: {sysStatus.ai_pipeline_ready ? 'Ready' : 'Initializing…'}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Reset button */}
      <div className="flex justify-end">
        <button
          onClick={() => setSettings({
            confidence_threshold: 0.45, iou_threshold: 0.45, target_fps: 25,
            jpeg_quality: 85, loiter_time: 60, abandoned_time: 30,
            crowd_threshold: 0.7, max_persons: 50, half_precision: true,
            pose_enabled: true, trajectory_enabled: true, anomaly_enabled: true,
          })}
          className="flex items-center gap-2 text-xs text-nv-muted hover:text-nv-text transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" /> Reset to defaults
        </button>
      </div>
    </div>
  )
}
