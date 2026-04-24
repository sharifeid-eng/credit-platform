import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import ChartPanel from '../ChartPanel'
import ConfidenceBadge from '../ConfidenceBadge'
import { getConcentrationChart, getGroupPerformanceChart, getAgeingChart } from '../../services/api'
import { tooltipStyle, fmtMoney, fmtPct } from '../../styles/chartTheme'

const SLICE_COLORS = [
  '#C9A84C','#2DD4BF','#5B8DEF','#F06060',
  '#A78BFA','#FB923C','#34D399','#F472B6',
  '#60A5FA','#FBBF24',
]

const HEALTH_COLORS = {
  Healthy: '#2DD4BF',
  Watch:   '#C9A84C',
  Delayed: '#F06060',
  Poor:    '#8B1A1A',
}

const AGEING_COLORS = ['#2DD4BF','#5B8DEF','#C9A84C','#F59E0B','#F06060','#A78BFA','#F472B6','#8B1A1A']

export default function ConcentrationChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]               = useState(null)
  const [groupPerf, setGroupPerf]     = useState(null)
  const [ageingData, setAgeingData]   = useState(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    Promise.all([
      getConcentrationChart(company, product, snapshot, currency, asOfDate),
      getGroupPerformanceChart(company, product, snapshot, currency, asOfDate),
      getAgeingChart(company, product, snapshot, currency, asOfDate),
    ])
      .then(([concRes, perfRes, ageRes]) => {
        const groupData = (concRes.group ?? []).map(d => ({
          name:  d.Group ?? d.name,
          value: d.purchase_value,
          pct:   d.percentage,
        }))
        const providerData = (concRes.provider ?? []).map(d => ({
          name:  d.Provider ?? d.name,
          value: d.purchase_value,
          pct:   d.percentage,
        }))
        const topDeals = (concRes.top_deals ?? []).map(d => ({
          date:          d['Deal date'] ?? d.date,
          status:        d.Status ?? d.status,
          purchase_value: d['Purchase value'] ?? d.purchase_value,
          discount:      d.Discount ?? d.discount,
          collected:     d['Collected till date'] ?? d.collected,
          denied:        d['Denied by insurance'] ?? d.denied,
        }))
        const ownerRaw = concRes.owner ?? {}
        setData({ groupData, providerData, topDeals, hhi: concRes.hhi ?? {}, owner: ownerRaw })
        setGroupPerf(perfRes.groups ?? [])

        // Portfolio health and ageing donuts from ageing endpoint
        const healthDonut = (ageRes.health_summary ?? []).map(d => ({
          name:  d.status,
          value: d.value,
          pct:   d.percentage,
        }))
        const ageingBuckets = (ageRes.ageing_buckets ?? [])
          .filter(d => (d.outstanding ?? d.purchase_value) > 0)
          .map(d => ({
            name:  d.bucket,
            value: d.outstanding ?? d.purchase_value,
          }))
        const totalOutstandingVal = ageRes.total_outstanding ?? ageRes.total_active_value ?? 0
        setAgeingData({ healthDonut, ageingBuckets, totalOutstandingVal })

        setError(null)
      })
      .catch(() => setError('Failed to load concentration data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const groupData    = data?.groupData ?? []
  const providerData = data?.providerData ?? []
  const topDeals     = data?.topDeals ?? []
  const hhi          = data?.hhi ?? {}
  const owner        = data?.owner ?? {}
  const ownerAvailable = owner.available === true
  const ownerList = (owner.owners ?? []).map(d => ({
    name:            d.owner,
    deal_count:      d.deal_count,
    purchase_value:  d.purchase_value,
    collected:       d.collected,
    denied:          d.denied,
    pending:         d.pending,
    collection_rate: d.collection_rate,
    denial_rate:     d.denial_rate,
    pct:             d.percentage,
  }))
  const healthDonut      = ageingData?.healthDonut ?? []
  const ageingBuckets    = ageingData?.ageingBuckets ?? []
  const totalOutstanding = ageingData?.totalOutstandingVal ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* HHI Concentration Badges */}
      {hhi.group && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <HHIBadge label="Group HHI" value={hhi.group.hhi} top1={hhi.group.top_1_pct} top5={hhi.group.top_5_pct} maxName={hhi.group.max_name} />
          {hhi.provider && <HHIBadge label="Provider HHI" value={hhi.provider.hhi} top1={hhi.provider.top_1_pct} top5={hhi.provider.top_5_pct} maxName={hhi.provider.max_name} />}
          {hhi.product && <HHIBadge label="Product HHI" value={hhi.product.hhi} top1={hhi.product.top_1_pct} top5={hhi.product.top_5_pct} maxName={hhi.product.max_name} />}
        </div>
      )}

      {/* Group concentration donut */}
      <ChartPanel title="Group Concentration" subtitle="Share of portfolio by provider group — top 15 shown" loading={loading} error={error} minHeight={260} action={<ConfidenceBadge confidence="A" population="total_originated" note="HHI + share percentages on the full originated book. Clean-book HHI (stale-filtered) available in overview KPIs." />}>
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

      {/* Provider concentration donut (Apr 2026+ only — hidden when res.provider absent) */}
      {providerData.length > 0 && (
        <ChartPanel title="Provider Concentration" subtitle="Branch-level attribution within each group — top 15 shown" loading={loading} error={error} minHeight={260} action={<ConfidenceBadge confidence="A" population="total_originated" note="Per-provider share of total portfolio PV." />}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <ResponsiveContainer width={220} height={220}>
              <PieChart>
                <Pie data={providerData} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={2}>
                  {providerData.map((_, i) => <Cell key={i} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />)}
                </Pie>
                <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
              {providerData.slice(0, 8).map((d, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: SLICE_COLORS[i % SLICE_COLORS.length], flexShrink: 0 }} />
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: SLICE_COLORS[i % SLICE_COLORS.length], fontWeight: 600, flexShrink: 0 }}>{fmtPct(d.pct)}</div>
                </div>
              ))}
              {providerData.length > 8 && <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 2 }}>+{providerData.length - 8} more</div>}
            </div>
          </div>
        </ChartPanel>
      )}

      {/* ── Owner / SPV Concentration ── */}
      {ownerAvailable && ownerList.length > 0 && (
        <ChartPanel title="Owner / SPV Concentration" subtitle="Capital deployment and performance by fund entity" loading={loading} error={error} minHeight={260}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
            {/* Owner Donut */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <div style={{ position: 'relative', width: 180, height: 180, flexShrink: 0 }}>
                <ResponsiveContainer width={180} height={180}>
                  <PieChart>
                    <Pie data={ownerList} dataKey="purchase_value" cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={2}>
                      {ownerList.map((_, i) => <Cell key={i} fill={SLICE_COLORS[i % SLICE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{
                  position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
                  textAlign: 'center', pointerEvents: 'none',
                }}>
                  <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{ownerList.length}</div>
                  <div style={{ fontSize: 8, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Owners</div>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flex: 1 }}>
                {ownerList.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: SLICE_COLORS[i % SLICE_COLORS.length], flexShrink: 0 }} />
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: SLICE_COLORS[i % SLICE_COLORS.length], fontWeight: 600, flexShrink: 0 }}>{fmtPct(d.pct)}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Owner Performance Table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    {['Owner', 'Deals', 'Exposure', 'Coll %', 'Denial %', 'Share %'].map(h => (
                      <th key={h} style={{
                        textAlign: 'left', padding: '6px 10px',
                        fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                        color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ownerList.map((o, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '7px 10px', color: 'var(--text-primary)', fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.name}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{o.deal_count}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--gold)' }}>{fmtMoney(o.purchase_value, currency)}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: o.collection_rate >= 90 ? 'var(--teal)' : 'var(--text-muted)' }}>{fmtPct(o.collection_rate)}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: o.denial_rate > 10 ? 'var(--red)' : 'var(--text-muted)' }}>{fmtPct(o.denial_rate)}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{fmtPct(o.pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </ChartPanel>
      )}

      {/* ── Portfolio Health + Ageing by Purchase Date (side by side) ── */}
      {healthDonut.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          {/* Portfolio Health Donut */}
          <ChartPanel title="Portfolio Health" subtitle="Outstanding amount by health classification" loading={loading} error={error} minHeight={260}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={healthDonut} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={2}>
                    {healthDonut.map((d, i) => <Cell key={i} fill={HEALTH_COLORS[d.name] ?? '#555'} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
                </PieChart>
              </ResponsiveContainer>
              {totalOutstanding > 0 && (
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: -8 }}>
                  {fmtMoney(totalOutstanding, currency)}
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10, width: '100%', paddingLeft: 8 }}>
                {healthDonut.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: HEALTH_COLORS[d.name] ?? '#555', flexShrink: 0 }} />
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1 }}>{d.name}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: HEALTH_COLORS[d.name] ?? '#555', fontWeight: 600 }}>
                      {fmtMoney(d.value, currency)}
                    </div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 36, textAlign: 'right' }}>
                      {fmtPct(d.pct)}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 10, lineHeight: 1.5, textAlign: 'left', width: '100%', paddingLeft: 8 }}>
                <b>Healthy:</b> In-line with expectations<br />
                <b>Watch:</b> Expected in past 30 days<br />
                <b>Delayed:</b> Expected in past 60 days<br />
                <b>Poor:</b> Over 60 days beyond expectations
              </div>
            </div>
          </ChartPanel>

          {/* Ageing by Purchase Date Donut */}
          <ChartPanel title="Ageing by Purchase Date" subtitle="Outstanding amount by days since purchase" loading={loading} error={error} minHeight={260}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={ageingBuckets} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={2}>
                    {ageingBuckets.map((_, i) => <Cell key={i} fill={AGEING_COLORS[i % AGEING_COLORS.length]} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v, name) => [fmtMoney(v, currency), name]} />
                </PieChart>
              </ResponsiveContainer>
              {totalOutstanding > 0 && (
                <div style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', marginTop: -8 }}>
                  {fmtMoney(totalOutstanding, currency)}
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10, width: '100%', paddingLeft: 8 }}>
                {ageingBuckets.map((d, i) => {
                  const pct = totalOutstanding > 0 ? (d.value / totalOutstanding * 100) : 0
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ width: 8, height: 8, borderRadius: 2, background: AGEING_COLORS[i % AGEING_COLORS.length], flexShrink: 0 }} />
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', flex: 1 }}>{d.name}</div>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: AGEING_COLORS[i % AGEING_COLORS.length], fontWeight: 600 }}>
                        {fmtMoney(d.value, currency)}
                      </div>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', width: 36, textAlign: 'right' }}>
                        {fmtPct(pct)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </ChartPanel>
        </div>
      )}

      {/* Group Performance Table */}
      {groupPerf && groupPerf.length > 0 && (
        <ChartPanel title="Group Performance" subtitle="Collection, denial, and DSO metrics per provider group" loading={loading} error={error} minHeight={0}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  {['Group', 'Deals', 'Purchase Value', 'Collect %', 'Denial %', 'Pending %', 'DSO', 'Completion'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                      color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groupPerf.slice(0, 20).map((g, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-faint)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '7px 10px', color: 'var(--text-primary)', fontWeight: 500, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.group}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{g.deal_count}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--gold)' }}>{fmtMoney(g.purchase_value, currency)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>{fmtPct(g.collection_rate)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>{fmtPct(g.denial_rate)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>{fmtPct(g.pending_rate)}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{g.dso > 0 ? `${g.dso.toFixed(0)}d` : '—'}</td>
                    <td style={{ padding: '7px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{fmtPct(g.completion_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartPanel>
      )}

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

/* ── HHI Badge ── */
function HHIBadge({ label, value, top1, top5, maxName }) {
  const level = value > 0.25 ? 'High' : value > 0.15 ? 'Moderate' : 'Low'
  const color = value > 0.25 ? 'var(--red)' : value > 0.15 ? 'var(--gold)' : 'var(--teal)'

  return (
    <div style={{
      flex: 1, background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '14px 18px',
      display: 'flex', alignItems: 'center', gap: 16,
    }}>
      <div>
        <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>
          {label}
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>
          {value.toFixed(4)}
        </div>
        <div style={{
          fontSize: 9, fontWeight: 600, padding: '2px 8px', borderRadius: 20, display: 'inline-block', marginTop: 4,
          background: color === 'var(--teal)' ? 'var(--teal-muted)' : color === 'var(--red)' ? 'var(--red-muted)' : 'var(--gold-muted)',
          color,
        }}>
          {level} concentration
        </div>
      </div>
      <div style={{ flex: 1, fontSize: 10, color: 'var(--text-muted)' }}>
        <div>Top 1: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{top1}%</span> ({maxName})</div>
        <div style={{ marginTop: 3 }}>Top 5: <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{top5}%</span></div>
      </div>
    </div>
  )
}
