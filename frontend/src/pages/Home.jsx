import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { getCompanies } from '../services/api'

export default function Home() {
  const [companies, setCompanies] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    getCompanies().then(data => {
      // API returns objects with {name, products, total_snapshots} or strings
      setCompanies(data.map(c => {
        if (typeof c === 'string') return { name: c, products: [], total_snapshots: 0 }
        return {
          name: c.name ?? c.id ?? String(c),
          products: c.products ?? [],
          total_snapshots: c.total_snapshots ?? 0,
        }
      }))
    })
  }, [])

  return (
    <div style={{ padding: '36px 28px' }}>
      {/* Page header — no logo (Navbar already shows it) */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{
          fontSize: 26, fontWeight: 800, letterSpacing: '-0.03em',
          color: 'var(--text-primary)', margin: 0,
        }}>
          Portfolio Companies
        </h1>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5 }}>
          Select a company to open its analytics dashboard.
        </p>
      </div>

      {/* Company grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 14,
      }}>
        {companies.map(co => (
          <CompanyCard
            key={co.name}
            company={co}
            onClick={() => {
              const defaultProduct = co.products?.[0] ?? ''
              if (defaultProduct) {
                navigate(`/company/${co.name}/${defaultProduct}/tape/overview`)
              } else {
                navigate(`/company/${co.name}`)
              }
            }}
          />
        ))}
        {companies.length === 0 && <EmptyState />}
      </div>

      {/* Resources section */}
      <div style={{ marginTop: 40, paddingTop: 28, borderTop: '1px solid var(--border)' }}>
        <div style={{ marginBottom: 16 }}>
          <h2 style={{
            fontSize: 16, fontWeight: 700, color: 'var(--text-primary)',
            margin: 0, letterSpacing: '-0.01em',
          }}>
            Resources
          </h2>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Platform documentation and analytical methodology.
          </p>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 14,
        }}>
          <FrameworkCard />
        </div>
      </div>
    </div>
  )
}

function CompanyCard({ company, onClick }) {
  const [hovered, setHovered] = useState(false)
  const safeName = typeof company.name === 'string' ? company.name : String(company.name ?? '')
  const initials = safeName.slice(0, 2).toUpperCase()

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'rgba(201,168,76,0.4)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-md)',
        padding: '20px',
        cursor: 'pointer',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        boxShadow: hovered ? 'var(--shadow-glow-gold)' : 'none',
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* Subtle top gradient on hover */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: hovered ? 'linear-gradient(90deg, var(--gold), transparent)' : 'transparent',
        transition: 'background 0.2s',
      }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        {/* Logo mark */}
        <div style={{
          width: 40, height: 40,
          background: 'linear-gradient(135deg, var(--gold), var(--gold-dim))',
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 800, color: '#000',
          flexShrink: 0,
        }}>
          {initials}
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            {safeName.toUpperCase()}
          </div>
          <div style={{ fontSize: 9, color: 'var(--teal)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>
            ● Active
          </div>
        </div>
      </div>

      {/* Product tags */}
      {company.products && company.products.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {company.products.map(p => (
            <span key={p} style={{
              fontSize: 10,
              padding: '2px 8px',
              borderRadius: 12,
              background: 'rgba(45, 212, 191, 0.1)',
              color: 'var(--accent-teal)',
              border: '1px solid rgba(45, 212, 191, 0.2)',
              fontWeight: 500,
            }}>
              {p.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div style={{
        fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.55,
        paddingTop: 12, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <span>Open Dashboard</span>
          {company.total_snapshots > 0 && (
            <span style={{ color: 'var(--text-faint)' }}>
              {company.total_snapshots} snapshot{company.total_snapshots !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <span style={{ color: hovered ? 'var(--gold)' : 'var(--text-faint)', transition: 'color 0.15s', fontSize: 13 }}>→</span>
      </div>
    </div>
  )
}

function FrameworkCard() {
  const [hovered, setHovered] = useState(false)
  return (
    <Link
      to="/framework"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        textDecoration: 'none',
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'rgba(45, 212, 191, 0.4)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-md)',
        padding: '20px',
        cursor: 'pointer',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        boxShadow: hovered ? '0 0 20px rgba(45, 212, 191, 0.08)' : 'none',
        position: 'relative', overflow: 'hidden',
        display: 'block',
      }}
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: hovered ? 'linear-gradient(90deg, var(--teal), transparent)' : 'transparent',
        transition: 'background 0.2s',
      }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div style={{
          width: 40, height: 40,
          background: 'linear-gradient(135deg, var(--teal), rgba(45,212,191,0.4))',
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, flexShrink: 0,
        }}>
          <span role="img" aria-label="book" style={{ filter: 'brightness(0) invert(0)' }}>&#128218;</span>
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
            Analysis Framework
          </div>
          <div style={{ fontSize: 10, color: 'var(--teal)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>
            Methodology
          </div>
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 12 }}>
        The analytical hierarchy, metric definitions, and philosophy that guide
        every dashboard, chart, and AI insight in Laith.
      </div>
      <div style={{
        fontSize: 11, color: 'var(--text-muted)',
        paddingTop: 12, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>Read Framework</span>
        <span style={{ color: hovered ? 'var(--teal)' : 'var(--text-faint)', transition: 'color 0.15s', fontSize: 13 }}>→</span>
      </div>
    </Link>
  )
}

function EmptyState() {
  return (
    <div style={{
      gridColumn: '1 / -1', padding: '40px',
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
      color: 'var(--text-muted)', fontSize: 12,
    }}>
      <div style={{ fontSize: 28, opacity: 0.3 }}>◻</div>
      <div>No companies found. Check that data directories are set up correctly.</div>
    </div>
  )
}
