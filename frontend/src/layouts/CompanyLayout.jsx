import { Outlet } from 'react-router-dom'
import { CompanyProvider } from '../contexts/CompanyContext'
import Sidebar from '../components/Sidebar'
import useBreakpoint from '../hooks/useBreakpoint'
import { useMobileMenu } from '../contexts/MobileMenuContext'

export default function CompanyLayout() {
  const { isMobile } = useBreakpoint()
  const { isOpen, close } = useMobileMenu()

  return (
    <CompanyProvider>
      <div style={{ display: 'flex', minHeight: 'calc(100vh - var(--navbar-height))', background: 'var(--bg-base)' }}>
        {/* Mobile backdrop */}
        {isMobile && isOpen && (
          <div
            onClick={close}
            style={{
              position: 'fixed', inset: 0, zIndex: 190,
              background: 'rgba(0,0,0,0.6)',
              transition: 'opacity 0.25s',
            }}
          />
        )}
        <Sidebar />
        <main style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
          <Outlet />
        </main>
      </div>
    </CompanyProvider>
  )
}
