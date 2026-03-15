import { Outlet } from 'react-router-dom'
import { CompanyProvider } from '../contexts/CompanyContext'
import Sidebar from '../components/Sidebar'

export default function CompanyLayout() {
  return (
    <CompanyProvider>
      <div style={{ display: 'flex', minHeight: 'calc(100vh - 56px)', background: 'var(--bg-base)' }}>
        <Sidebar />
        <main style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
          <Outlet />
        </main>
      </div>
    </CompanyProvider>
  )
}
