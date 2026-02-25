/**
 * chartTheme.jsx — shared Recharts props for the dark design system
 * Import what you need in each chart component.
 */

export const COLORS = {
  gold:  '#C9A84C',
  teal:  '#2DD4BF',
  red:   '#F06060',
  blue:  '#5B8DEF',
  muted: '#2A3548',
  text:  '#4A5568',
  grid:  '#1E2736',
}

/** Standard CartesianGrid props */
export const gridProps = {
  strokeDasharray: '3 3',
  stroke: COLORS.grid,
  vertical: false,
}

/** Standard XAxis props */
export const xAxisProps = {
  tick: { fill: COLORS.text, fontSize: 10, fontFamily: 'IBM Plex Mono' },
  axisLine: { stroke: COLORS.grid },
  tickLine: false,
}

/** Standard YAxis props */
export const yAxisProps = {
  tick: { fill: COLORS.text, fontSize: 10, fontFamily: 'IBM Plex Mono' },
  axisLine: false,
  tickLine: false,
  width: 52,
}

/** Standard Tooltip style */
export const tooltipStyle = {
  contentStyle: {
    background: '#0C1018',
    border: '1px solid #1E2736',
    borderRadius: 8,
    fontSize: 11,
    fontFamily: 'IBM Plex Mono',
    color: '#E8EAF0',
    boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
  },
  labelStyle: {
    color: '#8A94A8',
    fontSize: 10,
    marginBottom: 4,
    fontFamily: 'Inter',
  },
  itemStyle: { color: '#E8EAF0' },
  cursor: { fill: 'rgba(255,255,255,0.03)' },
}

/** Standard Legend props */
export const legendProps = {
  wrapperStyle: {
    fontSize: 10,
    fontFamily: 'Inter',
    color: '#4A5568',
    paddingTop: 8,
  },
}

/**
 * Gradient defs for area/bar charts.
 * Usage: place <GradientDefs /> inside your <BarChart> or <AreaChart>,
 * then reference with fill="url(#grad-gold)" etc.
 */
export function GradientDefs() {
  return (
    <defs>
      {[
        { id: 'grad-gold', color: '#C9A84C' },
        { id: 'grad-teal', color: '#2DD4BF' },
        { id: 'grad-red',  color: '#F06060' },
        { id: 'grad-blue', color: '#5B8DEF' },
      ].map(({ id, color }) => (
        <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity={0.35} />
          <stop offset="100%" stopColor={color} stopOpacity={0.03} />
        </linearGradient>
      ))}
    </defs>
  )
}

/** Format large numbers: 1_400_000 → "$1.4M" */
export function fmtMoney(val, currency = 'USD') {
  if (val === null || val === undefined) return '—'
  const symbol = currency === 'AED' ? 'AED ' : '$'
  if (Math.abs(val) >= 1_000_000) return `${symbol}${(val / 1_000_000).toFixed(1)}M`
  if (Math.abs(val) >= 1_000)     return `${symbol}${(val / 1_000).toFixed(0)}K`
  return `${symbol}${val.toFixed(0)}`
}

/** Format percentage */
export function fmtPct(val) {
  if (val === null || val === undefined) return '—'
  return `${val.toFixed(1)}%`
}