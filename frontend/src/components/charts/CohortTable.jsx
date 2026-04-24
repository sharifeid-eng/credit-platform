import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import ConfidenceBadge from '../ConfidenceBadge'
import { getCohortChart } from '../../services/api'
import { fmtPct, fmtMoney } from '../../styles/chartTheme'

export default function CohortTable({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getCohortChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const raw = res.cohorts ?? res.data ?? res
        setData(raw)
        setError(null)
      })
      .catch(() => setError('Failed to load cohort data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const hasIrr = data.some(r => r.avg_expected_irr != null || r.avg_actual_irr != null)
  const hasSpeed = data.some(r => r.collected_90d_pct != null)

  // Summary row
  const totals = data.length ? {
    deals: data.reduce((s, r) => s + (r.total_deals ?? 0), 0),
    completed: data.reduce((s, r) => s + (r.completed_deals ?? 0), 0),
    pv: data.reduce((s, r) => s + (r.purchase_value ?? 0), 0),
    pp: data.reduce((s, r) => s + (r.purchase_price ?? 0), 0),
    collected: data.reduce((s, r) => s + (r.collected ?? 0), 0),
    denied: data.reduce((s, r) => s + (r.denied ?? 0), 0),
    pending: data.reduce((s, r) => s + (r.pending ?? 0), 0),
  } : null

  if (totals) {
    totals.collRate = totals.pv ? (totals.collected / totals.pv * 100) : 0
    totals.denialRate = totals.pv ? (totals.denied / totals.pv * 100) : 0
    totals.completionRate = totals.deals ? (totals.completed / totals.deals * 100) : 0
    totals.pendingRate = totals.pv ? (totals.pending / totals.pv * 100) : 0
    totals.expectedMargin = totals.pp ? ((totals.pv - totals.pp) / totals.pp * 100) : 0
    totals.realisedMargin = totals.pp ? ((totals.collected - totals.pp) / totals.pp * 100) : 0
    const irrVals = data.filter(r => r.avg_actual_irr != null)
    totals.avgActualIrr = irrVals.length ? irrVals.reduce((s, r) => s + r.avg_actual_irr, 0) / irrVals.length : null
    const eirrVals = data.filter(r => r.avg_expected_irr != null)
    totals.avgExpectedIrr = eirrVals.length ? eirrVals.reduce((s, r) => s + r.avg_expected_irr, 0) / eirrVals.length : null
    // Collection speed weighted averages
    const s90 = data.filter(r => r.collected_90d_pct != null)
    const s90w = s90.reduce((s, r) => s + (r.collected_90d_pct * (r.purchase_value ?? 0)), 0)
    const s90d = s90.reduce((s, r) => s + (r.purchase_value ?? 0), 0)
    totals.speed90 = s90d ? s90w / s90d : null
    const s180 = data.filter(r => r.collected_180d_pct != null)
    const s180w = s180.reduce((s, r) => s + (r.collected_180d_pct * (r.purchase_value ?? 0)), 0)
    const s180d = s180.reduce((s, r) => s + (r.purchase_value ?? 0), 0)
    totals.speed180 = s180d ? s180w / s180d : null
    const s360 = data.filter(r => r.collected_360d_pct != null)
    const s360w = s360.reduce((s, r) => s + (r.collected_360d_pct * (r.purchase_value ?? 0)), 0)
    const s360d = s360.reduce((s, r) => s + (r.purchase_value ?? 0), 0)
    totals.speed360 = s360d ? s360w / s360d : null
  }

  const columns = [
    'Vintage', 'Deals', 'Done', 'Deployed', 'Collected', 'Denied', 'Pending',
    'Coll %', 'Denial %', 'Pend %', 'Done %',
    ...(hasSpeed ? ['90d %', '180d %', '360d %'] : []),
    'Exp Margin', 'Act Margin', 'Δ Margin',
    ...(hasIrr ? ['Exp IRR', 'Act IRR', 'Spread'] : []),
  ]

  return (
    <ChartPanel
      title="Cohort Analysis"
      subtitle="Vintage performance — collection, denial, pending exposure, margins, and IRR tracking by origination month"
      loading={loading}
      error={error}
      minHeight={0}
      action={<ConfidenceBadge
        confidence="A"
        population="total_originated"
        note="Per-vintage rates computed over each cohort's originated PV (collection/denial) and completed count (completion rate). Margins use PP as denom. §17: population is per-row cohort; denominators are visible in the table."
      />}
    >
      <div style={{ overflowX: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: (hasIrr ? 1200 : 1000) + (hasSpeed ? 200 : 0) }}>
          <thead>
            <tr>
              {columns.map(h => (
                <th key={h} style={{
                  textAlign: h === 'Vintage' ? 'left' : 'right',
                  padding: '8px 8px',
                  fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em',
                  color: 'var(--text-muted)', borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => {
              const irrSpread = (row.avg_actual_irr != null && row.avg_expected_irr != null)
                ? row.avg_actual_irr - row.avg_expected_irr : null
              const marginSpread = (row.realised_margin != null && row.expected_margin != null)
                ? row.realised_margin - row.expected_margin : null
              const pendingRate = row.purchase_value ? (row.pending ?? 0) / row.purchase_value * 100 : 0

              return (
                <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <Cell left mono bold color="var(--text-primary)">{row.month}</Cell>
                  <Cell mono>{row.total_deals}</Cell>
                  <Cell mono>{row.completed_deals}</Cell>
                  <Cell mono color="var(--gold)">{fmtMoney(row.purchase_value, currency)}</Cell>
                  <Cell mono color="var(--teal)">{fmtMoney(row.collected, currency)}</Cell>
                  <Cell mono color="var(--red)">{fmtMoney(row.denied, currency)}</Cell>
                  <Cell mono color={pendingRate > 20 ? 'var(--blue)' : 'var(--text-secondary)'}>{fmtMoney(row.pending, currency)}</Cell>
                  <Cell><Heat v={row.collection_rate} good={v => v >= 90} goodC="var(--teal)" badC="var(--gold)" /></Cell>
                  <Cell><Heat v={row.denial_rate} good={v => v <= 10} goodC="var(--text-secondary)" badC="var(--red)" /></Cell>
                  <Cell><Heat v={pendingRate} good={v => v <= 20} goodC="var(--text-secondary)" badC="var(--blue)" /></Cell>
                  <Cell><Heat v={row.completion_rate} good={v => v >= 70} goodC="var(--teal)" badC="var(--red)" /></Cell>
                  {/* Collection speed — only shown when tape has speed data */}
                  {hasSpeed && <>
                    <Cell><SpeedHeat v={row.collected_90d_pct} /></Cell>
                    <Cell><SpeedHeat v={row.collected_180d_pct} /></Cell>
                    <Cell><SpeedHeat v={row.collected_360d_pct} /></Cell>
                  </>}
                  {/* Margins — always shown */}
                  <Cell mono color="var(--text-secondary)">{row.expected_margin != null ? `${row.expected_margin.toFixed(2)}%` : '–'}</Cell>
                  <Cell>
                    {row.realised_margin != null
                      ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: row.realised_margin >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                          {row.realised_margin.toFixed(2)}%
                        </span>
                      : <span style={{ color: 'var(--text-faint)' }}>–</span>
                    }
                  </Cell>
                  <Cell>
                    {marginSpread != null
                      ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: marginSpread >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                          {marginSpread >= 0 ? '+' : ''}{marginSpread.toFixed(2)}%
                        </span>
                      : <span style={{ color: 'var(--text-faint)' }}>–</span>
                    }
                  </Cell>
                  {/* IRR — only shown when tape has IRR data */}
                  {hasIrr && <>
                    <Cell mono color="var(--text-secondary)">{row.avg_expected_irr != null ? `${row.avg_expected_irr.toFixed(1)}%` : '–'}</Cell>
                    <Cell mono color="var(--teal)">{row.avg_actual_irr != null ? `${row.avg_actual_irr.toFixed(1)}%` : '–'}</Cell>
                    <Cell>
                      {irrSpread != null
                        ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: irrSpread >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                            {irrSpread >= 0 ? '+' : ''}{irrSpread.toFixed(1)}%
                          </span>
                        : <span style={{ color: 'var(--text-faint)' }}>–</span>
                      }
                    </Cell>
                  </>}
                </tr>
              )
            })}

            {/* Totals row */}
            {totals && (
              <tr style={{ borderTop: '2px solid var(--border)', background: 'rgba(201,168,76,0.04)' }}>
                <Cell left mono bold color="var(--gold)">TOTAL</Cell>
                <Cell mono bold>{totals.deals}</Cell>
                <Cell mono bold>{totals.completed}</Cell>
                <Cell mono bold color="var(--gold)">{fmtMoney(totals.pv, currency)}</Cell>
                <Cell mono bold color="var(--teal)">{fmtMoney(totals.collected, currency)}</Cell>
                <Cell mono bold color="var(--red)">{fmtMoney(totals.denied, currency)}</Cell>
                <Cell mono bold color="var(--blue)">{fmtMoney(totals.pending, currency)}</Cell>
                <Cell bold><Heat v={totals.collRate} good={v => v >= 90} goodC="var(--teal)" badC="var(--gold)" /></Cell>
                <Cell bold><Heat v={totals.denialRate} good={v => v <= 10} goodC="var(--text-secondary)" badC="var(--red)" /></Cell>
                <Cell bold><Heat v={totals.pendingRate} good={v => v <= 20} goodC="var(--text-secondary)" badC="var(--blue)" /></Cell>
                <Cell bold><Heat v={totals.completionRate} good={v => v >= 70} goodC="var(--teal)" badC="var(--red)" /></Cell>
                {/* Collection speed totals */}
                {hasSpeed && <>
                  <Cell bold><SpeedHeat v={totals.speed90} /></Cell>
                  <Cell bold><SpeedHeat v={totals.speed180} /></Cell>
                  <Cell bold><SpeedHeat v={totals.speed360} /></Cell>
                </>}
                {/* Margin totals */}
                <Cell mono bold color="var(--text-secondary)">{totals.expectedMargin.toFixed(2)}%</Cell>
                <Cell bold>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: totals.realisedMargin >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                    {totals.realisedMargin.toFixed(2)}%
                  </span>
                </Cell>
                <Cell bold>
                  {(() => {
                    const ms = totals.realisedMargin - totals.expectedMargin
                    return <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: ms >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                      {ms >= 0 ? '+' : ''}{ms.toFixed(2)}%
                    </span>
                  })()}
                </Cell>
                {/* IRR totals */}
                {hasIrr && <>
                  <Cell mono bold color="var(--text-secondary)">{totals.avgExpectedIrr != null ? `${totals.avgExpectedIrr.toFixed(1)}%` : '–'}</Cell>
                  <Cell mono bold color="var(--teal)">{totals.avgActualIrr != null ? `${totals.avgActualIrr.toFixed(1)}%` : '–'}</Cell>
                  <Cell bold>
                    {totals.avgActualIrr != null && totals.avgExpectedIrr != null
                      ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: (totals.avgActualIrr - totals.avgExpectedIrr) >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                          {(totals.avgActualIrr - totals.avgExpectedIrr) >= 0 ? '+' : ''}{(totals.avgActualIrr - totals.avgExpectedIrr).toFixed(1)}%
                        </span>
                      : <span style={{ color: 'var(--text-faint)' }}>–</span>
                    }
                  </Cell>
                </>}
              </tr>
            )}

            {data.length === 0 && !loading && (
              <tr><td colSpan={columns.length} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No cohort data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </ChartPanel>
  )
}

/* ── Helper components ── */

function Cell({ children, left, mono, bold, color }) {
  return (
    <td style={{
      padding: '7px 8px',
      textAlign: left ? 'left' : 'right',
      fontFamily: mono ? 'var(--font-mono)' : 'inherit',
      fontWeight: bold ? 700 : 400,
      color: color ?? 'var(--text-secondary)',
      whiteSpace: 'nowrap',
    }}>
      {children}
    </td>
  )
}

function Heat({ v, good, goodC, badC }) {
  if (v == null) return <span style={{ color: 'var(--text-faint)' }}>–</span>
  const isGood = good(v)
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      color: isGood ? goodC : badC,
    }}>
      {v.toFixed(1)}%
    </span>
  )
}

function SpeedHeat({ v }) {
  if (v == null) return <span style={{ color: 'var(--text-faint)' }}>–</span>
  const color = v >= 80 ? 'var(--teal)' : v >= 50 ? 'var(--gold)' : 'var(--red)'
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      color,
    }}>
      {v.toFixed(1)}%
    </span>
  )
}