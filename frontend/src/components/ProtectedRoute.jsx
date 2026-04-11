import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute({ children, requireAdmin = false }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--bg-base)',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-ui)',
        fontSize: 14,
      }}>
        Loading...
      </div>
    )
  }

  if (!user) {
    // Not authenticated — Cloudflare Access should handle this,
    // but if we somehow got here without auth, redirect to home
    // which will trigger Cloudflare's login page
    return <Navigate to="/" replace />
  }

  if (requireAdmin && user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return children
}
