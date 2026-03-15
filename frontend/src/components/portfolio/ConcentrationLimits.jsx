import LimitCard from './LimitCard'
import { MOCK_CONCENTRATION_LIMITS } from './mockData'

export default function ConcentrationLimits() {
  const limits = MOCK_CONCENTRATION_LIMITS

  const compliantCount = limits.filter(l => l.compliant).length
  const breachCount = limits.length - compliantCount

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary bar */}
      <div style={{
        display: 'flex', gap: 16, alignItems: 'center',
        padding: '12px 20px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
          Concentration Limits
        </div>
        <div style={{ display: 'flex', gap: 12, marginLeft: 'auto' }}>
          <span style={{ fontSize: 11, color: 'var(--accent-teal)' }}>
            ● {compliantCount} Compliant
          </span>
          {breachCount > 0 && (
            <span style={{ fontSize: 11, color: 'var(--accent-red)' }}>
              ● {breachCount} Breach
            </span>
          )}
        </div>
      </div>

      {/* Limit cards grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 14,
      }}>
        {limits.map((limit, i) => (
          <LimitCard key={i} {...limit} />
        ))}
      </div>
    </div>
  )
}
