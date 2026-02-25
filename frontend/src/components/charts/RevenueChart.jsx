import { useState, useEffect } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getRevenueChart } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function RevenueChart({ company, product, snapshot, currency }) {
  const [data, setData]       = useState([])
  const [totals, setTotals]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getRevenueChart(company, product, snapshot, currency)
      .then(res => {
        const raw = res.monthly ?? res.data ?? res
        const normalised = raw.map(d => ({
          month:       d.Month ?? d.month,
          realised:    d.realised_revenue ?? d.realised,
          unrealised:  d.unrealised_revenue ?? d.unrealised,
          gross_margin: d.gross_margin,
        }))
        setData(normalised)
        setTotals(res.totals ?? null)
        setError(null)
      })
      .catch(() => setError('Failed to load revenue data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {totals && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[
            { label: 'Gross Revenue',   value: fmtMoney(totals.gross_revenue, currency), color: 'var(--gold)' },
            { label: 'Setup Fees',      value: fmtMoney(totals.setup_fees, currency),    color: 'var(--blue)' },
            { label: 'Other Fees',      value: fmtMoney(totals.other_fees, currency),    color: 'var(--blue)' },
            { label: 'Gross Margin',    value: fmtPct(totals.gross_margin),               color: 'var(--teal)' },
          ].map((t, i) => (
            <div key={i} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px' }}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 6 }}>{t.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: t.color, letterSpacing: '-0.02em' }}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      <ChartPanel title="Revenue Analysis" subtitle="Monthly realised vs unrealised revenue with gross margin % overlay" loading={loading} error={error}>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={data} barCategoryGap="30%">
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="month" {...xAxisProps} />
            <YAxis yAxisId="amt" {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
            <YAxis yAxisId="pct" orientation="right" {...yAxisProps} tickFormatter={v => fmtPct(v)} width={42} />
            <Tooltip {...tooltipStyle} formatter={(v, name) => name === 'Gross Margin' ? [fmtPct(v), name] : [fmtMoney(v, currency), name]} />
            <Legend {...legendProps} />
            <Bar yAxisId="amt" dataKey="realised"   name="Realised"   stackId="a" fill="url(#grad-teal)" stroke={COLORS.teal} strokeWidth={0} radius={[0,0,0,0]} />
            <Bar yAxisId="amt" dataKey="unrealised" name="Unrealised" stackId="a" fill="url(#grad-blue)" stroke={COLORS.blue} strokeWidth={0} radius={[3,3,0,0]} />
            <Line yAxisId="pct" type="monotone" dataKey="gross_margin" name="Gross Margin" stroke={COLORS.gold} strokeWidth={2} dot={{ fill: COLORS.gold, r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>
    </div>
  )
}