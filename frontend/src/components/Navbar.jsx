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
      height: '104px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Left — Logo */}
      <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 14 }}>
        <LaithLogo size="nav" />
        <div style={{
          fontSize: 14,
          fontWeight: 600,
          color: 'var(--gold)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
        }}>
          Portfolio Analytics
        </div>
      </Link>

      {/* Right — Nav link + Status chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Link to="/methodology" style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          textDecoration: 'none',
          fontSize: 11,
          fontWeight: 600,
          color: pathname === '/methodology' ? 'var(--gold)' : 'var(--text-muted)',
          transition: 'color 0.2s',
          letterSpacing: '0.04em',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          Methodology
        </Link>
        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />
        <LiveDot />
        <Chip>v1.0</Chip>
        <Chip highlight>Sharif Eid</Chip>
      </div>
    </nav>
  )
}

function LaithLogo({ size = 'nav' }) {
  const isNav = size === 'nav'
  const h = isNav ? 60 : 44

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: isNav ? 12 : 10,
      height: h,
    }}>
      {/* Icon mark — lion */}
      <div style={{
        width: h,
        height: h,
        borderRadius: isNav ? 12 : 10,
        overflow: 'hidden',
        flexShrink: 0,
        boxShadow: '0 2px 8px rgba(201,168,76,0.25)',
        background: '#000',
      }}>
        <img
          src="/lion.png"
          alt="Laith"
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
          }}
        />
      </div>

      {/* Wordmark */}
      <div style={{ display: 'flex', alignItems: 'baseline' }}>
        <span style={{
          fontSize: isNav ? 30 : 28,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)',
        }}>
          L
        </span>
        <span style={{
          fontSize: isNav ? 30 : 28,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--gold)',
          fontFamily: 'var(--font-ui)',
        }}>
          AI
        </span>
        <span style={{
          fontSize: isNav ? 30 : 28,
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: 'var(--teal)',
        boxShadow: 'var(--shadow-glow-teal)',
        animation: 'pulse 2s infinite',
      }} />
      <span style={{
        fontSize: 12,
        fontWeight: 500,
        color: 'var(--teal)',
        fontFamily: 'var(--font-mono)',
      }}>
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
      fontSize: 12,
      padding: '4px 12px',
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