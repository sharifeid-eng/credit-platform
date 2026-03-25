import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import { getCohortLossWaterfall, getVintageLossCurves, getLossCategorization } from '../../services/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell,
} from 'recharts'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function CohortLossWaterfallChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]             = useState(null)
  const [lossCurves, setLossCurves] = useState(null)
  const [lossCats, setLossCats]     = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    Promise.all([
      getCohortLossWaterfall(company, product, snapshot, currency, asOfDate).catch(() => null),
      getVintageLossCurves(company, product, snapshot, currency, asOfDate).catch(() => null),
      getLossCategorization(company, product, snapshot, currency, asOfDate).catch(() => null),
    ])
      .then(([wf, curves, cats]) => {
        if (!wf) { setError('Failed to load cohort loss waterfall data.'); return }
        setData(wf)
        setLossCurves(curves)
        setLossCats(cats)
        setError(null)
      })
      .catch(() => setError('Failed to load cohort loss waterfall data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const cohorts = data?.cohorts ?? data?.vintages ?? []
  const totals = data?.totals ?? null

  // Compute totals from cohorts if not provided
  const summary = totals || (cohorts.length ? {
    total_originated: cohorts.reduce((s, r) => s + (r.originated ?? r.purchase_value ?? 0), 0),
    gross_default: cohorts.reduce((s, r) => s + (r.gross_default ?? r.denied ?? 0), 0),
    recovery: cohorts.reduce((s, r) => s + (r.recovery ?? 0), 0),
    net_loss: cohorts.reduce((s, r) => s + (r.net_loss ?? 0), 0),
    total_deals: cohorts.reduce((s, r) => s + (r.deals ?? r.total_deals ?? 0), 0),
  } : null)

  if (summary && !summary.gross_default_pct) {
    summary.gross_default_pct = summary.total_originated ? (summary.gross_default / summary.total_originated * 100) : 0
    summary.net_loss_pct = summary.total_originated ? (summary.net_loss / summary.total_originated * 100) : 0
    summary.recovery_pct = summary.gross_default ? (summary.recovery / summary.gross_default * 100) : 0
  }

  const lossCurveData = lossCurves?.curves ?? lossCurves?.vintages ?? []
  const lossCatData = lossCats?.categories ?? lossCats?.segments ?? []
  const PIE_COLORS = [COLORS.red, COLORS.gold, COLORS.blue, COLORS.teal, '#9F7AEA', '#ED8936']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPI Cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            { label: 'Total Originated',    value: fmtMoney(summary.total_originated, currency), color: 'var(--gold)' },
            { label: 'Gross Default Rate',   value: fmtPct(summary.gross_default_pct),            color: 'var(--red)' },
            { label: 'Net Loss Rate',        value: fmtPct(summary.net_loss_pct),                 color: 'var(--red)' },
            { label: 'Recovery Rate',        value: fmtPct(summary.recovery_pct),                 color: 'var(--teal)' },
          ].map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Cohort Loss Table */}
      <ChartPanel title="Cohort Loss Waterfall" subtitle="Per-vintage gross default, recovery, and net loss breakdown" loading={loading} error={error} minHeight={0}>
        <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 900 }}>
            <thead>
              <tr>
                {['Vintage', 'Deals', 'Originated', 'Gross Default', 'Recovery', 'Net Loss', 'Gross Default %', 'Net Loss %', 'Recovery %'].map(h => (
                  <th key={h} style={{
                    textAlign: h === 'Vintage' ? 'left' : 'right',
                    padding: '8px 8px', fontSize: 9, fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    color: 'var(--text-muted)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cohorts.map((row, i) => {
                const originated = row.originated ?? row.purchase_value ?? 0
                const grossDef = row.gross_default ?? row.denied ?? 0
                const recovery = row.recovery ?? 0
                const netLoss = row.net_loss ?? (grossDef - recovery)
                const grossDefPct = originated ? (grossDef / originated * 100) : 0
                const netLossPct = originated ? (netLoss / originated * 100) : 0
                const recoveryPct = grossDef ? (recovery / grossDef * 100) : 0

                return (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                      {row.vintage ?? row.month}
                    </td>
                    <td style={cellRight}>{row.deals ?? row.total_deals ?? 0}</td>
                    <td style={{ ...cellRight, color: 'var(--gold)' }}>{fmtMoney(originated, currency)}</td>
                    <td style={{ ...cellRight, color: 'var(--red)' }}>{fmtMoney(grossDef, currency)}</td>
                    <td style={{ ...cellRight, color: 'var(--teal)' }}>{fmtMoney(recovery, currency)}</td>
                    <td style={{ ...cellRight, color: 'var(--red)' }}>{fmtMoney(netLoss, currency)}</td>
                    <td style={cellRight}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: grossDefPct > 10 ? 'var(--red)' : 'var(--text-muted)' }}>
                        {grossDefPct.toFixed(1)}%
                      </span>
                    </td>
                    <td style={cellRight}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: netLossPct > 5 ? 'var(--red)' : 'var(--text-muted)' }}>
                        {netLossPct.toFixed(1)}%
                      </span>
                    </td>
                    <td style={cellRight}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: recoveryPct >= 50 ? 'var(--teal)' : 'var(--gold)' }}>
                        {recoveryPct.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                )
              })}

              {/* Totals row */}
              {summary && cohorts.length > 0 && (
                <tr style={{ borderTop: '2px solid var(--border)', background: 'rgba(201,168,76,0.04)' }}>
                  <td style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--gold)' }}>TOTAL</td>
                  <td style={{ ...cellRight, fontWeight: 700 }}>{summary.total_deals}</td>
                  <td style={{ ...cellRight, fontWeight: 700, color: 'var(--gold)' }}>{fmtMoney(summary.total_originated, currency)}</td>
                  <td style={{ ...cellRight, fontWeight: 700, color: 'var(--red)' }}>{fmtMoney(summary.gross_default, currency)}</td>
                  <td style={{ ...cellRight, fontWeight: 700, color: 'var(--teal)' }}>{fmtMoney(summary.recovery, currency)}</td>
                  <td style={{ ...cellRight, fontWeight: 700, color: 'var(--red)' }}>{fmtMoney(summary.net_loss, currency)}</td>
                  <td style={{ ...cellRight, fontWeight: 700 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmtPct(summary.gross_default_pct)}</span>
                  </td>
                  <td style={{ ...cellRight, fontWeight: 700 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmtPct(summary.net_loss_pct)}</span>
                  </td>
                  <td style={{ ...cellRight, fontWeight: 700 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>{fmtPct(summary.recovery_pct)}</span>
                  </td>
                </tr>
              )}

              {cohorts.length === 0 && !loading && (
                <tr><td colSpan={9} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No cohort loss data.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </ChartPanel>

      {/* Vintage Loss Curves */}
      {lossCurves && lossCurveData.length > 0 && (
        <ChartPanel title="Vintage Loss Curves" subtitle="Cumulative loss development by vintage over time" loading={false} error={null}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={lossCurveData[0]?.points ?? lossCurveData}>
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="age" {...xAxisProps} label={{ value: 'Age (days)', position: 'insideBottomRight', offset: -5, fill: COLORS.text, fontSize: 9 }} />
              <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtPct(v), name]} />
              <Legend {...legendProps} />
              {lossCurveData.slice(0, 8).map((vintage, i) => {
                const lineColors = [COLORS.red, COLORS.gold, COLORS.blue, COLORS.teal, '#9F7AEA', '#ED8936', '#63B3ED', '#F6AD55']
                return (
                  <Line
                    key={vintage.vintage ?? i}
                    data={vintage.points ?? undefined}
                    type="monotone"
                    dataKey={vintage.vintage ? undefined : 'loss_pct'}
                    name={vintage.vintage ?? `Vintage ${i + 1}`}
                    stroke={lineColors[i % lineColors.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                )
              })}
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>
      )}

      {/* Loss Categorization */}
      {lossCats && lossCatData.length > 0 && (
        <ChartPanel title="Loss Categorization" subtitle="Breakdown of losses by category" loading={false} error={null}>
          <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            <ResponsiveContainer width="45%" height={250}>
              <PieChart>
                <Pie
                  data={lossCatData}
                  dataKey="amount"
                  nameKey="category"
                  cx="50%" cy="50%"
                  innerRadius={55} outerRadius={95}
                  stroke="var(--bg-surface)" strokeWidth={2}
                >
                  {lossCatData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...tooltipStyle} formatter={(v) => [fmtMoney(v, currency), 'Amount']} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {lossCatData.map((cat, i) => {
                const total = lossCatData.reduce((s, c) => s + (c.amount ?? 0), 0)
                const pct = total ? (cat.amount / total * 100) : 0
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
                    <div style={{ width: 10, height: 10, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                    <div style={{ flex: 1, fontSize: 11, color: 'var(--text-primary)' }}>{cat.category ?? cat.name}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', minWidth: 60, textAlign: 'right' }}>{fmtMoney(cat.amount, currency)}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', minWidth: 45, textAlign: 'right' }}>{pct.toFixed(1)}%</div>
                  </div>
                )
              })}
            </div>
          </div>
        </ChartPanel>
      )}
    </div>
  )
}

const cellRight = {
  padding: '7px 8px',
  textAlign: 'right',
  fontFamily: 'var(--font-mono)',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap',
}
