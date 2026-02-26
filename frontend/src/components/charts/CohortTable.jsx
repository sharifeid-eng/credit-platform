import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import { getCohortChart } from '../../services/api'
import { fmtPct, fmtMoney } from '../../styles/chartTheme'

export default function CohortTable({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getCohortChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const raw = res.cohorts ?? res.data ?? res
        setData(raw)
        setError(null)
      })
      .catch(() => setError('Failed to load cohort data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  return (
    <ChartPanel
      title="Cohort Analysis"
      subtitle="Vintage performance by origination month — collection rate, denial rate, completion"
      loading={loading}
      error={error}
      minHeight={0}
    >
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              {['Vintage', 'Deals', 'Completed', 'Deployed', 'Collection Rate', 'Denial Rate', 'Completion'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '8px 10px',
                  fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
                  color: 'var(--text-muted)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const collGood    = (row.collection_rate ?? 0) >= 90
              const denialBad   = (row.denial_rate     ?? 0) > 10
              const completeBad = (row.completion_rate ?? 0) < 70
              return (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{row.month}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{row.total_deals}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{row.completed_deals}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', color: 'var(--gold)' }}>{fmtMoney(row.purchase_value, currency)}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <Heat value={row.collection_rate} fmt={fmtPct} good={collGood} goodColor="var(--teal)" badColor="var(--gold)" />
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    <Heat value={row.denial_rate} fmt={fmtPct} good={!denialBad} goodColor="var(--text-secondary)" badColor="var(--red)" />
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    <Heat value={row.completion_rate} fmt={fmtPct} good={!completeBad} goodColor="var(--teal)" badColor="var(--red)" />
                  </td>
                </tr>
              )
            })}
            {data.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No cohort data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </ChartPanel>
  )
}

function Heat({ value, fmt, good, goodColor, badColor }) {
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: value == null ? 'var(--text-faint)' : good ? goodColor : badColor }}>
      {value == null ? '—' : fmt(value)}
    </span>
  )
}
