import { useState, useEffect } from 'react'
import ChartPanel from '../ChartPanel'
import { getDenialFunnelChart } from '../../services/api'
import { fmtMoney, fmtPct } from '../../styles/chartTheme'

const STAGE_COLORS = {
  'Total Portfolio':  'var(--gold)',
  'Collected':        'var(--teal)',
  'Pending Response': 'var(--blue)',
  'Denied':           'var(--red)',
  'Provisioned':      '#A78BFA',
}

export default function DenialFunnelChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    getDenialFunnelChart(company, product, snapshot, currency, asOfDate)
      .then(res => { setData(res); setError(null) })
      .catch(() => setError('Failed to load denial funnel data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  const stages = data?.stages ?? []
  const maxAmount = stages.length ? stages[0].amount : 1

  return (
    <ChartPanel
      title="Resolution Pipeline"
      subtitle="Claim resolution funnel — from total portfolio to final outcomes"
      loading={loading} error={error} minHeight={200}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {stages.map((s, i) => {
          const barWidth = Math.max((s.amount / maxAmount) * 100, 2)
          const color = STAGE_COLORS[s.stage] ?? 'var(--text-muted)'
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {/* Label */}
              <div style={{ width: 120, fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', textAlign: 'right', flexShrink: 0 }}>
                {s.stage}
              </div>
              {/* Bar */}
              <div style={{ flex: 1, position: 'relative', height: 28 }}>
                <div style={{
                  width: `${barWidth}%`, height: '100%',
                  background: color, borderRadius: 4, opacity: 0.25,
                  position: 'absolute', top: 0, left: 0,
                }} />
                <div style={{
                  width: `${barWidth}%`, height: '100%',
                  display: 'flex', alignItems: 'center', paddingLeft: 10,
                  position: 'relative', zIndex: 1,
                }}>
                  <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>
                    {fmtMoney(s.amount, currency)}
                  </span>
                </div>
              </div>
              {/* Percentage */}
              <div style={{ width: 55, fontSize: 11, fontFamily: 'var(--font-mono)', color, textAlign: 'right', flexShrink: 0 }}>
                {fmtPct(s.pct)}
              </div>
            </div>
          )
        })}
      </div>

      {/* Bottom summary */}
      {data && (
        <div style={{ display: 'flex', gap: 24, marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Net Loss: <span style={{ color: 'var(--red)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{fmtMoney(data.net_loss, currency)}</span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Provision Recovery: <span style={{ color: '#A78BFA', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{fmtPct(data.recovery_rate)}</span>
          </div>
        </div>
      )}
    </ChartPanel>
  )
}
