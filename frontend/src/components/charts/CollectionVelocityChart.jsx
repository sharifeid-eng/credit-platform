import { useState, useEffect } from 'react'
import {
  ComposedChart, BarChart, Bar, Line, LineChart, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell, PieChart, Pie, ReferenceLine,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getCollectionVelocityChart, getCollectionCurvesChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtPct, fmtMoney, COLORS,
} from '../../styles/chartTheme'

const BUCKET_COLORS = ['#2DD4BF', '#5B8DEF', '#C9A84C', '#F59E0B', '#F06060', '#A78BFA']

function rolling3m(arr, key) {
  return arr.map((d, i) => {
    const slice = arr.slice(Math.max(0, i - 2), i + 1)
    const avg = slice.reduce((s, x) => s + (x[key] ?? 0), 0) / slice.length
    return { ...d, rolling_avg: parseFloat(avg.toFixed(2)) }
  })
}

function getAccuracyColor(accuracy) {
  if (accuracy >= 90 && accuracy <= 110) return COLORS.teal
  if ((accuracy >= 80 && accuracy < 90) || (accuracy > 110 && accuracy <= 130)) return COLORS.gold
  return COLORS.red
}

export default function CollectionVelocityChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]             = useState([])
  const [buckets, setBuckets]       = useState([])
  const [avgDays, setAvgDays]       = useState(0)
  const [totalCompleted, setTotal]  = useState(0)
  const [curveBased, setCurveBased] = useState(false)
  const [curves, setCurves]         = useState(null)
  const [curvesAvailable, setCurvesAvailable] = useState(false)
  const [hasForecast, setHasForecast] = useState(false)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    Promise.all([
      getCollectionVelocityChart(company, product, snapshot, currency, asOfDate),
      getCollectionCurvesChart(company, product, snapshot, currency, asOfDate).catch(() => null),
    ])
      .then(([res, curvesRes]) => {
        // Collection velocity data
        const raw = res.monthly ?? res.data ?? res
        const forecast = res.has_forecast ?? false
        setHasForecast(forecast)
        const normalised = raw.map(d => ({
          month:           d.Month ?? d.month,
          collection_rate: d.collection_rate,
          ...(forecast && d.expected_rate != null ? { expected_rate: d.expected_rate } : {}),
        }))
        setData(rolling3m(normalised, 'collection_rate'))
        setBuckets((res.buckets ?? []).filter(b => b.deal_count > 0))
        setAvgDays(res.avg_days ?? 0)
        setTotal(res.total_completed ?? 0)
        setCurveBased(res.curve_based ?? false)
        setError(null)

        // Collection curves data
        if (curvesRes && curvesRes.aggregate && curvesRes.aggregate.points && curvesRes.aggregate.points.length > 0) {
          setCurves(curvesRes)
          setCurvesAvailable(true)
        } else {
          setCurves(null)
          setCurvesAvailable(false)
        }
      })
      .catch(() => setError('Failed to load collection data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const totalCollected = buckets.reduce((s, b) => s + b.collected, 0)
  const pieData = buckets.map(b => ({
    name: b.bucket,
    value: b.deal_count,
  }))

  // Prepare curves chart data
  const ACCURACY_CAP = 200
  const curvePoints = curvesAvailable
    ? curves.aggregate.points.map(pt => {
        const rawAccuracy = pt.expected_pct > 0
          ? parseFloat(((pt.actual_pct / pt.expected_pct) * 100).toFixed(1))
          : null
        return {
          days: pt.days,
          label: `${pt.days}d`,
          actual_pct: pt.actual_pct != null ? parseFloat(pt.actual_pct.toFixed(1)) : null,
          expected_pct: pt.expected_pct != null ? parseFloat(pt.expected_pct.toFixed(1)) : null,
          accuracy: rawAccuracy != null ? Math.min(rawAccuracy, ACCURACY_CAP) : null,
          rawAccuracy,
        }
      })
    : []

  return (
    <>
      <ChartPanel
        title="Collection Rate"
        subtitle={hasForecast
          ? "Monthly collection rate by origination vintage — expected rate shows forecast benchmark per vintage"
          : "Monthly collection rate % with 3-month rolling average overlay"
        }
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
            {hasForecast && (
              <Line type="monotone" dataKey="expected_rate" name="Expected Rate" stroke={COLORS.blue} strokeWidth={2} dot={false} strokeDasharray="6 3" />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {buckets.length > 0 && (
        <ChartPanel
          title="Cash Collection — Breakdown by Deal Age"
          subtitle={`${totalCompleted.toLocaleString()} completed deals grouped by ${curveBased ? 'days to collect (curve-based)' : 'days since purchase'} — excludes active deals still collecting`}
          loading={loading}
          error={error}
        >
          <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
            {/* Horizontal bar chart */}
            <div style={{ flex: 1 }}>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={buckets} layout="vertical" barCategoryGap="25%">
                  <GradientDefs />
                  <CartesianGrid {...gridProps} horizontal={false} />
                  <XAxis type="number" {...xAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
                  <YAxis type="category" dataKey="bucket" {...yAxisProps} width={90} />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v, name) => [
                      name === 'Collected' ? fmtMoney(v, currency) : v.toLocaleString(),
                      name,
                    ]}
                  />
                  <Legend {...legendProps} />
                  <Bar dataKey="collected" name="Collected" radius={[0,3,3,0]}>
                    {buckets.map((_, i) => (
                      <Cell key={i} fill={BUCKET_COLORS[i % BUCKET_COLORS.length]} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Summary donut + stat */}
            <div style={{ width: 200, textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%" cy="50%"
                    innerRadius={50} outerRadius={75}
                    dataKey="value"
                    stroke="none"
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={BUCKET_COLORS[i % BUCKET_COLORS.length]} fillOpacity={0.8} />
                    ))}
                  </Pie>
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v, name) => [`${v.toLocaleString()} deals`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ fontFamily: 'IBM Plex Mono', color: '#E8EAF0', fontSize: 28, fontWeight: 700 }}>
                {Math.round(avgDays)}
              </div>
              <div style={{ fontFamily: 'Inter', color: '#8494A7', fontSize: 11, marginTop: 2 }}>
                {curveBased ? 'Avg Days to Collect' : 'Avg Days Outstanding'}
              </div>
            </div>
          </div>
        </ChartPanel>
      )}

      {curvesAvailable === true && (
        <ChartPanel
          title="Collection Curves — Expected vs Actual"
          subtitle="Cumulative % of purchase value collected at 30-day intervals (portfolio aggregate)"
          loading={loading}
          error={error}
        >
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={curvePoints}>
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} domain={[0, 100]} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name) => [fmtPct(v), name]}
                labelFormatter={label => `Day ${label}`}
              />
              <Legend {...legendProps} />
              <Line
                type="monotone"
                dataKey="actual_pct"
                name="Actual"
                stroke={COLORS.teal}
                strokeWidth={2}
                dot={{ r: 3, fill: COLORS.teal }}
                activeDot={{ r: 5 }}
              />
              <Line
                type="monotone"
                dataKey="expected_pct"
                name="Expected"
                stroke={COLORS.blue}
                strokeWidth={2}
                strokeDasharray="6 3"
                dot={{ r: 3, fill: COLORS.blue }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>
      )}

      {curvesAvailable === true && (
        <ChartPanel
          title="Model Accuracy by Interval"
          subtitle="Actual collection as % of expected at each milestone"
          loading={loading}
          error={error}
        >
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={curvePoints} barCategoryGap="25%">
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => `${v}%`} domain={[0, ACCURACY_CAP]} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name, props) => {
                  const real = props.payload.rawAccuracy
                  return [`${real != null ? real : v}%`, 'Accuracy']
                }}
                labelFormatter={label => `Day ${label}`}
              />
              <ReferenceLine y={100} stroke={COLORS.text} strokeDasharray="4 2" label={{
                value: '100%',
                position: 'right',
                fill: COLORS.text,
                fontSize: 10,
                fontFamily: 'IBM Plex Mono',
              }} />
              <Bar dataKey="accuracy" name="Accuracy" radius={[3,3,0,0]}
                label={({ x, y, width, index }) => {
                  const pt = curvePoints[index]
                  if (!pt || pt.rawAccuracy == null || pt.rawAccuracy <= ACCURACY_CAP) return null
                  return (
                    <text x={x + width / 2} y={y - 4} textAnchor="middle"
                      fill={COLORS.red} fontSize={9} fontFamily="IBM Plex Mono">
                      {pt.rawAccuracy}%
                    </text>
                  )
                }}
              >
                {curvePoints.map((pt, i) => (
                  <Cell key={i} fill={getAccuracyColor(pt.rawAccuracy)} fillOpacity={0.75} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
      )}
    </>
  )
}
