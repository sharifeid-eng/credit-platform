import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import ChartPanel from '../ChartPanel'
import { getConcentrationChart } from '../../services/api'
import { tooltipStyle, fmtMoney, fmtPct } from '../../styles/chartTheme'

const SLICE_COLORS = [
  '#C9A84C','#2DD4BF','#5B8DEF','#F06060',
  '#A78BFA','#FB923C','#34D399','#F472B6',
  '#60A5FA','#FBBF24',
]

export default function ConcentrationChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getConcentrationChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const groupData = (res.group ?? []).map(d => ({
          name:  d.Group ?? d.name,
          value: d.purchase_value,
          pct:   d.percentage,
        }))
        const topDeals = (res.top_deals ?? []).map(d => ({
          date:          d['Deal date'] ?? d.date,
          status:        d.Status ?? d.status,
          purchase_value: d['Purchase value'] ?? d.purchase_value,
          discount:      d.Discount ?? d.discount,
          collected:     d['Collected till date'] ?? d.collected,
          denied:        d['Denied by insurance'] ?? d.denied,
        }))
        setData({ groupData, topDeals })
        setError(null)
      })
      .catch(() => setError('Failed to load concentration data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const groupData = data?.groupData ?? []
  const topDeals  = data?.topDeals  ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Group concentration donut */}
      <ChartPanel title="Group Concentration" subtitle="Share of portfolio by insurer / payer group — top 15 shown" loading={loading} error={error} minHeight={260}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <ResponsiveContainer width={220} height={220}>
            <PieChart>
              <Pie data={groupData} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={2}>
                {groupData.map((_, i) => <Cell key={i} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />)}
              </Pie>
              <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
            {groupData.slice(0, 8).map((d, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: SLICE_COLORS[i % SLICE_COLORS.length], flexShrink: 0 }} />
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: SLICE_COLORS[i % SLICE_COLORS.length], fontWeight: 600, flexShrink: 0 }}>{fmtPct(d.pct)}</div>
              </div>
            ))}
            {groupData.length > 8 && <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>+{groupData.length - 8} more</div>}
          </div>
        </div>
      </ChartPanel>

      {/* Top deals table */}
      <ChartPanel title="Top 10 Deals" subtitle="Largest receivables by purchase value" loading={loading} error={error} minHeight={0}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr>
                {['Deal Date', 'Status', 'Purchase Value', 'Discount', 'Collected', 'Denied'].map(h => (
                  <th key={h} style={{
                    textAlign: 'left', padding: '6px 10px',
                    fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
                    color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topDeals.map((d, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{d.date}</td>
                  <td style={{ padding: '7px 10px' }}>
                    <span style={{
                      fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 20,
                      background: d.status === 'Executed' ? 'var(--teal-muted)' : 'var(--blue-muted)',
                      color: d.status === 'Executed' ? 'var(--teal)' : 'var(--blue)',
                    }}>{d.status}</span>
                  </td>
                  <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--gold)', fontWeight: 600 }}>{fmtMoney(d.purchase_value, currency)}</td>
                  <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{fmtPct((d.discount ?? 0) * 100)}</td>
                  <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>{fmtMoney(d.collected, currency)}</td>
                  <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmtMoney(d.denied, currency)}</td>
                </tr>
              ))}
              {topDeals.length === 0 && (
                <tr><td colSpan={6} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </ChartPanel>
    </div>
  )
}
