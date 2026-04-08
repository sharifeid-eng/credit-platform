import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, BarChart,
} from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../../styles/chartTheme'

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

export default function YieldMarginsChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/yield-margins`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(res => {
        setData(res.data)
        setError(null)
      })
      .catch(() => setError('Failed to load yield & margins data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const cur = data?.currency ?? currency
  const monthly = (data?.monthly ?? []).map(d => ({
    month: d.Month ?? d.month,
    margin: d.margin,
    disbursed: d.disbursed,
    margin_rate: d.margin_rate,
  }))
  const byProduct = data?.by_product ?? []
  const byTenure = data?.by_tenure ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPI Cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
          <KpiCard
            label="Portfolio Margin Rate"
            value={fmtPct(data.margin_rate)}
            sub={`On ${fmtMoney(data.total_disbursed, cur)} disbursed`}
            color="gold"
          />
          <KpiCard
            label="Realised Margin"
            value={fmtPct(data.realised_margin_rate)}
            sub="Closed deals only"
            color="teal"
          />
          <KpiCard
            label="Total Margin Earned"
            value={fmtMoney(data.total_margin, cur)}
            sub={`${fmtPct(data.margin_rate)} of capital deployed`}
            color="blue"
          />
        </div>
      )}

      {/* Monthly Margin Trend */}
      <ChartPanel
        title="Monthly Margin Trend"
        subtitle="Margin earned per month with margin rate % overlay"
        loading={loading}
        error={error}
      >
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={monthly} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="month" {...xAxisProps} />
            <YAxis yAxisId="amt" {...yAxisProps} tickFormatter={v => fmtMoney(v, cur)} />
            <YAxis yAxisId="pct" orientation="right" {...yAxisProps} tickFormatter={v => fmtPct(v)} width={42} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) =>
                name === 'Margin Rate' ? [fmtPct(v), name] : [fmtMoney(v, cur), name]
              }
            />
            <Legend {...legendProps} />
            <Bar yAxisId="amt" dataKey="margin" name="Margin" fill="url(#grad-teal)" stroke={COLORS.teal} strokeWidth={0} radius={[3, 3, 0, 0]} />
            <Line yAxisId="pct" type="monotone" dataKey="margin_rate" name="Margin Rate" stroke={COLORS.gold} strokeWidth={2} dot={{ fill: COLORS.gold, r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* Margin by Product */}
      <ChartPanel
        title="Margin by Product"
        subtitle="Margin rate comparison across product types"
        loading={loading}
        error={error}
        minHeight={240}
      >
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={byProduct} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="product" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => {
                if (name === 'Margin Rate') return [fmtPct(v), name]
                if (name === 'Disbursed') return [fmtMoney(v, cur), name]
                return [v.toLocaleString(), name]
              }}
            />
            <Legend {...legendProps} />
            <Bar dataKey="margin_rate" name="Margin Rate" fill={COLORS.teal} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {byProduct.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${byProduct.length}, 1fr)`, gap: 10, marginTop: 12 }}>
            {byProduct.map((p, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '10px 12px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{p.product}</div>
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                  {fmtMoney(p.margin, cur)}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
                  {p.deals} deals &middot; {fmtMoney(p.disbursed, cur)} deployed
                </div>
              </div>
            ))}
          </div>
        )}
        {data?.margin_not_available?.length > 0 && (
          <div style={{
            marginTop: 12, padding: '8px 12px',
            background: 'rgba(201,168,76,0.06)',
            border: '1px solid rgba(201,168,76,0.2)',
            borderRadius: 6, fontSize: 11,
            color: 'var(--text-muted)', lineHeight: 1.5,
          }}>
            <span style={{ color: 'var(--accent-gold)', marginRight: 6 }}>&#x2139;</span>
            <strong>{data.margin_not_available.join(', ')}</strong> &mdash; RBF revenue structure does not break out margin separately. 0% margin reflects missing source data, not zero earnings.
          </div>
        )}
      </ChartPanel>

      {/* Margin by Tenure Band */}
      <ChartPanel
        title="Margin by Tenure Band"
        subtitle="How margin rate varies with loan tenure"
        loading={loading}
        error={error}
        minHeight={260}
      >
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={byTenure} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="band" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => {
                if (name === 'Margin Rate') return [fmtPct(v), name]
                if (name === 'Disbursed') return [fmtMoney(v, cur), name]
                return [v.toLocaleString(), name]
              }}
            />
            <Legend {...legendProps} />
            <Bar dataKey="margin_rate" name="Margin Rate" fill={COLORS.blue} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {byTenure.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: 12 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
              <thead>
                <tr>
                  {['Band', 'Deals', 'Disbursed', 'Margin', 'Rate'].map(h => (
                    <th key={h} style={{
                      textAlign: h === 'Band' ? 'left' : 'right',
                      padding: '6px 8px',
                      fontSize: 9,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: 'var(--text-muted)',
                      borderBottom: '1px solid var(--border)',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byTenure.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-primary)', fontWeight: 500 }}>{row.band}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{row.deals?.toLocaleString()}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: '#C9A84C' }}>{fmtMoney(row.disbursed, cur)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: '#2DD4BF' }}>{fmtMoney(row.margin, cur)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.margin_rate >= 5 ? '#2DD4BF' : row.margin_rate >= 0 ? '#C9A84C' : '#F06060' }}>
                      {fmtPct(row.margin_rate)}
                    </td>
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
