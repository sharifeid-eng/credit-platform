import CovenantCard from './CovenantCard'
import { MOCK_COVENANTS } from './mockData'

export default function Covenants() {
  const covenants = MOCK_COVENANTS

  const compliantCount = covenants.filter(c => c.compliant).length
  const breachCount = covenants.length - compliantCount

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header with date selector */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 20px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Covenants
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
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

        {/* Date selector placeholder */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px',
          background: 'var(--bg-base)',
          border: '1px solid var(--border)',
          borderRadius: 7,
          fontSize: 11,
          color: 'var(--text-primary)',
          fontFamily: 'var(--font-mono)',
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          28 Feb 2026
        </div>
      </div>

      {/* Covenant cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {covenants.map((covenant, i) => (
          <CovenantCard key={i} covenant={covenant} />
        ))}
      </div>
    </div>
  )
}
