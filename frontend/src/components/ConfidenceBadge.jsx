/**
 * ConfidenceBadge — compact A/B/C grade badge with hover tooltip
 * disclosing the population code.
 *
 * Framework §17 disclosure primitive. Use on any metric display where
 * the analyst should see the confidence grade + measurement population.
 *
 * Props:
 *   confidence  'A' | 'B' | 'C'  — required, the grade
 *   population  string           — optional, §17 population code (e.g.
 *                                  'active_outstanding', 'clean_book').
 *                                  Appears in the hover tooltip body.
 *   method      string           — optional, compute method tag (e.g.
 *                                  'direct', 'age_pending', 'cumulative').
 *                                  Appears in tooltip when present.
 *   note        string           — optional, free-form extra disclosure
 *                                  (e.g. "Single-snapshot approximation")
 *                                  appended to tooltip body.
 *   size        'sm' | 'md'      — optional, default 'sm' (8px font, inline)
 *                                  'md' = 10px, more prominent on cards.
 *   inline      boolean          — optional, default false. If true, renders
 *                                  as an inline-flex span (no positioning).
 *                                  If false, returns just the pill — caller
 *                                  positions.
 *
 * Usage examples:
 *   <ConfidenceBadge confidence="A" />
 *   <ConfidenceBadge confidence="B" population="active_outstanding"
 *                    method="age_pending"
 *                    note="Operational-age proxy for contractual DPD" />
 *   <ConfidenceBadge confidence="C" population="total_originated"
 *                    method="cumulative" size="md" inline />
 */

const CONFIDENCE = {
  A: {
    color:    'var(--accent-teal)',
    bg:       'rgba(45,212,191,0.12)',
    border:   'rgba(45,212,191,0.25)',
    label:    'Observed',
    headline: 'Grade A — Observed',
    body:     'Directly measured from tape data. Numerator, denominator, and filter are all observed without proxy or model substitution.',
  },
  B: {
    color:    'var(--accent-gold)',
    bg:       'rgba(201,168,76,0.12)',
    border:   'rgba(201,168,76,0.25)',
    label:    'Inferred',
    headline: 'Grade B — Inferred',
    body:     'Derived from a proxy column, judgement threshold, or cross-snapshot reconstruction. Still observable in principle but with a documented caveat.',
  },
  C: {
    color:    '#F59E0B',  // amber
    bg:       'rgba(245,158,11,0.12)',
    border:   'rgba(245,158,11,0.25)',
    label:    'Derived',
    headline: 'Grade C — Derived',
    body:     'Estimated from empirical patterns, single-snapshot approximation of a multi-snapshot definition, or model-based. Highest interpretation risk — use with discretion.',
  },
}

// Common population codes → human-readable labels for tooltip disclosure
const POPULATION_LABELS = {
  total_originated:      'all deals ever originated (lifetime)',
  active_outstanding:    'active deals, outstanding-weighted',
  active_pv:             'active deals, face-value-weighted',
  completed_only:        'closed / resolved deals only',
  clean_book:            'stale-filtered book (loss + zombie stripped)',
  loss_subset:           'defaulted deals only',
  zombie_subset:         'operationally stale deals',
  snapshot_date_state:   'point-in-time snapshot, not a rate',
}

export default function ConfidenceBadge({
  confidence,
  population,
  method,
  note,
  size = 'sm',
  inline = false,
}) {
  const cfg = CONFIDENCE[confidence]
  if (!cfg) return null

  // Build tooltip body — Framework §17 disclosure.
  // Format:
  //   Grade A — Observed
  //   <body>
  //   Population: <label>
  //   Method: <method>
  //   <note>
  const tooltipLines = [cfg.headline, cfg.body]
  if (population) {
    const popLabel = POPULATION_LABELS[population]
    tooltipLines.push('')
    tooltipLines.push(
      popLabel
        ? `Population: ${population} — ${popLabel}`
        : `Population: ${population}`
    )
  }
  if (method) {
    tooltipLines.push(`Method: ${method}`)
  }
  if (note) {
    tooltipLines.push('')
    tooltipLines.push(note)
  }
  const tooltip = tooltipLines.join('\n')

  const fontSize = size === 'md' ? 10 : 8
  const padding  = size === 'md' ? '2px 6px' : '1px 5px'

  const pillStyle = {
    display: inline ? 'inline-flex' : 'inline-block',
    alignItems: 'center',
    fontSize,
    fontWeight: 700,
    letterSpacing: '0.05em',
    padding,
    borderRadius: 4,
    color: cfg.color,
    background: cfg.bg,
    border: `1px solid ${cfg.border}`,
    cursor: 'help',
    fontFamily: 'var(--font-mono)',
    userSelect: 'none',
    verticalAlign: 'middle',
  }

  return (
    <span
      title={tooltip}
      style={pillStyle}
      role="status"
      aria-label={`Data confidence ${confidence} — ${cfg.label}${population ? `, population ${population}` : ''}`}
    >
      {confidence}
    </span>
  )
}

// ── Companion: PopulationPill ──────────────────────────────────────────────
// Explicit population-only badge. Useful on detail views where confidence
// is already shown separately and you want to name the population alongside
// a metric value.
//
// Usage:
//   <PopulationPill population="clean_book" />
//   <PopulationPill population="active_outstanding" label="Covenant-bound" />

export function PopulationPill({ population, label }) {
  if (!population) return null
  const humanLabel = label || population
  const title = POPULATION_LABELS[population]
    ? `Population: ${population} — ${POPULATION_LABELS[population]}`
    : `Population: ${population}`
  return (
    <span
      title={title}
      style={{
        display: 'inline-block',
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: '0.04em',
        padding: '2px 6px',
        borderRadius: 3,
        color: 'var(--text-muted)',
        background: 'rgba(132,148,167,0.08)',
        border: '1px solid var(--border)',
        cursor: 'help',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {humanLabel}
    </span>
  )
}
