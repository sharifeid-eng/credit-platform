import { useState, useEffect } from 'react'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer, Area,
} from 'recharts'
import ChartPanel from '../../ChartPanel'
import { getSilqCdrCcr } from '../../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps, COLORS,
} from '../../../styles/chartTheme.jsx'

function KpiTile({ label, value, color, sub }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '12px 16px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontFamily: 'IBM Plex Mono', color: color ?? 'var(--text-primary)', fontWeight: 600 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{sub}</div>}
    </div>
  )
}

const fmt1 = v => v == null ? '—' : `${Number(v).toFixed(1)}%`
const fmt2 = v => v == null ? '—' : `${Number(v).toFixed(2)}%`

export default function SilqCdrCcrChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getSilqCdrCcr(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load CDR/CCR data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (data && !data.available) {
    return (
      <ChartPanel title="CDR / CCR — Conditional Rates" loading={false} error={null}>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Insufficient data to compute CDR/CCR.
        </p>
      </ChartPanel>
    )
  }

  const vintages = data?.vintages ?? []
  const portfolio = data?.portfolio ?? {}

  const chartData = vintages.map(v => ({
    vintage: v.vintage,
    CDR: v.cdr,
    CCR: v.ccr,
    net_spread: v.net_spread,
    months: v.months_outstanding,
  }))

  const spreadColor = (portfolio.net_spread ?? 0) >= 0 ? COLORS.teal : COLORS.red

  return (
    <ChartPanel title="CDR / CCR — Conditional Rates by Vintage" loading={loading} error={error}>
      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 20 }}>
        <KpiTile
          label="Portfolio CDR (ann.)"
          value={fmt2(portfolio.cdr)}
          color={COLORS.red}
          sub="conditional default rate"
        />
        <KpiTile
          label="Portfolio CCR (ann.)"
          value={fmt2(portfolio.ccr)}
          color={COLORS.teal}
          sub="conditional collection rate"
        />
        <KpiTile
          label="Net Spread (CCR − CDR)"
          value={fmt2(portfolio.net_spread)}
          color={spreadColor}
          sub="net monthly spread"
        />
        <KpiTile
          label="Avg Vintage Age"
          value={portfolio.avg_vintage_age_months != null ? `${portfolio.avg_vintage_age_months.toFixed(1)} mo` : '—'}
          color="var(--text-primary)"
          sub="volume-weighted"
        />
      </div>

      {/* Methodology note */}
      <div style={{
        background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 6,
        padding: '8px 12px', marginBottom: 16, fontSize: 12, color: 'var(--text-muted)',
        lineHeight: 1.5,
      }}>
        <strong style={{ color: 'var(--text-primary)' }}>How to read:</strong>{' '}
        CDR uses DPD&gt;90 outstanding as the default proxy. CCR uses total repaid amount.
        Both are annualized by vintage age so young and mature cohorts are directly comparable.
        Net spread = CCR − CDR; positive spread means collections outpace defaults on a normalized basis.
      </div>

      {/* CDR / CCR line chart */}
      <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--text-muted)' }}>
        Annualized conditional rates by origination vintage (%)
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 20, left: 0, bottom: 40 }}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="vintage"
            {...xAxisProps}
            angle={-40}
            textAnchor="end"
            interval={0}
            height={60}
          />
          <YAxis
            {...yAxisProps}
            tickFormatter={v => `${v.toFixed(1)}%`}
            label={{ value: 'Annualized Rate (%)', angle: -90, position: 'insideLeft', fill: COLORS.text, fontSize: 10, dy: 60 }}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(val, name) => [`${Number(val).toFixed(2)}%`, name]}
            labelFormatter={l => `Vintage: ${l}`}
          />
          <Legend {...legendProps} />
          <Area
            type="monotone"
            dataKey="CCR"
            fill={COLORS.teal}
            fillOpacity={0.08}
            stroke="none"
            legendType="none"
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="CDR"
            stroke={COLORS.red}
            strokeWidth={2}
            dot={{ r: 3, fill: COLORS.red }}
            name="CDR (ann.)"
          />
          <Line
            type="monotone"
            dataKey="CCR"
            stroke={COLORS.teal}
            strokeWidth={2}
            dot={{ r: 3, fill: COLORS.teal }}
            name="CCR (ann.)"
          />
          {portfolio.cdr != null && (
            <ReferenceLine
              y={portfolio.cdr}
              stroke={COLORS.red}
              strokeDasharray="4 3"
              strokeOpacity={0.5}
              label={{ value: `Avg CDR ${fmt1(portfolio.cdr)}`, fill: COLORS.red, fontSize: 10, position: 'right' }}
            />
          )}
          {portfolio.ccr != null && (
            <ReferenceLine
              y={portfolio.ccr}
              stroke={COLORS.teal}
              strokeDasharray="4 3"
              strokeOpacity={0.5}
              label={{ value: `Avg CCR ${fmt1(portfolio.ccr)}`, fill: COLORS.teal, fontSize: 10, position: 'right' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Net spread line */}
      {chartData.length > 0 && (
        <>
          <div style={{ marginTop: 20, marginBottom: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            Net Spread by Vintage (CCR − CDR, %)
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 20, left: 0, bottom: 40 }}>
              <CartesianGrid {...gridProps} />
              <XAxis
                dataKey="vintage"
                {...xAxisProps}
                angle={-40}
                textAnchor="end"
                interval={0}
                height={60}
              />
              <YAxis
                {...yAxisProps}
                tickFormatter={v => `${v.toFixed(1)}%`}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(val) => [`${Number(val).toFixed(2)}%`, 'Net Spread']}
                labelFormatter={l => `Vintage: ${l}`}
              />
              <ReferenceLine y={0} stroke="var(--border)" />
              <Line
                type="monotone"
                dataKey="net_spread"
                stroke={COLORS.gold}
                strokeWidth={2}
                dot={(props) => {
                  const { cx, cy, payload, index } = props
                  const c = (payload.net_spread ?? 0) >= 0 ? COLORS.teal : COLORS.red
                  return <circle key={index} cx={cx} cy={cy} r={4} fill={c} stroke={c} />
                }}
                name="Net Spread"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </ChartPanel>
  )
}
