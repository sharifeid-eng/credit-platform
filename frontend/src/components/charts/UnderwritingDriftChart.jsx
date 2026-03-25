import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getUnderwritingDrift } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function UnderwritingDriftChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getUnderwritingDrift(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load underwriting drift data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const monthly = data?.monthly ?? data?.cohorts ?? data?.data ?? []
  const driftFlags = data?.drift_flags ?? data?.flags ?? []
  const summary = data?.summary ?? {}
  const hasOutcomes = monthly.some(d => d.collection_rate != null || d.denial_rate != null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Drift Flags */}
      {driftFlags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {driftFlags.map((flag, i) => (
            <div key={i} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: flag.severity === 'critical' ? 'rgba(240,96,96,0.1)' : 'rgba(201,168,76,0.1)',
              border: `1px solid ${flag.severity === 'critical' ? 'rgba(240,96,96,0.3)' : 'rgba(201,168,76,0.3)'}`,
              borderRadius: 'var(--radius-sm)', padding: '5px 10px',
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: flag.severity === 'critical' ? COLORS.red : COLORS.gold,
              }} />
              <span style={{ fontSize: 10, color: 'var(--text-primary)' }}>
                {flag.message ?? flag.description ?? `${flag.metric}: ${flag.direction ?? 'drift'} (${flag.month ?? flag.period})`}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Summary KPIs */}
      {(summary.avg_deal_size != null || summary.avg_discount != null) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            summary.avg_deal_size != null && { label: 'Avg Deal Size', value: fmtMoney(summary.avg_deal_size, currency), color: 'var(--gold)' },
            summary.avg_discount != null && { label: 'Avg Discount', value: fmtPct(summary.avg_discount), color: 'var(--blue)' },
            summary.deal_size_trend != null && { label: 'Deal Size Trend', value: summary.deal_size_trend > 0 ? 'Increasing' : summary.deal_size_trend < 0 ? 'Decreasing' : 'Stable', color: summary.deal_size_trend > 0 ? 'var(--gold)' : 'var(--teal)' },
            summary.discount_trend != null && { label: 'Discount Trend', value: summary.discount_trend > 0 ? 'Widening' : summary.discount_trend < 0 ? 'Tightening' : 'Stable', color: summary.discount_trend > 0 ? 'var(--red)' : 'var(--teal)' },
          ].filter(Boolean).map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Dual-axis chart: Deal Size (bars) + Discount (line) */}
      <ChartPanel title="Underwriting Drift" subtitle="Average deal size and discount rate by cohort month with outcome overlay" loading={loading} error={error}>
        {monthly.length > 0 ? (
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={monthly} barCategoryGap="30%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey={monthly[0]?.Month ? 'Month' : 'month'} {...xAxisProps} />
              <YAxis yAxisId="amt" {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
              <YAxis yAxisId="pct" orientation="right" {...yAxisProps} tickFormatter={v => fmtPct(v)} width={42} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name) => {
                  if (name === 'Avg Discount' || name === 'Collection Rate' || name === 'Denial Rate') return [fmtPct(v), name]
                  return [fmtMoney(v, currency), name]
                }}
              />
              <Legend {...legendProps} />

              {/* Deal size bars */}
              <Bar
                yAxisId="amt"
                dataKey="avg_deal_size"
                name="Avg Deal Size"
                fill="url(#grad-gold)"
                stroke={COLORS.gold}
                strokeWidth={0}
                radius={[3, 3, 0, 0]}
              />

              {/* Discount line */}
              <Line
                yAxisId="pct"
                type="monotone"
                dataKey="avg_discount"
                name="Avg Discount"
                stroke={COLORS.blue}
                strokeWidth={2}
                dot={{ fill: COLORS.blue, r: 3 }}
              />

              {/* Outcome overlays when available */}
              {hasOutcomes && (
                <>
                  <Line
                    yAxisId="pct"
                    type="monotone"
                    dataKey="collection_rate"
                    name="Collection Rate"
                    stroke={COLORS.teal}
                    strokeWidth={1.5}
                    strokeDasharray="5 3"
                    dot={false}
                  />
                  <Line
                    yAxisId="pct"
                    type="monotone"
                    dataKey="denial_rate"
                    name="Denial Rate"
                    stroke={COLORS.red}
                    strokeWidth={1.5}
                    strokeDasharray="5 3"
                    dot={false}
                  />
                </>
              )}

              {/* Drift flag reference lines */}
              {driftFlags.filter(f => f.month).map((flag, i) => (
                <ReferenceLine
                  key={i}
                  x={flag.month}
                  yAxisId="amt"
                  stroke={flag.severity === 'critical' ? COLORS.red : COLORS.gold}
                  strokeDasharray="3 3"
                  strokeOpacity={0.6}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>No underwriting drift data available.</div>
        )}
      </ChartPanel>
    </div>
  )
}
