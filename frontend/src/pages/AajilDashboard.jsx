import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import useBreakpoint from '../hooks/useBreakpoint'
import { getAajilSummary, getAajilChart } from '../services/api'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import {
  BarChart, Bar, PieChart, Pie, Cell, ComposedChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from 'recharts'

// ── Colors ───────────────────────────────────────────────────────────────────
const GOLD   = '#C9A84C'
const TEAL   = '#2DD4BF'
const RED    = '#F06060'
const BLUE   = '#5B8DEF'
const MUTED  = '#8494A7'
const SURFACE = '#172231'
const BORDER  = '#243040'
const DEEP    = '#0A1119'
const PIE_COLORS = [GOLD, TEAL, BLUE, RED, '#A78BFA', '#F59E0B', '#EC4899']

const fmt = (v, prefix = '', suffix = '') => {
  if (v == null) return '--'
  if (typeof v === 'number') {
    if (Math.abs(v) >= 1e9) return `${prefix}${(v / 1e9).toFixed(1)}B${suffix}`
    if (Math.abs(v) >= 1e6) return `${prefix}${(v / 1e6).toFixed(1)}M${suffix}`
    if (Math.abs(v) >= 1e3) return `${prefix}${(v / 1e3).toFixed(1)}K${suffix}`
    return `${prefix}${v.toLocaleString()}${suffix}`
  }
  return `${prefix}${v}${suffix}`
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, padding: '8px 12px', borderRadius: 6, fontSize: 12 }}>
      <div style={{ color: MUTED, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || '#E8EAF0' }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
        </div>
      ))}
    </div>
  )
}

// ── Growth Stats Component (Cascade Debt inspired) ───────────────────────────
function GrowthStats({ stats, label = '' }) {
  if (!stats || Object.keys(stats).length === 0) return null
  const items = [
    { key: 'mom_pct', label: 'Month over Month' },
    { key: 'qoq_pct', label: 'Quarter over Quarter' },
    { key: 'yoy_pct', label: 'Year over Year' },
  ]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 160, padding: '12px 16px', background: SURFACE, borderRadius: 8, border: `1px solid ${BORDER}` }}>
      <div style={{ fontSize: 13, color: MUTED, fontWeight: 600 }}>Growth Rates{label ? ` — ${label}` : ''}</div>
      {items.map(({ key, label: lbl }) => {
        const v = stats[key]
        if (v == null) return null
        const color = v >= 0 ? TEAL : RED
        return (
          <div key={key} style={{ borderBottom: `1px solid ${BORDER}`, paddingBottom: 8 }}>
            <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
              {v >= 0 ? '+' : ''}{v.toFixed(2)}%
            </div>
            <div style={{ fontSize: 11, color: MUTED }}>{lbl}</div>
          </div>
        )
      })}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════
