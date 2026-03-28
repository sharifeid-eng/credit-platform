import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, ComposedChart } from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps, fmtMoney, COLORS } from '../../../styles/chartTheme'

export default function SilqSeasonalityChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/seasonality`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load seasonality data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (!data?.available) {
    return <ChartPanel title="Seasonality" subtitle="Requires disbursement date data" loading={loading} error={error || 'Not available for this tape'} minHeight={200} />
  }

  const months = data.months || []
  const years = data.years || []
  const seasonalIndex = data.seasonal_index || []
  const ccy = data.currency || currency
  const yearColors = ['#5B8DEF', '#C9A84C', '#2DD4BF', '#F06060']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <ChartPanel title="Disbursement by Calendar Month" subtitle="Year-over-year comparison of origination volume" loading={loading} error={error} minHeight={320}>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={months} {...gridProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="month_name" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, ccy)} />
            <Tooltip {...tooltipStyle} formatter={v => fmtMoney(v, ccy)} />
            <Legend {...legendProps} />
            {years.map((y, i) => (
              <Bar key={y} dataKey={`volume_${y}`} name={String(y)} fill={yearColors[i % yearColors.length]} radius={[4,4,0,0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      <ChartPanel title="Seasonal Index" subtitle="Month avg / overall avg (1.0 = average)" loading={loading} error={error} minHeight={250}>
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={seasonalIndex} {...gridProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="month_name" {...xAxisProps} />
            <YAxis {...yAxisProps} domain={[0, 'auto']} />
            <Tooltip {...tooltipStyle} />
            <Bar dataKey="index" fill="#5B8DEF" radius={[4,4,0,0]} name="Seasonal Index" />
            <Line type="monotone" dataKey={() => 1} stroke="#C9A84C" strokeDasharray="5 5" dot={false} name="Average (1.0)" />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  )
}
