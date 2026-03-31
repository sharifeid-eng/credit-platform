import KpiCard from '../KpiCard'
import WaterfallTable from './WaterfallTable'

export default function BorrowingBase({ data }) {
  const d = data
  const ccy = data.currency || 'AED'
  const fmt = (v) => `${ccy} ${(v / 1_000_000).toFixed(1)}M`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* KPI cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <KpiCard label="Total A/R"        value={fmt(d.kpis.total_ar)}          sub="Gross receivables"                color="gold" />
        <KpiCard label="Eligible A/R"     value={fmt(d.kpis.eligible_ar)}       sub={`${fmt(d.kpis.ineligible)} ineligible`} color="blue" />
        <KpiCard label="Borrowing Base"   value={fmt(d.kpis.borrowing_base)}    sub={`${((d.kpis.borrowing_base / d.kpis.facility_limit) * 100).toFixed(1)}% of facility`} color="teal" />
        <KpiCard label="Available to Draw" value={fmt(d.kpis.available_to_draw)} sub="Constrained by BB"                color="teal" />
      </div>

      {/* Waterfall table */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          Borrowing Base Waterfall
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
          Step-by-step calculation from gross receivables to borrowing base
        </div>
        <WaterfallTable data={d.waterfall} currency={ccy} />
      </div>

      {/* Movement Attribution */}
      {d.movement && (
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          padding: '20px',
        }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                Movement Attribution
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                Period-over-period drivers of borrowing base change
              </div>
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px',
              borderRadius: 20,
              background: d.movement.net_change >= 0 ? 'rgba(45,212,191,0.1)' : 'rgba(240,96,96,0.1)',
              border: `1px solid ${d.movement.net_change >= 0 ? 'rgba(45,212,191,0.3)' : 'rgba(240,96,96,0.3)'}`,
            }}>
              <span style={{
                fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: d.movement.net_change >= 0 ? 'var(--accent-teal)' : 'var(--accent-red)',
              }}>
                {d.movement.net_change >= 0 ? '+' : ''}{fmt(d.movement.net_change)}
              </span>
              <span style={{
                fontSize: 11,
                color: d.movement.net_change >= 0 ? 'var(--accent-teal)' : 'var(--accent-red)',
              }}>
                ({d.movement.net_change_pct >= 0 ? '+' : ''}{d.movement.net_change_pct.toFixed(1)}%)
              </span>
            </div>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 16 }}>
            {d.movement.from_date} → {d.movement.to_date}
          </div>

          {/* Steps */}
          {d.movement.steps.map((step, i) => {
            const isStart = step.type === 'start'
            const isEnd = step.type === 'end'
            const isDelta = step.type === 'delta'
            const positive = step.value >= 0
            const maxAbs = Math.max(...d.movement.steps.filter(s => s.type === 'delta').map(s => Math.abs(s.value)), 1)
            const barWidth = isDelta ? Math.min(Math.abs(step.value) / maxAbs * 80 + 5, 85) : 0

            return (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0',
                borderTop: i === 0 ? 'none' : isEnd ? '1px solid var(--border)' : '1px solid rgba(36,48,64,0.5)',
                marginTop: isEnd ? 4 : 0,
                paddingTop: isEnd ? 12 : 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
                  {/* Mini bar for deltas */}
                  <div style={{ width: 100, height: 6, borderRadius: 3, background: 'var(--bg-base)', position: 'relative', flexShrink: 0 }}>
                    {isDelta && (
                      <>
                        <div style={{
                          position: 'absolute',
                          left: positive ? '50%' : `calc(50% - ${barWidth / 2}%)`,
                          width: `${barWidth / 2}%`,
                          height: '100%',
                          borderRadius: 3,
                          background: positive ? 'var(--accent-teal)' : 'var(--accent-red)',
                          opacity: 0.75,
                        }} />
                        <div style={{ position: 'absolute', left: '50%', top: -1, bottom: -1, width: 1, background: 'var(--border)' }} />
                      </>
                    )}
                  </div>
                  <span style={{
                    fontSize: isDelta ? 11 : 12,
                    fontWeight: isEnd ? 700 : isStart ? 500 : 400,
                    color: isEnd ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}>
                    {step.label}
                  </span>
                </div>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: isDelta ? 12 : 13,
                  fontWeight: isEnd ? 700 : 500,
                  color: isStart || isEnd
                    ? 'var(--text-primary)'
                    : positive ? 'var(--accent-teal)' : 'var(--accent-red)',
                }}>
                  {isDelta && (positive ? '+' : '')}{fmt(step.value)}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* Two-column: Advance Rates + Facility Capacity */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 14 }}>
        {/* Advance Rates */}
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          padding: '20px',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            Advance Rates
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 16 }}>
            Maximum advance rates by segment
          </div>

          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 70px 100px 100px',
            padding: '8px 0', borderBottom: '1px solid var(--border)',
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)',
          }}>
            <div>{d.advance_rates?.[0]?.region ? 'Region' : 'Product'}</div>
            <div style={{ textAlign: 'right' }}>Rate</div>
            <div style={{ textAlign: 'right' }}>Eligible</div>
            <div style={{ textAlign: 'right' }}>Advanceable</div>
          </div>

          {d.advance_rates.map((r, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1fr 70px 100px 100px',
              padding: '10px 0',
              borderBottom: i < d.advance_rates.length - 1 ? '1px solid var(--border)' : 'none',
              fontSize: 12,
            }}>
              <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                <span style={{
                  display: 'inline-block', width: 8, height: 8, borderRadius: '50%', marginRight: 8,
                  background: ['var(--gold)', 'var(--accent-teal)', 'var(--accent-blue)'][i],
                }} />
                {r.region || r.product}
              </div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--accent-teal)', fontWeight: 600 }}>
                {((r.rate || r.advance_rate || 0) * 100).toFixed(0)}%
              </div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                {fmt(r.eligible_ar ?? r.eligible ?? 0)}
              </div>
              <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                {fmt(r.advanceable)}
              </div>
            </div>
          ))}
        </div>

        {/* Facility Capacity */}
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-md)',
          padding: '20px',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            Facility Capacity
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 20 }}>
            Utilization of the credit facility
          </div>

          {/* Capacity bar */}
          <div style={{ marginBottom: 16 }}>
            <div style={{
              height: 28, borderRadius: 6,
              background: 'var(--border)',
              overflow: 'hidden',
              display: 'flex',
            }}>
              <div style={{
                width: `${(d.facility.outstanding / d.facility.limit) * 100}%`,
                background: 'var(--gold)',
                height: '100%',
                transition: 'width 0.3s',
              }} />
              <div style={{
                width: `${(d.facility.available / d.facility.limit) * 100}%`,
                background: 'var(--accent-teal)',
                height: '100%',
                opacity: 0.5,
                transition: 'width 0.3s',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
              <div style={{ display: 'flex', gap: 16, fontSize: 10 }}>
                <span><span style={{ color: 'var(--gold)' }}>●</span> Outstanding {((d.facility.outstanding / d.facility.limit) * 100).toFixed(0)}%</span>
                <span><span style={{ color: 'var(--accent-teal)' }}>●</span> Available {((d.facility.available / d.facility.limit) * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {/* Segment breakdown */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
              Segment Breakdown
            </div>
            {[
              { label: 'Outstanding',   value: d.facility.outstanding, color: 'var(--gold)' },
              { label: 'Available',      value: d.facility.available,   color: 'var(--accent-teal)' },
              { label: 'Facility Limit', value: d.facility.limit,       color: 'var(--text-muted)' },
            ].map((s, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', padding: '5px 0',
                fontSize: 12,
              }}>
                <span style={{ color: 'var(--text-muted)' }}>
                  <span style={{ color: s.color, marginRight: 6 }}>●</span>{s.label}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 500 }}>
                  {fmt(s.value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
