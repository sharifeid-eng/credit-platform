import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/**
 * Stale / zombie exposure panel for Klaim Tape Overview.
 *
 * Props:
 *   data: the /charts/stale-exposure payload. When null / available:false the
 *         component renders nothing (graceful hide on older tapes or non-Klaim).
 *   ccy:  currency code for display (e.g. "AED", "USD").
 */
export default function StaleExposurePanel({ data, ccy = 'AED' }) {
  const [expanded, setExpanded] = useState(false)

  if (!data || !data.available) return null
  const offenders = data.top_offenders || []
  const categories = data.by_category || []

  const share = data.stale_pv_share ?? 0
  const pct = `${(share * 100).toFixed(1)}%`
  const fmtM = (v) => v == null ? '—'
    : Math.abs(v) >= 1e6 ? `${ccy} ${(v / 1e6).toFixed(1)}M`
    : `${ccy} ${(v / 1e3).toFixed(0)}K`

  // Amber > 10% share, red > 20%, teal otherwise
  const tone = share > 0.20 ? 'red' : share > 0.10 ? 'gold' : 'teal'
  const toneColor = tone === 'red' ? 'var(--accent-red)'
    : tone === 'gold' ? 'var(--accent-gold)'
    : 'var(--accent-teal)'
  const toneBg    = tone === 'red' ? 'rgba(240, 96, 96, 0.08)'
    : tone === 'gold' ? 'rgba(201, 168, 76, 0.08)'
    : 'rgba(45, 212, 191, 0.06)'
  const toneBorder = tone === 'red' ? 'rgba(240, 96, 96, 0.30)'
    : tone === 'gold' ? 'rgba(201, 168, 76, 0.30)'
    : 'rgba(45, 212, 191, 0.20)'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${toneBorder}`,
        borderRadius: 10,
        padding: 16,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
          Stale Exposure
        </span>
        <span style={{
          fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
          background: toneBg, color: toneColor, border: `1px dashed ${toneBorder}`,
        }}>
          {tone === 'red' ? '> 20% — RED' : tone === 'gold' ? '> 10% — AMBER' : 'LOW'}
        </span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', opacity: 0.75 }}>
          Forward signal — unresolved tail
        </span>
      </div>

      {/* Primary metric row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: 10,
        marginBottom: 14,
      }}>
        <Metric label="Total Stale PV"  value={fmtM(data.total_stale_pv)} sub={`${pct} of book`} tone={toneColor} />
        <Metric label="Stale Deals"     value={String(data.total_stale_count)} sub={`of ${data.total_deal_count}`} />
        <Metric label="Clean Book PV"   value={fmtM((data.total_pv ?? 0) - (data.total_stale_pv ?? 0))} sub={`${((1 - share) * 100).toFixed(1)}% of book`} />
        <Metric label="Age Threshold"   value={`${data.ineligibility_age_days}d`} sub="MMA ineligibility" />
      </div>

      {/* Category breakdown bars */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, letterSpacing: '0.04em' }}>
          Category Breakdown
        </div>
        {categories.map((c) => (
          <CategoryBar key={c.category} cat={c} totalPv={data.total_pv} fmtM={fmtM} />
        ))}
      </div>

      {/* Expand button */}
      {offenders.length > 0 && (
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            width: '100%',
            padding: '8px 12px',
            background: 'var(--bg-deep)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            color: 'var(--text-primary)',
            fontSize: 11,
            fontFamily: 'inherit',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background 150ms, border-color 150ms',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-hover)' }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
        >
          {expanded ? `▾ Hide top offenders` : `▸ View ${offenders.length} top offenders`}
        </button>
      )}

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={{ overflow: 'hidden' }}
          >
            <OffendersTable rows={offenders} fmtM={fmtM} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Methodology footnote */}
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 12, lineHeight: 1.55, opacity: 0.85 }}>
        <strong style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Stale rules:</strong>{' '}
        <em style={{ color: 'var(--accent-teal)' }}>loss_completed</em> (Completed &amp; Denied &gt; 50% of PV),{' '}
        <em style={{ color: 'var(--accent-gold)' }}>stuck_active</em> (Executed &amp; elapsed &gt; {data.ineligibility_age_days}d &amp; outstanding &lt; 10% of PV),{' '}
        <em style={{ color: 'var(--accent-red)' }}>denial_dominant_active</em> (Executed &amp; Denied &gt; 50% of PV).
        Top offenders tagged with primary category (loss_completed &gt; stuck_active &gt; denial_dominant_active precedence).
      </div>
    </motion.div>
  )
}

// ── Metric tile ──
function Metric({ label, value, sub, tone }) {
  return (
    <div style={{
      padding: '8px 10px',
      background: 'var(--bg-deep)',
      border: '1px solid var(--border)',
      borderRadius: 6,
    }}>
      <div style={{ fontSize: 9, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, color: tone || 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginBottom: 2 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 9, color: 'var(--text-muted)', opacity: 0.8 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

// ── Category mini-bar ──
const CAT_DISPLAY = {
  loss_completed:         { label: 'Loss (Completed)',         colorVar: 'var(--accent-teal)' },
  stuck_active:           { label: 'Stuck (Active)',            colorVar: 'var(--accent-gold)' },
  denial_dominant_active: { label: 'Denial-Dominant (Active)',  colorVar: 'var(--accent-red)' },
}

function CategoryBar({ cat, totalPv, fmtM }) {
  const disp = CAT_DISPLAY[cat.category] || { label: cat.category, colorVar: 'var(--text-muted)' }
  const widthPct = Math.min(100, (cat.pv_share ?? 0) * 100 / 0.25 * 100) // scale: 25% share = full bar
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3, gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--text-primary)', fontWeight: 500 }}>{disp.label}</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {cat.count} deals · {fmtM(cat.pv)} · {((cat.pv_share ?? 0) * 100).toFixed(1)}% · age {cat.pv_weighted_age_days}d
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--bg-deep)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${widthPct}%`,
          background: disp.colorVar,
          opacity: 0.7,
          transition: 'width 300ms ease-out',
        }} />
      </div>
    </div>
  )
}

