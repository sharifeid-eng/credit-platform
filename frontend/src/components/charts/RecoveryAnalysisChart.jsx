import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getRecoveryAnalysis } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function RecoveryAnalysisChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getRecoveryAnalysis(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load recovery analysis data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const summary = data?.summary ?? data ?? {}
  const byVintage = data?.by_vintage ?? data?.vintages ?? []
  const worstDeals = data?.worst_deals ?? []
  const bestRecoveries = data?.best_recoveries ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPI Cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            { label: 'Total Defaults',       value: summary.total_defaults ?? summary.total_defaulted_deals ?? '—', color: 'var(--red)' },
            { label: 'Total Default Amount',  value: fmtMoney(summary.total_default_amount ?? summary.total_denied, currency), color: 'var(--red)' },
            { label: 'Recovery Rate',         value: fmtPct(summary.recovery_rate),        color: 'var(--teal)' },
            { label: 'Avg Recovery Time',     value: summary.avg_recovery_days != null ? `${Math.round(summary.avg_recovery_days)}d` : '—', color: 'var(--blue)' },
          ].map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Recovery Rate by Vintage */}
      <ChartPanel title="Recovery Rate by Vintage" subtitle="Percentage of defaulted amount recovered per origination month" loading={loading} error={error}>
        {byVintage.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={byVintage} barCategoryGap="30%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey={byVintage[0]?.vintage ? 'vintage' : 'month'} {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtPct(v), name]} />
              <Legend {...legendProps} />
              <Bar dataKey="recovery_rate" name="Recovery Rate" fill="url(#grad-teal)" stroke={COLORS.teal} strokeWidth={0} radius={[3,3,0,0]}>
                {byVintage.map((entry, i) => (
                  <Cell key={i} fill={(entry.recovery_rate ?? 0) >= 50 ? COLORS.teal : COLORS.gold} fillOpacity={0.7} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>No vintage recovery data available.</div>
        )}
      </ChartPanel>

      {/* Worst Deals Table */}
      {worstDeals.length > 0 && (
        <ChartPanel title="Worst Defaults" subtitle="Largest unrecovered defaults by deal" loading={false} error={null} minHeight={0}>
          <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 600 }}>
              <thead>
                <tr>
                  {['Deal', 'Default Amount', 'Recovered', 'Recovery %', 'Status'].map(h => (
                    <th key={h} style={{
                      textAlign: h === 'Deal' ? 'left' : 'right',
                      padding: '8px 8px', fontSize: 9, fontWeight: 600,
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {worstDeals.slice(0, 10).map((deal, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 8px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                      {deal.deal_id ?? deal.id ?? `Deal ${i + 1}`}
                    </td>
                    <td style={{ ...cellR, color: 'var(--red)' }}>{fmtMoney(deal.default_amount ?? deal.denied, currency)}</td>
                    <td style={{ ...cellR, color: 'var(--teal)' }}>{fmtMoney(deal.recovered ?? deal.recovery ?? 0, currency)}</td>
                    <td style={cellR}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: (deal.recovery_pct ?? 0) >= 50 ? 'var(--teal)' : 'var(--red)' }}>
                        {fmtPct(deal.recovery_pct ?? 0)}
                      </span>
                    </td>
                    <td style={{ ...cellR, color: 'var(--text-muted)' }}>{deal.status ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartPanel>
      )}

      {/* Best Recoveries Table */}
      {bestRecoveries.length > 0 && (
        <ChartPanel title="Best Recoveries" subtitle="Deals with highest recovery rates after default" loading={false} error={null} minHeight={0}>
          <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 600 }}>
              <thead>
                <tr>
                  {['Deal', 'Default Amount', 'Recovered', 'Recovery %', 'Recovery Time'].map(h => (
                    <th key={h} style={{
                      textAlign: h === 'Deal' ? 'left' : 'right',
                      padding: '8px 8px', fontSize: 9, fontWeight: 600,
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bestRecoveries.slice(0, 10).map((deal, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 8px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                      {deal.deal_id ?? deal.id ?? `Deal ${i + 1}`}
                    </td>
                    <td style={{ ...cellR, color: 'var(--red)' }}>{fmtMoney(deal.default_amount ?? deal.denied, currency)}</td>
                    <td style={{ ...cellR, color: 'var(--teal)' }}>{fmtMoney(deal.recovered ?? deal.recovery, currency)}</td>
                    <td style={cellR}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--teal)' }}>
                        {fmtPct(deal.recovery_pct ?? 0)}
                      </span>
                    </td>
                    <td style={{ ...cellR, color: 'var(--text-muted)' }}>
                      {deal.recovery_days != null ? `${Math.round(deal.recovery_days)}d` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartPanel>
      )}
    </div>
  )
}

const cellR = {
  padding: '7px 8px',
  textAlign: 'right',
  fontFamily: 'var(--font-mono)',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap',
}
