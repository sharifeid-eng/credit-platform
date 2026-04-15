import React, { useState } from 'react'

const GOLD   = '#C9A84C'
const TEAL   = '#2DD4BF'
const MUTED  = '#8494A7'
const BORDER = '#243040'
const DEEP   = '#0A1119'

/**
 * VintageHeatmap — CSS-grid color-coded vintage × MOB matrix.
 *
 * Props:
 *   data           — full summary object containing vintage_performance
 *   metric         — default active toggle ('default' | 'delinquency' | 'dilution')
 *   metrics        — optional array of toggle keys (default: ['default','delinquency','dilution'])
 *   metricLabels   — optional map of metric key → display label
 */
export default function VintageHeatmap({
  data,
  metric = 'default',
  metrics = ['default', 'delinquency', 'dilution'],
  metricLabels = { default: 'Default (+120DPD)', delinquency: 'Delinquency (+7DPD)', dilution: 'Dilution (Refund)' },
}) {
  const [activeMetric, setActiveMetric] = useState(metric)
  const metricData = data?.vintage_performance?.[activeMetric] || {}
  const portfolio = metricData.portfolio || []
  const colorScale = metricData._color_scale || {}

  if (!portfolio.length) return <div style={{ color: MUTED, padding: 20 }}>No vintage data available for {activeMetric}</div>

  // Get all MOB columns (reporting months)
  const allCols = new Set()
  portfolio.forEach(r => Object.keys(r).forEach(k => { if (k !== 'vintage') allCols.add(k) }))
  const columns = [...allCols].sort()

  // Color mapping
  const getColor = (val) => {
    if (val == null) return 'transparent'
    const maxVal = colorScale.p75 || colorScale.max || 0.05
    const ratio = Math.min(val / maxVal, 1)
    if (ratio < 0.33) return `rgba(45, 212, 191, ${0.15 + ratio * 1.5})`  // teal
    if (ratio < 0.66) return `rgba(201, 168, 76, ${0.2 + (ratio - 0.33) * 1.5})`  // gold
    return `rgba(240, 96, 96, ${0.3 + (ratio - 0.66) * 2})`  // red
  }

  return (
    <div>
      {metrics.length > 1 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {metrics.map(m => (
            <button key={m} onClick={() => setActiveMetric(m)}
              style={{
                padding: '6px 16px', borderRadius: 6, border: `1px solid ${m === activeMetric ? GOLD : BORDER}`,
                background: m === activeMetric ? 'rgba(201,168,76,0.15)' : 'transparent',
                color: m === activeMetric ? GOLD : MUTED, fontSize: 12, cursor: 'pointer', textTransform: 'capitalize',
              }}>{metricLabels[m] || m}</button>
          ))}
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: `100px repeat(${columns.length}, 60px)`, gap: 1, fontSize: 10 }}>
          {/* Header row */}
          <div style={{ padding: '4px 6px', color: GOLD, fontWeight: 600, position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>Vintage</div>
          {columns.map(c => (
            <div key={c} style={{ padding: '4px 2px', color: MUTED, textAlign: 'center', whiteSpace: 'nowrap' }}>
              {c.replace('20', "'")}
            </div>
          ))}

          {/* Data rows */}
          {portfolio.map((row, ri) => (
            <React.Fragment key={ri}>
              <div style={{ padding: '4px 6px', color: '#E8EAF0', fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                position: 'sticky', left: 0, background: DEEP, zIndex: 1 }}>
                {row.vintage}
              </div>
              {columns.map(c => {
                const val = row[c]
                return (
                  <div key={c} style={{
                    padding: '4px 2px', textAlign: 'center', background: getColor(val),
                    color: val != null ? '#E8EAF0' : 'transparent', borderRadius: 2,
                    fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                  }}>
                    {val != null ? `${(val * 100).toFixed(1)}` : ''}
                  </div>
                )
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {colorScale.min != null && (
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 11, color: MUTED }}>
          <span>Min: {(colorScale.min * 100).toFixed(2)}%</span>
          <span>P25: {(colorScale.p25 * 100).toFixed(2)}%</span>
          <span>P75: {(colorScale.p75 * 100).toFixed(2)}%</span>
          <span>Max: {(colorScale.max * 100).toFixed(2)}%</span>
          <span>({colorScale.count} data points)</span>
        </div>
      )}
    </div>
  )
}