// ── Top offender drill-down table ──
function OffendersTable({ rows, fmtM }) {
  return (
    <div style={{ marginTop: 10, overflowX: 'auto' }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
      }}>
        <thead>
          <tr style={{ background: 'var(--bg-deep)' }}>
            <Th>#</Th>
            <Th>Deal ID</Th>
            <Th>Deal Date</Th>
            <Th align="right">Age</Th>
            <Th align="right">PV</Th>
            <Th>Category</Th>
            <Th>Group</Th>
            <Th>Provider</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((o, i) => (
            <tr key={o.id + i} style={{ borderBottom: '1px solid var(--border)' }}>
              <Td>{i + 1}</Td>
              <Td title={o.id} style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.id}</Td>
              <Td>{o.deal_date ?? '—'}</Td>
              <Td align="right" strong>{o.age_days}d</Td>
              <Td align="right" strong>{fmtM(o.pv)}</Td>
              <Td>
                <CategoryChip cat={o.category} />
              </Td>
              <Td title={o.group || ''} style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {o.group ?? '—'}
              </Td>
              <Td title={o.provider || ''} style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {o.provider ?? '—'}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Th({ children, align = 'left' }) {
  return (
    <th style={{
      padding: '6px 8px',
      fontSize: 9,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      color: 'var(--text-muted)',
      textAlign: align,
      fontFamily: 'var(--font-sans)',
      borderBottom: '1px solid var(--border)',
    }}>
      {children}
    </th>
  )
}

function Td({ children, align = 'left', strong = false, ...rest }) {
  return (
    <td style={{
      padding: '6px 8px',
      color: strong ? 'var(--text-primary)' : 'var(--text-muted)',
      textAlign: align,
      fontWeight: strong ? 600 : 400,
      ...rest.style,
    }} {...rest}>
      {children}
    </td>
  )
}

function CategoryChip({ cat }) {
  const disp = CAT_DISPLAY[cat] || { label: cat, colorVar: 'var(--text-muted)' }
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 600,
      padding: '2px 6px',
      borderRadius: 3,
      color: disp.colorVar,
      background: `color-mix(in srgb, ${disp.colorVar} 10%, transparent)`,
      border: `1px solid color-mix(in srgb, ${disp.colorVar} 25%, transparent)`,
      fontFamily: 'var(--font-sans)',
      whiteSpace: 'nowrap',
    }}>
      {disp.label}
    </span>
  )
}