export default function AajilDashboard() {
  const { tab } = useParams()
  const { company, product, snapshots } = useCompany()
  const { isMobile } = useBreakpoint()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [chartData, setChartData] = useState({})
  const [chartLoading, setChartLoading] = useState(false)
  const [dpdThreshold, setDpdThreshold] = useState('dpd_7')
  const [tractionView, setTractionView] = useState('volume')

  const activeTab = tab || 'overview'
  const snap = snapshots?.[snapshots.length - 1]?.filename

  // Load JSON data for qualitative tabs (trust scores, underwriting, notes)
  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getAajilSummary(company, product, snap)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [company, product, snapshots])

  // Load chart data from live tape endpoints
  const CHART_TABS = ['traction', 'delinquency', 'collections', 'cohort-analysis',
    'concentration', 'underwriting', 'yield-margins', 'loss-waterfall',
    'customer-segments', 'seasonality']
  const chartSlugMap = {
    'cohort-analysis': 'cohort', 'yield-margins': 'yield-margins',
    'loss-waterfall': 'loss-waterfall', 'customer-segments': 'customer-segments',
  }

  useEffect(() => {
    if (!company || !product || !CHART_TABS.includes(activeTab)) return
    if (chartData[activeTab]) return  // Already loaded
    setChartLoading(true)
    const slug = chartSlugMap[activeTab] || activeTab
    getAajilChart(company, product, slug, snap)
      .then(d => { setChartData(prev => ({ ...prev, [activeTab]: d })); setChartLoading(false) })
      .catch(() => setChartLoading(false))
  }, [activeTab, company, product])

  if (loading) return <div style={{ color: MUTED, padding: 40 }}>Loading Aajil dashboard...</div>
  if (!data) return <div style={{ color: RED, padding: 40 }}>Failed to load Aajil data</div>

  const co = data.company_overview || {}
  const ov = data.overview || {}

  // Chart data from live endpoints (preferred) or fallback to JSON
  const traction = chartData['traction'] || data.traction || {}
  const delinquency = chartData['delinquency'] || data.delinquency || {}
  const collectionsData = chartData['collections'] || data.collections || {}
  const vintageData = chartData['cohort-analysis'] || data.vintage_cohorts || {}
  const concentrationData = chartData['concentration'] || {}
  const yieldData = chartData['yield-margins'] || {}
  const lossData = chartData['loss-waterfall'] || {}
  const segmentData = chartData['customer-segments'] || {}
  const seasonalityData = chartData['seasonality'] || {}

  // Prepare monthly volume data with short labels
  const volumeMonthly = (traction.volume_monthly || []).map(v => ({
    ...v,
    label: v.date?.slice(0, 7),
    value: v.disbursed_sar
  }))
  const balanceMonthly = (traction.balance_monthly || []).map(v => ({
    ...v,
    label: v.date?.slice(0, 7),
    value: v.balance_sar
  }))
  const collectionsMonthly = (collectionsData.monthly || []).map(c => ({
    ...c,
    label: c.date?.slice(0, 7),
    rate: c.collection_rate != null ? c.collection_rate * 100 : null
  }))

  const fadeIn = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.25 } }

  return (
    <AnimatePresence mode="wait">
      <motion.div key={activeTab} {...fadeIn}>

        {/* ── OVERVIEW TAB ─────────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div>
            {/* KPI Grid — tape-computed metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              <KpiCard label="Outstanding (Receivable)" value={fmt(data.total_receivable, 'SAR ')} index={0} />
              <KpiCard label="GMV (Bill Notional)" value={fmt(data.total_bill_notional, 'SAR ')} index={1} />
              <KpiCard label="Transactions" value={data.total_deals?.toLocaleString()} subtitle={`${data.avg_deals_per_customer || co.avg_deals_per_customer || ''}x per customer`} index={2} />
              <KpiCard label="Customers" value={(data.total_customers || co.total_customers)?.toLocaleString()} index={3} />
              <KpiCard label="Write-Off Rate" value={data.write_off_rate != null ? `${(data.write_off_rate * 100).toFixed(1)}%` : '--'} subtitle={`${data.written_off_count || 0} deals`} index={4} />
            </div>

            {/* Second row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              <KpiCard label="Avg Tenor" value={data.avg_tenure ? `${data.avg_tenure.toFixed(1)} months` : `${co.avg_tenor_months} months`} subtitle={`Max ${co.max_tenor_months || 12} months`} index={5} />
              <KpiCard label="PN Coverage" value={`${(co.pn_coverage * 100).toFixed(0)}%`} subtitle="Promissory notes" index={6} />
              <KpiCard label="Credit/Revenue" value={co.credit_as_pct_revenue} subtitle="Per customer" index={7} />
              <KpiCard label="Deployment Speed" value={`<${co.credit_deployment_hours}h`} subtitle="KYB: instantaneous" index={8} />
              <KpiCard label="Employees" value={co.employees} subtitle="64+ staff" index={9} />
            </div>

            {/* Portfolio Composition */}
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <ChartPanel title="Deal Status" height={250}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={[
                      { name: 'Realised', value: data.realised_count || 0 },
                      { name: 'Accrued', value: data.accrued_count || 0 },
                      { name: 'Written Off', value: data.written_off_count || 0 },
                    ].filter(d => d.value > 0)} dataKey="value" cx="50%" cy="50%" outerRadius={70}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      <Cell fill={TEAL} />
                      <Cell fill={GOLD} />
                      <Cell fill={RED} />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </ChartPanel>

              <ChartPanel title="Deal Type Mix" height={250}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={[
                      { name: 'EMI (Instalment)', value: data.emi_count || 0 },
                      { name: 'Bullet (Single)', value: data.bullet_count || 0 },
                    ].filter(d => d.value > 0)} dataKey="value" cx="50%" cy="50%" outerRadius={70}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      <Cell fill={BLUE} />
                      <Cell fill={GOLD} />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </ChartPanel>
            </div>

            {/* Collection & Yield KPIs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
              <KpiCard label="Collection Rate" value={data.collection_rate ? `${(data.collection_rate * 100).toFixed(1)}%` : '--'} index={10} />
              <KpiCard label="Total Realised" value={fmt(data.total_realised, 'SAR ')} index={11} />
              <KpiCard label="Total Overdue" value={fmt(data.total_overdue, 'SAR ')} index={12} />
              <KpiCard label="Avg Yield" value={data.avg_total_yield ? `${(data.avg_total_yield * 100).toFixed(2)}%` : '--'} index={13} />
              <KpiCard label="HHI (Customer)" value={data.hhi_customer?.toFixed(4) || '--'} subtitle={data.hhi_customer < 0.05 ? 'Well diversified' : ''} index={14} />
            </div>

            {/* Investors */}
            <ChartPanel title="Investors" style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: 8 }}>
                {(co.investors || []).map((inv, i) => (
                  <span key={i} style={{ padding: '6px 12px', borderRadius: 6, background: `${GOLD}15`, border: `1px solid ${GOLD}33`, color: '#E8EAF0', fontSize: 12 }}>
                    {inv}
                  </span>
                ))}
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── TRACTION TAB (Cascade-inspired — real data) ────────────── */}
        {activeTab === 'traction' && (
          <div>
            {/* Volume/Balance toggle */}
            <div style={{ display: 'flex', gap: 0, marginBottom: 16 }}>
              {['volume', 'balance'].map(v => (
                <button key={v} onClick={() => setTractionView(v)}
                  style={{ padding: '8px 24px', background: tractionView === v ? GOLD : 'transparent', color: tractionView === v ? '#0A1119' : MUTED, border: `1px solid ${BORDER}`, borderRadius: v === 'volume' ? '6px 0 0 6px' : '0 6px 6px 0', cursor: 'pointer', fontWeight: 600, fontSize: 13, textTransform: 'capitalize' }}>
                  {v}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: 16, flexDirection: isMobile ? 'column' : 'row' }}>
              <div style={{ flex: 1 }}>
                <ChartPanel title={tractionView === 'volume' ? 'Monthly Disbursement Volume' : 'Outstanding Balance'} height={350}>
                  <ResponsiveContainer width="100%" height={300}>
                    {tractionView === 'volume' ? (
                      <BarChart data={volumeMonthly}>
                        <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                        <XAxis dataKey="label" stroke={MUTED} fontSize={10} interval={5} angle={-45} textAnchor="end" height={50} />
                        <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v)} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="disbursed_sar" fill={GOLD} radius={[2, 2, 0, 0]} name="Disbursed (SAR)" />
                      </BarChart>
                    ) : (
                      <AreaChart data={balanceMonthly}>
                        <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                        <XAxis dataKey="label" stroke={MUTED} fontSize={10} interval={5} angle={-45} textAnchor="end" height={50} />
                        <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v)} />
                        <Tooltip content={<CustomTooltip />} />
                        <Area type="monotone" dataKey="balance_sar" fill={`${GOLD}30`} stroke={GOLD} strokeWidth={2} name="Balance (SAR)" />
                      </AreaChart>
                    )}
                  </ResponsiveContainer>
                </ChartPanel>
              </div>
              <GrowthStats stats={tractionView === 'volume' ? traction.volume_summary_stats : traction.balance_summary_stats} label={tractionView === 'volume' ? 'Disbursements' : 'Balance'} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 16 }}>
              <KpiCard label="Total Disbursed (GMV)" value={fmt(traction.total_disbursed, 'SAR ')} index={0} />
              <KpiCard label="Outstanding Balance" value={fmt(traction.latest_balance, 'SAR ')} index={1} />
              <KpiCard label="Volume Months" value={volumeMonthly.length} subtitle="May 2022 - Apr 2026" index={2} />
            </div>
          </div>
        )}

        {/* ── DELINQUENCY TAB (real Cascade data) ──────────────────────── */}
        {activeTab === 'delinquency' && (() => {
          const dpd = delinquency[dpdThreshold] || {}
          const recent = (dpd.recent || []).map(r => ({
            ...r,
            label: r.date?.slice(0, 7),
            balance_m: r.balance / 1e6
          }))
          const stats = dpd.summary_stats || {}
          const dpdLabel = dpdThreshold.replace('dpd_', '') + ' DPD'
          const latestBal = recent.length ? recent[recent.length - 1].balance : 0
          return (
          <div>
            {/* DPD toggle buttons */}
            <div style={{ display: 'flex', gap: 0, marginBottom: 16 }}>
              {['dpd_7', 'dpd_30', 'dpd_60', 'dpd_90'].map(d => (
                <button key={d} onClick={() => setDpdThreshold(d)}
                  style={{ padding: '8px 18px', background: dpdThreshold === d ? GOLD : 'transparent', color: dpdThreshold === d ? '#0A1119' : MUTED, border: `1px solid ${BORDER}`, borderRadius: d === 'dpd_7' ? '6px 0 0 6px' : d === 'dpd_90' ? '0 6px 6px 0' : 0, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
                  {d.replace('dpd_', '')} DPD
                </button>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
              <KpiCard label={`${dpdLabel} Balance`} value={fmt(latestBal, 'SAR ')} subtitle="Latest month" index={0} />
              <KpiCard label="MoM Change" value={stats.mom_pct != null ? `${stats.mom_pct > 0 ? '+' : ''}${stats.mom_pct}%` : '--'} subtitle="Month over Month" index={1} />
              <KpiCard label="QoQ Change" value={stats.qoq_pct != null ? `${stats.qoq_pct > 0 ? '+' : ''}${stats.qoq_pct}%` : '--'} subtitle="Quarter over Quarter" index={2} />
              <KpiCard label="YoY Change" value={stats.yoy_pct != null ? `${stats.yoy_pct > 0 ? '+' : ''}${stats.yoy_pct}%` : '--'} subtitle="Year over Year" index={3} />
            </div>

            <div style={{ display: 'flex', gap: 16, flexDirection: isMobile ? 'column' : 'row' }}>
              <div style={{ flex: 1 }}>
                <ChartPanel title={`Rolling Default Rate — ${dpdLabel}`} height={300}>
                  <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={recent}>
                      <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                      <XAxis dataKey="label" stroke={MUTED} fontSize={11} />
                      <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => `${v.toFixed(1)}M`} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="balance_m" fill={`${RED}20`} stroke={RED} strokeWidth={2} name={`${dpdLabel} Balance (M SAR)`} />
                      <Line type="monotone" dataKey="balance_m" stroke={RED} strokeWidth={2} dot={{ r: 3, fill: RED }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </ChartPanel>
              </div>
              <GrowthStats stats={stats} label={dpdLabel} />
            </div>
          </div>
          )
        })()}

        {/* ── COLLECTIONS TAB (real Cascade data) ──────────────────────── */}
        {activeTab === 'collections' && (
          <div>
            <ChartPanel title="Cash Collected by Cohort" height={350}>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={collectionsMonthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="label" stroke={MUTED} fontSize={10} interval={5} angle={-45} textAnchor="end" height={50} />
                  <YAxis yAxisId="left" stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v)} />
                  <YAxis yAxisId="right" orientation="right" stroke={TEAL} fontSize={11} tickFormatter={v => `${v}%`} domain={[0, 130]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar yAxisId="left" dataKey="collected_sar" fill={GOLD} radius={[2, 2, 0, 0]} name="Collected (SAR)" />
                  <Line yAxisId="right" type="monotone" dataKey="rate" stroke={TEAL} strokeWidth={2} dot={false} name="Collection Rate %" connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartPanel>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 16 }}>
              <KpiCard label="Total Collected" value={fmt(collectionsMonthly.reduce((s, c) => s + (c.collected_sar || 0), 0), 'SAR ')} index={0} />
              <KpiCard label="Months with Data" value={collectionsMonthly.filter(c => c.collected_sar > 0).length} index={1} />
              <KpiCard label="Avg Monthly Collection" value={fmt(collectionsMonthly.filter(c => c.collected_sar > 0).reduce((s, c) => s + c.collected_sar, 0) / Math.max(1, collectionsMonthly.filter(c => c.collected_sar > 0).length), 'SAR ')} index={2} />
            </div>
          </div>
        )}

        {/* ── COHORT ANALYSIS TAB (real Cascade vintage heatmap) ─────── */}
        {activeTab === 'cohort-analysis' && (() => {
          const cohorts = vintageData.cohorts || []
          const maxMob = 12
          const getColor = (val) => {
            if (val == null || val === 0) return 'transparent'
            if (val < 3) return 'rgba(45, 212, 191, 0.25)'
            if (val < 8) return 'rgba(45, 212, 191, 0.5)'
            if (val < 15) return 'rgba(201, 168, 76, 0.4)'
            if (val < 25) return 'rgba(240, 96, 96, 0.4)'
            return 'rgba(240, 96, 96, 0.7)'
          }
          return (
          <div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ color: MUTED, fontSize: 12 }}>DPD {vintageData.dpd_threshold}+ | {vintageData.measurement} | {vintageData.cohort_type}-level | {vintageData.recoveries}</span>
              <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
                {[{c:'rgba(45,212,191,0.25)',l:'<3%'},{c:'rgba(45,212,191,0.5)',l:'3-8%'},{c:'rgba(201,168,76,0.4)',l:'8-15%'},{c:'rgba(240,96,96,0.4)',l:'15-25%'},{c:'rgba(240,96,96,0.7)',l:'>25%'}].map(({c,l}) => (
                  <span key={l} style={{ display:'flex',alignItems:'center',gap:4,fontSize:10,color:MUTED }}>
                    <span style={{ width:12,height:12,borderRadius:2,background:c,border:`1px solid ${BORDER}` }} />{l}
                  </span>
                ))}
              </div>
            </div>
            <ChartPanel title="Vintage Analysis — DPD 30+ by Month on Books">
              <div style={{ overflowX: 'auto', padding: '0 4px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: MUTED, position: 'sticky', left: 0, background: SURFACE, borderBottom: `1px solid ${BORDER}`, minWidth: 70 }}>Cohort</th>
                      <th style={{ padding: '6px 8px', textAlign: 'right', color: MUTED, borderBottom: `1px solid ${BORDER}`, minWidth: 80 }}>Orig Bal</th>
                      {Array.from({length: maxMob}, (_, i) => (
                        <th key={i} style={{ padding: '6px 6px', textAlign: 'center', color: MUTED, borderBottom: `1px solid ${BORDER}`, minWidth: 48 }}>{i + 1}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cohorts.map((c, idx) => (
                      <tr key={idx}>
                        <td style={{ padding: '4px 8px', color: '#E8EAF0', fontWeight: 600, position: 'sticky', left: 0, background: SURFACE, borderBottom: `1px solid ${BORDER}22`, whiteSpace: 'nowrap' }}>{c.cohort}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: MUTED, fontFamily: 'var(--font-mono)', borderBottom: `1px solid ${BORDER}22`, whiteSpace: 'nowrap' }}>{fmt(c.original_balance, 'SAR ')}</td>
                        {Array.from({length: maxMob}, (_, i) => {
                          const val = c.mob && i < c.mob.length ? c.mob[i] : null
                          return (
                            <td key={i} style={{ padding: '4px 6px', textAlign: 'center', background: getColor(val), color: val != null && val > 0 ? '#E8EAF0' : MUTED, fontFamily: 'var(--font-mono)', borderBottom: `1px solid ${BORDER}22`, fontSize: 10 }}>
                              {val != null ? (val === 0 ? '0' : `${val.toFixed(1)}%`) : ''}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>
          </div>
          )
        })()}

        {/* ── CONCENTRATION TAB ────────────────────────────────────────── */}
        {activeTab === 'concentration' && (() => {
          const cd = concentrationData
          if (chartLoading && !cd.available) return <div style={{ color: MUTED, padding: 40 }}>Loading concentration data...</div>
          return (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
              <KpiCard label="HHI (Customer)" value={cd.hhi_customer?.toFixed(4) || '--'} subtitle={cd.hhi_customer < 0.05 ? 'Well diversified' : 'Moderate'} index={0} />
              <KpiCard label="Top 5 Share" value={cd.top5_share ? `${(cd.top5_share * 100).toFixed(1)}%` : '--'} index={1} />
              <KpiCard label="Top 10 Share" value={cd.top10_share ? `${(cd.top10_share * 100).toFixed(1)}%` : '--'} index={2} />
              <KpiCard label="Total Customers" value={cd.total_customers || '--'} index={3} />
            </div>

            {/* Deal Type Mix */}
            <ChartPanel title="Deal Type Mix">
              <div style={{ height: 200, padding: '0 16px' }}>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={cd.deal_type_mix || []} dataKey="volume" nameKey="deal_type"
                      cx="50%" cy="50%" outerRadius={70} label={({ deal_type, share }) => `${deal_type} ${share ? (share * 100).toFixed(0) : 0}%`}>
                      {(cd.deal_type_mix || []).map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </ChartPanel>

            {/* Top Customers */}
            <ChartPanel title="Top 15 Customers" style={{ marginTop: 16 }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: MUTED }}>#</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left', color: MUTED }}>Customer</th>
                      <th style={{ padding: '6px 8px', textAlign: 'right', color: MUTED }}>Volume</th>
                      <th style={{ padding: '6px 8px', textAlign: 'right', color: MUTED }}>Deals</th>
                      <th style={{ padding: '6px 8px', textAlign: 'right', color: MUTED }}>Share</th>
                      <th style={{ padding: '6px 8px', textAlign: 'right', color: MUTED }}>Cumulative</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(cd.top_customers || []).map((c, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${BORDER}22` }}>
                        <td style={{ padding: '4px 8px', color: MUTED }}>{i + 1}</td>
                        <td style={{ padding: '4px 8px', color: '#E8EAF0' }}>{c.customer_id}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: '#E8EAF0', fontFamily: 'var(--font-mono)' }}>{fmt(c.volume, 'SAR ')}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: MUTED }}>{c.count}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: GOLD }}>{c.share ? `${(c.share * 100).toFixed(1)}%` : '--'}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: MUTED }}>{c.cumulative ? `${(c.cumulative * 100).toFixed(1)}%` : '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>

            {/* Industry Breakdown */}
            <ChartPanel title="Industry Concentration" style={{ marginTop: 16 }}>
              <div style={{ height: 300, padding: '0 16px' }}>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={(cd.industries || []).slice(0, 12)} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis type="number" stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v)} />
                    <YAxis type="category" dataKey="industry" stroke={MUTED} fontSize={10} width={120} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="volume" fill={TEAL} radius={[0, 4, 4, 0]} name="Volume (SAR)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {cd.industry_unknown_pct > 0 && (
                <div style={{ padding: '8px 16px', color: MUTED, fontSize: 11 }}>
                  Note: {(cd.industry_unknown_pct * 100).toFixed(0)}% of deals have no industry classification
                </div>
              )}
            </ChartPanel>
          </div>
          )
        })()}

        {/* ── UNDERWRITING TAB ─────────────────────────────────────────── */}
        {activeTab === 'underwriting' && (
          <div>
            <ChartPanel title="4-Stage Underwriting Process">
              <div style={{ display: 'flex', gap: 8, padding: 20, flexWrap: 'wrap' }}>
                {(data.underwriting?.stages_enriched || []).map(s => (
                  <div key={s.number} style={{ flex: 1, minWidth: 200, padding: 16, background: DEEP, borderRadius: 8, border: `1px solid ${s.color}33` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <div style={{ width: 28, height: 28, borderRadius: '50%', background: `${s.color}22`, border: `2px solid ${s.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.color, fontWeight: 700, fontSize: 13 }}>{s.number}</div>
                      <span style={{ color: '#E8EAF0', fontWeight: 600, fontSize: 13 }}>{s.name}</span>
                    </div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            {/* Financial Thresholds */}
            <ChartPanel title="Financial Ratio Thresholds by Customer Type" style={{ marginTop: 16 }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: MUTED }}>Metric</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center', color: BLUE }}>Contractor</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center', color: GOLD }}>Manufacturer</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center', color: TEAL }}>Trader</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Gross Margin (min)', '7%', '6%', '7%'],
                      ['Net Margin (min)', '1%', '1%', '1%'],
                      ['Current Ratio (min)', '0.8', '0.8', '0.8'],
                      ['Gross Margin (ideal)', '20-34%', '20-34%', '20-34%'],
                    ].map(([metric, c, m, t], i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                        <td style={{ padding: '8px 12px', color: '#E8EAF0' }}>{metric}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', color: '#E8EAF0' }}>{c}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', color: '#E8EAF0' }}>{m}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', color: '#E8EAF0' }}>{t}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>

            {/* Disqualification Rules */}
            <ChartPanel title="Key Disqualification Rules" style={{ marginTop: 16 }}>
              <div style={{ padding: 12 }}>
                {(data.underwriting?.disqualification_rules || []).map((rule, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: `1px solid ${BORDER}`, alignItems: 'flex-start' }}>
                    <span style={{ color: RED, fontSize: 10, marginTop: 3 }}>x</span>
                    <span style={{ color: '#E8EAF0', fontSize: 12 }}>{rule}</span>
                  </div>
                ))}
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── TRUST & COLLECTIONS TAB ──────────────────────────────────── */}
        {activeTab === 'trust-collections' && (
          <div>
            <ChartPanel title="Trust Score System">
              <div style={{ display: 'flex', gap: 12, padding: 16, flexWrap: 'wrap' }}>
                {(data.trust_score_system?.scores || []).map(s => (
                  <div key={s.score} style={{ flex: 1, minWidth: 140, padding: 14, background: DEEP, borderRadius: 8, border: `1px solid ${s.color}44`, textAlign: 'center' }}>
                    <div style={{ fontSize: 28, fontWeight: 700, color: s.color }}>{s.score}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: s.color, marginBottom: 4 }}>{s.label}</div>
                    <div style={{ fontSize: 11, color: MUTED }}>{s.description}</div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            <ChartPanel title="Collections Phases" style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', gap: 0 }}>
                {(data.trust_score_system?.collections_phases || []).map((p, i) => (
                  <div key={i} style={{ flex: 1, padding: 16, background: `${p.color}10`, borderRight: i < 2 ? `1px solid ${BORDER}` : 'none', textAlign: 'center' }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: p.color }}>{p.phase}</div>
                    <div style={{ fontSize: 13, color: MUTED, marginTop: 4 }}>DPD {p.dpd_range}</div>
                    <div style={{ fontSize: 11, color: MUTED, marginTop: 8 }}>{p.description}</div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            {/* DPD Reassessment Rules */}
            <ChartPanel title="DPD Reassessment Policy" style={{ marginTop: 16 }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: MUTED }}>DPD Range</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: MUTED }}>Policy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.dpd_reassessment || []).map((r, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                        <td style={{ padding: '8px 12px', color: GOLD, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>{r.dpd_range}</td>
                        <td style={{ padding: '8px 12px', color: '#E8EAF0' }}>{r.policy}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── CUSTOMER SEGMENTS TAB ────────────────────────────────────── */}
        {activeTab === 'customer-segments' && (
          <div>
            <ChartPanel title="Customer Types">
              <div style={{ display: 'flex', gap: 12, padding: 16, flexWrap: 'wrap' }}>
                {(data.customer_types || []).map((ct, i) => (
                  <div key={i} style={{ flex: 1, minWidth: 200, padding: 16, background: DEEP, borderRadius: 8, border: `1px solid ${ct.color}44` }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: ct.color, marginBottom: 4 }}>{ct.type}</div>
                    <div style={{ fontSize: 12, color: MUTED, marginBottom: 8 }}>{ct.description}</div>
                    <div style={{ fontSize: 11, color: MUTED }}>
                      <div>Min Gross Margin: {(ct.min_gross_margin * 100).toFixed(0)}%</div>
                      <div>Min Net Margin: {(ct.min_net_margin * 100).toFixed(0)}%</div>
                      <div>Min Current Ratio: {ct.min_current_ratio}</div>
                    </div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            <ChartPanel title="Sales Channels" style={{ marginTop: 16 }}>
              <div style={{ height: 250, padding: '0 16px' }}>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={data.sales_channels || []} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis type="number" stroke={MUTED} fontSize={11} tickFormatter={v => `${v}%`} />
                    <YAxis type="category" dataKey="channel" stroke={MUTED} fontSize={11} width={150} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="pct" name="% of Sales" radius={[0, 4, 4, 0]}>
                      {(data.sales_channels || []).map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── YIELD & MARGINS TAB (live tape data) ─────────────────────── */}
        {activeTab === 'yield-margins' && (() => {
          const yd = yieldData
          if (chartLoading && !yd.available) return <div style={{ color: MUTED, padding: 40 }}>Loading yield data...</div>
          return (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
              <KpiCard label="Total Margin" value={fmt(yd.total_margin, 'SAR ')} index={0} />
              <KpiCard label="Total Fees" value={fmt(yd.total_fees, 'SAR ')} index={1} />
              <KpiCard label="Total Revenue" value={fmt(yd.total_revenue, 'SAR ')} index={2} />
              <KpiCard label="Revenue/GMV" value={yd.revenue_over_gmv ? `${(yd.revenue_over_gmv * 100).toFixed(2)}%` : '--'} index={3} />
              <KpiCard label="Avg Total Yield" value={yd.avg_total_yield ? `${(yd.avg_total_yield * 100).toFixed(2)}%` : '--'} index={4} />
            </div>

            {/* By Deal Type */}
            <ChartPanel title="Yield by Deal Type">
              <div style={{ display: 'flex', gap: 12, padding: 16, flexWrap: 'wrap' }}>
                {(yd.by_deal_type || []).map((dt, i) => (
                  <div key={i} style={{ flex: 1, minWidth: 200, padding: 16, background: DEEP, borderRadius: 8, border: `1px solid ${BORDER}` }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: i === 0 ? GOLD : TEAL, marginBottom: 8 }}>{dt.deal_type}</div>
                    <div style={{ fontSize: 12, color: MUTED }}>Avg Yield: {dt.avg_total_yield ? `${(dt.avg_total_yield * 100).toFixed(2)}%` : '--'}</div>
                    <div style={{ fontSize: 12, color: MUTED }}>Margin: {fmt(dt.total_margin, 'SAR ')}</div>
                    <div style={{ fontSize: 12, color: MUTED }}>Fees: {fmt(dt.total_fees, 'SAR ')}</div>
                    <div style={{ fontSize: 12, color: MUTED }}>Deals: {dt.count}</div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            {/* Yield by Vintage */}
            <ChartPanel title="Yield Trend by Vintage" style={{ marginTop: 16 }} height={300}>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={yd.by_vintage || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="vintage" stroke={MUTED} fontSize={10} angle={-45} textAnchor="end" height={50} />
                  <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="margin_rate" fill={GOLD} radius={[2, 2, 0, 0]} name="Margin Rate" />
                  <Line type="monotone" dataKey="avg_yield" stroke={TEAL} strokeWidth={2} dot={{ r: 3 }} name="Avg Yield" />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartPanel>
          </div>
          )
        })()}

        {/* ── LOSS WATERFALL TAB (live tape data) ──────────────────────── */}
        {activeTab === 'loss-waterfall' && (() => {
          const ld = lossData
          if (chartLoading && !ld.available) return <div style={{ color: MUTED, padding: 40 }}>Loading loss data...</div>
          return (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
              <KpiCard label="Gross Loss Rate" value={ld.gross_loss_rate ? `${(ld.gross_loss_rate * 100).toFixed(2)}%` : '--'} index={0} />
              <KpiCard label="Written Off" value={fmt(ld.written_off_amount, 'SAR ')} subtitle={`${(ld.waterfall || []).find(s => s.stage === 'Written Off')?.count || 0} deals`} index={1} />
              <KpiCard label="Net Loss" value={fmt(ld.net_loss, 'SAR ')} index={2} />
              <KpiCard label="VAT Recovered" value={fmt(ld.vat_recovered, 'SAR ')} index={3} />
            </div>

            {/* Waterfall table */}
            <ChartPanel title="Portfolio Waterfall">
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: MUTED }}>Stage</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: MUTED }}>Amount (SAR)</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: MUTED }}>Deals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ld.waterfall || []).map((s, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${BORDER}22` }}>
                        <td style={{ padding: '8px 12px', color: '#E8EAF0', fontWeight: 600 }}>{s.stage}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: s.stage === 'Written Off' ? RED : '#E8EAF0', fontFamily: 'var(--font-mono)' }}>{fmt(s.amount, 'SAR ')}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: MUTED }}>{s.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ChartPanel>

            {/* Loss by Vintage */}
            <ChartPanel title="Loss Rate by Vintage" style={{ marginTop: 16 }} height={300}>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={(ld.by_vintage || []).filter(v => v.wo_count > 0)}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="vintage" stroke={MUTED} fontSize={10} angle={-45} textAnchor="end" height={50} />
                  <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="loss_rate" fill={RED} radius={[4, 4, 0, 0]} name="Loss Rate" />
                </BarChart>
              </ResponsiveContainer>
            </ChartPanel>
          </div>
          )
        })()}

        {/* ── COVENANTS TAB ────────────────────────────────────────────── */}
        {activeTab === 'covenants' && (
          <div>
            <ChartPanel title="Covenant Compliance">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>Covenant thresholds and compliance monitoring</div>
                <div style={{ fontSize: 12 }}>Requires facility agreement terms and live portfolio data.</div>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── DATA NOTES TAB ───────────────────────────────────────────── */}
        {activeTab === 'notes' && (
          <div>
            <ChartPanel title="Data Notes & Caveats">
              <div style={{ padding: 16 }}>
                {(data.data_notes || []).map((note, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: `1px solid ${BORDER}`, alignItems: 'flex-start' }}>
                    <span style={{ color: GOLD, fontSize: 12, marginTop: 1 }}>{i + 1}.</span>
                    <span style={{ color: '#E8EAF0', fontSize: 12 }}>{note}</span>
                  </div>
                ))}
              </div>
            </ChartPanel>

            {/* Risk Mitigation */}
            <ChartPanel title="Risk Mitigation Factors" style={{ marginTop: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12, padding: 12 }}>
                {(data.risk_mitigation || []).map((rm, i) => (
                  <div key={i} style={{ padding: 12, background: DEEP, borderRadius: 8, border: `1px solid ${BORDER}` }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: GOLD, marginBottom: 4 }}>{rm.factor}</div>
                    <div style={{ fontSize: 12, color: MUTED }}>{rm.detail}</div>
                  </div>
                ))}
              </div>
            </ChartPanel>

            {/* Technology */}
            <ChartPanel title="Technology Stack" style={{ marginTop: 16 }}>
              <div style={{ padding: 12 }}>
                <div style={{ fontSize: 12, color: MUTED, marginBottom: 8 }}>Platforms: {data.technology?.platforms?.join(', ')}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(data.technology?.stack || []).concat(data.technology?.ai_tools || []).map((t, i) => (
                    <span key={i} style={{ padding: '3px 10px', borderRadius: 4, background: `${BLUE}15`, border: `1px solid ${BLUE}33`, color: '#E8EAF0', fontSize: 11 }}>{t}</span>
                  ))}
                </div>
              </div>
            </ChartPanel>
          </div>
        )}

      </motion.div>
    </AnimatePresence>
  )
}
