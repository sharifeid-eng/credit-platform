import React, { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import useBreakpoint from '../hooks/useBreakpoint'
import { getTamaraSummary } from '../services/api'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, ComposedChart,
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

const PIE_COLORS = ['#C9A84C', '#2DD4BF', '#5B8DEF', '#F06060', '#A78BFA', '#F59E0B', '#EC4899', '#6366F1', '#10B981', '#EF4444']

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

const pct = (v) => v != null ? `${(v * 100).toFixed(2)}%` : '--'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, padding: '8px 12px', borderRadius: 6, fontSize: 12 }}>
      <div style={{ color: MUTED, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || '#E8EAF0' }}>
          {p.name}: {typeof p.value === 'number' && p.value < 1 ? (p.value * 100).toFixed(2) + '%' : p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// VINTAGE HEATMAP (novel component — CSS grid)
// ═══════════════════════════════════════════════════════════════════════════════
function VintageHeatmap({ data, metric = 'default' }) {
  const [activeMetric, setActiveMetric] = useState(metric)
  const metricData = data?.vintage_performance?.[activeMetric] || {}
  const portfolio = metricData.portfolio || []
  const colorScale = metricData._color_scale || {}

  if (!portfolio.length) return <div style={{ color: MUTED, padding: 20 }}>No vintage data available for {activeMetric}</div>

  // Get all MOB columns (reporting months)
  const allCols = new Set()
  portfolio.forEach(r => Object.keys(r).forEach(k => { if (k !== 'vintage') allCols.add(k) }))
  const columns = [...allCols].sort()

  // Color mapping
  const getColor = (val) => {
    if (val == null) return 'transparent'
    const maxVal = colorScale.p75 || colorScale.max || 0.05
    const ratio = Math.min(val / maxVal, 1)
    if (ratio < 0.33) return `rgba(45, 212, 191, ${0.15 + ratio * 1.5})`  // teal
    if (ratio < 0.66) return `rgba(201, 168, 76, ${0.2 + (ratio - 0.33) * 1.5})`  // gold
    return `rgba(240, 96, 96, ${0.3 + (ratio - 0.66) * 2})`  // red
  }

  const toggles = ['default', 'delinquency', 'dilution']

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {toggles.map(m => (
          <button key={m} onClick={() => setActiveMetric(m)}
            style={{
              padding: '6px 16px', borderRadius: 6, border: `1px solid ${m === activeMetric ? GOLD : BORDER}`,
              background: m === activeMetric ? 'rgba(201,168,76,0.15)' : 'transparent',
              color: m === activeMetric ? GOLD : MUTED, fontSize: 12, cursor: 'pointer', textTransform: 'capitalize',
            }}>{m === 'default' ? 'Default (+120DPD)' : m === 'delinquency' ? 'Delinquency (+7DPD)' : 'Dilution (Refund)'}</button>
        ))}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: `100px repeat(${columns.length}, 60px)`, gap: 1, fontSize: 10 }}>
          {/* Header row */}
          <div style={{ padding: '4px 6px', color: GOLD, fontWeight: 600, position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>Vintage</div>
          {columns.map(c => (
            <div key={c} style={{ padding: '4px 2px', color: MUTED, textAlign: 'center', whiteSpace: 'nowrap' }}>
              {c.replace('20', "'")}
            </div>
          ))}

          {/* Data rows */}
          {portfolio.map((row, ri) => (
            <React.Fragment key={ri}>
              <div style={{ padding: '4px 6px', color: '#E8EAF0', fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>
                {row.vintage}
              </div>
              {columns.map(c => {
                const val = row[c]
                return (
                  <div key={c} style={{
                    padding: '4px 2px', textAlign: 'center', background: getColor(val),
                    color: val != null ? '#E8EAF0' : 'transparent', borderRadius: 2,
                    fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                  }}>
                    {val != null ? `${(val * 100).toFixed(1)}` : ''}
                  </div>
                )
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {colorScale.min != null && (
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 11, color: MUTED }}>
          <span>Min: {(colorScale.min * 100).toFixed(2)}%</span>
          <span>P25: {(colorScale.p25 * 100).toFixed(2)}%</span>
          <span>P75: {(colorScale.p75 * 100).toFixed(2)}%</span>
          <span>Max: {(colorScale.max * 100).toFixed(2)}%</span>
          <span>({colorScale.count} data points)</span>
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// COVENANT TRIGGER CARD
// ═══════════════════════════════════════════════════════════════════════════════
function CovenantTriggerCard({ trigger }) {
  const { name, metric, current_value, l1_threshold, l2_threshold, l3_threshold, status, headroom_pct } = trigger
  const maxVal = l3_threshold * 1.2
  const barWidth = (val) => `${Math.min((val / maxVal) * 100, 100)}%`

  const statusColors = {
    compliant: TEAL,
    l1_breach: '#F59E0B',
    l2_breach: '#F97316',
    l3_breach: RED,
    unknown: MUTED,
  }

  return (
    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: '#E8EAF0', fontWeight: 600, textTransform: 'capitalize' }}>{name}</span>
        <span style={{ color: statusColors[status] || MUTED, fontSize: 12, fontWeight: 600 }}>
          {status === 'compliant' ? 'COMPLIANT' : status === 'unknown' ? 'N/A' : status.toUpperCase().replace('_', ' ')}
        </span>
      </div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 12 }}>{metric}</div>

      {/* Trigger zone bar */}
      <div style={{ position: 'relative', height: 24, background: DEEP, borderRadius: 4, overflow: 'hidden' }}>
        {/* L3 zone (red) */}
        <div style={{ position: 'absolute', left: barWidth(l2_threshold), right: 0, top: 0, bottom: 0, background: 'rgba(240,96,96,0.15)' }} />
        {/* L2 zone (orange) */}
        <div style={{ position: 'absolute', left: barWidth(l1_threshold), width: `calc(${barWidth(l2_threshold)} - ${barWidth(l1_threshold)})`, top: 0, bottom: 0, background: 'rgba(249,115,22,0.15)' }} />
        {/* L1 zone (amber) */}
        <div style={{ position: 'absolute', left: barWidth(l1_threshold * 0.7), width: `calc(${barWidth(l1_threshold)} - ${barWidth(l1_threshold * 0.7)})`, top: 0, bottom: 0, background: 'rgba(245,158,11,0.1)' }} />

        {/* Current value marker */}
        {current_value != null && (
          <div style={{
            position: 'absolute', left: barWidth(current_value), top: 0, bottom: 0,
            width: 3, background: statusColors[status] || TEAL, borderRadius: 2,
          }} />
        )}

        {/* Threshold markers */}
        {[{ val: l1_threshold, label: 'L1' }, { val: l2_threshold, label: 'L2' }, { val: l3_threshold, label: 'L3' }].map(t => (
          <div key={t.label} style={{
            position: 'absolute', left: barWidth(t.val), top: 0, bottom: 0,
            borderLeft: `1px dashed ${MUTED}`, opacity: 0.5,
          }}>
            <span style={{ position: 'absolute', top: -14, left: -8, fontSize: 9, color: MUTED }}>{t.label}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11 }}>
        <span style={{ color: statusColors[status] || MUTED }}>
          Current: {current_value != null ? `${current_value.toFixed(2)}%` : 'N/A'}
        </span>
        {headroom_pct != null && (
          <span style={{ color: TEAL }}>Headroom: {headroom_pct.toFixed(1)}pp to L1</span>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONCENTRATION GAUGE
// ═══════════════════════════════════════════════════════════════════════════════
function ConcentrationGauge({ name, actual, threshold, type = 'max' }) {
  const maxVal = type === 'max' ? threshold * 1.3 : 100
  const barPct = Math.min((actual / maxVal) * 100, 100)
  const threshPct = Math.min((threshold / maxVal) * 100, 100)
  const compliant = type === 'max' ? actual <= threshold : actual >= threshold

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: '#E8EAF0' }}>{name}</span>
        <span style={{ color: compliant ? TEAL : RED }}>{actual?.toFixed(1)}% / {threshold}%</span>
      </div>
      <div style={{ position: 'relative', height: 8, background: DEEP, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${barPct}%`, height: '100%', background: compliant ? TEAL : RED, borderRadius: 4, transition: 'width 0.5s ease' }} />
        <div style={{ position: 'absolute', left: `${threshPct}%`, top: -2, bottom: -2, width: 2, background: GOLD }} />
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// DATA TABLE (reusable)
// ═══════════════════════════════════════════════════════════════════════════════
function DataTable({ headers, rows, highlightLast = false }) {
  if (!rows?.length) return <div style={{ color: MUTED, padding: 16 }}>No data available</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: '8px 10px', textAlign: i === 0 ? 'left' : 'right', color: GOLD,
                borderBottom: `1px solid ${BORDER}`, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} style={{ background: ri % 2 === 0 ? 'transparent' : 'rgba(23,34,49,0.5)',
              ...(highlightLast && ri === rows.length - 1 ? { fontWeight: 600, borderTop: `1px solid ${GOLD}` } : {}) }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: '6px 10px', textAlign: ci === 0 ? 'left' : 'right', color: '#E8EAF0',
                  borderBottom: `1px solid ${BORDER}`, fontFamily: ci > 0 ? 'var(--font-mono, JetBrains Mono, monospace)' : 'inherit',
                  whiteSpace: 'nowrap' }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════
export default function TamaraDashboard() {
  const { tab } = useParams()
  const { company, product, snapshots, config } = useCompany()
  const { isMobile } = useBreakpoint()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const activeSection = tab || 'overview'
  const ccy = config?.currency || 'SAR'

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    const snap = snapshots?.[snapshots.length - 1]?.filename
    getTamaraSummary(company, product, snap)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [company, product, snapshots])

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300, color: MUTED }}>
      <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.5, repeat: Infinity }}>Loading Tamara data...</motion.div>
    </div>
  )

  if (!data) return <div style={{ color: RED, padding: 20 }}>Failed to load Tamara data</div>

  const overview = data.overview || {}
  const facilityTerms = data.facility_terms || {}
  const covenantStatus = data.covenant_status || {}
  const vintagePerf = data.vintage_performance || {}
  const fdd = data.deloitte_fdd || {}
  const hsbc = data.hsbc_reports || []
  const demographics = data.demographics || {}
  const businessPlan = data.business_plan || {}
  const companyOverview = data.company_overview || {}
  const dataNotes = data.data_notes || []
  const investorReporting = data.investor_reporting || {}

  // ── RENDER SECTION ───────────────────────────────────────────────────────
  const renderSection = () => {
    switch (activeSection) {

      // ── OVERVIEW ─────────────────────────────────────────────────────────
      case 'overview': {
        const kpis = [
          { label: 'Outstanding AR', value: fmt(overview.total_pending, `${ccy} `), subtitle: `as of ${overview.latest_date || ''}` },
          { label: 'Data Months', value: overview.months_of_data, subtitle: `${fdd.dpd_timeseries?.length || 0} monthly snapshots` },
          { label: 'Facility Limit', value: fmt(overview.facility_limit, '$'), subtitle: facilityTerms.facility_name?.split(' -- ')[0] || '' },
          { label: 'Registered Users', value: fmt(overview.registered_users), subtitle: `${fmt(overview.merchants)} merchants` },
          { label: 'Vintage Cohorts', value: overview.vintage_count, subtitle: 'origination months analyzed' },
        ]

        const productData = (overview.product_breakdown || []).map(p => ({
          name: p.product, value: p.pending_amount || 0,
        })).filter(p => p.value > 0)

        return (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              {kpis.map((k, i) => (
                <KpiCard key={i} label={k.label} value={k.value} subtitle={k.subtitle} index={i} />
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
              <ChartPanel title="Product Mix" subtitle="Outstanding by instalment type">
                {productData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={productData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                        innerRadius={50} outerRadius={90} paddingAngle={2} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        labelLine={{ stroke: MUTED, strokeWidth: 1 }}>
                        {productData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <div style={{ color: MUTED, padding: 20 }}>No product breakdown available</div>}
              </ChartPanel>

              <ChartPanel title="Company Snapshot" subtitle={companyOverview.full_name || 'Tamara Finance Company'}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                  {[
                    ['Founded', companyOverview.founded],
                    ['HQ', companyOverview.headquarters],
                    ['CEO', companyOverview.ceo],
                    ['Valuation', fmt(companyOverview.valuation, '$')],
                    ['Equity Raised', fmt(companyOverview.total_equity_raised, '$')],
                    ['Latest Round', companyOverview.latest_round],
                    ['Employees', companyOverview.employees?.toLocaleString()],
                    ['IPO Target', companyOverview.ipo_target],
                  ].map(([label, val], i) => (
                    <div key={i} style={{ padding: '6px 8px', background: i % 2 === 0 ? DEEP : 'transparent', borderRadius: 4 }}>
                      <div style={{ color: MUTED, fontSize: 10, marginBottom: 2 }}>{label}</div>
                      <div style={{ color: '#E8EAF0' }}>{val || '--'}</div>
                    </div>
                  ))}
                </div>
              </ChartPanel>
            </div>
          </div>
        )
      }

      // ── VINTAGE PERFORMANCE ──────────────────────────────────────────────
      case 'vintage':
        return (
          <ChartPanel title="Vintage Cohort Heatmap" subtitle="Default / Delinquency / Dilution rates by origination vintage and reporting month">
            <VintageHeatmap data={data} metric="default" />
          </ChartPanel>
        )

      // ── DELINQUENCY ──────────────────────────────────────────────────────
      case 'delinquency': {
        const ts = fdd.dpd_timeseries || []
        const chartData = ts.map(entry => {
          const dpd = entry.dpd_distribution || {}
          const total = Object.values(dpd).reduce((s, v) => s + (v || 0), 0)
          return {
            date: (entry.date || '').slice(0, 7),
            'Not Late': (dpd['Not Late'] || 0) / (total || 1) * 100,
            '1-7 DPD': (dpd['1-7'] || 0) / (total || 1) * 100,
            '8-30 DPD': ((dpd['8-15'] || 0) + (dpd['16-30'] || 0)) / (total || 1) * 100,
            '31-90 DPD': ((dpd['31-60'] || 0) + (dpd['61-90'] || 0)) / (total || 1) * 100,
            '91+ DPD': ((dpd['91-120'] || 0) + (dpd['121-150'] || 0) + (dpd['151-180'] || 0) + (dpd['181-365'] || 0) + (dpd['>365'] || 0)) / (total || 1) * 100,
          }
        }).filter(d => d.date)

        return (
          <div>
            <ChartPanel title="DPD Bucket Distribution Over Time" subtitle="Percentage of outstanding by days past due">
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="date" tick={{ fill: MUTED, fontSize: 10 }} />
                  <YAxis tick={{ fill: MUTED, fontSize: 10 }} domain={[0, 100]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Area type="monotone" dataKey="Not Late" stackId="1" fill={TEAL} stroke={TEAL} fillOpacity={0.6} />
                  <Area type="monotone" dataKey="1-7 DPD" stackId="1" fill={BLUE} stroke={BLUE} fillOpacity={0.6} />
                  <Area type="monotone" dataKey="8-30 DPD" stackId="1" fill={GOLD} stroke={GOLD} fillOpacity={0.6} />
                  <Area type="monotone" dataKey="31-90 DPD" stackId="1" fill="#F59E0B" stroke="#F59E0B" fillOpacity={0.6} />
                  <Area type="monotone" dataKey="91+ DPD" stackId="1" fill={RED} stroke={RED} fillOpacity={0.6} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartPanel>

            <ChartPanel title="Customer Type Breakdown" subtitle="Latest snapshot" style={{ marginTop: 16 }}>
              <DataTable
                headers={['Customer Type', 'Pending Amount', 'Written Off', 'Write-off %']}
                rows={(fdd.customer_breakdown || []).map(c => [
                  c.customer_type, fmt(c.pending_amount, `${ccy} `), fmt(c.written_off, `${ccy} `),
                  c.pending_amount ? `${((c.written_off || 0) / c.pending_amount * 100).toFixed(2)}%` : '--',
                ])}
              />
            </ChartPanel>
          </div>
        )
      }

      // ── DEFAULT ANALYSIS ─────────────────────────────────────────────────
      case 'default-analysis': {
        const defaults = vintagePerf.default?.portfolio || []
        if (!defaults.length) return <ChartPanel title="Default Analysis"><div style={{ color: MUTED, padding: 20 }}>No default data available</div></ChartPanel>

        // Build cumulative curves per vintage
        const columns = [...new Set(defaults.flatMap(r => Object.keys(r).filter(k => k !== 'vintage')))].sort()
        const lineData = columns.map(col => {
          const point = { month: col.replace('20', "'") }
          defaults.forEach(row => {
            if (row[col] != null) point[row.vintage] = row[col] * 100
          })
          return point
        })

        // Only show last 8 vintages for readability
        const vintageKeys = defaults.slice(-8).map(r => r.vintage)

        return (
          <ChartPanel title="Default Rate (+120DPD) by Vintage" subtitle="Cumulative default progression over reporting months">
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={lineData}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="month" tick={{ fill: MUTED, fontSize: 10 }} />
                <YAxis tick={{ fill: MUTED, fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                {vintageKeys.map((v, i) => (
                  <Line key={v} type="monotone" dataKey={v} stroke={PIE_COLORS[i % PIE_COLORS.length]}
                    dot={false} strokeWidth={2} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </ChartPanel>
        )
      }

      // ── DILUTION ─────────────────────────────────────────────────────────
      case 'dilution': {
        const dilutionData = vintagePerf.dilution || {}
        const products = Object.keys(dilutionData).filter(k => !k.startsWith('_'))

        // Get the latest value per product
        const barData = products.map(prod => {
          const records = dilutionData[prod] || []
          if (!records.length) return null
          const latest = records[records.length - 1]
          const cols = Object.keys(latest).filter(k => k !== 'vintage').sort()
          const lastCol = cols[cols.length - 1]
          return { product: prod, rate: (latest[lastCol] || 0) * 100 }
        }).filter(Boolean)

        return (
          <ChartPanel title="Dilution (Refund) Rate by Product" subtitle="Latest vintage's cumulative dilution rate">
            {barData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={barData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <YAxis type="category" dataKey="product" tick={{ fill: MUTED, fontSize: 10 }} width={120} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="rate" fill={GOLD} name="Dilution Rate %" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <div style={{ color: MUTED, padding: 20 }}>No dilution data available</div>}
          </ChartPanel>
        )
      }

      // ── COLLECTIONS ──────────────────────────────────────────────────────
      case 'collections': {
        const ts = fdd.dpd_timeseries || []
        const chartData = ts.slice(-12).map(entry => ({
          date: (entry.date || '').slice(0, 7),
          pending: (entry.total_pending || 0) / 1e6,
          writeoff: (entry.total_written_off || 0) / 1e6,
        }))

        return (
          <ChartPanel title="Portfolio Outstanding & Write-offs" subtitle={`Last 12 months (${ccy} millions)`}>
            <ResponsiveContainer width="100%" height={350}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="date" tick={{ fill: MUTED, fontSize: 10 }} />
                <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Bar dataKey="pending" name="Outstanding (M)" fill={BLUE} opacity={0.7} />
                <Line type="monotone" dataKey="writeoff" name="Written Off (M)" stroke={RED} strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartPanel>
        )
      }

      // ── CONCENTRATION ────────────────────────────────────────────────────
      case 'concentration': {
        const latestReport = hsbc[hsbc.length - 1] || {}
        const strats = latestReport.stratifications || {}
        const limits = facilityTerms.concentration_limits || []

        // Find merchant category stratification
        const catStrat = strats['Category'] || strats['Merchant Category'] || null
        const catData = catStrat?.rows?.slice(0, 10).map(r => ({
          name: r[0]?.slice(0, 20) || '', value: parseFloat((r[1] || '0').replace(/[,$]/g, '')) || 0,
        })).filter(d => d.value > 0) || []

        return (
          <div>
            {limits.length > 0 && (
              <ChartPanel title="Concentration Limit Compliance" subtitle={`${limits.length} limits monitored`}>
                {limits.map((l, i) => (
                  <ConcentrationGauge key={i} name={l.name} actual={0} threshold={parseFloat(l.threshold?.replace(/[^0-9.]/g, '') || '0')} type={l.type} />
                ))}
              </ChartPanel>
            )}

            {catData.length > 0 && (
              <ChartPanel title="Portfolio by Merchant Category" subtitle="Top categories by outstanding balance" style={{ marginTop: 16 }}>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={catData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: MUTED, fontSize: 10 }} width={150} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" fill={GOLD} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartPanel>
            )}
          </div>
        )
      }

      // ── COVENANT COMPLIANCE ──────────────────────────────────────────────
      case 'covenant-compliance': {
        const triggers = covenantStatus.triggers || []
        const corpCovenants = facilityTerms.corporate_covenants || {}

        return (
          <div>
            <ChartPanel title="Performance Trigger Tests" subtitle={`3-level trigger system: L1 (Stop Funding) / L2 (Cash Sweep) / L3 (Event of Default)`}>
              <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr 1fr', gap: 12 }}>
                {triggers.map((t, i) => <CovenantTriggerCard key={i} trigger={t} />)}
              </div>
            </ChartPanel>

            <ChartPanel title="Corporate Covenants" subtitle="Financial covenant requirements" style={{ marginTop: 16 }}>
              <DataTable
                headers={['Covenant', 'L1 Threshold', 'L2 Threshold', 'L3 Threshold']}
                rows={Object.entries(corpCovenants).map(([name, vals]) => [
                  name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                  typeof vals.threshold === 'number' && vals.threshold < 1 ? pct(vals.threshold) : fmt(vals.threshold, '$'),
                  typeof vals.l2 === 'number' && vals.l2 < 1 ? pct(vals.l2) : fmt(vals.l2, '$'),
                  typeof vals.l3 === 'number' && vals.l3 < 1 ? pct(vals.l3) : fmt(vals.l3, '$'),
                ])}
              />
            </ChartPanel>
          </div>
        )
      }

      // ── FACILITY STRUCTURE ───────────────────────────────────────────────
      case 'facility-structure': {
        const tranches = facilityTerms.tranches || []

        return (
          <div>
            <ChartPanel title="Facility Structure" subtitle={facilityTerms.facility_name}>
              <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
                {[
                  { label: 'Total Limit', value: fmt(facilityTerms.total_limit, '$') },
                  { label: 'Max Advance Rate', value: `${(facilityTerms.max_advance_rate || 0) * 100}%` },
                  { label: 'SPV', value: facilityTerms.spv?.split('(')[0]?.trim() || '--' },
                  { label: 'Close Date', value: facilityTerms.close_date },
                  { label: 'Revolving End', value: facilityTerms.revolving_end },
                  { label: 'Final Maturity', value: facilityTerms.final_maturity },
                ].map((k, i) => (
                  <div key={i} style={{ padding: '10px 12px', background: DEEP, borderRadius: 6, border: `1px solid ${BORDER}` }}>
                    <div style={{ color: MUTED, fontSize: 10, marginBottom: 4 }}>{k.label}</div>
                    <div style={{ color: '#E8EAF0', fontSize: 14, fontFamily: 'var(--font-mono, JetBrains Mono, monospace)' }}>{k.value}</div>
                  </div>
                ))}
              </div>

              <DataTable
                headers={['Tranche', 'Limit', 'Rate', 'Lender']}
                rows={tranches.map(t => [t.name, fmt(t.limit, '$'), t.rate, t.lender])}
              />
            </ChartPanel>

            {hsbc.length > 0 && (
              <ChartPanel title="HSBC Monthly Reports" subtitle={`${hsbc.length} reports available`} style={{ marginTop: 16 }}>
                <DataTable
                  headers={['Report', 'Date', 'BB Test Keys', 'Triggers', 'Stratifications']}
                  rows={hsbc.map(r => [
                    r.filename?.slice(0, 40) || '', r.report_date || '',
                    Object.keys(r.bb_test || {}).length, (r.triggers || []).length,
                    Object.keys(r.stratifications || {}).length,
                  ])}
                />
              </ChartPanel>
            )}
          </div>
        )
      }

      // ── DEMOGRAPHICS ─────────────────────────────────────────────────────
      case 'demographics': {
        const raw = demographics.raw || []
        if (!raw.length) return <ChartPanel title="Demographics"><div style={{ color: MUTED, padding: 20 }}>No demographic data available for this product</div></ChartPanel>

        return (
          <ChartPanel title="Portfolio Demographics" subtitle="Outstanding AR and Ever-90 loss rates by borrower segment">
            <DataTable
              headers={Object.keys(raw[0] || {})}
              rows={raw.map(r => Object.values(r).map(v => v != null ? String(v) : '--'))}
            />
          </ChartPanel>
        )
      }

      // ── FINANCIAL PERFORMANCE ────────────────────────────────────────────
      case 'financial-performance': {
        const kpis = investorReporting.kpis || []
        const financials = investorReporting.financials || []

        return (
          <div>
            <ChartPanel title="Key Performance Indicators" subtitle="From Investor Monthly Reporting">
              {kpis.length > 0 ? (
                <DataTable
                  headers={['Metric', ...Object.keys(kpis[0]?.values || {}).slice(0, 12)]}
                  rows={kpis.slice(0, 30).map(k => [k.metric, ...Object.values(k.values).slice(0, 12).map(v => typeof v === 'number' ? v.toLocaleString() : String(v || ''))])}
                />
              ) : <div style={{ color: MUTED, padding: 20 }}>No KPI data available</div>}
            </ChartPanel>

            {financials.length > 0 && (
              <ChartPanel title="Financial Statements" subtitle="P&L / Balance Sheet" style={{ marginTop: 16 }}>
                <DataTable
                  headers={['Line Item', ...Object.keys(financials[0]?.values || {}).slice(0, 12)]}
                  rows={financials.slice(0, 40).map(f => [f.line_item, ...Object.values(f.values).slice(0, 12).map(v => typeof v === 'number' ? v.toLocaleString() : String(v || ''))])}
                />
              </ChartPanel>
            )}
          </div>
        )
      }

      // ── BUSINESS PLAN ────────────────────────────────────────────────────
      case 'business-plan': {
        const summary = businessPlan.summary || []
        if (!summary.length) return <ChartPanel title="Business Plan"><div style={{ color: MUTED, padding: 20 }}>No business plan data available</div></ChartPanel>

        return (
          <ChartPanel title="Business Plan FY26-FY30" subtitle="Management projections">
            <DataTable
              headers={['Metric', ...Object.keys(summary[0]?.values || {}).slice(0, 12)]}
              rows={summary.slice(0, 30).map(s => [s.metric, ...Object.values(s.values).slice(0, 12).map(v => typeof v === 'number' ? v.toLocaleString() : String(v || ''))])}
            />
          </ChartPanel>
        )
      }

      // ── BNPL+ DEEP DIVE ──────────────────────────────────────────────────
      case 'bnpl-plus': {
        const defaultData = vintagePerf.default || {}
        const delinqData = vintagePerf.delinquency || {}
        const bnplProducts = Object.keys(defaultData).filter(k => k.startsWith('BNPL+') && !k.startsWith('_'))
        const bnplStd = Object.keys(defaultData).filter(k => k.startsWith('BNPL ') && !k.startsWith('BNPL+') && !k.startsWith('_'))

        const compareData = []
        // Compare BNPL Portfolio vs BNPL+ Portfolio for delinquency
        const bnplDelinq = delinqData['BNPL Portfolio'] || []
        const bnplPlusDelinq = delinqData['BNPL+ Portfolio'] || []

        if (bnplDelinq.length || bnplPlusDelinq.length) {
          const allVintages = [...new Set([
            ...bnplDelinq.map(r => r.vintage),
            ...bnplPlusDelinq.map(r => r.vintage),
          ])].sort()

          allVintages.forEach(v => {
            const bnplRow = bnplDelinq.find(r => r.vintage === v)
            const plusRow = bnplPlusDelinq.find(r => r.vintage === v)
            if (bnplRow || plusRow) {
              // Get latest value for each
              const getLatestVal = (row) => {
                if (!row) return null
                const cols = Object.keys(row).filter(k => k !== 'vintage').sort()
                return cols.length ? row[cols[cols.length - 1]] : null
              }
              const bnplVal = getLatestVal(bnplRow)
              const plusVal = getLatestVal(plusRow)
              compareData.push({
                vintage: v,
                'BNPL': bnplVal != null ? bnplVal * 100 : null,
                'BNPL+': plusVal != null ? plusVal * 100 : null,
              })
            }
          })
        }

        // APR schedule
        const products = companyOverview.products?.bnpl_plus || {}
        const apr = products.apr || {}

        return (
          <div>
            <ChartPanel title="BNPL vs BNPL+ Delinquency Comparison" subtitle="Latest +7DPD rate by vintage">
              {compareData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={compareData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis dataKey="vintage" tick={{ fill: MUTED, fontSize: 10 }} />
                    <YAxis tick={{ fill: MUTED, fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Bar dataKey="BNPL" fill={TEAL} />
                    <Bar dataKey="BNPL+" fill={GOLD} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div style={{ color: MUTED, padding: 20 }}>Insufficient data for BNPL vs BNPL+ comparison</div>}
            </ChartPanel>

            {Object.keys(apr).length > 0 && (
              <ChartPanel title="BNPL+ APR Schedule" subtitle="Effective APR by instalment plan (Jan 2026)" style={{ marginTop: 16 }}>
                <DataTable
                  headers={['Plan', 'APR']}
                  rows={Object.entries(apr).map(([plan, rate]) => [plan, `${(rate * 100).toFixed(0)}%`])}
                />
              </ChartPanel>
            )}

            <ChartPanel title="BNPL+ Product Breakdown" subtitle="Available product-level vintage data" style={{ marginTop: 16 }}>
              <DataTable
                headers={['Product', 'Default Vintages', 'Delinquency Vintages']}
                rows={bnplProducts.map(p => [
                  p,
                  (defaultData[p] || []).length,
                  (delinqData[p] || []).length,
                ])}
              />
            </ChartPanel>
          </div>
        )
      }

      // ── DATA NOTES ───────────────────────────────────────────────────────
      case 'notes':
        return (
          <ChartPanel title="Data Notes & Sources" subtitle="Methodology, definitions, and data source inventory">
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {dataNotes.map((note, i) => (
                <li key={i} style={{
                  padding: '8px 12px', borderBottom: `1px solid ${BORDER}`, color: '#E8EAF0', fontSize: 13,
                  display: 'flex', gap: 8,
                }}>
                  <span style={{ color: GOLD, fontWeight: 600, flexShrink: 0 }}>{i + 1}.</span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>

            {data.meta?.data_sources && (
              <div style={{ marginTop: 16 }}>
                <h4 style={{ color: GOLD, fontSize: 13, marginBottom: 8 }}>Data Sources</h4>
                {data.meta.data_sources.map((src, i) => (
                  <div key={i} style={{ padding: '4px 0', color: MUTED, fontSize: 12 }}>{src}</div>
                ))}
              </div>
            )}
          </ChartPanel>
        )

      default:
        return <div style={{ color: MUTED, padding: 20 }}>Tab "{activeSection}" not yet implemented</div>
    }
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeSection}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.25 }}
      >
        {renderSection()}
      </motion.div>
    </AnimatePresence>
  )
}
