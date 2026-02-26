import { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ComposedChart, Area,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getReturnsAnalysisChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct,
} from '../../styles/chartTheme'

export default function ReturnsAnalysisChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getReturnsAnalysisChart(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load returns data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (loading || error || !data) {
    return <ChartPanel title="Returns Analysis" loading={loading} error={error} minHeight={200} />
  }

  const s = data.summary
  const ccy = data.currency ?? currency

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── KPI Tiles ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <Tile label="Total Deployed" value={fmtCcy(s.total_deployed, ccy)} color="var(--gold)" />
        <Tile label="Wtd Avg Discount" value={`${s.weighted_avg_discount}%`} color="var(--blue)" />
        <Tile label="Realised Margin" value={`${s.realised_margin}%`} sub={`Expected: ${s.expected_margin}%`}
          color={s.realised_margin >= s.expected_margin ? 'var(--teal)' : 'var(--red)'} />
        <Tile label="Completed Margin" value={`${s.completed_margin}%`} sub={`Loss rate: ${s.completed_loss_rate}%`} color="var(--teal)" />
        <Tile label="Fee Yield" value={`${s.fee_yield}%`} sub={fmtCcy(s.total_fees, ccy)} color="var(--gold)" />
        <Tile label="Provision Coverage" value={`${s.provision_coverage}%`} sub={fmtCcy(s.total_provisions, ccy)} color="var(--blue)" />
        <Tile label="Completed Loss Rate" value={`${s.completed_loss_rate}%`} color={s.completed_loss_rate > 5 ? 'var(--red)' : 'var(--teal)'} />
        <Tile label="Total Adjustments" value={fmtCcy(s.total_adjustments, ccy)} color="var(--text-muted)" />
      </div>

      {/* ── Monthly Margin Chart ── */}
      <ChartPanel title="Monthly Returns" subtitle="Realised vs expected margin by origination month" minHeight={0}>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data.monthly}>
            <defs>
              <linearGradient id="marginFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2DD4BF" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#2DD4BF" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="month" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => `${v}%`} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => [`${v.toFixed(2)}%`, name]}
            />
            <Legend {...legendProps} />
            <Area type="monotone" dataKey="realised_margin" name="Realised Margin" fill="url(#marginFill)" stroke="#2DD4BF" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="expected_margin" name="Expected Margin" stroke="#5B8DEF" strokeWidth={2} strokeDasharray="6 3" dot={false} />
            <Line type="monotone" dataKey="avg_discount" name="Avg Discount" stroke="#C9A84C" strokeWidth={1.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── Discount Band Analysis ── */}
      <ChartPanel title="Discount Band Performance" subtitle="Collection rate, denial rate, and margin by discount tier" minHeight={0}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Chart */}
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.discount_bands}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="band" {...xAxisProps} />
              <YAxis {...yAxisProps} tickFormatter={v => `${v}%`} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => [name.includes('Rate') || name.includes('Margin') ? `${v}%` : fmtCcy(v, ccy), name]} />
              <Legend {...legendProps} />
              <Bar dataKey="collection_rate" name="Collection Rate" fill="#2DD4BF" radius={[3,3,0,0]} />
              <Bar dataKey="denial_rate" name="Denial Rate" fill="#F06060" radius={[3,3,0,0]} />
              <Bar dataKey="margin" name="Margin" fill="#C9A84C" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          {/* Table */}
          <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  {['Band', 'Deals', 'Deployed', 'Coll %', 'Denial %', 'Margin'].map(h => (
                    <th key={h} style={{
                      textAlign: h === 'Band' ? 'left' : 'right', padding: '6px 8px',
                      fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '2px solid var(--border)',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.discount_bands.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>{r.band}</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: 'var(--text-secondary)' }}>{r.deals}</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: 'var(--gold)' }}>{fmtCcy(r.deployed, ccy)}</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: r.collection_rate >= 90 ? 'var(--teal)' : 'var(--gold)' }}>{r.collection_rate}%</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', color: r.denial_rate > 10 ? 'var(--red)' : 'var(--text-secondary)' }}>{r.denial_rate}%</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)', textAlign: 'right', fontWeight: 600, color: r.margin >= 0 ? 'var(--teal)' : 'var(--red)' }}>{r.margin}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </ChartPanel>

      {/* ── New vs Repeat ── */}
      {data.new_vs_repeat.length > 0 && (
        <ChartPanel title="New vs Repeat Business" subtitle="Performance comparison — do repeat clients perform better?" minHeight={0}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
            {data.new_vs_repeat.map((r, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                borderRadius: 8, padding: 16,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                  {r.type} Business
                  <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>
                    {r.deals} deals
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                  <MiniStat label="Deployed" value={fmtCcy(r.deployed, ccy)} color="var(--gold)" />
                  <MiniStat label="Collection Rate" value={`${r.collection_rate}%`} color={r.collection_rate >= 90 ? 'var(--teal)' : 'var(--gold)'} />
                  <MiniStat label="Denial Rate" value={`${r.denial_rate}%`} color={r.denial_rate > 10 ? 'var(--red)' : 'var(--text-secondary)'} />
                  <MiniStat label="Margin" value={`${r.margin}%`} color={r.margin >= 0 ? 'var(--teal)' : 'var(--red)'} />
                  <MiniStat label="Completion" value={`${r.completion_rate}%`} color={r.completion_rate >= 70 ? 'var(--teal)' : 'var(--red)'} />
                </div>
              </div>
            ))}
          </div>
        </ChartPanel>
      )}
    </div>
  )
}

/* ── Helpers ── */

function fmtCcy(v, ccy) {
  if (v == null) return '—'
  if (Math.abs(v) >= 1_000_000) return `${ccy} ${(v / 1_000_000).toFixed(1)}M`
  if (Math.abs(v) >= 1_000) return `${ccy} ${(v / 1_000).toFixed(0)}K`
  return `${ccy} ${v.toFixed(0)}`
}

function Tile({ label, value, sub, color }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '14px 16px',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: color, borderRadius: '8px 0 0 8px' }} />
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color, fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>
      )}
    </div>
  )
}

function MiniStat({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
        {value}
      </div>
    </div>
  )
}