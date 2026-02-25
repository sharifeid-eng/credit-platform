import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCompanies } from '../services/api'

export default function Home() {
  const [companies, setCompanies] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    getCompanies().then(data => {
      // API may return strings or objects like {name: "klaim"}
      setCompanies(data.map(c => (typeof c === 'string' ? c : c.name ?? c.id ?? String(c))))
    })
  }, [])

  return (
    <div style={{ padding: '36px 28px' }}>
      {/* Page title */}
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
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 14,
      }}>
        {companies.map(co => (
          <CompanyCard key={co} name={co} onClick={() => navigate(`/company/${co}`)} />
        ))}
        {companies.length === 0 && <EmptyState />}
      </div>
    </div>
  )
}

function CompanyCard({ name, onClick }) {
  const [hovered, setHovered] = useState(false)
  const safeName = typeof name === 'string' ? name : String(name ?? '')
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

      <div style={{
        fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.55,
        paddingTop: 12, borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>Open Dashboard</span>
        <span style={{ color: hovered ? 'var(--gold)' : 'var(--text-faint)', transition: 'color 0.15s', fontSize: 13 }}>→</span>
      </div>
    </div>
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