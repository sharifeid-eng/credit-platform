import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getDeploymentChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney,
} from '../../styles/chartTheme'

export default function DeploymentChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getDeploymentChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const raw = res.data ?? res
        const normalised = raw.map(d => ({
          month:        d.Month ?? d.month,
          new_business: d.new_business,
          repeat:       d.repeat_business ?? d.repeat,
        }))
        setData(normalised)
        setError(null)
      })
      .catch(() => setError('Failed to load deployment data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  return (
    <ChartPanel
      title="Capital Deployed"
      subtitle="Monthly new vs repeat originations — stacked by deal type"
      loading={loading}
      error={error}
    >
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} barCategoryGap="30%">
          <GradientDefs />
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" {...xAxisProps} />
          <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
          <Tooltip
            {...tooltipStyle}
            formatter={(v, name) => [fmtMoney(v, currency), name]}
          />
          <Legend {...legendProps} />
          <Bar dataKey="new_business"  name="New"    stackId="a" fill="url(#grad-blue)" stroke="#5B8DEF" strokeWidth={0} radius={[0,0,0,0]} />
          <Bar dataKey="repeat"        name="Repeat" stackId="a" fill="url(#grad-gold)" stroke="#C9A84C" strokeWidth={0} radius={[3,3,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartPanel>
  )
}
