import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import { getRiskMigrationChart } from '../../services/api'
import { fmtMoney, fmtPct, COLORS } from '../../styles/chartTheme'

const BUCKET_ORDER = ['Paid', '0-30', '31-60', '61-90', '91-180', '180+']

function heatColor(pct) {
  if (pct >= 50) return 'rgba(201,168,76,0.35)'   // gold — strong diagonal
  if (pct >= 20) return 'rgba(91,141,239,0.25)'   // blue
  if (pct >= 10) return 'rgba(45,212,191,0.15)'   // teal
  if (pct > 0)   return 'rgba(255,255,255,0.04)'
  return 'transparent'
}

export default function RiskMigrationChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getRiskMigrationChart(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load risk migration data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (!data && !loading && !error) return null

  const matrix      = data?.matrix ?? []
  const cureRates   = data?.cure_rates ?? {}
  const summary     = data?.summary ?? {}
  const stressTest  = data?.stress_test ?? {}
  const expectedLoss = data?.expected_loss ?? {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Migration Summary KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <MiniKpi label="Matched Deals" value={summary.total_matched_deals ?? '—'} color="var(--gold)" />
        <MiniKpi label="Improved" value={summary.improved_pct ? `${summary.improved_pct}%` : '—'} sub={`${summary.improved ?? 0} deals`} color="var(--teal)" />
        <MiniKpi label="Stable" value={summary.stable ?? '—'} color="var(--blue)" />
        <MiniKpi label="Worsened" value={summary.worsened_pct ? `${summary.worsened_pct}%` : '—'} sub={`${summary.worsened ?? 0} deals`} color="var(--red)" />
      </div>

      {/* Roll-Rate Migration Matrix */}
      <ChartPanel
        title="Roll-Rate Migration Matrix"
        subtitle={`Transition probabilities: ${data?.old_snapshot ?? '?'} → ${data?.new_snapshot ?? '?'}`}
        loading={loading} error={error} minHeight={200}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr>
                <th style={thStyle}>From ↓ / To →</th>
                {BUCKET_ORDER.map(b => <th key={b} style={thStyle}>{b}</th>)}
                <th style={thStyle}>Total</th>
              </tr>
            </thead>
            <tbody>
              {matrix.map(row => (
                <tr key={row.from_bucket}>
                  <td style={{ ...tdStyle, fontWeight: 600, color: 'var(--text-primary)' }}>{row.from_bucket}</td>
                  {BUCKET_ORDER.map(to => {
                    const pct = row[`pct_${to}`] ?? 0
                    return (
                      <td key={to} style={{ ...tdStyle, background: heatColor(pct), textAlign: 'center' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', color: pct >= 50 ? 'var(--gold)' : 'var(--text-primary)' }}>
                          {pct > 0 ? `${pct}%` : '—'}
                        </span>
                      </td>
                    )
                  })}
                  <td style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)' }}>{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartPanel>

      {/* Cure Rates */}
      <ChartPanel title="Cure Rates" subtitle="% of delinquent deals that improved or resolved between snapshots" loading={loading} error={error} minHeight={100}>
        <div style={{ display: 'flex', gap: 20 }}>
          {Object.entries(cureRates).map(([bucket, stats]) => (
            <div key={bucket} style={{ flex: 1, textAlign: 'center', padding: '12px 0' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8 }}>
                {bucket} days
              </div>
              <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color: stats.cure_rate > 15 ? 'var(--teal)' : stats.cure_rate > 5 ? 'var(--gold)' : 'var(--red)' }}>
                {stats.cure_rate}%
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                {stats.cured} / {stats.total} deals
              </div>
            </div>
          ))}
        </div>
      </ChartPanel>

      {/* Expected Loss Model */}
      <ChartPanel title="Expected Loss Model" subtitle="PD × LGD × Exposure derived from completed deal outcomes" loading={loading} error={error} minHeight={100}>
        {expectedLoss.portfolio && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16 }}>
            <ELMetric label="PD (Prob. Default)" value={`${expectedLoss.portfolio.pd}%`} />
            <ELMetric label="LGD (Loss Given Default)" value={`${expectedLoss.portfolio.lgd}%`} />
            <ELMetric label="EAD (Exposure)" value={fmtMoney(expectedLoss.portfolio.ead, currency)} />
            <ELMetric label="Expected Loss" value={fmtMoney(expectedLoss.portfolio.el, currency)} color="var(--red)" />
            <ELMetric label="EL Rate" value={`${expectedLoss.portfolio.el_rate}%`} color="var(--red)" />
          </div>
        )}
      </ChartPanel>

      {/* Stress Test Scenarios */}
      <ChartPanel title="Stress Testing" subtitle="Payer concentration shock scenarios" loading={loading} error={error} minHeight={100}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {(stressTest.scenarios ?? []).map((s, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px',
              background: 'rgba(255,255,255,0.02)', borderRadius: 8,
              border: '1px solid var(--border)',
            }}>
              <div style={{ flex: 2 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{s.scenario}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                  Affected: {fmtMoney(s.affected_exposure, currency)} ({s.affected_pct}% of portfolio)
                </div>
              </div>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Collection Loss</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
                  {fmtMoney(s.collection_loss, currency)}
                </div>
              </div>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Rate Impact</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
                  {s.rate_impact}%
                </div>
              </div>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Stressed Rate</div>
                <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.stressed_collection_rate > 80 ? 'var(--teal)' : 'var(--gold)' }}>
                  {s.stressed_collection_rate}%
                </div>
              </div>
            </div>
          ))}
        </div>
      </ChartPanel>
    </div>
  )
}

/* ── Small helpers ── */

const thStyle = {
  textAlign: 'left', padding: '8px 10px',
  fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
  color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
}

const tdStyle = {
  padding: '8px 10px', borderBottom: '1px solid var(--border)',
  fontSize: 11, color: 'var(--text-secondary)',
}

function MiniKpi({ label, value, sub, color }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '14px 16px', position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: color, borderRadius: '10px 0 0 10px' }} />
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color, lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function ELMetric({ label, value, color = 'var(--gold)' }) {
  return (
    <div style={{ textAlign: 'center', padding: '8px 0' }}>
      <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>
        {value}
      </div>
    </div>
  )
}
