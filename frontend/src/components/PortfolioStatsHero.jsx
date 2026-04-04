/**
 * StatsBanners — two stacked banners on the landing page.
 *
 * Banner 1 "Data Analyzed" — gold tint, live data from /aggregate-stats (cached backend).
 * Banner 2 "Live Portfolio" — neutral, all dashes until real DB data is connected.
 */
import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { getAggregateStats } from '../services/api'

// ── Ease-out expo count-up ────────────────────────────────────────────────────
function useCountUp(target, duration = 1400) {
  const [val, setVal] = useState(0)
  const raf = useRef(null)
  useEffect(() => {
    if (target == null || target === 0) return
    const startTime = performance.now()
    const animate = (now) => {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased    = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
      setVal(target * eased)
      if (progress < 1) raf.current = requestAnimationFrame(animate)
      else setVal(target)
    }
    raf.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])
  return val
}

// ── Single stat cell ──────────────────────────────────────────────────────────
function StatCell({ label, rawValue, format, loading, empty, index, valueColor }) {
  const animated = useCountUp(loading || empty ? null : rawValue)
  const display  = empty ? '—' : loading ? null : format(animated)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: 'easeOut' }}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 110 }}
    >
      <div style={{
        fontFamily:    'var(--font-mono)',
        fontSize:      26,
        fontWeight:    500,
        letterSpacing: '-0.03em',
        color:         valueColor,
        lineHeight:    1,
        minHeight:     30,
      }}>
        {display ?? <Skeleton />}
      </div>
      <div style={{
        fontSize:      9,
        fontWeight:    600,
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        color:         'var(--text-muted)',
      }}>
        {label}
      </div>
    </motion.div>
  )
}

function Skeleton() {
  return (
    <div style={{
      width: 80, height: 24, borderRadius: 4,
      background: 'linear-gradient(90deg, var(--bg-surface) 25%, var(--border) 50%, var(--bg-surface) 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.4s infinite',
    }} />
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────
function Divider({ color }) {
  return <div style={{ width: 1, height: 32, background: color, flexShrink: 0 }} />
}

// ── Banner shell ──────────────────────────────────────────────────────────────
function Banner({ label, children, variant }) {
  const isGold = variant === 'gold'
  return (
    <div style={{
      borderBottom: `1px solid ${isGold ? 'rgba(201,168,76,0.15)' : 'var(--border)'}`,
      background:    isGold
        ? 'linear-gradient(to bottom, rgba(201,168,76,0.07), rgba(201,168,76,0.01) 70%, transparent)'
        : 'transparent',
      padding: '16px 48px',
      position: 'relative',
    }}>
      {/* Section label — top-left */}
      <div style={{
        position:      'absolute',
        top:           10,
        left:          28,
        fontSize:      8,
        fontWeight:    700,
        textTransform: 'uppercase',
        letterSpacing: '0.16em',
        color:         isGold ? 'rgba(201,168,76,0.5)' : 'rgba(132,148,167,0.4)',
      }}>
        {label}
      </div>

      <div style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'center',
        gap:            56,
        flexWrap:       'wrap',
        paddingTop:     8,
      }}>
        {children}
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function PortfolioStatsHero() {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAggregateStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  const fmtValue      = v => `$${(v / 1_000_000).toFixed(0)}M`
  const fmtDeals      = v => Math.round(v).toLocaleString()
  const fmtDataPoints = v => `${(v / 1_000_000).toFixed(1)}M+`
  const fmtSnaps      = v => Math.round(v).toString()
  const fmtCompanies  = v => Math.round(v).toString()

  const goldDiv    = <Divider color="rgba(201,168,76,0.18)" />
  const neutralDiv = <Divider color="var(--border)" />

  return (
    <div style={{ borderTop: '1px solid rgba(201,168,76,0.2)' }}>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>

      {/* Banner 1 — Data Analyzed */}
      <Banner label="Data Analyzed" variant="gold">
        <StatCell label="Face Value Analyzed" rawValue={stats?.total_face_value_usd} format={fmtValue}      loading={loading} index={0} valueColor="var(--gold)" />
        {goldDiv}
        <StatCell label="Deals Processed"     rawValue={stats?.total_deals}          format={fmtDeals}      loading={loading} index={1} valueColor="var(--gold)" />
        {goldDiv}
        <StatCell label="Data Points"         rawValue={stats?.total_data_points}    format={fmtDataPoints} loading={loading} index={2} valueColor="var(--gold)" />
        {goldDiv}
        <StatCell label="Snapshots Loaded"    rawValue={stats?.total_snapshots}      format={fmtSnaps}      loading={loading} index={3} valueColor="var(--gold)" />
        {goldDiv}
        <StatCell label="Portfolio Companies" rawValue={stats?.total_companies}      format={fmtCompanies}  loading={loading} index={4} valueColor="var(--gold)" />
      </Banner>

      {/* Banner 2 — Live Portfolio (empty until DB connected) */}
      <Banner label="Live Portfolio" variant="neutral">
        <StatCell label="Active Exposure"     empty index={0} valueColor="var(--text-muted)" />
        {neutralDiv}
        <StatCell label="PAR 30+"             empty index={1} valueColor="var(--text-muted)" />
        {neutralDiv}
        <StatCell label="PAR 90+"             empty index={2} valueColor="var(--text-muted)" />
        {neutralDiv}
        <StatCell label="Covenants in Breach" empty index={3} valueColor="var(--text-muted)" />
        {neutralDiv}
        <StatCell label="Concentration (HHI)" empty index={4} valueColor="var(--text-muted)" />
      </Banner>
    </div>
  )
}
