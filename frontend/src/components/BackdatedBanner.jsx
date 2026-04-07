import { useState } from 'react'

export default function BackdatedBanner({ asOfDate, snapshotDate }) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div style={{
      margin: '0 0 16px 0',
      padding: '12px 14px',
      background: 'rgba(201,168,76,0.08)',
      border: '1px solid rgba(201,168,76,0.25)',
      borderLeft: '3px solid var(--accent-gold)',
      borderRadius: 6,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      fontSize: 11,
      lineHeight: 1.7,
      color: 'var(--text-muted)',
    }}>
      <span style={{ color: 'var(--accent-gold)', fontSize: 14, flexShrink: 0, marginTop: 1 }}>&#x26A0;</span>
      <div style={{ flex: 1 }}>
        <strong style={{ color: 'var(--text-primary)' }}>
          Backdated view: as-of date ({asOfDate}) is before tape date ({snapshotDate}).
        </strong>
        <div style={{ marginTop: 6, display: 'flex', gap: 20 }}>
          <div>
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--accent-teal)' }}>ACCURATE: </span>
            Deal count, originated volume, deployment, cohort selection, vintage composition
          </div>
          <div>
            <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--accent-gold)' }}>TAPE DATE: </span>
            Outstanding, collected, denied, rates, margins, PAR, revenue, ageing
          </div>
        </div>
        <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-faint)' }}>
          Metrics marked <span style={{ fontSize: 8, fontWeight: 700, padding: '1px 4px', borderRadius: 2, background: 'rgba(201,168,76,0.12)', color: 'var(--accent-gold)' }}>TAPE DATE</span> reflect the snapshot date, not the as-of date. AI analysis is disabled for backdated views.
        </div>
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
