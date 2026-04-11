import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import useBreakpoint from '../hooks/useBreakpoint'
import { useMobileMenu } from '../contexts/MobileMenuContext'
import { useAuth } from '../contexts/AuthContext'

export default function Navbar() {
  const { pathname } = useLocation()
  const { isMobile } = useBreakpoint()
  const { toggle } = useMobileMenu()
  const { user, isAdmin, logout } = useAuth()
  const isCompanyPage = pathname.startsWith('/company/')

  return (
    <nav style={{
      background: 'var(--bg-nav)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: isMobile ? '0 14px' : '0 28px',
      height: 'var(--navbar-height)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Left — Hamburger (mobile company pages) + Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 14 }}>
        {isMobile && isCompanyPage && (
          <button
            onClick={toggle}
            aria-label="Toggle sidebar"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', padding: 4, display: 'flex',
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 14 }}>
          <LaithLogo size={isMobile ? 'mobile' : 'nav'} />
          {!isMobile && (
            <div style={{
              fontSize: 15,
              fontWeight: 600,
              color: 'var(--gold)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}>
              Data Analytics
            </div>
          )}
        </Link>
      </div>

      {/* Right — Nav links + Status chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 6 : 12 }}>
        {!isMobile && (
          <>
            <Link to="/operator" style={{
              fontSize: 12,
              fontWeight: 600,
              color: pathname === '/operator' ? 'var(--gold)' : 'var(--text-muted)',
              textDecoration: 'none',
              padding: '4px 10px',
              borderRadius: 6,
              transition: 'color var(--transition-fast)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.02em',
            }}>
              Ops
            </Link>
            <Link to="/framework" style={{
              fontSize: 12,
              fontWeight: 600,
              color: pathname === '/framework' ? 'var(--gold)' : 'var(--text-muted)',
              textDecoration: 'none',
              padding: '4px 10px',
              borderRadius: 6,
              transition: 'color var(--transition-fast)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.02em',
            }}>
              Framework
            </Link>
            <LiveDot />
            <Chip>v0.5</Chip>
          </>
        )}
        {user && <UserMenu user={user} isAdmin={isAdmin} logout={logout} />}
      </div>
    </nav>
  )
}

function UserMenu({ user, isAdmin, logout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const initials = (user.name || user.email || '?')
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: open ? 'var(--bg-surface)' : 'transparent',
          border: '1px solid var(--border)',
          borderRadius: 20, padding: '4px 12px 4px 4px',
          cursor: 'pointer', color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)', fontSize: 12,
          letterSpacing: '0.02em',
          transition: 'border-color var(--transition-fast)',
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-hover)'}
        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
      >
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--gold-muted)', color: 'var(--gold)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-ui)',
        }}>
          {initials}
        </div>
        {user.name || user.email}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: 'calc(100% + 6px)',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '8px 0', minWidth: 220,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          zIndex: 200,
        }}>
          {/* User info */}
          <div style={{ padding: '8px 16px 12px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-ui)' }}>
              {user.name}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
              {user.email}
            </div>
            <div style={{
              display: 'inline-block', marginTop: 6,
              fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '2px 8px', borderRadius: 10,
              background: isAdmin ? 'var(--gold-muted)' : 'var(--blue-muted)',
              color: isAdmin ? 'var(--gold)' : 'var(--blue)',
              fontFamily: 'var(--font-mono)',
            }}>
              {user.role}
            </div>
          </div>

          {/* Menu items */}
          {isAdmin && (
            <Link
              to="/admin/users"
              onClick={() => setOpen(false)}
              style={{
                display: 'block', padding: '10px 16px', fontSize: 13,
                color: 'var(--text-secondary)', textDecoration: 'none',
                fontFamily: 'var(--font-ui)',
                transition: 'background var(--transition-fast)',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-deep)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              Manage Users
            </Link>
          )}
          <button
            onClick={() => { setOpen(false); logout() }}
            style={{
              display: 'block', width: '100%', textAlign: 'left',
              padding: '10px 16px', fontSize: 13,
              color: 'var(--red)', background: 'none', border: 'none',
              cursor: 'pointer', fontFamily: 'var(--font-ui)',
              transition: 'background var(--transition-fast)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-deep)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  )
}

function LaithLogo({ size = 'nav' }) {
  const isMob = size === 'mobile'
  const isNav = size === 'nav'
  const h = isMob ? 36 : isNav ? 54 : 44
  const fs = isMob ? 22 : isNav ? 33 : 28

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: isMob ? 8 : isNav ? 12 : 10,
      height: h,
    }}>
      {/* Icon mark — lion */}
      <div style={{
        width: h,
        height: h,
        borderRadius: isMob ? 8 : isNav ? 12 : 10,
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
          fontSize: fs,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-display)',
        }}>
          L
        </span>
        <span style={{
          fontSize: fs,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--gold)',
          fontFamily: 'var(--font-display)',
        }}>
          AI
        </span>
        <span style={{
          fontSize: fs,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-display)',
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
    <div
      style={{
        fontSize: 12,
        padding: '4px 12px',
        borderRadius: 20,
        border: '1px solid var(--border)',
        color: highlight ? 'var(--text-secondary)' : 'var(--text-muted)',
        background: highlight ? 'var(--bg-surface)' : 'transparent',
        fontFamily: 'var(--font-mono)',
        letterSpacing: '0.02em',
        transition: 'opacity var(--transition-fast), border-color var(--transition-fast)',
        cursor: 'default',
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.opacity = '1' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.opacity = '' }}
    >
      {children}
    </div>
  )
}