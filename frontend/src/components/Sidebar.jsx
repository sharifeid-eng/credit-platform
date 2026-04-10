import { Link, useParams, useLocation } from 'react-router-dom'
import { motion, AnimatePresence }       from 'framer-motion'
import { useCompany }                    from '../contexts/CompanyContext'
import useBreakpoint                     from '../hooks/useBreakpoint'
import { useMobileMenu }                from '../contexts/MobileMenuContext'

// Default Klaim tabs (fallback when config has no tabs array)
const DEFAULT_TAPE_TABS = [
  { slug: 'overview',           label: 'Overview' },
  { slug: 'actual-vs-expected', label: 'Actual vs Expected' },
  { slug: 'deployment',         label: 'Deployment' },
  { slug: 'collection',         label: 'Collection' },
  { slug: 'collections-timing', label: 'Collections Timing' },
  { slug: 'denial-trend',       label: 'Denial Trend' },
  { slug: 'ageing',             label: 'Ageing' },
  { slug: 'revenue',            label: 'Revenue' },
  { slug: 'portfolio-tab',      label: 'Portfolio' },
  { slug: 'cohort-analysis',    label: 'Cohort Analysis' },
  { slug: 'loss-waterfall',     label: 'Loss Waterfall' },
  { slug: 'recovery-analysis',  label: 'Recovery Analysis' },
  { slug: 'returns',            label: 'Returns' },
  { slug: 'underwriting-drift', label: 'Underwriting Drift' },
  { slug: 'segment-analysis',   label: 'Segment Analysis' },
  { slug: 'seasonality',        label: 'Seasonality' },
  { slug: 'risk-migration',     label: 'Risk & Migration' },
  { slug: 'data-integrity',     label: 'Data Integrity' },
]

const PORTFOLIO_TABS = [
  { slug: 'borrowing-base',       label: 'Borrowing Base' },
  { slug: 'concentration-limits', label: 'Concentration Limits' },
  { slug: 'covenants',            label: 'Covenants' },
  { slug: 'invoices',             label: 'Invoices' },
  { slug: 'payments',             label: 'Payments' },
  { slug: 'bank-statements',     label: 'Bank Statements' },
]

