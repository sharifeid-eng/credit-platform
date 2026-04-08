import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtPct, COLORS,
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

export default function TenureAnalysisChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/tenure`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(res => {
        setData(res.data)
        setError(null)
      })
      .catch(() => setError('Failed to load tenure analysis data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const distribution = data?.distribution ?? []
  const byProduct = data?.by_product ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* KPI Cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
          <KpiCard
            label="Average Tenure"
            value={data.avg_tenure != null ? `${data.avg_tenure.toFixed(1)}w` : '\u2013'}
            sub="Weighted by disbursed amount"
            color="gold"
          />
          <KpiCard
            label="Median Tenure"
            value={data.median_tenure != null ? `${data.median_tenure.toFixed(1)}w` : '\u2013'}
            sub="50th percentile"
            color="blue"
          />
        </div>
      )}

      {/* Tenure Distribution */}
      <ChartPanel
        title="Tenure Distribution"
        subtitle="Number of deals by tenure band"
        loading={loading}
        error={error}
        minHeight={280}
      >
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={distribution} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="band" {...xAxisProps} />
            <YAxis {...yAxisProps} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => [v.toLocaleString(), name]}
            />
            <Legend {...legendProps} />
            <Bar dataKey="count" name="Deals" fill="url(#grad-gold)" stroke={COLORS.gold} strokeWidth={0} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* Performance by Tenure Band */}
      <ChartPanel
        title="Performance by Tenure Band"
        subtitle="Collection rate, DPD rate, and margin rate across tenure segments"
        loading={loading}
        error={error}
        minHeight={300}
      >
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={distribution} barCategoryGap="20%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="band" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtPct(v)} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => [fmtPct(v), name]}
            />
            <Legend {...legendProps} />
            <Bar dataKey="collection_rate" name="Collection Rate" fill={COLORS.teal} radius={[3, 3, 0, 0]} />
            <Bar dataKey="dpd_rate" name="DPD Rate" fill={COLORS.red} radius={[3, 3, 0, 0]} />
            <Bar dataKey="margin_rate" name="Margin Rate" fill={COLORS.blue} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        {distribution.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: 12 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
              <thead>
                <tr>
                  {['Band', 'Deals', 'Collection %', 'DPD %', 'PAR30 %', 'Margin %', 'Avg Tenure'].map(h => (
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
                {distribution.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-primary)', fontWeight: 500 }}>{row.band}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{row.count?.toLocaleString()}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.collection_rate >= 90 ? '#2DD4BF' : row.collection_rate >= 70 ? '#C9A84C' : '#F06060' }}>
                      {fmtPct(row.collection_rate)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.dpd_rate <= 5 ? '#2DD4BF' : row.dpd_rate <= 15 ? '#C9A84C' : '#F06060' }}>
                      {fmtPct(row.dpd_rate)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.par30_rate <= 5 ? '#2DD4BF' : row.par30_rate <= 15 ? '#C9A84C' : '#F06060' }}>
                      {fmtPct(row.par30_rate)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.margin_rate >= 5 ? '#2DD4BF' : row.margin_rate >= 0 ? '#C9A84C' : '#F06060' }}>
                      {fmtPct(row.margin_rate)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {row.avg_tenure != null ? `${row.avg_tenure.toFixed(1)}w` : '\u2013'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartPanel>

      {/* Tenure by Product */}
      <ChartPanel
        title="Tenure by Product"
        subtitle="Average, median, and range of loan tenure per product type"
        loading={loading}
        error={error}
        minHeight={byProduct.length > 0 ? 0 : 200}
      >
        {byProduct.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(byProduct.length, 3)}, 1fr)`, gap: 12 }}>
            {byProduct.map((p, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                padding: '16px',
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
                  {p.product}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
                  {p.count?.toLocaleString()} deals
                </div>

                {/* Tenure bar visualization */}
                <div style={{ marginTop: 12, marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--text-muted)', marginBottom: 4 }}>
                    <span>Min: {p.min_tenure != null ? `${p.min_tenure.toFixed(1)}w` : '\u2013'}</span>
                    <span>Max: {p.max_tenure != null ? `${p.max_tenure.toFixed(1)}w` : '\u2013'}</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
                    {p.min_tenure != null && p.max_tenure != null && p.max_tenure > 0 && (
                      <>
                        {/* Average marker */}
                        <div style={{
                          position: 'absolute',
                          left: `${Math.min(((p.avg_tenure - p.min_tenure) / (p.max_tenure - p.min_tenure)) * 100, 100)}%`,
                          top: -2,
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          background: '#C9A84C',
                          transform: 'translateX(-50%)',
                        }} />
                        {/* Median marker */}
                        <div style={{
                          position: 'absolute',
                          left: `${Math.min(((p.median_tenure - p.min_tenure) / (p.max_tenure - p.min_tenure)) * 100, 100)}%`,
                          top: -2,
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          background: '#5B8DEF',
                          transform: 'translateX(-50%)',
                          border: '2px solid var(--bg-surface)',
                        }} />
                      </>
                    )}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8, marginTop: 12 }}>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Average</div>
                    <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#C9A84C' }}>
                      {p.avg_tenure != null ? `${p.avg_tenure.toFixed(1)}w` : '\u2013'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Median</div>
                    <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#5B8DEF' }}>
                      {p.median_tenure != null ? `${p.median_tenure.toFixed(1)}w` : '\u2013'}
                    </div>
                  </div>
                </div>

                {/* Legend dots */}
                <div style={{ display: 'flex', gap: 12, marginTop: 10, fontSize: 9, color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#C9A84C' }} />
                    Avg
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#5B8DEF' }} />
                    Median
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0', fontSize: 11 }}>
            No product tenure data available.
          </div>
        )}
      </ChartPanel>
    </div>
  )
}
