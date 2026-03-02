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

      {/* Right — Status chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
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
      {/* Icon mark — lion (cropped & gold-tinted from original SVG) */}
      <div style={{
        width: h,
        height: h,
        borderRadius: isNav ? 12 : 10,
        overflow: 'hidden',
        flexShrink: 0,
        boxShadow: '0 2px 8px rgba(201,168,76,0.25)',
        position: 'relative',
      }}>
        {/* SVG filter to map to exact brand gold #C9A84C */}
        <svg style={{ position: 'absolute', width: 0, height: 0 }}>
          <defs>
            <filter id="gold-tint">
              <feColorMatrix type="matrix" values="
                -0.79 -0.59 -0.11 0 0.79
                -0.66 -0.49 -0.09 0 0.66
                -0.30 -0.22 -0.04 0 0.30
                 0     0     0    1 0
              "/>
            </filter>
          </defs>
        </svg>

        <img
          src="/logo.svg"
          alt="Laith"
          style={{
            width: h * 2.3,
            height: 'auto',
            marginTop: h * -0.3,
            marginLeft: h * -0.6,
            display: 'block',
            filter: 'url(#gold-tint)',
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