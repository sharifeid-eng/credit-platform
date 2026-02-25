import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getActualVsExpectedChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function ActualVsExpectedChart({ company, product, snapshot, currency }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [perfPct, setPerfPct] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getActualVsExpectedChart(company, product, snapshot, currency)
      .then(res => {
        // normalise field names from backend
        const raw = res.data ?? res
        const normalised = raw.map(d => ({
          month:    d.Month ?? d.month,
          actual:   d.cumulative_collected ?? d.actual,
          expected: d.cumulative_expected  ?? d.expected,
        }))
        setData(normalised)
        setPerfPct(res.overall_performance ?? res.performance_pct ?? null)
        setError(null)
      })
      .catch(() => setError('Failed to load actual vs expected data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency])

  const action = perfPct != null && (
    <div style={{
      fontSize: 11, fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      color: perfPct >= 100 ? 'var(--teal)' : 'var(--red)',
      background: perfPct >= 100 ? 'var(--teal-muted)' : 'var(--red-muted)',
      padding: '3px 10px', borderRadius: 20,
    }}>
      {fmtPct(perfPct)} of expected collected
    </div>
  )

  return (
    <ChartPanel
      title="Actual vs Expected Collections"
      subtitle="Cumulative collected amount vs expected total — measures recovery performance"
      loading={loading}
      error={error}
      action={action}
    >
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data}>
          <GradientDefs />
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" {...xAxisProps} />
          <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
          <Tooltip
            {...tooltipStyle}
            formatter={(v, name) => [fmtMoney(v, currency), name]}
          />
          <Legend {...legendProps} />
          <Area
            type="monotone" dataKey="expected"
            name="Expected" stroke={COLORS.blue} strokeWidth={1.5}
            fill="url(#grad-blue)" strokeDasharray="5 3"
          />
          <Area
            type="monotone" dataKey="actual"
            name="Actual" stroke={COLORS.teal} strokeWidth={2}
            fill="url(#grad-teal)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartPanel>
  )
}