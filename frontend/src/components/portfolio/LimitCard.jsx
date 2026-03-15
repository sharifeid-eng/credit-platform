import ComplianceBadge from './ComplianceBadge'

export default function LimitCard({ name, current, threshold, compliant, unit, format }) {
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

  // Bar color based on how close to threshold
  const barColor = !compliant
    ? 'var(--accent-red)'
    : ratio > 0.8
    ? 'var(--gold)'
    : 'var(--accent-teal)'

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${compliant ? 'var(--border)' : 'rgba(240, 96, 96, 0.3)'}`,
      borderRadius: 'var(--radius-md)',
      padding: '20px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          {name}
        </div>
        <ComplianceBadge compliant={compliant} />
      </div>

      {/* Value */}
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 26,
        fontWeight: 700,
        color: compliant ? 'var(--text-primary)' : 'var(--accent-red)',
        marginBottom: 4,
      }}>
        {fmtValue(current)}
      </div>

      {/* Threshold label */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>
        Limit: {fmtThreshold(threshold)}
      </div>

      {/* Progress bar */}
      <div style={{
        height: 6,
        borderRadius: 3,
        background: 'var(--border)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${barWidth}%`,
          borderRadius: 3,
          background: barColor,
          transition: 'width 0.3s ease',
        }} />
      </div>

      {/* Bar legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Current: {fmtValue(current)}</span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Limit: {fmtValue(threshold)}</span>
      </div>
    </div>
  )
}
