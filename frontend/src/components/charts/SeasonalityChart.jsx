import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getSeasonality } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const YEAR_COLORS = [COLORS.gold, COLORS.teal, COLORS.blue, '#9F7AEA', '#ED8936', COLORS.red]

export default function SeasonalityChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getSeasonality(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load seasonality data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const monthly = data?.monthly ?? data?.data ?? []
  const years = data?.years ?? []
  const seasonalIndex = data?.seasonal_index ?? data?.index ?? []
  const summary = data?.summary ?? {}

  // Derive years from data if not provided
  const derivedYears = years.length > 0
    ? years
    : [...new Set(monthly.flatMap(d => Object.keys(d).filter(k => /^\d{4}$/.test(k))))].sort()

  // Build chart data: one entry per month with year-based origination columns
  const chartData = monthly.length > 0
    ? monthly.map((d, i) => ({
        month: d.month ?? d.Month ?? MONTH_LABELS[i] ?? `M${i + 1}`,
        ...d,
      }))
    : (seasonalIndex.length > 0
        ? seasonalIndex.map((d, i) => ({
            month: d.month ?? MONTH_LABELS[i] ?? `M${i + 1}`,
            ...d,
          }))
        : [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Summary KPIs */}
      {(summary.peak_month != null || summary.trough_month != null) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            summary.peak_month != null && { label: 'Peak Month', value: summary.peak_month, color: 'var(--teal)' },
            summary.trough_month != null && { label: 'Trough Month', value: summary.trough_month, color: 'var(--red)' },
            summary.peak_value != null && { label: 'Peak Origination', value: fmtMoney(summary.peak_value, currency), color: 'var(--gold)' },
            summary.seasonality_strength != null && { label: 'Seasonality Strength', value: fmtPct(summary.seasonality_strength), color: 'var(--blue)' },
          ].filter(Boolean).map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Grouped Bar Chart: Months x Years + Collection Rate + Seasonal Index */}
      <ChartPanel title="Seasonality Analysis" subtitle="Monthly origination volume by year with collection rate and seasonal index overlay" loading={loading} error={error}>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={chartData} barCategoryGap="20%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="month" {...xAxisProps} />
              <YAxis yAxisId="amt" {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
              <YAxis yAxisId="pct" orientation="right" {...yAxisProps} tickFormatter={v => fmtPct(v)} width={42} domain={[0, 'auto']} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name) => {
                  if (name === 'Collection Rate' || name === 'Seasonal Index') return [fmtPct(v), name]
                  return [fmtMoney(v, currency), name]
                }}
              />
              <Legend {...legendProps} />

              {/* One bar per year */}
              {derivedYears.map((year, i) => (
                <Bar
                  key={year}
                  yAxisId="amt"
                  dataKey={year}
                  name={String(year)}
                  fill={YEAR_COLORS[i % YEAR_COLORS.length]}
                  fillOpacity={0.7}
                  radius={[3, 3, 0, 0]}
                />
              ))}

              {/* If no year breakdown, use total origination */}
              {derivedYears.length === 0 && (
                <Bar
                  yAxisId="amt"
                  dataKey="origination"
                  name="Origination"
                  fill="url(#grad-gold)"
                  stroke={COLORS.gold}
                  strokeWidth={0}
                  radius={[3, 3, 0, 0]}
                />
              )}

              {/* Collection rate overlay */}
              {chartData.some(d => d.collection_rate != null) && (
                <Line
                  yAxisId="pct"
                  type="monotone"
                  dataKey="collection_rate"
                  name="Collection Rate"
                  stroke={COLORS.teal}
                  strokeWidth={2}
                  dot={{ fill: COLORS.teal, r: 3 }}
                />
              )}

              {/* Seasonal index overlay */}
              {chartData.some(d => d.seasonal_index != null) && (
                <Line
                  yAxisId="pct"
                  type="monotone"
                  dataKey="seasonal_index"
                  name="Seasonal Index"
                  stroke={COLORS.blue}
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ fill: COLORS.blue, r: 3 }}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>No seasonality data available.</div>
        )}
      </ChartPanel>
    </div>
  )
}
