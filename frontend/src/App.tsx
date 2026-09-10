import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/dashboard/Layout'
import DashboardPage from './pages/Dashboard'
import CamerasPage from './pages/Cameras'
import IncidentsPage from './pages/Incidents'
import AnalyticsPage from './pages/Analytics'
import CameraDetailPage from './pages/CameraDetail'
import SettingsPage from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="cameras" element={<CamerasPage />} />
        <Route path="cameras/:id" element={<CameraDetailPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
