import { useState, useEffect } from 'react'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { fmtMoney, fmtPct } from '../../../styles/chartTheme'

export default function SilqCohortTable({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/cohort`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(res => {
        setData(res.data)
        setError(null)
      })
      .catch(() => setError('Failed to load SILQ cohort data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const cohorts = data?.cohorts ?? []
  const dataRows = cohorts.filter(r => r.vintage !== 'Total')
  const totalsRow = cohorts.find(r => r.vintage === 'Total') ?? null
  const cur = data?.currency ?? currency

  const columns = [
    { key: 'vintage',        label: 'Vintage',       align: 'left' },
    { key: 'deals',          label: 'Deals',         type: 'int' },
    { key: 'disbursed',      label: 'Disbursed',     type: 'money' },
    { key: 'repaid',         label: 'Repaid',        type: 'money' },
    { key: 'outstanding',    label: 'Outstanding',   type: 'money' },
    { key: 'overdue',        label: 'Overdue',       type: 'money' },
    { key: 'collection_pct', label: 'Collection %',  type: 'heat_good_high' },
    { key: 'overdue_pct',    label: 'Overdue %',     type: 'heat_bad_high' },
    { key: 'par30_pct',      label: 'PAR30 %',       type: 'heat_bad_high' },
    { key: 'avg_tenure',     label: 'Avg Tenure',    type: 'tenure' },
  ]

  function heatColor(val, badHigh) {
    if (val == null) return 'var(--text-faint)'
    if (badHigh) {
      if (val <= 5)  return '#2DD4BF'
      if (val <= 15) return '#C9A84C'
      return '#F06060'
    }
    if (val >= 90) return '#2DD4BF'
    if (val >= 70) return '#C9A84C'
    return '#F06060'
  }

  function renderCell(row, col, isTotals) {
    const val = row[col.key]
    const base = {
      padding: '7px 8px',
      textAlign: col.align || 'right',
      fontFamily: col.align === 'left' ? 'inherit' : 'var(--font-mono)',
      fontWeight: isTotals ? 700 : 400,
      whiteSpace: 'nowrap',
    }

    if (col.key === 'vintage') {
      return (
        <td key={col.key} style={{ ...base, color: isTotals ? '#C9A84C' : 'var(--text-primary)', fontWeight: isTotals ? 700 : 600 }}>
          {isTotals ? 'TOTAL' : val}
        </td>
      )
    }

    if (col.type === 'int') {
      return <td key={col.key} style={{ ...base, color: 'var(--text-secondary)' }}>{val != null ? val.toLocaleString() : '\u2013'}</td>
    }

    if (col.type === 'money') {
      const moneyColors = { disbursed: '#C9A84C', repaid: '#2DD4BF', outstanding: '#5B8DEF', overdue: '#F06060' }
      return <td key={col.key} style={{ ...base, color: moneyColors[col.key] || 'var(--text-secondary)' }}>{fmtMoney(val, cur)}</td>
    }

    if (col.type === 'heat_good_high') {
      return (
        <td key={col.key} style={{ ...base, fontWeight: 600, color: heatColor(val, false) }}>
          {val != null ? `${val.toFixed(1)}%` : '\u2013'}
        </td>
      )
    }

    if (col.type === 'heat_bad_high') {
      return (
        <td key={col.key} style={{ ...base, fontWeight: 600, color: heatColor(val, true) }}>
          {val != null ? `${val.toFixed(1)}%` : '\u2013'}
        </td>
      )
    }

    if (col.type === 'tenure') {
      return <td key={col.key} style={{ ...base, color: 'var(--text-secondary)' }}>{val != null ? `${val.toFixed(1)}w` : '\u2013'}</td>
    }

    return <td key={col.key} style={{ ...base, color: 'var(--text-secondary)' }}>{val ?? '\u2013'}</td>
  }

  return (
    <ChartPanel
      title="SILQ Cohort Analysis"
      subtitle="Vintage performance \u2014 disbursement, repayment, overdue exposure, and tenure by origination month"
      loading={loading}
      error={error}
      minHeight={0}
    >
      <div style={{ overflowX: 'auto', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 900 }}>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} style={{
                  textAlign: col.align || 'right',
                  padding: '8px 8px',
                  fontSize: 9,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-muted)',
                  borderBottom: '2px solid var(--border)',
                  whiteSpace: 'nowrap',
                  background: 'var(--bg-surface)',
                }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, i) => (
              <tr
                key={i}
                style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                {columns.map(col => renderCell(row, col, false))}
              </tr>
            ))}

            {totalsRow && (
              <tr style={{ borderTop: '2px solid var(--border)', background: 'rgba(201,168,76,0.04)' }}>
                {columns.map(col => renderCell(totalsRow, col, true))}
              </tr>
            )}

            {cohorts.length === 0 && !loading && (
              <tr>
                <td colSpan={columns.length} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No cohort data available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </ChartPanel>
  )
}
