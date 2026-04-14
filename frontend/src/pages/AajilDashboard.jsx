import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import useBreakpoint from '../hooks/useBreakpoint'
import { getAajilSummary } from '../services/api'
import KpiCard from '../components/KpiCard'
import ChartPanel from '../components/ChartPanel'
import {
  BarChart, Bar, PieChart, Pie, Cell, ComposedChart, Line,
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

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    const snap = snapshots?.[snapshots.length - 1]?.filename
    getAajilSummary(company, product, snap)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [company, product, snapshots])

  if (loading) return <div style={{ color: MUTED, padding: 40 }}>Loading Aajil dashboard...</div>
  if (!data) return <div style={{ color: RED, padding: 40 }}>Failed to load Aajil data</div>

  const activeTab = tab || 'overview'
  const co = data.company_overview || {}
  const ov = data.overview || {}
  const traction = data.traction || {}

  const fadeIn = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.25 } }

  return (
    <AnimatePresence mode="wait">
      <motion.div key={activeTab} {...fadeIn}>

        {/* ── OVERVIEW TAB ─────────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div>
            {/* Read-only badge */}
            <div style={{ display: 'inline-block', padding: '4px 10px', borderRadius: 6, background: 'rgba(201,168,76,0.15)', border: `1px solid ${GOLD}33`, color: GOLD, fontSize: 11, fontWeight: 600, marginBottom: 16 }}>
              INVESTOR DECK DATA — Tape from Cascade Debt pending
            </div>

            {/* KPI Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              <KpiCard label="AUM (Outstanding)" value={fmt(co.aum_sar, 'SAR ')} subtitle={fmt(co.aum_usd, '$')} index={0} />
              <KpiCard label="GMV Disbursed" value={fmt(co.gmv_sar, '>SAR ')} subtitle={fmt(co.gmv_usd, '>$')} index={1} />
              <KpiCard label="Transactions" value={co.total_transactions?.toLocaleString()} subtitle={`${co.avg_deals_per_customer}x per customer`} index={2} />
              <KpiCard label="Customers" value={co.total_customers?.toLocaleString()} subtitle={ov.customer_growth_pct ? `+${ov.customer_growth_pct}% growth` : ''} index={3} />
              <KpiCard label="DPD 60+" value={`<${(co.dpd60_plus_rate * 100).toFixed(0)}%`} subtitle="Last 12 months" index={4} />
            </div>

            {/* Second row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
              <KpiCard label="Avg Tenor" value={`${co.avg_tenor_months} months`} subtitle={`Max ${co.max_tenor_months} months`} index={5} />
              <KpiCard label="PN Coverage" value={`${(co.pn_coverage * 100).toFixed(0)}%`} subtitle="Promissory notes" index={6} />
              <KpiCard label="Credit/Revenue" value={co.credit_as_pct_revenue} subtitle="Per customer" index={7} />
              <KpiCard label="Deployment Speed" value={`<${co.credit_deployment_hours}h`} subtitle="KYB: instantaneous" index={8} />
              <KpiCard label="Employees" value={co.employees} subtitle="64+ staff" index={9} />
            </div>

            {/* GMV Growth */}
            <ChartPanel title="GMV Growth by Year" height={280}>
              <ResponsiveContainer>
                <ComposedChart data={data.gmv_milestones || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="year" stroke={MUTED} fontSize={12} />
                  <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v, 'SAR ')} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="gmv_sar" fill={GOLD} radius={[4, 4, 0, 0]} name="Cumulative GMV (SAR)" />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartPanel>

            {/* Customer Growth */}
            <ChartPanel title="Customer Growth" height={250} style={{ marginTop: 16 }}>
              <ResponsiveContainer>
                <ComposedChart data={data.customer_growth || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                  <XAxis dataKey="date" stroke={MUTED} fontSize={11} tickFormatter={d => d?.slice(0, 7)} />
                  <YAxis stroke={MUTED} fontSize={11} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="total_customers" fill={TEAL} radius={[4, 4, 0, 0]} name="Total Customers" />
                  <Line type="monotone" dataKey="total_customers" stroke={GOLD} dot={false} strokeWidth={2} name="Trend" />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartPanel>

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

        {/* ── TRACTION TAB (Cascade-inspired) ──────────────────────────── */}
        {activeTab === 'traction' && (
          <div>
            <div style={{ display: 'flex', gap: 16, flexDirection: isMobile ? 'column' : 'row' }}>
              <div style={{ flex: 1 }}>
                <ChartPanel title="Disbursement Volume (Annual)" height={300}>
                  <ResponsiveContainer>
                    <BarChart data={traction.volume || []}>
                      <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                      <XAxis dataKey="year" stroke={MUTED} fontSize={12} />
                      <YAxis stroke={MUTED} fontSize={11} tickFormatter={v => fmt(v, 'SAR ')} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="disbursed_sar" fill={GOLD} radius={[4, 4, 0, 0]} name="Disbursed (SAR)" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartPanel>
              </div>
              <GrowthStats stats={traction.growth_stats} label="Disbursements" />
            </div>

            {/* Balance */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 16 }}>
              <KpiCard label="Outstanding Balance (AUM)" value={fmt(traction.balance_sar, 'SAR ')} subtitle={fmt(traction.balance_sar * 0.2667, '$')} index={0} />
              <KpiCard label="GMV YoY Growth" value={ov.gmv_yoy_growth ? `+${ov.gmv_yoy_growth}%` : '--'} index={1} />
            </div>

            <div style={{ marginTop: 16, padding: '12px 16px', background: `${GOLD}10`, border: `1px solid ${GOLD}33`, borderRadius: 8, color: MUTED, fontSize: 12 }}>
              {traction.note || 'Monthly granularity available from Cascade Debt tape.'}
            </div>
          </div>
        )}

        {/* ── DELINQUENCY TAB ──────────────────────────────────────────── */}
        {activeTab === 'delinquency' && (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
              <KpiCard label="DPD 7+" value="--" subtitle="Tape data required" index={0} />
              <KpiCard label="DPD 30+" value="--" subtitle="Tape data required" index={1} />
              <KpiCard label="DPD 60+" value={`<${(co.dpd60_plus_rate * 100).toFixed(0)}%`} subtitle="Trailing 12M (Dec 2025)" index={2} />
              <KpiCard label="DPD 90+" value="--" subtitle="Tape data required" index={3} />
            </div>
            <ChartPanel title="Rolling Default Rate">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>DPD threshold toggles: 7 / 30 / 60 / 90 DPD</div>
                <div style={{ fontSize: 12 }}>Rolling default rate chart requires loan tape data from Cascade Debt.</div>
                <div style={{ fontSize: 12, marginTop: 8, color: GOLD }}>
                  Cascade shows: MoM -5.35%, QoQ -9.15%, YoY -13.56% at 7 DPD (improving trend)
                </div>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── COLLECTIONS TAB ──────────────────────────────────────────── */}
        {activeTab === 'collections' && (
          <div>
            <ChartPanel title="Cash Collected by Cohort">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>Monthly collection rate per vintage cohort</div>
                <div style={{ fontSize: 12 }}>Requires loan tape with disbursement and payment data.</div>
                <div style={{ fontSize: 12, marginTop: 8 }}>Will include: Payment Breakdown toggle (Total vs Principal)</div>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── COHORT ANALYSIS TAB ──────────────────────────────────────── */}
        {activeTab === 'cohort-analysis' && (
          <div>
            <ChartPanel title="Vintage Analysis">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>DPD% by Month on Books (MoB) per cohort</div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 12 }}>
                  {['30 DPD', '60 DPD', '90 DPD'].map(d => (
                    <span key={d} style={{ padding: '4px 12px', borderRadius: 12, background: `${GOLD}15`, border: `1px solid ${GOLD}33`, color: MUTED, fontSize: 11 }}>{d}</span>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 12 }}>
                  {['Original Balance', 'Number of Loans'].map(d => (
                    <span key={d} style={{ padding: '4px 12px', borderRadius: 12, background: `${BLUE}15`, border: `1px solid ${BLUE}33`, color: MUTED, fontSize: 11 }}>{d}</span>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 12 }}>
                  {['Loan', 'Borrower'].map(d => (
                    <span key={d} style={{ padding: '4px 12px', borderRadius: 12, background: `${TEAL}15`, border: `1px solid ${TEAL}33`, color: MUTED, fontSize: 11 }}>{d}</span>
                  ))}
                </div>
                <div style={{ fontSize: 12 }}>Vintage curves + color-coded heatmap table require loan tape data.</div>
                <div style={{ fontSize: 11, color: GOLD, marginTop: 8 }}>Cascade supports: With Cure / Without Cure toggle</div>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── CONCENTRATION TAB ────────────────────────────────────────── */}
        {activeTab === 'concentration' && (
          <div>
            <ChartPanel title="Customer Type Breakdown">
              <div style={{ display: 'flex', gap: 16, flexDirection: isMobile ? 'column' : 'row', padding: 16 }}>
                <div style={{ width: isMobile ? '100%' : 300, height: 250 }}>
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={[{ name: 'Manufacturer', value: 33 }, { name: 'Contractor', value: 34 }, { name: 'Wholesale Trader', value: 33 }]}
                        dataKey="value" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                        {[BLUE, GOLD, TEAL].map((c, i) => <Cell key={i} fill={c} />)}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ flex: 1, color: MUTED, fontSize: 12 }}>
                  <div style={{ marginBottom: 8, color: '#E8EAF0', fontWeight: 600 }}>Segmentation Dimensions (from Cascade)</div>
                  {['Customer Type', 'Loan Grade', 'Product Type', 'Term Group', 'VAT / Non-VAT Loan', 'Loan Status', 'Loan Counts'].map(d => (
                    <div key={d} style={{ padding: '4px 0', borderBottom: `1px solid ${BORDER}` }}>{d}</div>
                  ))}
                  <div style={{ marginTop: 12, color: GOLD, fontSize: 11 }}>Exact distribution requires tape data.</div>
                </div>
              </div>
            </ChartPanel>
          </div>
        )}

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
                <ResponsiveContainer>
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

        {/* ── YIELD & MARGINS TAB ──────────────────────────────────────── */}
        {activeTab === 'yield-margins' && (
          <div>
            <ChartPanel title="Yield & Margin Analysis">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>Revenue structure: Margin + Admin Fee (locked at origination)</div>
                <div style={{ fontSize: 12 }}>Yield and margin analysis requires loan tape with revenue columns.</div>
              </div>
            </ChartPanel>
          </div>
        )}

        {/* ── LOSS WATERFALL TAB ───────────────────────────────────────── */}
        {activeTab === 'loss-waterfall' && (
          <div>
            <ChartPanel title="Loss Waterfall by Vintage">
              <div style={{ padding: 40, textAlign: 'center', color: MUTED }}>
                <div style={{ fontSize: 14, marginBottom: 8 }}>Originated → Gross Default (DPD60+) → Recovery → Net Loss</div>
                <div style={{ fontSize: 12 }}>Per-vintage loss waterfall requires loan tape data.</div>
                <div style={{ fontSize: 12, marginTop: 8 }}>Recovery enhanced by 100% promissory note coverage.</div>
              </div>
            </ChartPanel>
          </div>
        )}

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
