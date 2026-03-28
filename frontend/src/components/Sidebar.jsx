import { Link, useParams, useLocation } from 'react-router-dom'
import { useCompany } from '../contexts/CompanyContext'

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
  const TAPE_TABS = tapeTabs || DEFAULT_TAPE_TABS
  const hidePortfolio = config?.hide_portfolio_tabs === true

  const isTape = location.pathname.includes('/tape/')
  const isPortfolio = location.pathname.includes('/portfolio/')
  const currentSlug = tab || ''

  const basePath = `/company/${company}/${product}`

  return (
    <nav style={{
      width: 240,
      flexShrink: 0,
      position: 'sticky',
      top: 56,
      height: 'calc(100vh - 56px)',
      overflowY: 'auto',
      padding: '20px 0 20px 0',
      borderRight: '1px solid var(--border)',
      background: 'var(--bg-nav)',
      scrollbarWidth: 'thin',
      scrollbarColor: 'var(--border) transparent',
      scrollBehavior: 'smooth',
    }}>
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

function NavItem({ label, to, active, icon }) {
  return (
    <Link
      to={to}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 20px',
        fontSize: 11,
        fontWeight: active ? 600 : 400,
        color: active ? 'var(--gold)' : 'var(--text-muted)',
        borderLeft: `2px solid ${active ? 'var(--gold)' : 'transparent'}`,
        textDecoration: 'none',
        transition: 'all var(--transition-fast)',
        whiteSpace: 'nowrap',
        background: active ? 'rgba(201,168,76,0.04)' : 'transparent',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.color = 'var(--text-primary)'
          e.currentTarget.style.paddingLeft = '22px'
          e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.color = 'var(--text-muted)'
          e.currentTarget.style.paddingLeft = '20px'
          e.currentTarget.style.background = 'transparent'
        }
      }}
    >
      {icon}
      {label}
    </Link>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--border)', margin: '12px 20px' }} />
}

export { DEFAULT_TAPE_TABS as TAPE_TABS, PORTFOLIO_TABS }
