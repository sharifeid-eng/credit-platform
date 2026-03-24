import { useState } from 'react'
import ComplianceBadge from './ComplianceBadge'

export default function LimitCard({ name, current, threshold, compliant, unit, format,
                                     breaching_shops, breaches, conc_adjustment, breakdown, wal_days }) {
  const [expanded, setExpanded] = useState(false)
  const ratio = Math.min(current / threshold, 1.5)
  const barWidth = Math.min(ratio * 100, 100)

  const fmtValue = (v) => {
    if (format === 'pct') return `${(v * 100).toFixed(1)}%`
    if (format === 'days') return `${v} days`
    return String(v)
  }

  const fmtThreshold = (v) => {
    if (format === 'pct') return `${(v * 100).toFixed(0)}% of portfolio`
    if (format === 'days') return `< ${v} days`
    return String(v)
  }

  const fmtMoney = (v) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
    return v.toFixed(0)
  }

  const barColor = !compliant
    ? 'var(--accent-red)'
    : ratio > 0.8
    ? 'var(--gold)'
    : 'var(--accent-teal)'

  // Determine if there's drill-down data
  const drillItems = breaching_shops || breaches || []
  const hasDrillDown = !compliant && drillItems.length > 0

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${compliant ? 'var(--border)' : 'rgba(240, 96, 96, 0.3)'}`,
      borderRadius: 'var(--radius-md)',
      padding: '20px',
      cursor: hasDrillDown ? 'pointer' : 'default',
    }} onClick={() => hasDrillDown && setExpanded(e => !e)}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</div>
          {hasDrillDown && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)', transition: 'transform 0.2s',
              display: 'inline-block', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
          )}
        </div>
        <ComplianceBadge compliant={compliant} />
      </div>

      {/* Value */}
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 700,
        color: compliant ? 'var(--text-primary)' : 'var(--accent-red)', marginBottom: 4,
      }}>
        {fmtValue(current)}
      </div>

      {/* Threshold label */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>
        Limit: {fmtThreshold(threshold)}
      </div>

      {/* Progress bar */}
      <div style={{ height: 6, borderRadius: 3, background: 'var(--border)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${barWidth}%`, borderRadius: 3, background: barColor, transition: 'width 0.3s ease' }} />
      </div>

      {/* Bar legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Current: {fmtValue(current)}</span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Limit: {fmtValue(threshold)}</span>
      </div>

      {/* Drill-down section (expandable) */}
      {hasDrillDown && expanded && (
        <div style={{
          marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border)',
        }} onClick={e => e.stopPropagation()}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-red)', marginBottom: 8 }}>
            {drillItems.length} breaching item{drillItems.length !== 1 ? 's' : ''}
          </div>

          {/* Concentration adjustment */}
          {conc_adjustment != null && conc_adjustment > 0 && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
              Concentration adjustment: <span style={{ color: 'var(--accent-red)', fontFamily: 'var(--font-mono)' }}>
                -{fmtMoney(conc_adjustment)}
              </span>
            </div>
          )}

          {/* Breaching items table */}
          <div style={{ maxHeight: 200, overflowY: 'auto' }}>
            {drillItems.slice(0, 10).map((item, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                fontSize: 11, borderBottom: i < Math.min(drillItems.length, 10) - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <span style={{ color: 'var(--text-primary)' }}>
                  {item.shop_id || item.payer || item.name || `Item ${i + 1}`}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-red)' }}>
                  {item.pct != null ? `${(item.pct * 100).toFixed(1)}%` :
                   item.current != null ? fmtValue(item.current) :
                   item.amount != null ? fmtMoney(item.amount) :
                   item.excess != null ? fmtMoney(item.excess) : ''}
                </span>
              </div>
            ))}
            {drillItems.length > 10 && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 6 }}>
                ...and {drillItems.length - 10} more
              </div>
            )}
          </div>

          {/* Breakdown if available */}
          {breakdown && breakdown.length > 0 && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
              {breakdown.map((item, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 10,
                  fontWeight: item.bold ? 700 : 400,
                  color: item.bold ? 'var(--text-primary)' : 'var(--text-muted)',
                }}>
                  <span>{item.label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>
                    {typeof item.value === 'number' ? (item.value < 1 && item.value > 0 ? `${(item.value * 100).toFixed(1)}%` : fmtMoney(item.value)) : String(item.value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
