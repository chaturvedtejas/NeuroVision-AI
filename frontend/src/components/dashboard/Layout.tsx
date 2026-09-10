import React, { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import AlertToaster from '../alerts/AlertToaster'
import { useGlobalEvents } from '../../hooks/useWebSocket'
import { useNVStore } from '../../store'
import { camerasApi } from '../../services/api'

export default function Layout() {
  // Connect to global event WebSocket
  useGlobalEvents()

  const setCameras = useNVStore((s) => s.setCameras)

  // Initial camera fetch
  useEffect(() => {
    camerasApi.list()
      .then((cameras) => setCameras(cameras))
      .catch(console.error)
  }, [])

  return (
    <div className="flex h-screen bg-nv-bg overflow-hidden grid-bg">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
      <AlertToaster />
    </div>
  )
}
