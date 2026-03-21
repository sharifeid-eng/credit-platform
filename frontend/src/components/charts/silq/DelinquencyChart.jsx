import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LineChart, Line,
} from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps, GradientDefs, fmtMoney, fmtPct, COLORS } from '../../../styles/chartTheme'

function KpiCard({ label, value, sub, color }) {
  const colors = { gold: '#C9A84C', teal: '#2DD4BF', red: '#F06060', blue: '#5B8DEF' }
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', position: 'relative' }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: colors[color] || colors.gold, borderRadius: '10px 0 0 10px' }} />
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'IBM Plex Mono' }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function DelinquencyChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/delinquency`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load delinquency data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const buckets = data?.buckets ?? []
  const monthly = data?.monthly ?? []
  const topShops = (data?.top_shops ?? []).slice(0, 10)
  const par30 = data?.par30 ?? 0
  const par60 = data?.par60 ?? 0
  const par90 = data?.par90 ?? 0
  const ccy = data?.currency ?? currency

  const fmt = (v) => fmtMoney(v, ccy)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <KpiCard label="PAR 30+" value={fmtPct(par30)} sub="Portfolio at risk > 30 DPD" color="gold" />
        <KpiCard label="PAR 60+" value={fmtPct(par60)} sub="Portfolio at risk > 60 DPD" color="red" />
        <KpiCard label="PAR 90+" value={fmtPct(par90)} sub="Portfolio at risk > 90 DPD" color="red" />
      </div>

      {/* DPD Bucket Distribution */}
      <ChartPanel title="DPD Bucket Distribution" subtitle="Overdue amount by days past due bucket" loading={loading} error={error} minHeight={320}>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={buckets} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
            <GradientDefs />
            <CartesianGrid {...gridProps} horizontal={false} vertical />
            <XAxis type="number" {...xAxisProps} tickFormatter={fmt} />
            <YAxis type="category" dataKey="label" {...yAxisProps} width={80} />
            <Tooltip {...tooltipStyle} formatter={(v, name) => {
              if (name === 'amount') return [fmt(v), 'Amount']
              return [v, name]
            }} />
            <Bar dataKey="amount" name="Amount" fill="url(#grad-gold)" radius={[0, 4, 4, 0]} barSize={20} />
          </BarChart>
        </ResponsiveContainer>
        {buckets.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 10, paddingLeft: 8 }}>
            {buckets.map((b, i) => (
              <div key={i} style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'IBM Plex Mono', fontWeight: 600 }}>{b.label}</span>
                {' — '}{b.count} loans ({fmtPct(b.pct)})
              </div>
            ))}
          </div>
        )}
      </ChartPanel>

      {/* Top Overdue Shops */}
      <ChartPanel title="Top Overdue Shops" subtitle="Top 10 shops by total overdue amount" loading={loading} error={error} minHeight={320}>
        {topShops.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 280, fontSize: 11, color: 'var(--text-muted)' }}>
            No overdue shops to display
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(280, topShops.length * 36)}>
            <BarChart data={topShops} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <GradientDefs />
              <CartesianGrid {...gridProps} horizontal={false} vertical />
              <XAxis type="number" {...xAxisProps} tickFormatter={fmt} />
              <YAxis
                type="category"
                dataKey="shop_id"
                {...yAxisProps}
                width={120}
                tick={{ fill: COLORS.text, fontSize: 9, fontFamily: 'IBM Plex Mono' }}
              />
              <Tooltip {...tooltipStyle} formatter={(v, name) => {
                if (name === 'overdue') return [fmt(v), 'Overdue']
                if (name === 'count') return [v, 'Loans']
                return [v, name]
              }} />
              <Bar dataKey="overdue" name="Overdue" fill={COLORS.red} radius={[0, 4, 4, 0]} barSize={18} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>

      {/* Monthly Delinquency Trend */}
      <ChartPanel title="Monthly Delinquency Trend" subtitle="Overdue rate and PAR30 rate over time" loading={loading} error={error} minHeight={300}>
        {monthly.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, fontSize: 11, color: 'var(--text-muted)' }}>
            Insufficient monthly data
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={monthly} margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="Month" {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={(v) => fmtPct(v)} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => {
                if (name === 'overdue_rate') return [fmtPct(v), 'Overdue Rate']
                if (name === 'par30_rate') return [fmtPct(v), 'PAR30 Rate']
                return [fmtPct(v), name]
              }} />
              <Legend {...legendProps} />
              <Line type="monotone" dataKey="overdue_rate" name="Overdue Rate" stroke={COLORS.red} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="par30_rate" name="PAR30 Rate" stroke={COLORS.gold} strokeWidth={2} dot={false} strokeDasharray="6 3" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartPanel>
    </div>
  )
}
