import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()

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
        <LaithLogo size="nav" />
        <div style={{
          fontSize: 9, fontWeight: 600,
          color: 'var(--gold)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        }}>
          Portfolio Analytics
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

function LaithLogo({ size = 'nav' }) {
  const isNav = size === 'nav'
  const h = isNav ? 30 : 44

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: isNav ? 8 : 10,
      height: h,
    }}>
      {/* Icon mark — lion */}
      <div style={{
        width: h, height: h,
        background: 'linear-gradient(135deg, var(--gold), #8A6D2E)',
        borderRadius: isNav ? 8 : 10,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: isNav ? 22 : 32,
        lineHeight: 1,
        flexShrink: 0,
        boxShadow: '0 2px 8px rgba(201,168,76,0.25)',
      }}>
        🦁
      </div>
      {/* Wordmark */}
      <div style={{ display: 'flex', alignItems: 'baseline' }}>
        <span style={{
          fontSize: isNav ? 18 : 28,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)',
        }}>
          L
        </span>
        <span style={{
          fontSize: isNav ? 18 : 28,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--gold)',
          fontFamily: 'var(--font-ui)',
        }}>
          AI
        </span>
        <span style={{
          fontSize: isNav ? 18 : 28,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)',
        }}>
          TH
        </span>
      </div>
    </div>
  )
}

export { LaithLogo }

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