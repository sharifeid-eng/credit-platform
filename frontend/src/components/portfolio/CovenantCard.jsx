import ComplianceBadge from './ComplianceBadge'

export default function CovenantCard({ covenant, currency = 'AED' }) {
  const { name, current, threshold, compliant, operator, format, period, breakdown,
          previous_value, days_since_previous } = covenant

  const fmtValue = (v) => {
    if (format === 'pct') return `${(v * 100).toFixed(1)}%`
    if (format === 'money') return `${currency} ${(v / 1_000_000).toFixed(1)}M`
    if (format === 'ratio') return typeof v === 'number' ? v.toFixed(2) : String(v)
    if (format === 'weeks') return `${Math.round(v)} weeks`
    if (format === 'days') return `${Math.round(v)} days`
    return String(v)
  }

  const fmtBreakdownValue = (v) => {
    if (typeof v !== 'number') return String(v)
    if (v >= 1_000_000) return `${currency} ${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${currency} ${(v / 1_000).toFixed(0)}K`
    if (v < 1 && v > 0) return `${(v * 100).toFixed(1)}%`
    return String(v)
  }

  // Threshold bar positioning
  const isGreaterThan = operator === '>=' || operator === '>'
  const maxVal = Math.max(current, threshold) * 1.3
  const thresholdPct = (threshold / maxVal) * 100
  const currentPct = (current / maxVal) * 100

  // Trigger distance (headroom when compliant)
  const headroom = isGreaterThan ? current - threshold : threshold - current

  // Trend / projected breach
  const hasTrend = typeof previous_value === 'number' && typeof days_since_previous === 'number' && days_since_previous > 0
  const changePerDay = hasTrend ? (current - previous_value) / days_since_previous : 0
  const movingTowardBreach = hasTrend && compliant && (isGreaterThan ? changePerDay < 0 : changePerDay > 0)
  const daysToBreachRaw = movingTowardBreach && Math.abs(changePerDay) > 0
    ? headroom / Math.abs(changePerDay)
    : null
  const projectedBreachDate = daysToBreachRaw != null
    ? new Date(Date.now() + daysToBreachRaw * 86_400_000)
        .toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${compliant ? 'var(--border)' : 'rgba(240, 96, 96, 0.3)'}`,
      borderRadius: 'var(--radius-md)',
      padding: '24px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
          {name}
        </div>
        <ComplianceBadge compliant={compliant} />
      </div>

      {/* Value */}
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 32,
        fontWeight: 700,
        color: compliant ? 'var(--accent-teal)' : 'var(--accent-red)',
        marginBottom: 4,
      }}>
        {fmtValue(current)}
      </div>

      {/* Threshold info */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
        Limit: {operator} {fmtValue(threshold)}
      </div>

      {/* Period */}
      {period && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 12 }}>
          Period: {period}
        </div>
      )}

      {/* Compliance distance (breach) */}
      {!compliant && (
        <div style={{
          fontSize: 10, color: 'var(--accent-red)', marginBottom: 12,
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <span>⚠</span>
          {format === 'pct'
            ? `${Math.abs((current - threshold) * 100).toFixed(1)}% ${isGreaterThan ? 'below minimum' : 'over limit'}`
            : `${fmtValue(Math.abs(current - threshold))} ${isGreaterThan ? 'below minimum' : 'over limit'}`
          }
        </div>
      )}

      {/* Trigger distance (headroom when compliant) */}
      {compliant && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: 'var(--accent-teal)', display: 'flex', alignItems: 'center', gap: 4 }}>
            <span>✓</span>
            {format === 'pct'
              ? `${(headroom * 100).toFixed(1)}% headroom to limit`
              : `${fmtValue(headroom)} headroom to limit`
            }
          </div>
          {projectedBreachDate && (
            <div style={{ fontSize: 10, color: 'var(--accent-gold)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>⚠</span>
              Breach projected: {projectedBreachDate}
              {daysToBreachRaw < 90 && (
                <span style={{
                  marginLeft: 4, padding: '1px 5px',
                  background: 'rgba(201, 168, 76, 0.15)',
                  border: '1px solid rgba(201, 168, 76, 0.3)',
                  borderRadius: 3, fontSize: 9, fontWeight: 600,
                }}>
                  {Math.round(daysToBreachRaw)}d
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Threshold bar */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>Risk Threshold View</div>
        <div style={{
          height: 20,
          borderRadius: 4,
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
        }}>
          {isGreaterThan ? (
            <>
              <div style={{ width: `${thresholdPct}%`, background: 'rgba(240, 96, 96, 0.25)', height: '100%' }} />
              <div style={{ flex: 1, background: 'rgba(45, 212, 191, 0.2)', height: '100%' }} />
            </>
          ) : (
            <>
              <div style={{ width: `${thresholdPct}%`, background: 'rgba(45, 212, 191, 0.2)', height: '100%' }} />
              <div style={{ flex: 1, background: 'rgba(240, 96, 96, 0.25)', height: '100%' }} />
            </>
          )}
          {/* Current value marker */}
          <div style={{
            position: 'absolute',
            left: `${Math.min(currentPct, 98)}%`,
            top: 0, bottom: 0,
            width: 2,
            background: compliant ? 'var(--accent-teal)' : 'var(--accent-red)',
          }}>
            <div style={{
              position: 'absolute', top: -6, left: -3,
              width: 0, height: 0,
              borderLeft: '4px solid transparent',
              borderRight: '4px solid transparent',
              borderTop: `5px solid ${compliant ? 'var(--accent-teal)' : 'var(--accent-red)'}`,
            }} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
            <span style={{ color: compliant ? 'var(--accent-teal)' : 'var(--accent-red)' }}>▲</span> Current: {fmtValue(current)}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
            {hasTrend && (
              <span style={{ marginRight: 8, color: movingTowardBreach ? 'var(--accent-gold)' : 'var(--text-muted)' }}>
                {movingTowardBreach ? '↘' : '↗'} vs prior
              </span>
            )}
            <span style={{ color: isGreaterThan ? 'var(--accent-red)' : 'var(--accent-teal)' }}>●</span> Limit: {operator} {fmtValue(threshold)}
          </div>
        </div>
      </div>

      {/* Calculation breakdown */}
      {breakdown && breakdown.length > 0 && (
        <div style={{
          borderTop: '1px solid var(--border)',
          paddingTop: 12,
        }}>
          {breakdown.map((item, i) => (
            <div key={i} style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '4px 0',
              fontSize: 11,
              fontWeight: item.bold ? 700 : 400,
              color: item.bold ? 'var(--text-primary)' : 'var(--text-muted)',
              borderTop: item.bold ? '1px solid var(--border)' : 'none',
              marginTop: item.bold ? 4 : 0,
              paddingTop: item.bold ? 8 : 4,
            }}>
              <span>{item.label}</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{fmtBreakdownValue(item.value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
