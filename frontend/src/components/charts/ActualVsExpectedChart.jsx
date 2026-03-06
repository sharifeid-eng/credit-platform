import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import ChartPanel from '../ChartPanel'
import { getActualVsExpectedChart, getSummary } from '../../services/api'
import {
  gridProps, xAxisProps, yAxisProps, tooltipStyle, legendProps,
  GradientDefs, fmtMoney, fmtPct, COLORS,
} from '../../styles/chartTheme'

export default function ActualVsExpectedChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [perfPct, setPerfPct] = useState(null)
  const [kpis, setKpis]       = useState(null)
  const [todayLabel, setTodayLabel] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    Promise.all([
      getActualVsExpectedChart(company, product, snapshot, currency, asOfDate),
      getSummary(company, product, snapshot, currency, asOfDate),
    ])
      .then(([res, summary]) => {
        // normalise field names from backend
        const raw = res.data ?? res
        const normalised = raw.map(d => ({
          month:    d.Month ?? d.month,
          actual:   d.cumulative_collected ?? d.actual,
          expected: d.cumulative_expected  ?? d.expected,
        }))
        setData(normalised)
        setPerfPct(res.overall_performance ?? res.performance_pct ?? null)

        // Find today's month label for reference line
        const now = new Date()
        const todayMonth = now.toISOString().slice(0, 7) // "YYYY-MM"
        const months = normalised.map(d => d.month)
        // Find closest month to today
        if (months.length > 0) {
          let closest = months[0]
          for (const m of months) {
            if (m <= todayMonth) closest = m
          }
          setTodayLabel(closest)
        }

        // Build KPI data from summary
        const pv = summary.total_purchase_value ?? 0
        const total_expected = summary.total_expected ?? pv
        const collected = summary.total_collected ?? 0
        const denied = summary.total_denied ?? 0
        const pending = summary.total_pending ?? 0
        const collRate = summary.collection_rate ?? 0
        const denialRate = summary.denial_rate ?? 0
        const pendingRate = summary.pending_rate ?? 0
        const discount = summary.avg_discount ?? summary.discount ?? 0

        setKpis({
          receivable_value: total_expected,
          purchase_price: pv,
          discount: discount * 100, // backend sends 0-1 decimal, we need 0-100 for fmtPct
          collected, collected_pct: collRate,
          pending, pending_pct: pendingRate,
          denied, denied_pct: denialRate,
        })

        setError(null)
      })
      .catch(() => setError('Failed to load actual vs expected data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const action = perfPct != null && (
    <div style={{
      fontSize: 11, fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      color: perfPct >= 100 ? 'var(--teal)' : 'var(--red)',
      background: perfPct >= 100 ? 'var(--teal-muted)' : 'var(--red-muted)',
      padding: '3px 10px', borderRadius: 20,
    }}>
      {fmtPct(perfPct)} of expected collected
    </div>
  )

  return (
    <>
      <ChartPanel
        title="Actual vs Expected Collections"
        subtitle="Cumulative collected amount vs expected total — measures recovery performance"
        loading={loading}
        error={error}
        action={action}
      >
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data}>
            <GradientDefs />
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="month" {...xAxisProps} />
            <YAxis {...yAxisProps} tickFormatter={v => fmtMoney(v, currency)} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v, name) => [fmtMoney(v, currency), name]}
            />
            <Legend {...legendProps} />
            <Area
              type="monotone" dataKey="expected"
              name="Expected" stroke={COLORS.blue} strokeWidth={1.5}
              fill="url(#grad-blue)" strokeDasharray="5 3"
            />
            <Area
              type="monotone" dataKey="actual"
              name="Collected" stroke={COLORS.teal} strokeWidth={2}
              fill="url(#grad-teal)"
            />
            {todayLabel && (
              <ReferenceLine
                x={todayLabel}
                stroke="var(--text-muted)"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: 'Today',
                  position: 'top',
                  fill: 'var(--text-muted)',
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* ── KPI Summary Cards ── */}
      {kpis && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          marginTop: 2,
        }}>
          <KpiTile label="Purchase Price" value={fmtMoney(kpis.purchase_price, currency)} color="var(--gold)" />
          <KpiTile label="Avg Discount" value={fmtPct(kpis.discount)} color="var(--text-primary)" />
          <KpiTile label="Expected Total" value={fmtMoney(kpis.receivable_value, currency)} color="var(--blue)" />
          <KpiTile
            label="Collected So Far"
            value={fmtMoney(kpis.collected, currency)}
            badge={fmtPct(kpis.collected_pct)}
            badgeColor="var(--teal)"
            color="var(--teal)"
          />
          <KpiTile
            label="Pending Response"
            value={fmtMoney(kpis.pending, currency)}
            badge={fmtPct(kpis.pending_pct)}
            badgeColor="var(--blue)"
            color="var(--blue)"
          />
          <KpiTile
            label="Denied So Far"
            value={fmtMoney(kpis.denied, currency)}
            badge={fmtPct(kpis.denied_pct)}
            badgeColor="var(--red)"
            color="var(--red)"
          />
        </div>
      )}
    </>
  )
}

/* ── Compact KPI tile for the summary row ── */
function KpiTile({ label, value, badge, badgeColor, color = 'var(--gold)' }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 16px',
      textAlign: 'center',
    }}>
      <div style={{
        fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
        color, lineHeight: 1,
      }}>
        {value}
      </div>
      {badge && (
        <div style={{
          display: 'inline-block', marginTop: 6,
          fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
          padding: '2px 8px', borderRadius: 20,
          color: badgeColor,
          background: badgeColor === 'var(--teal)' ? 'var(--teal-muted)'
                    : badgeColor === 'var(--red)'  ? 'var(--red-muted)'
                    : 'var(--blue-muted)',
        }}>
          {badge}
        </div>
      )}
    </div>
  )
}
