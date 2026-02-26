import { useState, useEffect } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getAgeingChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

const HEALTH_COLORS = {
  Healthy: '#2DD4BF',
  Watch:   '#C9A84C',
  Delayed: '#F06060',
  Poor:    '#8B1A1A',
}

export default function AgeingChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getAgeingChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        // health_summary → donut, ageing_buckets → bar
        const donut = (res.health_summary ?? []).map(d => ({
          name:  d.status,
          value: d.value,
          pct:   d.percentage,
        }))
        const buckets = (res.ageing_buckets ?? []).map(d => ({
          bucket: d.bucket,
          value:  d.purchase_value,
        }))
        setData({ donut, buckets })
        setError(null)
      })
      .catch(() => setError('Failed to load ageing data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const donut   = data?.donut   ?? []
  const buckets = data?.buckets ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <ChartPanel title="Active Deal Health" subtitle="Health classification of open receivables by value" loading={loading} error={error} minHeight={260}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <ResponsiveContainer width={220} height={220}>
            <PieChart>
              <Pie data={donut} dataKey="value" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2}>
                {donut.map((d, i) => <Cell key={i} fill={HEALTH_COLORS[d.name] ?? COLORS.muted} />)}
              </Pie>
              <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
            {donut.map((d, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: HEALTH_COLORS[d.name] ?? COLORS.muted, flexShrink: 0 }} />
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{d.name}</div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: HEALTH_COLORS[d.name] ?? COLORS.muted, fontWeight: 600 }}>
                  {fmtPct(d.pct)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </ChartPanel>

      <ChartPanel title="Ageing Buckets" subtitle="Outstanding deal value by days since origination" loading={loading} error={error}>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={buckets} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="bucket" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
            <Tooltip {...tooltipStyle} formatter={(v) => [fmtMoney(v, currency), 'Outstanding']} />
            <Bar dataKey="value" name="Outstanding" fill="url(#grad-blue)" stroke={COLORS.blue} strokeWidth={0} radius={[3,3,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  )
}
