import { useState, useEffect } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getAgeingChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

const HEALTH_COLORS = {
  Healthy: '#2DD4BF',
  Watch:   '#C9A84C',
  Delayed: '#F06060',
  Poor:    '#8B1A1A',
}

const HEALTH_ORDER = ['Healthy', 'Watch', 'Delayed', 'Poor']

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
        // Monthly health breakdown for stacked bars
        const monthlyHealth = (res.monthly_health ?? []).map(d => ({
          month:   d.Month ?? d.month,
          Healthy: d.Healthy ?? 0,
          Watch:   d.Watch ?? 0,
          Delayed: d.Delayed ?? 0,
          Poor:    d.Poor ?? 0,
          total:   d.total ?? 0,
        }))
        const totalActiveValue = res.total_active_value ?? 0
        setData({ donut, buckets, monthlyHealth, totalActiveValue })
        setError(null)
      })
      .catch(() => setError('Failed to load ageing data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const donut         = data?.donut ?? []
  const buckets       = data?.buckets ?? []
  const monthlyHealth = data?.monthlyHealth ?? []
  const totalActive   = data?.totalActiveValue ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* ── Monthly Health Stacked Bars + Cumulative Donut ── */}
      {monthlyHealth.length > 0 && (
        <ChartPanel
          title="Active Portfolio — Health Over Time"
          subtitle="Face value of active (Executed) deals by health classification — does not deduct amounts already collected"
          loading={loading} error={error}
        >
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            {/* Stacked bar chart */}
            <div style={{ flex: 1 }}>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={monthlyHealth} barCategoryGap="25%">
                  <GradientDefs />
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="month" {...xAxisProps} />
                  <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
                  <Tooltip
                    {...tooltipStyle}
                    formatter={(v, name) => [fmtMoney(v, currency), name]}
                  />
                  <Legend {...legendProps} />
                  {HEALTH_ORDER.map((status, i) => (
                    <Bar
                      key={status}
                      dataKey={status}
                      name={status}
                      stackId="health"
                      fill={HEALTH_COLORS[status]}
                      radius={i === HEALTH_ORDER.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Cumulative donut + legend on right */}
            <div style={{ width: 220, textAlign: 'center', flexShrink: 0 }}>
              <div style={{
                fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
                letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8,
              }}>
                Cumulative
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={donut} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={2}>
                    {donut.map((d, i) => <Cell key={i} fill={HEALTH_COLORS[d.name] ?? COLORS.muted} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
                </PieChart>
              </ResponsiveContainer>
              {totalActive > 0 && (
                <div style={{ marginTop: -8, marginBottom: 10, textAlign: 'center' }}>
                  <div style={{
                    fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: 'var(--text-primary)',
                  }}>
                    {fmtMoney(totalActive, currency)}
                  </div>
                  <div style={{
                    fontSize: 9, color: 'var(--text-muted)', fontWeight: 500, marginTop: 2,
                  }}>
                    Active Deal Face Value
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, textAlign: 'left', paddingLeft: 12 }}>
                {donut.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: HEALTH_COLORS[d.name] ?? COLORS.muted, flexShrink: 0 }} />
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1 }}>{d.name}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: HEALTH_COLORS[d.name] ?? COLORS.muted, fontWeight: 600 }}>
                      {fmtMoney(d.value, currency)}
                    </div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 36, textAlign: 'right' }}>
                      {fmtPct(d.pct)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </ChartPanel>
      )}

      {/* ── Ageing Buckets Bar Chart ── */}
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
