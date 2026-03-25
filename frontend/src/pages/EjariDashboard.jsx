import { useState, useEffect } from 'react'
import { useCompany } from '../contexts/CompanyContext'
import { getEjariSummary } from '../services/api'

const fmt = (v) => v == null ? '—' : typeof v === 'number' ? (v >= 1_000_000 ? `$${(v/1_000_000).toFixed(1)}M` : v >= 1_000 ? `$${(v/1_000).toFixed(0)}K` : v < 1 && v > 0 ? `${(v*100).toFixed(1)}%` : v.toLocaleString()) : String(v)
const fmtPct = (v) => v == null ? '—' : `${(v * 100).toFixed(1)}%`
const fmtDollar = (v) => v == null ? '—' : v >= 1_000_000 ? `$${(v/1_000_000).toFixed(1)}M` : v >= 1_000 ? `$${(v/1_000).toFixed(0)}K` : `$${v.toFixed(0)}`

export default function EjariDashboard() {
  const { company, product, snapshot } = useCompany()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState('overview')

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getEjariSummary(company, product, snapshot)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [company, product, snapshot])

  const SECTIONS = [
    { id: 'overview', label: 'Portfolio Overview' },
    { id: 'cohort', label: 'Monthly Cohorts' },
    { id: 'loss-waterfall', label: 'Loss Waterfall' },
    { id: 'roll-rates', label: 'Roll Rates' },
    { id: 'historical', label: 'Historical Performance' },
    { id: 'collections-month', label: 'Collections (by Month)' },
    { id: 'collections-orig', label: 'Collections (by Origination)' },
    { id: 'segments', label: 'Segment Analysis' },
    { id: 'credit-quality', label: 'Credit Quality Trends' },
    { id: 'najiz', label: 'Najiz & Legal' },
    { id: 'writeoffs', label: 'Write-offs & Fraud' },
    { id: 'notes', label: 'Data Notes' },
  ]

  if (loading) return (
    <div style={{ padding: 40, color: 'var(--text-muted)', textAlign: 'center' }}>
      Loading Ejari summary data...
    </div>
  )

  if (!data) return (
    <div style={{ padding: 40, color: 'var(--red)', textAlign: 'center' }}>
      Failed to load Ejari data.
    </div>
  )

  const ov = data.portfolio_overview || {}
  const km = ov.key_metrics || {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header badge */}
      <div style={{
        background: 'var(--bg-surface)', borderRadius: 10, padding: '12px 18px',
        border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--gold)' }}>
          Read-Only Summary
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Pre-computed portfolio analysis — no live tape calculations
        </span>
        {ov.report_date && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Report date: {ov.report_date}
          </span>
        )}
      </div>

      {/* Section navigation pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {SECTIONS.map(s => (
          <button key={s.id} onClick={() => {
            setActiveSection(s.id)
            document.getElementById(`ejari-${s.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }} style={{
            fontSize: 11, padding: '4px 12px', borderRadius: 14,
            border: `1px solid ${activeSection === s.id ? 'var(--gold)' : 'var(--border)'}`,
            background: activeSection === s.id ? 'rgba(201,168,76,0.1)' : 'transparent',
            color: activeSection === s.id ? 'var(--gold)' : 'var(--text-muted)',
            cursor: 'pointer', fontWeight: activeSection === s.id ? 600 : 400,
            transition: 'all 0.15s',
          }}>
            {s.label}
          </button>
        ))}
      </div>

      {/* ── Portfolio Overview ── */}
      <Panel id="ejari-overview" title="Portfolio Overview" subtitle={`Report date: ${ov.report_date || '—'}`}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
          <Kpi label="Total Contracts" value={km.total_contracts} color="gold" />
          <Kpi label="Active Loans" value={km.active_loans} color="teal" />
          <Kpi label="Matured / Closed" value={km.matured_loans} color="blue" />
          <Kpi label="Total Originated" value={fmtDollar(km.total_originated)} color="gold" />
          <Kpi label="Total Funded" value={fmtDollar(km.total_funded)} color="blue" />
          <Kpi label="Outstanding Principal" value={fmtDollar(km.outstanding_principal)} color="red" />
          <Kpi label="Outstanding Fee" value={fmtDollar(km.outstanding_fee)} color="gold" />
          <Kpi label="Total Collections" value={fmtDollar(km.total_collections)} color="teal" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
          <Kpi label="PAR 30+" value={fmtPct(km.par30)} color={km.par30 > 0.05 ? 'red' : 'teal'} />
          <Kpi label="PAR 60+" value={fmtPct(km.par60)} color={km.par60 > 0.04 ? 'red' : 'teal'} />
          <Kpi label="PAR 90+" value={fmtPct(km.par90)} color={km.par90 > 0.03 ? 'red' : 'teal'} />
          <Kpi label="PAR 180+" value={fmtPct(km.par180)} color={km.par180 > 0.02 ? 'red' : 'teal'} />
        </div>
        {ov.dpd_distribution?.length > 0 && (
          <DataTable
            title="DPD Distribution (Active Loans)"
            columns={[
              { key: 'bucket', label: 'DPD Bucket' },
              { key: 'loans', label: '# Loans', align: 'right' },
              { key: 'outstanding', label: 'O/S Principal', align: 'right', fmt: fmtDollar },
              { key: 'pct_loans', label: '% of Loans', align: 'right', fmt: fmtPct },
              { key: 'pct_outstanding', label: '% of O/S', align: 'right', fmt: fmtPct },
            ]}
            rows={ov.dpd_distribution}
          />
        )}
      </Panel>

      {/* ── Monthly Cohorts ── */}
      <Panel id="ejari-cohort" title="Monthly Cohort Performance" subtitle="Cohorts by rent start date — write-offs excluded">
        <DataTable
          columns={[
            { key: 'cohort', label: 'Cohort' },
            { key: 'vintage', label: 'Vintage' },
            { key: 'loans', label: '# Loans', align: 'right' },
            { key: 'active', label: 'Active', align: 'right' },
            { key: 'originated', label: 'Originated', align: 'right', fmt: fmtDollar },
            { key: 'collections', label: 'Collections', align: 'right', fmt: fmtDollar },
            { key: 'coll_pct', label: 'Coll %', align: 'right', fmt: fmtPct },
            { key: 'par30', label: 'PAR30+', align: 'right', fmt: fmtPct },
            { key: 'par90', label: 'PAR90+', align: 'right', fmt: fmtPct },
          ]}
          rows={data.monthly_cohort || []}
          highlightLast
        />
      </Panel>

      {/* ── Loss Waterfall ── */}
      <Panel id="ejari-loss-waterfall" title="Cohort Loss Waterfall" subtitle="Origination -> 90DPD Default -> Recovery -> Net Loss | Fraud isolated">
        <DataTable
          columns={[
            { key: 'cohort', label: 'Cohort' },
            { key: 'disbursed', label: 'Disbursed', align: 'right', fmt: fmtDollar },
            { key: 'gross_default', label: 'Gross Default', align: 'right', fmt: fmtDollar, color: 'red' },
            { key: 'default_rate', label: 'Default %', align: 'right', fmt: fmtPct },
            { key: 'fraud_amount', label: 'Fraud', align: 'right', fmt: fmtDollar, color: 'gold' },
            { key: 'recovery', label: 'Recovery', align: 'right', fmt: fmtDollar, color: 'teal' },
            { key: 'net_loss', label: 'Net Loss', align: 'right', fmt: fmtDollar, color: 'red' },
            { key: 'net_loss_rate', label: 'Net Loss %', align: 'right', fmt: fmtPct },
            { key: 'recovery_rate_ex_fraud', label: 'Recovery % (ex-Fraud)', align: 'right', fmt: fmtPct },
          ]}
          rows={data.cohort_loss_waterfall || []}
          highlightLast
        />
      </Panel>

      {/* ── Roll Rates ── */}
      <Panel id="ejari-roll-rates" title="Roll Rate Analysis" subtitle="Clean active loans — payment activity and cure/roll signals by DPD bucket">
        <DataTable
          columns={[
            { key: 'bucket', label: 'DPD Bucket' },
            { key: 'loans', label: '# Loans', align: 'right' },
            { key: 'outstanding', label: 'O/S', align: 'right', fmt: fmtDollar },
            { key: 'pct_outstanding', label: '% of O/S', align: 'right', fmt: fmtPct },
            { key: 'avg_dpd', label: 'Avg DPD', align: 'right' },
            { key: 'avg_days_since_pay', label: 'Days Since Pay', align: 'right' },
            { key: 'pct_paying_30d', label: '% Pay<30d', align: 'right', fmt: fmtPct },
            { key: 'pct_paying_60d', label: '% Pay<60d', align: 'right', fmt: fmtPct },
            { key: 'implied_cure_rate', label: 'Cure Rate', align: 'right', fmt: fmtPct, color: 'teal' },
            { key: 'implied_roll_rate', label: 'Roll Rate', align: 'right', fmt: fmtPct, color: 'red' },
          ]}
          rows={data.roll_rates || []}
        />
      </Panel>

      {/* ── Historical Performance ── */}
      <Panel id="ejari-historical" title="Historical Vintage Performance" subtitle="90DPD data — cumulative default & recovery curves | Fraud isolated">
        <DataTable
          columns={[
            { key: 'vintage', label: 'Vintage' },
            { key: 'period', label: 'Period' },
            { key: 'disbursed', label: 'Disbursed', align: 'right', fmt: fmtDollar },
            { key: 'default_90dpd', label: '90DPD O/S', align: 'right', fmt: fmtDollar, color: 'red' },
            { key: 'fraud', label: 'Fraud', align: 'right', fmt: fmtDollar, color: 'gold' },
            { key: 'non_fraud_default', label: 'Non-Fraud', align: 'right', fmt: fmtDollar },
            { key: 'recovery', label: 'Recovery', align: 'right', fmt: fmtDollar, color: 'teal' },
            { key: 'recovery_rate_ex_fraud', label: 'Rec Rate (ex-Fraud)', align: 'right', fmt: fmtPct },
            { key: 'gross_default_pct', label: 'Gross Def %', align: 'right', fmt: fmtPct },
            { key: 'lgd', label: 'LGD', align: 'right', fmt: fmtPct },
          ]}
          rows={data.historical_performance || []}
        />
      </Panel>

      {/* ── Collections by Month ── */}
      <Panel id="ejari-collections-month" title="Collections Waterfall by Payment Month" subtitle="Timing distribution of collections">
        <DataTable
          columns={[
            { key: 'month', label: 'Month' },
            { key: 'total_due', label: 'Total Due', align: 'right', fmt: fmtDollar },
            { key: 'total_paid', label: 'Total Paid', align: 'right', fmt: fmtDollar },
            { key: 'coll_pct', label: 'Coll %', align: 'right', fmt: fmtPct },
            { key: 'early', label: 'Early', align: 'right', fmt: fmtDollar },
            { key: '0_15d', label: '0-15d', align: 'right', fmt: fmtDollar },
            { key: '15_30d', label: '15-30d', align: 'right', fmt: fmtDollar },
            { key: '30_45d', label: '30-45d', align: 'right', fmt: fmtDollar },
            { key: '60_90d', label: '60-90d', align: 'right', fmt: fmtDollar },
            { key: '180_plus', label: '180+d', align: 'right', fmt: fmtDollar },
          ]}
          rows={data.collections_by_month || []}
        />
      </Panel>

      {/* ── Collections by Origination ── */}
      <Panel id="ejari-collections-orig" title="Collections Waterfall by Origination" subtitle="Timing distribution by vintage">
        <DataTable
          columns={[
            { key: 'month', label: 'Month' },
            { key: 'total_due', label: 'Total Due', align: 'right', fmt: fmtDollar },
            { key: 'total_paid', label: 'Total Paid', align: 'right', fmt: fmtDollar },
            { key: 'coll_pct', label: 'Coll %', align: 'right', fmt: fmtPct },
            { key: 'early', label: 'Early', align: 'right', fmt: fmtDollar },
            { key: '0_15d', label: '0-15d', align: 'right', fmt: fmtDollar },
            { key: '15_30d', label: '15-30d', align: 'right', fmt: fmtDollar },
            { key: '60_90d', label: '60-90d', align: 'right', fmt: fmtDollar },
            { key: 'fraud', label: 'Fraud?', align: 'center' },
          ]}
          rows={data.collections_by_origination || []}
        />
      </Panel>

      {/* ── Segment Analysis ── */}
      <Panel id="ejari-segments" title="Segment Analysis" subtitle="Performance breakdown by multiple dimensions — write-offs excluded">
        {data.segment_analysis && Object.entries(data.segment_analysis).map(([key, segments]) => (
          <div key={key} style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--gold)', marginBottom: 8, textTransform: 'capitalize' }}>
              {key.replace(/_/g, ' ')}
            </div>
            <DataTable
              columns={[
                { key: 'segment', label: 'Segment' },
                { key: 'loans', label: '# Loans', align: 'right' },
                { key: 'active', label: 'Active', align: 'right' },
                { key: 'originated', label: 'Originated', align: 'right', fmt: fmtDollar },
                { key: 'outstanding', label: 'Outstanding', align: 'right', fmt: fmtDollar },
                { key: 'coll_pct', label: 'Coll %', align: 'right', fmt: fmtPct },
                { key: 'par30', label: 'PAR30+', align: 'right', fmt: fmtPct },
                { key: 'par90', label: 'PAR90+', align: 'right', fmt: fmtPct },
                { key: 'avg_simah', label: 'Avg SIMAH', align: 'right' },
                { key: 'avg_salary', label: 'Avg Salary', align: 'right', fmt: fmtDollar },
              ]}
              rows={segments}
            />
          </div>
        ))}
      </Panel>

      {/* ── Credit Quality Trends ── */}
      <Panel id="ejari-credit-quality" title="Credit Quality Trends" subtitle="Underwriting metrics by monthly cohort — write-offs excluded">
        <DataTable
          columns={[
            { key: 'cohort', label: 'Cohort' },
            { key: 'loans', label: '# Loans', align: 'right' },
            { key: 'avg_simah', label: 'Avg SIMAH', align: 'right' },
            { key: 'avg_salary', label: 'Avg Salary', align: 'right', fmt: fmtDollar },
            { key: 'avg_ticket', label: 'Avg Ticket', align: 'right', fmt: fmtDollar },
            { key: 'avg_dbr', label: 'Avg DBR', align: 'right', fmt: fmtPct },
            { key: 'pct_govt', label: '% Govt', align: 'right', fmt: fmtPct },
            { key: 'pct_female', label: '% Female', align: 'right', fmt: fmtPct },
            { key: 'pct_married', label: '% Married', align: 'right', fmt: fmtPct },
            { key: 'avg_term', label: 'Avg Term', align: 'right' },
          ]}
          rows={data.credit_quality_trends || []}
        />
      </Panel>

      {/* ── Najiz & Legal ── */}
      <Panel id="ejari-najiz" title="Najiz & Legal Collections" subtitle="Court execution data by vintage">
        <DataTable
          columns={[
            { key: 'vintage', label: 'Vintage' },
            { key: 'cases', label: '# Cases', align: 'right' },
            { key: 'executions', label: '# Exec', align: 'right' },
            { key: 'exec_rate', label: 'Exec Rate', align: 'right', fmt: fmtPct },
            { key: 'exec_value', label: 'Exec Value', align: 'right', fmt: fmtDollar },
            { key: 'recovery', label: 'Recovery', align: 'right', fmt: fmtDollar, color: 'teal' },
            { key: 'rec_exec_rate', label: 'Rec/Exec', align: 'right', fmt: fmtPct },
            { key: 'avg_rec_case', label: 'Avg Rec/Case', align: 'right', fmt: fmtDollar },
            { key: 'fraud_writeoff', label: 'Fraud WO', align: 'right', fmt: fmtDollar, color: 'red' },
          ]}
          rows={data.najiz_legal || []}
          highlightLast
        />
      </Panel>

      {/* ── Write-offs & Fraud ── */}
      <Panel id="ejari-writeoffs" title="Write-offs & Fraud Analysis" subtitle="32 WO loans — FULLY EXCLUDED from all other sheets">
        {data.writeoffs_fraud?.by_reason?.length > 0 && (
          <DataTable
            title="By Reason Code"
            columns={[
              { key: 'reason', label: 'Reason' },
              { key: 'loans', label: '# Loans', align: 'right' },
              { key: 'orig_principal', label: 'Orig Principal', align: 'right', fmt: fmtDollar },
              { key: 'os_principal', label: 'O/S Principal', align: 'right', fmt: fmtDollar },
              { key: 'total_os', label: 'Total O/S', align: 'right', fmt: fmtDollar },
              { key: 'pct_wo', label: '% of WO', align: 'right', fmt: fmtPct },
              { key: 'type', label: 'Type', align: 'center' },
            ]}
            rows={data.writeoffs_fraud.by_reason}
          />
        )}
      </Panel>

      {/* ── Data Notes ── */}
      <Panel id="ejari-notes" title="Data Notes & Methodology" subtitle="Full audit trail of corrections and methodology">
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.8 }}>
          {(data.data_notes || []).map((note, i) => (
            <div key={i} style={{
              padding: '4px 0',
              borderBottom: i < (data.data_notes?.length || 0) - 1 ? '1px solid var(--border)' : 'none',
              fontFamily: note.startsWith('1.') || note.startsWith('2.') || note.startsWith('3.') ? 'var(--font-mono)' : 'inherit',
              fontWeight: note === note.toUpperCase() && note.length > 5 ? 600 : 400,
              color: note === note.toUpperCase() && note.length > 5 ? 'var(--text-primary)' : 'var(--text-muted)',
            }}>
              {note}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

/* ── Reusable Components ── */

function Panel({ id, title, subtitle, children }) {
  return (
    <div id={id} style={{
      background: 'var(--bg-surface)', borderRadius: 12, padding: '20px 24px',
      border: '1px solid var(--border)', scrollMarginTop: 80,
    }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{title}</div>
        {subtitle && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{subtitle}</div>}
      </div>
      {children}
    </div>
  )
}

function Kpi({ label, value, color = 'gold' }) {
  const colorMap = { gold: 'var(--gold)', teal: 'var(--teal)', red: 'var(--red)', blue: 'var(--blue)' }
  return (
    <div style={{
      background: 'var(--bg-deep)', borderRadius: 8, padding: '12px 14px',
      borderLeft: `3px solid ${colorMap[color] || colorMap.gold}`,
    }}>
      <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: colorMap[color], marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  )
}

function DataTable({ title, columns, rows, highlightLast = false }) {
  if (!rows || rows.length === 0) return null
  return (
    <div style={{ marginBottom: title ? 16 : 0 }}>
      {title && <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>{title}</div>}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} style={{
                  textAlign: col.align || 'left', padding: '8px 10px',
                  borderBottom: '1px solid var(--border)', color: 'var(--text-muted)',
                  fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em',
                  whiteSpace: 'nowrap',
                }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const isLast = highlightLast && i === rows.length - 1
              return (
                <tr key={i} style={{
                  background: isLast ? 'rgba(201,168,76,0.05)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}>
                  {columns.map(col => {
                    const raw = row[col.key]
                    const display = col.fmt && raw != null ? col.fmt(raw) : (raw == null ? '—' : typeof raw === 'number' ? raw.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(raw))
                    const cellColor = col.color ? `var(--${col.color})` : (isLast ? 'var(--gold)' : 'var(--text-primary)')
                    return (
                      <td key={col.key} style={{
                        textAlign: col.align || 'left', padding: '7px 10px',
                        borderBottom: '1px solid var(--border)', color: cellColor,
                        fontFamily: col.align === 'right' ? 'var(--font-mono)' : 'inherit',
                        fontWeight: isLast ? 600 : 400, whiteSpace: 'nowrap',
                      }}>
                        {display}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
