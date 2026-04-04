/**
 * PortfolioStatsHero — full-width stats strip below the navbar.
 * Shows animated count-up aggregates across all portfolio companies.
 * Props:
 *   companies  array   — from /companies endpoint
 *   summaries  object  — keyed by "companyName:product", values from /summary endpoint
 */
import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

// ── Ease-out expo count-up ───────────────────────────────────────────────────
function useCountUp(target, duration = 1400) {
  const [val, setVal] = useState(0)
  const raf = useRef(null)

  useEffect(() => {
    if (target == null || target === 0) return
    const startTime = performance.now()

    const animate = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out exponential
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
      setVal(target * eased)
      if (progress < 1) {
        raf.current = requestAnimationFrame(animate)
      } else {
        setVal(target)
      }
    }
    raf.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return val
}

// ── Aggregate from summaries ──────────────────────────────────────────────────
function aggregate(summaries) {
  const vals = Object.values(summaries)
  if (vals.length === 0) return null

  const totalDeployed = vals.reduce((s, v) => s + (v.total_purchase_value || 0), 0)
  const totalActive   = vals.reduce((s, v) => s + (v.active_deals || 0), 0)
  const totalDeals    = vals.reduce((s, v) => s + (v.total_deals || 0), 0)

  // Weighted average collection rate (weight by purchase value)
  const totalPV = vals.reduce((s, v) => s + (v.total_purchase_value || 0), 0)
  const weightedCR = vals.reduce((s, v) => s + (v.collection_rate || 0) * (v.total_purchase_value || 0), 0)
  const collectionRate = totalPV > 0 ? weightedCR / totalPV : 0

  return { totalDeployed, totalActive, totalDeals, collectionRate }
}

// ── Individual stat item ──────────────────────────────────────────────────────
function StatItem({ label, rawValue, format, loading, index }) {
  const animated = useCountUp(loading ? null : rawValue)
  const display  = loading ? null : format(animated)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07, ease: 'easeOut' }}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, minWidth: 120 }}
    >
      {/* Value */}
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 38,
        fontWeight: 500,
        letterSpacing: '-0.03em',
        color: 'var(--gold)',
        lineHeight: 1,
        minHeight: 42,
      }}>
        {display ?? <Skeleton width={100} />}
      </div>
      {/* Label */}
      <div style={{
        fontSize: 10,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.14em',
        color: 'var(--text-muted)',
        marginTop: 2,
      }}>
        {label}
      </div>
    </motion.div>
  )
}

function Skeleton({ width }) {
  return (
    <div style={{
      width,
      height: 24,
      borderRadius: 4,
      background: 'linear-gradient(90deg, var(--bg-surface) 25%, var(--border) 50%, var(--bg-surface) 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.4s infinite',
    }} />
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function PortfolioStatsHero({ companies, summaries }) {
  const stats   = aggregate(summaries)
  const loading = !stats

  const fmtDeployed    = v => `$${(v / 1_000_000).toFixed(1)}M`
  const fmtCollRate    = v => `${v.toFixed(1)}%`
  const fmtActiveDeals = v => Math.round(v).toLocaleString()
  const fmtCompanies   = v => Math.round(v).toString()

  return (
    <div style={{
      borderTop:    '1px solid rgba(201,168,76,0.25)',
      borderBottom: '1px solid rgba(201,168,76,0.12)',
      background:   'linear-gradient(to bottom, rgba(201,168,76,0.08), rgba(201,168,76,0.02) 70%, transparent)',
      padding:      '32px 48px',
      position:     'relative',
      overflow:     'hidden',
    }}>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>

      <div style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'center',
        gap:            80,
        flexWrap:       'wrap',
      }}>
        <StatItem
          label="Total Deployed"
          rawValue={stats?.totalDeployed ?? 0}
          format={fmtDeployed}
          loading={loading}
          index={0}
        />

        {/* Divider */}
        <div style={{ width: 1, height: 48, background: 'rgba(201,168,76,0.2)', flexShrink: 0 }} />

        <StatItem
          label="Collection Rate"
          rawValue={stats?.collectionRate ?? 0}
          format={fmtCollRate}
          loading={loading}
          index={1}
        />

        <div style={{ width: 1, height: 48, background: 'rgba(201,168,76,0.2)', flexShrink: 0 }} />

        <StatItem
          label="Active Deals"
          rawValue={stats?.totalActive ?? 0}
          format={fmtActiveDeals}
          loading={loading}
          index={2}
        />

        <div style={{ width: 1, height: 48, background: 'rgba(201,168,76,0.2)', flexShrink: 0 }} />

        <StatItem
          label="Portfolio Companies"
          rawValue={companies.length}
          format={fmtCompanies}
          loading={companies.length === 0}
          index={3}
        />
      </div>
    </div>
  )
}
