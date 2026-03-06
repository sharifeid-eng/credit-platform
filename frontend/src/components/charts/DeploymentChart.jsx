import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getDeploymentChart, getDeploymentByProductChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, COLORS,
} from '../../styles/chartTheme'

const PRODUCT_COLORS = ['#5B8DEF', '#C9A84C', '#2DD4BF', '#F06060', '#A78BFA', '#F59E0B']
const PRODUCT_GRADS  = ['grad-blue', 'grad-gold', 'grad-teal', 'grad-red']

export default function DeploymentChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]               = useState([])
  const [prodData, setProdData]       = useState([])
  const [prodNames, setProdNames]     = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    Promise.all([
      getDeploymentChart(company, product, snapshot, currency, asOfDate),
      getDeploymentByProductChart(company, product, snapshot, currency, asOfDate),
    ])
      .then(([res, prodRes]) => {
        const raw = res.data ?? res
        setData(raw.map(d => ({
          month:        d.Month ?? d.month,
          new_business: d.new_business,
          repeat:       d.repeat_business ?? d.repeat,
        })))

        const pMonthly = prodRes.monthly ?? []
        setProdNames(prodRes.products ?? [])
        setProdData(pMonthly.map(d => ({ ...d, month: d.Month ?? d.month })))
        setError(null)
      })
      .catch(() => setError('Failed to load deployment data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  return (
    <>
      <ChartPanel
        title="Capital Deployed by Business Type"
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

      {prodNames.length > 0 && (
        <ChartPanel
          title="Capital Deployed by Product"
          subtitle="Monthly capital deployed — stacked by product type"
          loading={loading}
          error={error}
        >
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={prodData} barCategoryGap="30%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="month" {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name) => [fmtMoney(v, currency), name]}
              />
              <Legend {...legendProps} />
              {prodNames.map((name, i) => (
                <Bar
                  key={name}
                  dataKey={name}
                  name={name.charAt(0).toUpperCase() + name.slice(1)}
                  stackId="b"
                  fill={`url(#${PRODUCT_GRADS[i % PRODUCT_GRADS.length]})`}
                  stroke={PRODUCT_COLORS[i % PRODUCT_COLORS.length]}
                  strokeWidth={0}
                  radius={i === prodNames.length - 1 ? [3,3,0,0] : [0,0,0,0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      )}
    </>
  )
}
