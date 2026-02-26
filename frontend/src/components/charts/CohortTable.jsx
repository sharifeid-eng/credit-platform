import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
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

  // Summary row
  const totals = data.length ? {
    deals: data.reduce((s, r) => s + (r.total_deals ?? 0), 0),
    completed: data.reduce((s, r) => s + (r.completed_deals ?? 0), 0),
    pv: data.reduce((s, r) => s + (r.purchase_value ?? 0), 0),
    collected: data.reduce((s, r) => s + (r.collected ?? 0), 0),
    denied: data.reduce((s, r) => s + (r.denied ?? 0), 0),
    pending: data.reduce((s, r) => s + (r.pending ?? 0), 0),
  } : null

  if (totals) {
    totals.collRate = totals.pv ? (totals.collected / totals.pv * 100) : 0
    totals.denialRate = totals.pv ? (totals.denied / totals.pv * 100) : 0
    totals.completionRate = totals.deals ? (totals.completed / totals.deals * 100) : 0
    totals.pendingRate = totals.pv ? (totals.pending / totals.pv * 100) : 0
    const irrVals = data.filter(r => r.avg_actual_irr != null)
    totals.avgActualIrr = irrVals.length ? irrVals.reduce((s, r) => s + r.avg_actual_irr, 0) / irrVals.length : null
    const eirrVals = data.filter(r => r.avg_expected_irr != null)
    totals.avgExpectedIrr = eirrVals.length ? eirrVals.reduce((s, r) => s + r.avg_expected_irr, 0) / eirrVals.length : null
  }

  const columns = [
    'Vintage', 'Deals', 'Done', 'Deployed', 'Collected', 'Denied', 'Pending',
    'Coll %', 'Denial %', 'Pend %', 'Done %',
    'Exp IRR', 'Act IRR', 'Spread',
  ]

  return (
    <ChartPanel
      title="Cohort Analysis"
      subtitle="Vintage performance — collection, denial, pending exposure, and IRR tracking by origination month"
      loading={loading}
      error={error}
      minHeight={0}
    >
      <div style={{ overflowX: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 900 }}>
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
              const spread = (row.avg_actual_irr != null && row.avg_expected_irr != null)
                ? row.avg_actual_irr - row.avg_expected_irr : null
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
                  <Cell mono color="var(--text-secondary)">{row.avg_expected_irr != null ? `${row.avg_expected_irr.toFixed(1)}%` : '—'}</Cell>
                  <Cell mono color="var(--teal)">{row.avg_actual_irr != null ? `${row.avg_actual_irr.toFixed(1)}%` : '—'}</Cell>
                  <Cell>
                    {spread != null
                      ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: spread >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                          {spread >= 0 ? '+' : ''}{spread.toFixed(1)}%
                        </span>
                      : <span style={{ color: 'var(--text-faint)' }}>—</span>
                    }
                  </Cell>
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
                <Cell mono bold color="var(--text-secondary)">{totals.avgExpectedIrr != null ? `${totals.avgExpectedIrr.toFixed(1)}%` : '—'}</Cell>
                <Cell mono bold color="var(--teal)">{totals.avgActualIrr != null ? `${totals.avgActualIrr.toFixed(1)}%` : '—'}</Cell>
                <Cell bold>
                  {totals.avgActualIrr != null && totals.avgExpectedIrr != null
                    ? <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: (totals.avgActualIrr - totals.avgExpectedIrr) >= 0 ? 'var(--teal)' : 'var(--red)' }}>
                        {(totals.avgActualIrr - totals.avgExpectedIrr) >= 0 ? '+' : ''}{(totals.avgActualIrr - totals.avgExpectedIrr).toFixed(1)}%
                      </span>
                    : <span style={{ color: 'var(--text-faint)' }}>—</span>
                  }
                </Cell>
              </tr>
            )}

            {data.length === 0 && !loading && (
              <tr><td colSpan={14} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No cohort data.</td></tr>
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
  if (v == null) return <span style={{ color: 'var(--text-faint)' }}>—</span>
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