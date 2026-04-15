import React from 'react'

const GOLD   = '#C9A84C'
const TEAL   = '#2DD4BF'
const RED    = '#F06060'
const MUTED  = '#8494A7'
const SURFACE = '#172231'
const BORDER  = '#243040'
const DEEP    = '#0A1119'

/**
 * CovenantTriggerCard — 3-level trigger zone visualization.
 *
 * Props:
 *   trigger — { name, metric, current_value, l1_threshold, l2_threshold, l3_threshold, status, headroom_pct }
 *   status values: 'compliant' | 'l1_breach' | 'l2_breach' | 'l3_breach' | 'unknown'
 */
export default function CovenantTriggerCard({ trigger }) {
  const { name, metric, current_value, l1_threshold, l2_threshold, l3_threshold, status, headroom_pct } = trigger
  const maxVal = l3_threshold * 1.2
  const barWidth = (val) => `${Math.min((val / maxVal) * 100, 100)}%`

  const statusColors = {
    compliant: TEAL,
    l1_breach: '#F59E0B',
    l2_breach: '#F97316',
    l3_breach: RED,
    unknown: MUTED,
  }

  return (
    <div style={{ background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: '#E8EAF0', fontWeight: 600, textTransform: 'capitalize' }}>{name}</span>
        <span style={{ color: statusColors[status] || MUTED, fontSize: 12, fontWeight: 600 }}>
          {status === 'compliant' ? 'COMPLIANT' : status === 'unknown' ? 'N/A' : status.toUpperCase().replace('_', ' ')}
        </span>
      </div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 12 }}>{metric}</div>

      {/* Trigger zone bar */}
      <div style={{ position: 'relative', height: 24, background: DEEP, borderRadius: 4, overflow: 'hidden' }}>
        {/* L3 zone (red) */}
        <div style={{ position: 'absolute', left: barWidth(l2_threshold), right: 0, top: 0, bottom: 0, background: 'rgba(240,96,96,0.15)' }} />
        {/* L2 zone (orange) */}
        <div style={{ position: 'absolute', left: barWidth(l1_threshold), width: `calc(${barWidth(l2_threshold)} - ${barWidth(l1_threshold)})`, top: 0, bottom: 0, background: 'rgba(249,115,22,0.15)' }} />
        {/* L1 zone (amber) */}
        <div style={{ position: 'absolute', left: barWidth(l1_threshold * 0.7), width: `calc(${barWidth(l1_threshold)} - ${barWidth(l1_threshold * 0.7)})`, top: 0, bottom: 0, background: 'rgba(245,158,11,0.1)' }} />

        {/* Current value marker */}
        {current_value != null && (
          <div style={{
            position: 'absolute', left: barWidth(current_value), top: 0, bottom: 0,
            width: 3, background: statusColors[status] || TEAL, borderRadius: 2,
          }} />
        )}

        {/* Threshold markers — stagger label vertically when thresholds are close */}
        {[{ val: l1_threshold, label: 'L1' }, { val: l2_threshold, label: 'L2' }, { val: l3_threshold, label: 'L3' }].map((t, i) => {
          const thresholds = [l1_threshold, l2_threshold, l3_threshold]
          const prevVal = i > 0 ? thresholds[i - 1] : 0
          const tooClose = i > 0 && maxVal > 0 && ((t.val - prevVal) / maxVal) < 0.08
          return (
            <div key={t.label} style={{
              position: 'absolute', left: barWidth(t.val), top: 0, bottom: 0,
              borderLeft: `1px dashed ${MUTED}`, opacity: 0.5,
            }}>
              <span style={{ position: 'absolute', top: tooClose ? -24 : -14, left: -8, fontSize: 9, color: MUTED }}>{t.label}</span>
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 11 }}>
        <span style={{ color: statusColors[status] || MUTED }}>
          Current: {current_value != null ? `${current_value.toFixed(2)}%` : 'N/A'}
        </span>
        {headroom_pct != null && (
          <span style={{ color: TEAL }}>Headroom: {headroom_pct.toFixed(1)}pp to L1</span>
        )}
      </div>
    </div>
  )
}
