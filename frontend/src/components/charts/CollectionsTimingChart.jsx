import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getCollectionsTiming } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

// Gradient from teal (early) to red (late)
const BUCKET_COLORS = [
  '#2DD4BF', // 0-30d   teal
  '#5BCCB0', // 31-60d
  '#5B8DEF', // 61-90d  blue
  '#C9A84C', // 91-120d gold
  '#ED8936', // 121-180d orange
  '#F06060', // 181-270d red
  '#C53030', // 271-360d dark red
  '#9B2C2C', // 360d+   deeper red
]

export default function CollectionsTimingChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getCollectionsTiming(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load collections timing data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const monthly = data?.monthly ?? data?.data ?? []
  const buckets = data?.buckets ?? data?.bucket_labels ?? []
  const distribution = data?.distribution ?? data?.portfolio_distribution ?? []
  const summary = data?.summary ?? {}

  // Derive bucket keys from first monthly entry if not explicit
  const bucketKeys = buckets.length > 0
    ? buckets
    : (monthly.length > 0 ? Object.keys(monthly[0]).filter(k => k !== 'month' && k !== 'Month' && k !== 'total') : [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Summary KPIs */}
      {(summary.avg_days != null || summary.median_days != null) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            summary.avg_days != null && { label: 'Avg Collection Time', value: `${Math.round(summary.avg_days)}d`, color: 'var(--teal)' },
            summary.median_days != null && { label: 'Median Collection Time', value: `${Math.round(summary.median_days)}d`, color: 'var(--blue)' },
            summary.early_pct != null && { label: 'Collected < 90d', value: fmtPct(summary.early_pct), color: 'var(--teal)' },
            summary.late_pct != null && { label: 'Collected > 180d', value: fmtPct(summary.late_pct), color: 'var(--red)' },
          ].filter(Boolean).map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Stacked Bar Chart — Monthly by Timing Bucket */}
      <ChartPanel title="Collections Timing by Month" subtitle="Collection amounts broken down by time-to-collect bucket per origination month" loading={loading} error={error}>
        {monthly.length > 0 && bucketKeys.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={monthly} barCategoryGap="20%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey={monthly[0]?.Month ? 'Month' : 'month'} {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
              <Legend {...legendProps} />
              {bucketKeys.map((bucket, i) => (
                <Bar
                  key={bucket}
                  dataKey={bucket}
                  name={bucket}
                  stackId="timing"
                  fill={BUCKET_COLORS[i % BUCKET_COLORS.length]}
                  fillOpacity={0.8}
                  radius={i === bucketKeys.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 11 }}>No monthly timing data available.</div>
        )}
      </ChartPanel>

      {/* Portfolio-Level Timing Distribution */}
      {distribution.length > 0 && (
        <ChartPanel title="Portfolio Timing Distribution" subtitle="Aggregate collection timing across all vintages" loading={false} error={null}>
          <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            {/* Donut */}
            <ResponsiveContainer width="40%" height={250}>
              <PieChart>
                <Pie
                  data={distribution}
                  dataKey="amount"
                  nameKey="bucket"
                  cx="50%" cy="50%"
                  innerRadius={55} outerRadius={95}
                  stroke="var(--bg-surface)" strokeWidth={2}
                >
                  {distribution.map((_, i) => (
                    <Cell key={i} fill={BUCKET_COLORS[i % BUCKET_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...tooltipStyle} formatter={(v) => [fmtMoney(v, currency), 'Amount']} />
              </PieChart>
            </ResponsiveContainer>

            {/* Horizontal bars */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {distribution.map((bucket, i) => {
                const totalAmt = distribution.reduce((s, b) => s + (b.amount ?? 0), 0)
                const pct = totalAmt ? (bucket.amount / totalAmt * 100) : 0
                return (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontSize: 10, color: 'var(--text-primary)' }}>{bucket.bucket ?? bucket.label}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {fmtMoney(bucket.amount, currency)} ({pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: 3,
                        width: `${Math.min(pct, 100)}%`,
                        background: BUCKET_COLORS[i % BUCKET_COLORS.length],
                        transition: 'width 0.4s ease',
                      }} />
                    </div>
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
