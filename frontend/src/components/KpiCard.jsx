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
 */
import { motion } from 'framer-motion'
import { useState } from 'react'

export default function KpiCard({ label, value, sub, trend, trendLabel, color = 'gold', stale = false, index = 0 }) {
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

      {/* Stale data indicator */}
      {stale && (
        <div
          title="This metric reflects tape snapshot balances, not the as-of date"
          style={{
            position: 'absolute', top: 8, right: 10,
            fontSize: 11, opacity: 0.55, cursor: 'help',
            color: 'var(--accent-gold)',
          }}
        >&#x26A0;</div>
      )}

      {/* Label */}
      <div style={{
        fontSize: 9, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.1em',
        color: 'var(--text-muted)', marginBottom: 9,
      }}>
        {label}
      </div>

      {/* Value */}
      <div style={{
        fontSize: 22, fontWeight: 700,
        fontFamily: 'var(--font-mono)',
        letterSpacing: '-0.02em', lineHeight: 1,
        color: accent, marginBottom: 5,
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
    </motion.div>
  )
}
