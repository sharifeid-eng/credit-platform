import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getDenialTrendChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function DenialTrendChart({ company, product, snapshot, currency }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getDenialTrendChart(company, product, snapshot, currency)
      .then(res => {
        const raw = res.data ?? res
        const normalised = raw.map(d => ({
          month:       d.Month ?? d.month,
          denial_rate: d.denial_rate,
          rolling_avg: d.denial_rate_3m_avg,
        }))
        setData(normalised)
        setError(null)
      })
      .catch(() => setError('Failed to load denial trend data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency])

  const avg = data.length
    ? data.reduce((s, d) => s + (d.denial_rate ?? 0), 0) / data.length
    : null

  return (
    <ChartPanel
      title="Denial Rate Trend"
      subtitle="Monthly denial rate % with 3-month rolling average — watch for spikes above portfolio avg"
      loading={loading}
      error={error}
    >
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} barCategoryGap="30%">
          <GradientDefs />
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" {...xAxisProps} />
          <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
          <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtPct(v), name]} />
          <Legend {...legendProps} />
          {avg != null && (
            <ReferenceLine y={avg} stroke={COLORS.muted} strokeDasharray="4 4"
              label={{ value: `Avg ${fmtPct(avg)}`, fill: COLORS.text, fontSize: 9, fontFamily: 'IBM Plex Mono' }}
            />
          )}
          <Bar dataKey="denial_rate" name="Denial Rate" fill="url(#grad-red)" stroke={COLORS.red} strokeWidth={0} radius={[3,3,0,0]} />
          <Line type="monotone" dataKey="rolling_avg" name="3M Avg" stroke={COLORS.gold} strokeWidth={2} dot={false} strokeDasharray="4 2" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartPanel>
  )
}