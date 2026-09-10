import { useEffect, useRef, useCallback } from 'react'
import { useNVStore } from '../store'

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000`

// ─── Camera Stream WebSocket ───────────────────────────────────────────────

export function useCameraStream(cameraId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  const setFrameData = useNVStore((s) => s.setFrameData)
  const addAlert = useNVStore((s) => s.addAlert)

  useEffect(() => {
    if (!cameraId) return

    const ws = new WebSocket(`${WS_BASE}/ws/stream/${cameraId}`)
    wsRef.current = ws

    ws.onopen = () => {
      console.log(`[WS] Stream connected: ${cameraId}`)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'frame') {
          setFrameData(cameraId, data)
          // Surface any alerts from this frame
          if (data.alerts?.length) {
            data.alerts.forEach((a: any) => addAlert({ ...a, timestamp: data.timestamp }))
          }
        }
      } catch (e) {
        // ignore parse errors
      }
    }

    ws.onerror = (e) => console.error(`[WS] Stream error ${cameraId}:`, e)
    ws.onclose = () => console.log(`[WS] Stream disconnected: ${cameraId}`)

    // Keepalive ping
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'ping' }))
      }
    }, 15000)

    return () => {
      clearInterval(pingInterval)
      ws.close()
    }
  }, [cameraId])

  const sendAction = useCallback((action: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action }))
    }
  }, [])

  return { sendAction }
}

// ─── Global Events WebSocket ──────────────────────────────────────────────

export function useGlobalEvents() {
  const wsRef = useRef<WebSocket | null>(null)
  const addAlert = useNVStore((s) => s.addAlert)
  const setMetrics = useNVStore((s) => s.setMetrics)
  const addIncident = useNVStore((s) => s.addIncident)

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>
    let ws: WebSocket

    function connect() {
      ws = new WebSocket(`${WS_BASE}/ws/events`)
      wsRef.current = ws

      ws.onopen = () => console.log('[WS] Events connected')

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          switch (data.type) {
            case 'alert':
              addAlert(data)
              break
            case 'system_metrics':
              setMetrics(data)
              break
            case 'incident':
              addIncident(data)
              break
            case 'heartbeat':
            case 'pong':
              break
          }
        } catch (e) {
          // ignore
        }
      }

      ws.onclose = () => {
        console.log('[WS] Events disconnected. Reconnecting in 3s…')
        reconnectTimeout = setTimeout(connect, 3000)
      }

      ws.onerror = () => ws.close()
    }

    connect()

    const pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'ping' }))
      }
    }, 20000)

    return () => {
      clearInterval(pingInterval)
      clearTimeout(reconnectTimeout)
      ws?.close()
    }
  }, [])
}