export default function Sidebar() {
  const { company, products, product, tapeTabs, config } = useCompany()
  const { tab } = useParams()
  const location = useLocation()
  const { isMobile } = useBreakpoint()
  const { isOpen, close } = useMobileMenu()
  const TAPE_TABS = tapeTabs || DEFAULT_TAPE_TABS
  const hidePortfolio = config?.hide_portfolio_tabs === true

  const isTape = location.pathname.includes('/tape/')
  const isPortfolio = location.pathname.includes('/portfolio/')
  const currentSlug = tab || ''

  const basePath = `/company/${company}/${product}`

  const navStyle = isMobile ? {
    position: 'fixed',
    top: 0,
    left: 0,
    width: 280,
    height: '100vh',
    zIndex: 200,
    transform: isOpen ? 'translateX(0)' : 'translateX(-100%)',
    transition: 'transform 0.25s ease',
    overflowY: 'auto',
    padding: '20px 0',
    borderRight: '1px solid var(--border)',
    background: 'var(--bg-nav)',
    scrollbarWidth: 'thin',
    scrollbarColor: 'var(--border) transparent',
  } : {
    width: 240,
    flexShrink: 0,
    position: 'sticky',
    top: 'var(--navbar-height)',
    height: 'calc(100vh - var(--navbar-height))',
    overflowY: 'auto',
    padding: '20px 0 20px 0',
    borderRight: '1px solid var(--border)',
    background: 'var(--bg-nav)',
    scrollbarWidth: 'thin',
    scrollbarColor: 'var(--border) transparent',
    scrollBehavior: 'smooth',
  }

  return (
    <nav style={navStyle}>
      {/* Mobile close button */}
      {isMobile && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 16px 8px' }}>
          <button
            onClick={close}
            aria-label="Close menu"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', padding: 4,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {/* Company name */}
      <div style={{
        padding: '0 20px',
        fontSize: 11,
        fontWeight: 800,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        color: 'var(--gold)',
        marginBottom: 18,
      }}>
        {company?.toUpperCase()}
      </div>

      {/* Product selector */}
      {products.length > 1 && (
        <>
          <SectionHeader>Products</SectionHeader>
          {products.map(p => (
            <NavItem
              key={p}
              label={p.replace(/_/g, ' ')}
              to={`/company/${company}/${p}/tape/overview`}
              active={p === product}
            />
          ))}
          <Divider />
        </>
      )}

      {/* Executive Summary — AI-powered holistic analysis (always shown) */}
      <NavItem
        label="Executive Summary"
        to={`${basePath}/executive-summary`}
        active={location.pathname.includes('/executive-summary')}
        icon={
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        }
        accent
      />
      <Divider />

      {/* Research */}
      <SectionHeader>Research</SectionHeader>
      <NavItem
        label="Document Library"
        to={`${basePath}/research/library`}
        active={location.pathname.includes('/research/library')}
        icon={
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            <line x1="8" y1="7" x2="16" y2="7" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        }
      />
      <NavItem
        label="Research Chat"
        to={`${basePath}/research/chat`}
        active={location.pathname.includes('/research/chat')}
        icon={
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        }
      />
      <NavItem
        label="Investment Memos"
        to={`${basePath}/research/memos`}
        active={location.pathname.includes('/research/memos')}
        icon={
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        }
      />
      <Divider />

      {/* Tape Analytics */}
      <SectionHeader>{hidePortfolio ? 'Analysis' : 'Tape Analytics'}</SectionHeader>
      {TAPE_TABS.map(t => (
        <NavItem
          key={t.slug}
          label={t.label}
          to={`${basePath}/tape/${t.slug}`}
          active={isTape && currentSlug === t.slug}
        />
      ))}

      <Divider />

      {/* Portfolio Analytics — hidden for read-only summary companies */}
      {!hidePortfolio && (
        <>
          <SectionHeader>Portfolio Analytics</SectionHeader>
          {PORTFOLIO_TABS.map(t => (
            <NavItem
              key={t.slug}
              label={t.label}
              to={`${basePath}/portfolio/${t.slug}`}
              active={isPortfolio && currentSlug === t.slug}
            />
          ))}
          <Divider />
        </>
      )}

      {/* Methodology */}
      <NavItem
        label="Methodology"
        to={`${basePath}/methodology`}
        active={location.pathname.includes('/methodology')}
        icon={
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        }
      />
    </nav>
  )
}

function SectionHeader({ children }) {
  return (
    <div style={{
      padding: '14px 20px 6px',
      fontSize: 9,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.12em',
      color: 'var(--text-muted)',
    }}>
      {children}
    </div>
  )
}

function NavItem({ label, to, active, icon, accent }) {
  return (
    <Link
      to={to}
      style={{
        display:        'flex',
        alignItems:     'center',
        gap:            6,
        padding:        '6px 20px 6px 22px',
        fontSize:       accent ? 12 : 11,
        fontWeight:     active ? 600 : accent ? 500 : 400,
        color:          active ? 'var(--gold)' : accent ? 'var(--gold)' : 'var(--text-muted)',
        textDecoration: 'none',
        whiteSpace:     'nowrap',
        position:       'relative',
        transition:     'color var(--transition-fast), background var(--transition-fast), padding-left var(--transition-fast)',
        background:     active
          ? 'linear-gradient(to right, rgba(201,168,76,0.07), transparent)'
          : 'transparent',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.color       = 'var(--text-primary)'
          e.currentTarget.style.paddingLeft = '24px'
          e.currentTarget.style.background  = 'rgba(255,255,255,0.02)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.color       = accent ? 'var(--gold)' : 'var(--text-muted)'
          e.currentTarget.style.paddingLeft = '22px'
          e.currentTarget.style.background  = 'transparent'
        }
      }}
    >
      {/* Animated left border — scaleY 0→1 when active */}
      <motion.span
        initial={false}
        animate={{ scaleY: active ? 1 : 0, opacity: active ? 1 : 0 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        style={{
          position:        'absolute',
          left:            0,
          top:             0,
          bottom:          0,
          width:           2,
          background:      'var(--gold)',
          borderRadius:    '0 2px 2px 0',
          transformOrigin: 'top',
          display:         'block',
        }}
      />
      {icon}
      {label}
    </Link>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--border)', margin: '12px 20px' }} />
}

export { DEFAULT_TAPE_TABS as TAPE_TABS, PORTFOLIO_TABS }
