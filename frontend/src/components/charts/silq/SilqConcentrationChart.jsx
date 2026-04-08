import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps, GradientDefs, fmtMoney, fmtPct, COLORS } from '../../../styles/chartTheme'

const SLICE_COLORS = [
  '#C9A84C', '#2DD4BF', '#5B8DEF', '#F06060',
  '#A78BFA', '#FB923C', '#34D399', '#F472B6',
  '#60A5FA', '#FBBF24', '#818CF8',
]

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

export default function SilqConcentrationChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/concentration`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load concentration data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const shops = data?.shops ?? []
  const hhi = data?.hhi ?? 0
  const utilization = (data?.utilization ?? []).slice(0, 15)
  const productMix = data?.product_mix ?? []
  const sizeDistribution = data?.size_distribution ?? []
  const ccy = data?.currency ?? currency

  const fmt = (v) => fmtMoney(v, ccy)

  // Build pie data: top 10 + "Other"
  const top10 = shops.slice(0, 10)
  const otherTotal = shops.slice(10).reduce((s, sh) => s + (sh.disbursed || 0), 0)
  const otherShare = shops.slice(10).reduce((s, sh) => s + (sh.share || 0), 0)
  const pieData = otherTotal > 0
    ? [...top10, { shop_id: 'Other', disbursed: otherTotal, share: otherShare, deals: shops.slice(10).reduce((s, sh) => s + (sh.deals || 0), 0) }]
    : top10

  // HHI classification
  const hhiLevel = hhi > 0.25 ? 'High' : hhi > 0.15 ? 'Moderate' : 'Low'
  const hhiColor = hhi > 0.25 ? 'red' : hhi > 0.15 ? 'gold' : 'teal'

  // Top shop stats
  const topShop = shops[0]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* KPI Row: HHI + top shop stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
        <KpiCard
          label="HHI Index"
          value={hhi.toFixed(4)}
          sub={`${hhiLevel} concentration`}
          color={hhiColor}
        />
        {topShop && (
          <KpiCard
            label="Top Shop"
            value={topShop.shop_id}
            sub={`${fmtPct(topShop.share)} of portfolio — ${fmt(topShop.disbursed)}`}
            color="gold"
          />
        )}
        <KpiCard
          label="Total Shops"
          value={shops.length.toLocaleString()}
          sub={`Top 5 share: ${fmtPct(shops.slice(0, 5).reduce((s, sh) => s + (sh.share || 0), 0))}`}
          color="blue"
        />
      </div>

      {/* Two pie charts side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>

        {/* Shop Concentration Pie */}
        <ChartPanel title="Shop Concentration" subtitle="Top 10 shops by disbursed amount" loading={loading} error={error} minHeight={300}>
          {pieData.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, fontSize: 11, color: 'var(--text-muted)' }}>
              No shop data available
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <ResponsiveContainer width={200} height={220}>
                <PieChart>
                  <Pie data={pieData} dataKey="disbursed" nameKey="shop_id" cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={2}>
                    {pieData.map((_, i) => <Cell key={i} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v, name) => [fmt(v), name]} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
                {pieData.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: SLICE_COLORS[i % SLICE_COLORS.length], flexShrink: 0 }} />
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.shop_id}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: SLICE_COLORS[i % SLICE_COLORS.length], fontWeight: 600, flexShrink: 0 }}>{fmtPct(d.share)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </ChartPanel>

        {/* Product Mix Pie */}
        <ChartPanel title="Product Mix" subtitle="BNPL vs RBF disbursement split" loading={loading} error={error} minHeight={300}>
          {productMix.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, fontSize: 11, color: 'var(--text-muted)' }}>
              No product mix data available
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <ResponsiveContainer width={220} height={220}>
                  <PieChart>
                    <Pie data={productMix} dataKey="disbursed" nameKey="product" cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3}>
                      {productMix.map((_, i) => <Cell key={i} fill={[COLORS.teal, COLORS.gold, COLORS.blue, COLORS.red][i % 4]} />)}
                    </Pie>
                    <Tooltip {...tooltipStyle} formatter={(v, name) => [fmt(v), name]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{
                  position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
                  textAlign: 'center', pointerEvents: 'none',
                }}>
                  <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                    {productMix.length}
                  </div>
                  <div style={{ fontSize: 8, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Products</div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10, width: '100%', paddingLeft: 8 }}>
                {productMix.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: [COLORS.teal, COLORS.gold, COLORS.blue, COLORS.red][i % 4], flexShrink: 0 }} />
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1 }}>{d.product}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{fmt(d.disbursed)}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 40, textAlign: 'right' }}>{fmtPct(d.share)}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 50, textAlign: 'right' }}>{(d.count || 0).toLocaleString()} loans</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </ChartPanel>
      </div>

      {/* Credit Utilization — Top Shops */}
      <ChartPanel title="Credit Utilization — Top Shops" subtitle="Outstanding balance as percentage of credit limit" loading={loading} error={error} minHeight={320}>
        {utilization.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 280, fontSize: 11, color: 'var(--text-muted)' }}>
            No utilization data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(280, utilization.length * 32)}>
            <BarChart data={utilization} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <CartesianGrid {...gridProps} horizontal={false} vertical />
              <XAxis type="number" {...xAxisProps} tickFormatter={(v) => fmtPct(v)} domain={[0, 100]} />
              <YAxis
                type="category"
                dataKey="shop_id"
                {...yAxisProps}
                width={120}
                tick={{ fill: COLORS.text, fontSize: 9, fontFamily: 'var(--font-mono)' }}
              />
              <Tooltip {...tooltipStyle} formatter={(v, name) => {
                if (name === 'util_pct') return [fmtPct(v), 'Utilization']
                return [v, name]
              }} />
              <Bar dataKey="util_pct" name="Utilization" barSize={18} radius={[0, 4, 4, 0]}>
                {utilization.map((d, i) => (
                  <Cell key={i} fill={d.util_pct > 90 ? COLORS.red : d.util_pct > 70 ? COLORS.gold : COLORS.teal} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
        {utilization.length > 0 && (
          <div style={{ display: 'flex', gap: 16, marginTop: 8, paddingLeft: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-muted)' }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: COLORS.teal }} /> &lt;70%
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-muted)' }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: COLORS.gold }} /> 70–90%
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-muted)' }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: COLORS.red }} /> &gt;90%
            </div>
          </div>
        )}
      </ChartPanel>

      {/* Loan Size Distribution */}
      <ChartPanel title="Loan Size Distribution" subtitle="Number of loans by disbursement size band" loading={loading} error={error} minHeight={300}>
        {sizeDistribution.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, fontSize: 11, color: 'var(--text-muted)' }}>
            No size distribution data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={sizeDistribution} margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <GradientDefs />
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="band" {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip {...tooltipStyle} formatter={(v, name) => {
                if (name === 'count') return [v.toLocaleString(), 'Loans']
                if (name === 'total') return [fmt(v), 'Total Disbursed']
                return [v, name]
              }} />
              <Legend {...legendProps} />
              <Bar dataKey="count" name="Loans" fill={COLORS.blue} radius={[4, 4, 0, 0]} barSize={32} />
            </BarChart>
          </ResponsiveContainer>
        )}
        {sizeDistribution.length > 0 && (
          <div style={{ overflowX: 'auto', marginTop: 12 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  {['Size Band', 'Loans', 'Total Disbursed'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sizeDistribution.map((d, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 10px', color: 'var(--text-primary)', fontWeight: 500 }}>{d.band}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: COLORS.blue }}>{(d.count || 0).toLocaleString()}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: COLORS.gold }}>{fmt(d.total)}</td>
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
