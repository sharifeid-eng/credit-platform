import React, { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import useBreakpoint from '../hooks/useBreakpoint'
import { getTamaraSummary } from '../services/api'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import VintageHeatmap from '../components/charts/VintageHeatmap'
import CovenantTriggerCard from '../components/portfolio/CovenantTriggerCard'
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
          {p.name}: {typeof p.value === 'number' && p.value <= 1 && p.value >= 0 ? (p.value * 100).toFixed(2) + '%' : p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  )
}

// VintageHeatmap and CovenantTriggerCard imported from shared components

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

          {/* Dilution time-series by vintage — use first product */}
          {(() => {
            const firstProd = products[0]
            const records = firstProd ? (dilutionData[firstProd] || []) : []
            if (!records.length) return null

            const allMobs = new Set()
            records.forEach(r => Object.keys(r).forEach(k => { if (k !== 'vintage') allMobs.add(k) }))
            const mobs = [...allMobs].sort()
            const recentVintages = records.slice(-8)

            const lineData = mobs.map(mob => {
              const point = { mob }
              recentVintages.forEach(v => {
                if (v[mob] != null) point[v.vintage] = (v[mob] * 100)
              })
              return point
            })

            return (
              <ChartPanel title="Dilution Curves by Vintage" subtitle={`${firstProd} — cumulative dilution rate over time`} style={{ marginTop: 16 }}>
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={lineData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis dataKey="mob" tick={{ fill: MUTED, fontSize: 10 }} />
                    <YAxis tick={{ fill: MUTED, fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    {recentVintages.map((v, i) => (
                      <Line key={v.vintage} type="monotone" dataKey={v.vintage} stroke={PIE_COLORS[i % PIE_COLORS.length]}
                        dot={false} strokeWidth={1.5} name={v.vintage} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </ChartPanel>
            )
          })()}
        </div>
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
        const hsbc_limits = latestReport.concentration_limits || []

        // Try to extract actual values from HSBC concentration limits
        const limitActuals = {}
        hsbc_limits.forEach(l => {
          const name = l.criterion || ''
          const vals = l.values || []
          // Try to find a percentage value
          for (const v of vals) {
            const num = parseFloat((v || '').replace(/[%,$]/g, '').trim())
            if (!isNaN(num) && num >= 0 && num <= 100) {
              limitActuals[name.slice(0, 30)] = num
              break
            }
          }
        })

        // Find merchant category stratification
        const catStrat = strats['Category'] || strats['Merchant Category'] || null
        const catData = catStrat?.rows?.slice(0, 10).map(r => ({
          name: r[0]?.slice(0, 20) || '', value: parseFloat((r[1] || '0').replace(/[,$]/g, '')) || 0,
        })).filter(d => d.value > 0) || []

        // Also show instalment type and obligor type stratifications
        const instStrat = strats['Instalments'] || strats['Instalment Type'] || null
        const instData = instStrat?.rows?.map(r => ({
          name: r[0] || '', value: parseFloat((r[1] || '0').replace(/[,$]/g, '')) || 0,
          pct: r[2] || '',
        })).filter(d => d.value > 0) || []

        const obligorStrat = strats['Obligors'] || strats['Obligor Type'] || null

        return (
          <div>
            {limits.length > 0 && (
              <ChartPanel title="Concentration Limit Compliance" subtitle={`${limits.length} limits from facility agreement | ${hsbc_limits.length} reported by HSBC`}>
                {limits.map((l, i) => {
                  const threshold = parseFloat(l.threshold?.replace(/[^0-9.]/g, '') || '0')
                  // Try to match actual from HSBC data
                  const matchKey = Object.keys(limitActuals).find(k => k.toLowerCase().includes(l.name.toLowerCase().slice(0, 10)))
                  const actual = matchKey ? limitActuals[matchKey] : null
                  return <ConcentrationGauge key={i} name={l.name} actual={actual || 0} threshold={threshold} type={l.type} />
                })}
              </ChartPanel>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16, marginTop: 16 }}>
              {catData.length > 0 && (
                <ChartPanel title="Portfolio by Merchant Category" subtitle="Top categories by outstanding">
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={catData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                      <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" tick={{ fill: MUTED, fontSize: 10 }} width={130} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="value" fill={GOLD} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartPanel>
              )}

              {instData.length > 0 && (
                <ChartPanel title="Portfolio by Instalment Type" subtitle="Outstanding by Pay-in-N plan">
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie data={instData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                        innerRadius={50} outerRadius={90} paddingAngle={2}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        labelLine={{ stroke: MUTED, strokeWidth: 1 }}>
                        {instData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                </ChartPanel>
              )}
            </div>
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
        const dims = demographics.dimensions || {}
        const dimNames = Object.keys(dims)
        const [activeDim, setActiveDim] = useState(dimNames[0] || '')
        const dimData = dims[activeDim] || []

        if (!dimNames.length) return <ChartPanel title="Demographics"><div style={{ color: MUTED, padding: 20 }}>No demographic data available for this product</div></ChartPanel>

        const chartData = dimData.map(d => ({
          category: String(d.category || '').slice(0, 18),
          'Outstanding AR': typeof d.outstanding_ar === 'number' ? d.outstanding_ar : parseFloat(d.outstanding_ar) || 0,
          'Ever-90 Rate': typeof d.ever_90_rate === 'number' ? d.ever_90_rate * 100 : parseFloat(d.ever_90_rate) * 100 || 0,
        }))

        return (
          <ChartPanel title="Portfolio Demographics" subtitle="Outstanding AR and Ever-90 loss rates by borrower segment">
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              {dimNames.map(d => (
                <button key={d} onClick={() => setActiveDim(d)}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                    border: `1px solid ${d === activeDim ? GOLD : BORDER}`,
                    background: d === activeDim ? 'rgba(201,168,76,0.15)' : 'transparent',
                    color: d === activeDim ? GOLD : MUTED, textTransform: 'capitalize',
                  }}>{d.replace(/_/g, ' ')}</button>
              ))}
            </div>

            {chartData.length > 0 && (
              <ResponsiveContainer width="100%" height={Math.max(250, chartData.length * 35)}>
                <ComposedChart data={chartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} />
                  <YAxis type="category" dataKey="category" tick={{ fill: MUTED, fontSize: 10 }} width={120} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="Outstanding AR" fill={BLUE} opacity={0.7} name="Outstanding AR %" />
                  <Line type="monotone" dataKey="Ever-90 Rate" stroke={RED} strokeWidth={2} dot={{ r: 4 }} name="Ever-90 Loss %" />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </ChartPanel>
        )
      }

      // ── FINANCIAL PERFORMANCE ────────────────────────────────────────────
      case 'financial-performance': {
        const kpis = investorReporting.kpis || []
        const financials = investorReporting.financials || []

        // Extract key metrics for trend chart
        const findKpi = (keyword) => kpis.find(k => k.metric?.toLowerCase().includes(keyword.toLowerCase()))
        const gmvRow = findKpi('Total GMV') || findKpi('GMV')
        const revenueRow = findKpi('Total Operating Revenue') || findKpi('Revenue') || findKpi('Net MDR')
        const marginRow = findKpi('Contribution Margin') || findKpi('EBTDA')

        // Build time-series from monthly values
        const trendData = []
        if (gmvRow) {
          const vals = gmvRow.values || {}
          Object.entries(vals).sort(([a], [b]) => a.localeCompare(b)).forEach(([month, val]) => {
            if (typeof val === 'number' && month.match(/^\d{4}/)) {
              const existing = trendData.find(d => d.month === month)
              if (existing) existing.GMV = val / 1e6
              else trendData.push({ month: month.slice(0, 7), GMV: val / 1e6 })
            }
          })
        }
        if (revenueRow) {
          const vals = revenueRow.values || {}
          Object.entries(vals).sort(([a], [b]) => a.localeCompare(b)).forEach(([month, val]) => {
            if (typeof val === 'number' && month.match(/^\d{4}/)) {
              const existing = trendData.find(d => d.month === month.slice(0, 7))
              if (existing) existing.Revenue = val / 1e6
              else trendData.push({ month: month.slice(0, 7), Revenue: val / 1e6 })
            }
          })
        }

        return (
          <div>
            {trendData.length > 3 && (
              <ChartPanel title="Financial Trends" subtitle="GMV and Revenue (monthly, $M)">
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis dataKey="month" tick={{ fill: MUTED, fontSize: 10 }} />
                    <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Bar dataKey="GMV" fill={BLUE} opacity={0.5} name="GMV ($M)" />
                    <Line type="monotone" dataKey="Revenue" stroke={GOLD} strokeWidth={2} dot={{ r: 3 }} name="Revenue ($M)" />
                  </ComposedChart>
                </ResponsiveContainer>
              </ChartPanel>
            )}

            <ChartPanel title="Key Performance Indicators" subtitle={`${kpis.length} metrics from Investor Monthly Reporting`} style={{ marginTop: 16 }}>
              {kpis.length > 0 ? (
                <DataTable
                  headers={['Metric', ...Object.keys(kpis[0]?.values || {}).slice(-8)]}
                  rows={kpis.slice(0, 30).map(k => {
                    const vals = Object.entries(k.values || {}).slice(-8)
                    return [k.metric, ...vals.map(([, v]) => typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : String(v || ''))]
                  })}
                />
              ) : <div style={{ color: MUTED, padding: 20 }}>No KPI data available</div>}
            </ChartPanel>

            {financials.length > 0 && (
              <ChartPanel title="Financial Statements" subtitle={`${financials.length} line items`} style={{ marginTop: 16 }}>
                <DataTable
                  headers={['Line Item', ...Object.keys(financials[0]?.values || {}).slice(-8)]}
                  rows={financials.slice(0, 40).map(f => {
                    const vals = Object.entries(f.values || {}).slice(-8)
                    return [f.line_item, ...vals.map(([, v]) => typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : String(v || ''))]
                  })}
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

        // Extract GMV and Revenue projections for chart
        const findRow = (keyword) => summary.find(s => s.metric?.toLowerCase().includes(keyword.toLowerCase()))
        const gmvRow = findRow('Total GMV') || findRow('GMV')
        const revRow = findRow('Revenue') && !findRow('Revenue')?.metric?.includes('Margin') ? findRow('Revenue') : findRow('Total Revenue')
        const ebtdaRow = findRow('EBTDA') || findRow('EBITDA')

        const projData = []
        const allRows = [gmvRow, revRow, ebtdaRow].filter(Boolean)
        if (allRows.length > 0) {
          const years = [...new Set(allRows.flatMap(r => Object.keys(r.values || {})))].sort()
          years.forEach(yr => {
            const point = { year: yr }
            if (gmvRow?.values?.[yr]) point.GMV = gmvRow.values[yr] / 1e6
            if (revRow?.values?.[yr]) point.Revenue = revRow.values[yr] / 1e6
            if (ebtdaRow?.values?.[yr]) point.EBTDA = ebtdaRow.values[yr] / 1e6
            if (Object.keys(point).length > 1) projData.push(point)
          })
        }

        return (
          <div>
            {projData.length > 2 && (
              <ChartPanel title="Business Plan Projections" subtitle="GMV, Revenue, EBTDA ($M)">
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={projData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis dataKey="year" tick={{ fill: MUTED, fontSize: 11 }} />
                    <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Bar dataKey="GMV" fill={BLUE} opacity={0.4} name="GMV ($M)" />
                    <Line type="monotone" dataKey="Revenue" stroke={GOLD} strokeWidth={2} dot={{ r: 4 }} name="Revenue ($M)" />
                    <Line type="monotone" dataKey="EBTDA" stroke={TEAL} strokeWidth={2} dot={{ r: 4 }} name="EBTDA ($M)" />
                  </ComposedChart>
                </ResponsiveContainer>
              </ChartPanel>
            )}

            <ChartPanel title="Business Plan Detail" subtitle={`${summary.length} projection metrics (FY26-FY30)`} style={{ marginTop: 16 }}>
              <DataTable
                headers={['Metric', ...Object.keys(summary[0]?.values || {})]}
                rows={summary.slice(0, 40).map(s => [s.metric, ...Object.values(s.values).map(v => typeof v === 'number' ? (Math.abs(v) >= 1e6 ? `${(v/1e6).toFixed(0)}M` : v.toLocaleString(undefined, { maximumFractionDigits: 1 })) : String(v || ''))])}
              />
            </ChartPanel>
          </div>
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

      // ── TRIGGER TRENDS HEATMAP ───────────────────────────────────────────
      case 'trigger-trends': {
        // Build time-series from all HSBC reports
        const ft = facilityTerms.triggers || {}
        const triggerKeys = Object.keys(ft)
        const months = hsbc.map((r, i) => {
          const label = r.report_date || r.meta?.report_date || `Report ${i + 1}`
          return label.slice(0, 7)
        }).filter(Boolean)

        // Build matrix: for each trigger key, for each report month, determine status
        const matrix = triggerKeys.map(tKey => {
          const def = ft[tKey] || {}
          const l1 = def.l1 || 0
          const l2 = def.l2 || 0
          const l3 = def.l3 || 0
          const row = { trigger: tKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }
          hsbc.forEach((report, ri) => {
            const triggerRows = report.triggers || []
            let val = null
            for (const tr of triggerRows) {
              const lbl = (tr.label || '').toLowerCase()
              if (tKey.toLowerCase().includes(lbl.slice(0, 8)) || lbl.includes(tKey.toLowerCase().slice(0, 8))) {
                for (const v of (tr.values || [])) {
                  try {
                    const n = parseFloat(String(v).replace('%', '').replace(',', ''))
                    if (n >= 0 && n <= 100) { val = n / 100; break }
                  } catch {}
                }
              }
            }
            let status = 0 // 0=unknown
            if (val !== null) {
              if (val < l1) status = 1 // compliant
              else if (val < l2) status = 2 // l1 breach
              else if (val < l3) status = 3 // l2 breach
              else status = 4 // l3 breach
            }
            row[months[ri] || `r${ri}`] = status
          })
          return row
        })

        const statusColors = ['transparent', 'rgba(45,212,191,0.5)', 'rgba(245,158,11,0.5)', 'rgba(249,115,22,0.6)', 'rgba(240,96,96,0.7)']
        const statusLabels = ['N/A', 'Compliant', 'L1 Breach', 'L2 Breach', 'L3 Breach']
        const cols = months.length ? months : hsbc.map((_, i) => `r${i}`)

        return (
          <ChartPanel title="Trigger Status Heatmap" subtitle="Performance trigger compliance across HSBC reporting months">
            {matrix.length > 0 && cols.length > 0 ? (
              <div>
                <div style={{ overflowX: 'auto' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: `160px repeat(${cols.length}, 70px)`, gap: 1, fontSize: 10 }}>
                    <div style={{ padding: '6px 8px', color: GOLD, fontWeight: 600, position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>Trigger</div>
                    {cols.map(c => <div key={c} style={{ padding: '6px 4px', color: MUTED, textAlign: 'center', whiteSpace: 'nowrap' }}>{c}</div>)}
                    {matrix.map((row, ri) => (
                      <React.Fragment key={ri}>
                        <div style={{ padding: '6px 8px', color: '#E8EAF0', fontSize: 10, position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>{row.trigger}</div>
                        {cols.map(c => {
                          const s = row[c] || 0
                          return (
                            <div key={c} style={{
                              padding: '6px 4px', textAlign: 'center', borderRadius: 2,
                              background: statusColors[s], color: s > 0 ? '#E8EAF0' : 'transparent',
                              fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                            }}>
                              {s > 0 ? statusLabels[s]?.charAt(0) : ''}
                            </div>
                          )
                        })}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
                <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 11 }}>
                  {statusLabels.slice(1).map((label, i) => (
                    <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, color: MUTED }}>
                      <span style={{ width: 12, height: 12, borderRadius: 2, background: statusColors[i + 1], display: 'inline-block' }} />
                      {label}
                    </span>
                  ))}
                </div>
              </div>
            ) : <div style={{ color: MUTED, padding: 20 }}>No trigger trend data available</div>}
          </ChartPanel>
        )
      }

      // ── FACILITY PAYMENT WATERFALL ────────────────────────────────────────
      case 'facility-waterfall': {
        // Get waterfall from latest HSBC report that has it
        let waterfallData = []
        let waterfallMonth = ''
        for (let i = hsbc.length - 1; i >= 0; i--) {
          const wf = hsbc[i].waterfall || []
          if (wf.length > 0) {
            waterfallData = wf
            waterfallMonth = (hsbc[i].report_date || hsbc[i].meta?.report_date || `Report ${i + 1}`).slice(0, 7)
            break
          }
        }

        // Build chart data from waterfall steps
        const chartData = waterfallData.map((step, i) => {
          const value = Array.isArray(step.values) ? step.values[0] : step.value
          let numVal = 0
          if (typeof value === 'number') numVal = value
          else if (typeof value === 'string') {
            numVal = parseFloat(value.replace(/[$,]/g, '')) || 0
          }
          return { step: step.step || step.label || `Step ${i + 1}`, value: numVal / 1e6 }
        })

        return (
          <ChartPanel title="Payment Waterfall" subtitle={waterfallMonth ? `Facility payment cascade — ${waterfallMonth}` : 'Facility payment cascade'}>
            {chartData.length > 0 ? (
              <div>
                <ResponsiveContainer width="100%" height={Math.max(400, chartData.length * 28)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} tickFormatter={v => `$${v.toFixed(1)}M`} />
                    <YAxis type="category" dataKey="step" tick={{ fill: MUTED, fontSize: 9 }} width={200} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" name="Amount ($M)" radius={[0, 4, 4, 0]}>
                      {chartData.map((entry, i) => (
                        <Cell key={i} fill={i === 0 ? TEAL : i === chartData.length - 1 ? GOLD : BLUE} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <DataTable
                  headers={['Step', 'Amount']}
                  rows={chartData.map(d => [d.step, `$${d.value.toFixed(2)}M`])}
                />
              </div>
            ) : <div style={{ color: MUTED, padding: 20 }}>No waterfall data available in HSBC reports</div>}
          </ChartPanel>
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
    <div>
      {/* Read-only badge */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        style={{
          background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', padding: '12px 18px',
          border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12,
          marginBottom: 16,
        }}
      >
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: GOLD }}>
          Read-Only Summary
        </span>
        <span style={{ fontSize: 11, color: MUTED }}>
          Pre-computed data room analysis — no live tape calculations
        </span>
      </motion.div>

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
    </div>
  )
}
