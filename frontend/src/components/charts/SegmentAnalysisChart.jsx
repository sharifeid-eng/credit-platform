import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import { getSegmentAnalysis } from '../../services/api'
import { fmtMoney, fmtPct, COLORS } from '../../styles/chartTheme'

const DIMENSIONS = [
  { key: 'product',        label: 'Product' },
  { key: 'provider_size',  label: 'Provider Size' },
  { key: 'deal_size',      label: 'Deal Size' },
  { key: 'new_repeat',     label: 'New vs Repeat' },
  { key: 'group',          label: 'Group' },
  { key: 'provider',       label: 'Provider' },
]

export default function SegmentAnalysisChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [dimension, setDim]     = useState('product')
  const [sortCol, setSortCol]   = useState('originated')
  const [sortAsc, setSortAsc]   = useState(false)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getSegmentAnalysis(company, product, snapshot, currency, asOfDate, dimension)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load segment analysis data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate, dimension])

  const segments = data?.segments ?? data?.data ?? []

  const sorted = [...segments].sort((a, b) => {
    const av = a[sortCol] ?? 0
    const bv = b[sortCol] ?? 0
    return sortAsc ? av - bv : bv - av
  })

  const handleSort = (col) => {
    if (sortCol === col) setSortAsc(!sortAsc)
    else { setSortCol(col); setSortAsc(false) }
  }

  const columns = [
    { key: 'segment',        label: 'Segment',       align: 'left',  fmt: v => v },
    { key: 'count',          label: 'Count',          align: 'right', fmt: v => v?.toLocaleString() ?? '—' },
    { key: 'active',         label: 'Active',         align: 'right', fmt: v => v?.toLocaleString() ?? '—' },
    { key: 'originated',     label: 'Originated',     align: 'right', fmt: v => fmtMoney(v, currency) },
    { key: 'outstanding',    label: 'Outstanding',    align: 'right', fmt: v => fmtMoney(v, currency) },
    { key: 'collection_pct', label: 'Collection %',   align: 'right', fmt: null },
    { key: 'denial_pct',     label: 'Denial %',       align: 'right', fmt: null },
  ]

  // Color scale for collection rate: green (high) to red (low)
  const collColor = (v) => {
    if (v == null) return 'var(--text-muted)'
    if (v >= 90) return COLORS.teal
    if (v >= 70) return COLORS.gold
    return COLORS.red
  }
  // Color scale for denial rate: green (low) to red (high)
  const denialColor = (v) => {
    if (v == null) return 'var(--text-muted)'
    if (v <= 5) return COLORS.teal
    if (v <= 15) return COLORS.gold
    return COLORS.red
  }

  // Only show dimensions the backend reports as available on this tape vintage
  // (e.g. 'provider' is Apr 2026+; older tapes hide it).
  const availableDims = data?.available_dimensions ?? null
  const visibleDims = availableDims
    ? DIMENSIONS.filter(d => availableDims.includes(d.key))
    : DIMENSIONS

  const dimSelector = (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {visibleDims.map(d => (
        <button
          key={d.key}
          onClick={() => setDim(d.key)}
          style={{
            padding: '4px 10px', borderRadius: 'var(--radius-sm)',
            fontSize: 10, fontWeight: 500, cursor: 'pointer',
            border: dimension === d.key ? '1px solid var(--gold)' : '1px solid var(--border)',
            background: dimension === d.key ? 'rgba(201,168,76,0.1)' : 'transparent',
            color: dimension === d.key ? 'var(--gold)' : 'var(--text-muted)',
            transition: 'all 0.15s ease',
          }}
        >
          {d.label}
        </button>
      ))}
    </div>
  )

  return (
    <ChartPanel
      title="Segment Analysis"
      subtitle={`Performance breakdown by ${DIMENSIONS.find(d => d.key === dimension)?.label?.toLowerCase() ?? dimension}`}
      action={dimSelector}
      loading={loading}
      error={error}
      minHeight={0}
    >
      <div style={{ overflowX: 'auto', scrollbarWidth: 'none' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 750 }}>
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => col.key !== 'segment' && handleSort(col.key)}
                  style={{
                    textAlign: col.align,
                    padding: '8px 8px', fontSize: 9, fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    color: sortCol === col.key ? 'var(--gold)' : 'var(--text-muted)',
                    borderBottom: '2px solid var(--border)', whiteSpace: 'nowrap',
                    cursor: col.key !== 'segment' ? 'pointer' : 'default',
                    userSelect: 'none',
                  }}
                >
                  {col.label}
                  {sortCol === col.key && (
                    <span style={{ marginLeft: 3, fontSize: 8 }}>{sortAsc ? '\u25B2' : '\u25BC'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const coll = row.collection_pct ?? row.collection_rate
              const denial = row.denial_pct ?? row.denial_rate
              return (
                <tr key={i} style={{ borderBottom: '1px solid rgba(30,39,54,0.5)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '7px 8px', color: 'var(--text-primary)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {row.segment ?? row.name ?? row.label}
                  </td>
                  <td style={cellR}>{row.count?.toLocaleString() ?? row.total_deals?.toLocaleString() ?? '—'}</td>
                  <td style={cellR}>{row.active?.toLocaleString() ?? row.active_deals?.toLocaleString() ?? '—'}</td>
                  <td style={{ ...cellR, color: 'var(--gold)' }}>{fmtMoney(row.originated ?? row.purchase_value, currency)}</td>
                  <td style={cellR}>{fmtMoney(row.outstanding, currency)}</td>

                  {/* Collection % with progress bar */}
                  <td style={{ padding: '7px 8px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                      <div style={{ width: 60, height: 5, borderRadius: 3, background: 'var(--border)', overflow: 'hidden', flexShrink: 0 }}>
                        <div style={{
                          height: '100%', borderRadius: 3,
                          width: `${Math.min(coll ?? 0, 100)}%`,
                          background: collColor(coll),
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                        color: collColor(coll), minWidth: 38, textAlign: 'right',
                      }}>
                        {coll != null ? `${coll.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                  </td>

                  {/* Denial % with progress bar */}
                  <td style={{ padding: '7px 8px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
                      <div style={{ width: 60, height: 5, borderRadius: 3, background: 'var(--border)', overflow: 'hidden', flexShrink: 0 }}>
                        <div style={{
                          height: '100%', borderRadius: 3,
                          width: `${Math.min(denial ?? 0, 100)}%`,
                          background: denialColor(denial),
                          transition: 'width 0.3s ease',
                        }} />
                      </div>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                        color: denialColor(denial), minWidth: 38, textAlign: 'right',
                      }}>
                        {denial != null ? `${denial.toFixed(1)}%` : '—'}
                      </span>
                    </div>
                  </td>
                </tr>
              )
            })}

            {sorted.length === 0 && !loading && (
              <tr><td colSpan={columns.length} style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)' }}>No segment data available.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </ChartPanel>
  )
}

const cellR = {
  padding: '7px 8px',
  textAlign: 'right',
  fontFamily: 'var(--font-mono)',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap',
}
