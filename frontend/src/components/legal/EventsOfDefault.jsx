import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalEventsOfDefault } from '../../services/api'
import ChartPanel from '../ChartPanel'

const SEVERITY_COLORS = {
  payment:       { bg: 'rgba(240,96,96,0.12)', color: '#F06060', label: 'Payment' },
  covenant:      { bg: 'rgba(201,168,76,0.12)', color: '#C9A84C', label: 'Covenant' },
  cross_default: { bg: 'rgba(240,150,60,0.12)', color: '#F0963C', label: 'Cross Default' },
  mac:           { bg: 'rgba(240,96,96,0.12)', color: '#F06060', label: 'MAC' },
  operational:   { bg: 'rgba(91,141,239,0.12)', color: '#5B8DEF', label: 'Operational' },
}

export default function EventsOfDefault({ company, product }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalEventsOfDefault(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  if (loading) return <ChartPanel title="Events of Default" loading />
  if (!data?.available) return (
    <ChartPanel title="Events of Default" subtitle="No legal documents extracted yet." />
  )

  const events = data.events_of_default || []

  // Group by severity
  const grouped = {}
  for (const ev of events) {
    const sev = ev.severity || 'operational'
    if (!grouped[sev]) grouped[sev] = []
    grouped[sev].push(ev)
  }

  return (
    <div>
      {/* Summary strip */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        {Object.entries(grouped).map(([sev, evs]) => {
          const c = SEVERITY_COLORS[sev] || SEVERITY_COLORS.operational
          return (
            <div key={sev} style={{ background: c.bg, borderRadius: 8, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 700, color: c.color, fontFamily: 'var(--font-mono)' }}>{evs.length}</span>
              <span style={{ fontSize: 11, color: c.color, fontWeight: 500 }}>{c.label}</span>
            </div>
          )
        })}
      </div>

      {/* Events list */}
      <ChartPanel title="Default Triggers" subtitle={`${events.length} events of default extracted`}>
        <div style={{ display: 'grid', gap: 10 }}>
          {events.map((ev, i) => {
            const c = SEVERITY_COLORS[ev.severity] || SEVERITY_COLORS.operational
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                style={{
                  background: 'var(--bg-deep)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '12px 16px',
                  borderLeft: `3px solid ${c.color}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                      {ev.trigger}
                    </div>
                    {ev.section_ref && (
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                        {ev.section_ref}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                      background: c.bg, color: c.color, textTransform: 'uppercase',
                    }}>
                      {c.label}
                    </span>
                    {ev.cure_period_days != null && (
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                        background: 'rgba(91,141,239,0.1)', color: '#5B8DEF',
                      }}>
                        {ev.cure_period_days}d cure
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </ChartPanel>
    </div>
  )
}
