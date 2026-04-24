/**
 * KpiCard — dark theme with hover effects and stagger animation
 *
 * Props:
 *   label      string   — uppercase label e.g. "Collection Rate"
 *   value      string   — formatted value e.g. "94.3%" or "$164.4M"
 *   sub        string   — small subtitle e.g. "7,536 deals"
 *   trend      number   — optional delta e.g. 1.2 or -0.4 (shows ↑↓ badge)
 *   trendLabel string   — optional suffix e.g. "vs prev month"
 *   color      string   — 'gold' | 'teal' | 'red' | 'blue'  (default 'gold')
 *   index      number   — optional index for stagger delay (default 0)
 *   confidence    string   — 'A' | 'B' | 'C' — Framework §10 grade badge
 *                           A = Observed (direct tape read)
 *                           B = Inferred (derived with solid methodology)
 *                           C = Derived (estimated/approximated)
 *   population   string  — optional, §17 population code (shown in confidence
 *                          badge tooltip when present). E.g. 'active_outstanding',
 *                          'clean_book', 'total_originated'.
 *   confidenceNote string — optional, extra disclosure string appended to
 *                           confidence tooltip.
 *   sparklineData number[] — optional last-N data points for inline sparkline
 */
import { motion } from 'framer-motion'
import { useState } from 'react'
import ConfidenceBadge from './ConfidenceBadge'

export default function KpiCard({ label, value, sub, trend, trendLabel, color = 'gold', stale = false, confidence, population, confidenceNote, sparklineData, index = 0 }) {
  const [hovered, setHovered] = useState(false)
  const palette = {
    gold: { accent: 'var(--gold)',  muted: 'var(--gold-muted)' },
    teal: { accent: 'var(--teal)',  muted: 'var(--teal-muted)' },
    red:  { accent: 'var(--red)',   muted: 'var(--red-muted)'  },
    blue: { accent: 'var(--blue)',  muted: 'var(--blue-muted)' },
  }
  const { accent, muted } = palette[color] || palette.gold
  const isUp = trend > 0
  const isDown = trend < 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04, ease: 'easeOut' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'var(--border-hover)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-md)',
        padding: '16px 16px 14px',
        position: 'relative',
        overflow: 'hidden',
        transform: hovered ? 'translateY(-1px)' : 'translateY(0)',
        boxShadow: hovered ? 'var(--shadow-card-hover)' : 'var(--shadow-card)',
        transition: 'border-color var(--transition-fast), box-shadow var(--transition-normal), transform var(--transition-fast)',
        cursor: 'default',
      }}
    >
      {/* Left accent bar */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
        background: accent,
        borderRadius: '10px 0 0 10px',
      }} />

      {/* Subtle background glow */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: '40%',
        background: `linear-gradient(to right, ${muted}, transparent)`,
        pointerEvents: 'none',
      }} />

      {/* Trend badge */}
      {trend !== undefined && trend !== null && (
        <div style={{
          position: 'absolute', top: 12, right: 12,
          fontSize: 9, fontWeight: 700,
          fontFamily: 'var(--font-mono)',
          padding: '2px 7px', borderRadius: 20,
          color: isUp ? 'var(--teal)' : isDown ? 'var(--red)' : 'var(--text-muted)',
          background: isUp ? 'var(--teal-muted)' : isDown ? 'var(--red-muted)' : 'transparent',
        }}>
          {isUp ? '↑' : isDown ? '↓' : '–'} {Math.abs(trend).toFixed(1)}%
        </div>
      )}

      {/* Stale data indicator — shown when as-of date is before snapshot date */}
      {stale && (
        <div
          title="Reflects tape snapshot date, not the as-of date. Deal selection is filtered but balances are not."
          style={{
            position: 'absolute',
            top: (trend !== undefined && trend !== null) ? 30 : 6,
            right: 8,
            fontSize: 8, fontWeight: 700, letterSpacing: '0.04em',
            padding: '2px 6px', borderRadius: 3,
            color: 'var(--accent-gold)',
            background: 'rgba(201,168,76,0.12)',
            border: '1px solid rgba(201,168,76,0.2)',
            cursor: 'help',
          }}
        >TAPE DATE</div>
      )}

      {/* Label */}
      <div style={{
        fontSize: 9, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.1em',
        color: 'var(--text-muted)', marginBottom: 9,
        paddingRight: (trend !== undefined && trend !== null) || stale ? 52 : 0,
      }}>
        {label}
      </div>

      {/* Value */}
      <div style={{
        fontSize: 22, fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '-0.02em', lineHeight: 1,
        color: accent, marginBottom: 5,
        opacity: stale ? 0.5 : 1,
      }}>
        {value}
      </div>

      {/* Sub */}
      {sub && (
        <div style={{
          fontSize: 10, color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          {sub}
        </div>
      )}

      {/* Trend label */}
      {trendLabel && trend !== undefined && (
        <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 3 }}>
          {trendLabel}
        </div>
      )}

      {/* Inline sparkline */}
      {sparklineData && sparklineData.length >= 3 && (
        <div style={{ marginTop: 8 }}>
          <Sparkline data={sparklineData} color={accent} />
        </div>
      )}

      {/* Confidence grade badge (Framework §10 + §17) */}
      {confidence && (
        <div style={{ position: 'absolute', bottom: 8, right: 8 }}>
          <ConfidenceBadge
            confidence={confidence}
            population={population}
            note={confidenceNote}
          />
        </div>
      )}
    </motion.div>
  )
}

// ── Inline sparkline — 60×18px SVG polyline ──────────────────────────────────
function Sparkline({ data, color }) {
  const W = 60, H = 18
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * W,
    H - ((v - min) / range) * (H - 2) - 1,
  ])
  const points = pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]

  return (
    <svg width={W} height={H} style={{ display: 'block', overflow: 'visible', opacity: 0.7 }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Dot at latest value */}
      <circle cx={last[0]} cy={last[1]} r="2" fill={color} />
    </svg>
  )
}
