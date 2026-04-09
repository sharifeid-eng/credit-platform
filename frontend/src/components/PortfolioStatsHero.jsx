/**
 * StatsBanners — two stacked banners on the landing page.
 *
 * Banner 1 "Data Analyzed" — gold tint, live data from /aggregate-stats (cached backend).
 * Banner 2 "Live Portfolio" — neutral, all dashes until real DB data is connected.
 */
import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { getAggregateStats } from '../services/api'
import useBreakpoint from '../hooks/useBreakpoint'

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
function StatCell({ label, rawValue, format, loading, empty, index, valueColor, isMobile }) {
  const animated = useCountUp(loading || empty ? null : rawValue)
  const display  = empty ? '—' : loading ? null : format(animated)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: 'easeOut' }}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: isMobile ? 70 : 110 }}
    >
      <div style={{
        fontFamily:    'var(--font-mono)',
        fontSize:      isMobile ? 18 : 26,
        fontWeight:    500,
        letterSpacing: '-0.03em',
        color:         valueColor,
        lineHeight:    1,
        minHeight:     isMobile ? 22 : 30,
      }}>
        {display ?? <Skeleton />}
      </div>
      <div style={{
        fontSize:      isMobile ? 7 : 9,
        fontWeight:    600,
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        color:         'var(--text-muted)',
        textAlign:     'center',
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
function Banner({ label, children, variant, isMobile }) {
  const isGold = variant === 'gold'
  return (
    <div style={{
      borderBottom: `1px solid ${isGold ? 'rgba(201,168,76,0.15)' : 'var(--border)'}`,
      background:    isGold
        ? 'linear-gradient(to bottom, rgba(201,168,76,0.07), rgba(201,168,76,0.01) 70%, transparent)'
        : 'transparent',
      padding: isMobile ? '20px 14px 14px' : '16px 48px',
      position: 'relative',
    }}>
      {/* Section label — top-left */}
      <div style={{
        position:      isMobile ? 'relative' : 'absolute',
        top:           isMobile ? undefined : 10,
        left:          isMobile ? undefined : 28,
        fontSize:      8,
        fontWeight:    700,
        textTransform: 'uppercase',
        letterSpacing: '0.16em',
        color:         isGold ? 'rgba(201,168,76,0.5)' : 'rgba(132,148,167,0.4)',
        marginBottom:  isMobile ? 10 : 0,
      }}>
        {label}
      </div>

      {isMobile ? (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '14px 8px',
          justifyItems: 'center',
        }}>
          {children}
        </div>
      ) : (
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
      )}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function PortfolioStatsHero() {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const { isMobile } = useBreakpoint()

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

  const goldDiv    = isMobile ? null : <Divider color="rgba(201,168,76,0.18)" />
  const neutralDiv = isMobile ? null : <Divider color="var(--border)" />

  return (
    <div style={{ borderTop: '1px solid rgba(201,168,76,0.2)' }}>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>

      {/* Banner 1 — Data Analyzed */}
      <Banner label="Data Analyzed" variant="gold" isMobile={isMobile}>
        <StatCell label="Face Value Analyzed" rawValue={stats?.total_face_value_usd} format={fmtValue}      loading={loading} index={0} valueColor="var(--gold)" isMobile={isMobile} />
        {goldDiv}
        <StatCell label="Deals Processed"     rawValue={stats?.total_deals}          format={fmtDeals}      loading={loading} index={1} valueColor="var(--gold)" isMobile={isMobile} />
        {goldDiv}
        <StatCell label="Data Points"         rawValue={stats?.total_data_points}    format={fmtDataPoints} loading={loading} index={2} valueColor="var(--gold)" isMobile={isMobile} />
        {goldDiv}
        <StatCell label="Snapshots Loaded"    rawValue={stats?.total_snapshots}      format={fmtSnaps}      loading={loading} index={3} valueColor="var(--gold)" isMobile={isMobile} />
        {goldDiv}
        <StatCell label="Portfolio Companies" rawValue={stats?.total_companies}      format={fmtCompanies}  loading={loading} index={4} valueColor="var(--gold)" isMobile={isMobile} />
      </Banner>

      {/* Banner 2 — Live Portfolio (hidden on mobile since all dashes) */}
      {!isMobile && (
        <Banner label="Live Portfolio" variant="neutral" isMobile={isMobile}>
          <StatCell label="Active Exposure"     empty index={0} valueColor="var(--text-muted)" isMobile={isMobile} />
          {neutralDiv}
          <StatCell label="PAR 30+"             empty index={1} valueColor="var(--text-muted)" isMobile={isMobile} />
          {neutralDiv}
          <StatCell label="PAR 90+"             empty index={2} valueColor="var(--text-muted)" isMobile={isMobile} />
          {neutralDiv}
          <StatCell label="Covenants in Breach" empty index={3} valueColor="var(--text-muted)" isMobile={isMobile} />
          {neutralDiv}
          <StatCell label="Concentration (HHI)" empty index={4} valueColor="var(--text-muted)" isMobile={isMobile} />
        </Banner>
      )}
    </div>
  )
}
