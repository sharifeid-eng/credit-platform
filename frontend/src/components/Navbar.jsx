import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  return (
    <nav style={{
      background: 'var(--bg-nav)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 28px',
      height: '52px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Left — Logo */}
      <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 10 }}>
        <LogoMark />
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            ACP Private Credit
          </div>
          <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--gold)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Portfolio Analytics
          </div>
        </div>
      </Link>

      {/* Right — Status chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <LiveDot />
        <Chip>v1.0</Chip>
        <Chip highlight>Sharif Eid</Chip>
      </div>
    </nav>
  )
}

function LogoMark() {
  return (
    <div style={{
      width: 30, height: 30,
      background: 'linear-gradient(135deg, #C9A84C, #8A6D2E)',
      borderRadius: 8,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 9, fontWeight: 800, color: '#000',
      letterSpacing: '0.05em',
      flexShrink: 0,
      boxShadow: '0 2px 8px rgba(201,168,76,0.25)',
    }}>
      ACP
    </div>
  )
}

function LiveDot() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        width: 5, height: 5, borderRadius: '50%',
        background: 'var(--teal)',
        boxShadow: 'var(--shadow-glow-teal)',
        animation: 'pulse 2s infinite',
      }} />
      <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--teal)', fontFamily: 'var(--font-mono)' }}>
        Live
      </span>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}

function Chip({ children, highlight }) {
  return (
    <div style={{
      fontSize: 10,
      padding: '3px 10px',
      borderRadius: 20,
      border: '1px solid var(--border)',
      color: highlight ? 'var(--text-secondary)' : 'var(--text-muted)',
      background: highlight ? 'var(--bg-surface)' : 'transparent',
      fontFamily: 'var(--font-mono)',
      letterSpacing: '0.02em',
    }}>
      {children}
    </div>
  )
}