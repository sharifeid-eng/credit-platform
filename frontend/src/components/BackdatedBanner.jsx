import { useState } from 'react'

export default function BackdatedBanner({ asOfDate, snapshotDate }) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div style={{
      margin: '0 0 16px 0',
      padding: '10px 14px',
      background: 'rgba(201,168,76,0.08)',
      border: '1px solid rgba(201,168,76,0.25)',
      borderLeft: '3px solid var(--accent-gold)',
      borderRadius: 6,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      fontSize: 11,
      lineHeight: 1.6,
      color: 'var(--text-muted)',
    }}>
      <span style={{ color: 'var(--accent-gold)', fontSize: 14, flexShrink: 0, marginTop: 1 }}>&#x26A0;</span>
      <div style={{ flex: 1 }}>
        <strong style={{ color: 'var(--text-primary)' }}>As-of date ({asOfDate}) is before tape date ({snapshotDate}).</strong>{' '}
        Balance metrics (outstanding, collected, overdue, margins, rates) reflect the tape snapshot date — only deal selection is filtered by as-of date.
      </div>
      <button
        onClick={() => setDismissed(true)}
        style={{
          background: 'none', border: 'none', color: 'var(--text-muted)',
          cursor: 'pointer', fontSize: 14, padding: 0, flexShrink: 0,
          opacity: 0.6,
        }}
        title="Dismiss"
      >&times;</button>
    </div>
  )
}
