import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getCollectionVelocityChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtPct, COLORS,
} from '../../styles/chartTheme'

function rolling3m(arr, key) {
  return arr.map((d, i) => {
    const slice = arr.slice(Math.max(0, i - 2), i + 1)
    const avg = slice.reduce((s, x) => s + (x[key] ?? 0), 0) / slice.length
    return { ...d, rolling_avg: parseFloat(avg.toFixed(2)) }
  })
}

export default function CollectionVelocityChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getCollectionVelocityChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const raw = res.monthly ?? res.data ?? res
        const normalised = raw.map(d => ({
          month:           d.Month ?? d.month,
          collection_rate: d.collection_rate,
        }))
        setData(rolling3m(normalised, 'collection_rate'))
        setError(null)
      })
      .catch(() => setError('Failed to load collection data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  return (
    <ChartPanel
      title="Collection Velocity"
      subtitle="Monthly collection rate % with 3-month rolling average overlay"
      loading={loading}
      error={error}
    >
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} barCategoryGap="30%">
          <GradientDefs />
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" {...xAxisProps} />
          <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} domain={[0, 110]} />
          <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtPct(v), name]} />
          <Legend {...legendProps} />
          <Bar dataKey="collection_rate" name="Collection Rate" fill="url(#grad-teal)" stroke={COLORS.teal} strokeWidth={0} radius={[3,3,0,0]} />
          <Line type="monotone" dataKey="rolling_avg" name="3M Avg" stroke={COLORS.gold} strokeWidth={2} dot={false} strokeDasharray="4 2" />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartPanel>
  )
}
