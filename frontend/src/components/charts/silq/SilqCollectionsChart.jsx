import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, LineChart, Line, ComposedChart,
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
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function SilqCollectionsChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/collections`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load collections data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const monthly = data?.monthly ?? []
  const byProduct = data?.by_product ?? []
  const totalRepaid = data?.total_repaid ?? 0
  const repaymentRate = data?.repayment_rate ?? 0
  const totalMargin = data?.total_margin ?? 0
  const totalPrincipal = data?.total_principal ?? 0
  const ccy = data?.currency ?? currency

  const fmt = (v) => fmtMoney(v, ccy)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
        <KpiCard label="Total Repaid" value={fmt(totalRepaid)} color="teal" />
        <KpiCard label="Repayment Rate" value={fmtPct(repaymentRate)} color="gold" />
        <KpiCard label="Total Margin" value={fmt(totalMargin)} sub="Revenue from interest & fees" color="blue" />
        <KpiCard label="Principal Collected" value={fmt(totalPrincipal)} color="teal" />
      </div>

      {/* Monthly Collections — stacked bars + rate line */}
      <ChartPanel title="Monthly Collections" subtitle="Principal and margin collected per month with repayment rate overlay" loading={loading} error={error} minHeight={340}>
        {monthly.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, fontSize: 11, color: 'var(--text-muted)' }}>
            No monthly data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart data={monthly} margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="Month" {...xAxisProps} />
              <YAxis yAxisId="left" {...yAxisProps} tickFormatter={fmt} />
              <YAxis yAxisId="right" orientation="right" {...yAxisProps} tickFormatter={(v) => fmtPct(v)} />
              <Tooltip
                {...tooltipStyle}
                formatter={(v, name) => {
                  if (name === 'Repayment Rate') return [fmtPct(v), name]
                  return [fmt(v), name]
                }}
              />
              <Legend {...legendProps} />
              <Bar yAxisId="left" dataKey="principal" name="Principal" stackId="stack" fill={COLORS.teal} radius={[0, 0, 0, 0]} />
              <Bar yAxisId="left" dataKey="margin" name="Margin" stackId="stack" fill={COLORS.gold} radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="rate" name="Repayment Rate" stroke={COLORS.blue} strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        )}
        {monthly.length > 0 && (
          <div style={{ display: 'flex', gap: 16, marginTop: 8, paddingLeft: 8 }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Total deals: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {monthly.reduce((s, m) => s + (m.deals || 0), 0).toLocaleString()}
              </span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Avg monthly rate: <span style={{ color: COLORS.blue, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {fmtPct(monthly.reduce((s, m) => s + (m.rate || 0), 0) / (monthly.filter(m => m.rate > 0).length || 1))}
              </span>
            </div>
          </div>
        )}
      </ChartPanel>

      {/* Collection by Product Type */}
      <ChartPanel title="Collection by Product Type" subtitle="Repaid amount and repayment rate by BNPL vs RBF" loading={loading} error={error} minHeight={300}>
        {byProduct.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, fontSize: 11, color: 'var(--text-muted)' }}>
            No product breakdown available
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
            {/* Repaid Amount bars */}
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Repaid Amount
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byProduct} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                  <GradientDefs />
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="product" {...xAxisProps} />
                  <YAxis {...yAxisProps} tickFormatter={fmt} />
                  <Tooltip {...tooltipStyle} formatter={(v) => [fmt(v), 'Repaid']} />
                  <Bar dataKey="repaid" fill={COLORS.teal} radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Repayment Rate bars */}
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Repayment Rate
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byProduct} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="product" {...xAxisProps} />
                  <YAxis {...yAxisProps} tickFormatter={(v) => fmtPct(v)} domain={[0, 100]} />
                  <Tooltip {...tooltipStyle} formatter={(v) => [fmtPct(v), 'Rate']} />
                  <Bar dataKey="rate" fill={COLORS.gold} radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
        {byProduct.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: 12 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  {['Product', 'Deals', 'Collectable', 'Repaid', 'Rate'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byProduct.map((p, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 10px', color: 'var(--text-primary)', fontWeight: 500 }}>{p.product}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{(p.deals || 0).toLocaleString()}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: COLORS.gold }}>{fmt(p.collectable)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: COLORS.teal }}>{fmt(p.repaid)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: p.rate >= 90 ? COLORS.teal : COLORS.text }}>{fmtPct(p.rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartPanel>
    </div>
  )
}
