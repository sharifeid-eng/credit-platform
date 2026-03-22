import { useState, useEffect } from 'react'
import api from '../../../services/api'
import CovenantCard from '../../portfolio/CovenantCard'

export default function SilqCovenantsChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/covenants`, {
      params: { snapshot, currency, as_of_date: asOfDate }
    })
      .then(res => setData(res.data))
      .catch(err => console.error('Covenants fetch error:', err))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (loading) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>Loading covenants...</div>
  if (!data) return <div style={{ color: 'var(--text-muted)', padding: 40 }}>No covenant data available</div>

  const displayCurrency = data.currency || currency || 'SAR'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 20,
        padding: '12px 18px',
        background: 'var(--bg-surface)', borderRadius: 8,
        border: '1px solid var(--border)',
      }}>
        <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 14 }}>
          COVENANT STATUS
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Test Date: {data.test_date}
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ color: 'var(--accent-teal)', fontSize: 13, fontWeight: 500 }}>
          ● {data.compliant_count} Compliant
        </span>
        {data.breach_count > 0 && (
          <span style={{ color: 'var(--accent-red)', fontSize: 13, fontWeight: 500 }}>
            ● {data.breach_count} Breach
          </span>
        )}
        {data.partial_count > 0 && (
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            ● {data.partial_count} Partial
          </span>
        )}
      </div>

      {/* Covenant cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {data.covenants.filter(c => c.available && !c.partial).map((cov, i) => (
          <CovenantCard key={i} covenant={cov} currency={displayCurrency} />
        ))}
      </div>

      {/* Partial / unavailable covenants */}
      {data.covenants.filter(c => c.partial || !c.available).map((cov, i) => (
        <div key={`partial-${i}`} style={{
          background: 'var(--bg-surface)', borderRadius: 8,
          border: '1px solid var(--border)', padding: '16px 20px',
          opacity: 0.7,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 14 }}>
              {cov.name}
            </span>
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 4,
              background: 'rgba(132, 148, 167, 0.15)', color: 'var(--text-muted)',
            }}>
              {cov.partial ? 'Partial Data' : 'Unavailable'}
            </span>
          </div>
          {cov.note && (
            <div style={{
              fontSize: 12, color: 'var(--accent-teal)', lineHeight: 1.5,
              padding: '8px 12px', borderRadius: 6,
              border: '1px solid rgba(45, 212, 191, 0.2)',
              background: 'rgba(45, 212, 191, 0.05)',
            }}>
              {cov.note}
            </div>
          )}
          {cov.breakdown && cov.breakdown.length > 0 && (
            <div style={{ marginTop: 10 }}>
              {cov.breakdown.map((row, j) => (
                <div key={j} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '4px 0', fontSize: 12,
                  color: row.note ? 'var(--text-muted)' : 'var(--text-primary)',
                  fontStyle: row.note ? 'italic' : 'normal',
                }}>
                  <span>{row.label}{row.note ? ` (${row.note})` : ''}</span>
                  <span style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {row.value >= 1_000_000 ? `${displayCurrency} ${(row.value / 1_000_000).toFixed(1)}M` :
                     row.value >= 1_000 ? `${displayCurrency} ${(row.value / 1_000).toFixed(0)}K` :
                     row.value < 1 && row.value > 0 ? `${(row.value * 100).toFixed(1)}%` :
                     String(row.value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Unavailable covenant note */}
      {data.covenants.some(c => !c.available && !c.partial) && (
        <div style={{
          fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0',
        }}>
          Some covenants cannot be computed — no qualifying loans in the measurement window.
        </div>
      )}
    </div>
  )
}
