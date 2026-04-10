import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalReporting } from '../../services/api'
import ChartPanel from '../ChartPanel'

const FREQ_COLORS = {
  monthly:   { bg: 'rgba(91,141,239,0.12)', color: '#5B8DEF' },
  quarterly: { bg: 'rgba(201,168,76,0.12)', color: '#C9A84C' },
  annual:    { bg: 'rgba(45,212,191,0.12)', color: '#2DD4BF' },
  per_draw:  { bg: 'rgba(240,96,96,0.12)', color: '#F06060' },
  ad_hoc:    { bg: 'rgba(132,148,167,0.12)', color: '#8494A7' },
}

export default function ReportingCalendar({ company, product }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalReporting(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  if (loading) return <ChartPanel title="Reporting & Obligations" loading />
  if (!data?.available) return (
    <ChartPanel title="Reporting & Obligations" subtitle="No legal documents extracted yet." />
  )

  const requirements = data.reporting_requirements || []
  const waterfallNormal = data.waterfall_normal || []
  const waterfallDefault = data.waterfall_default || []

  return (
    <div>
      {/* Reporting Requirements */}
      <ChartPanel title="Reporting Obligations" subtitle={`${requirements.length} reporting requirements`}>
        {requirements.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
            No reporting requirements found in the document.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            {requirements.map((req, i) => {
              const fc = FREQ_COLORS[req.frequency] || FREQ_COLORS.ad_hoc
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  style={{
                    background: 'var(--bg-deep)', border: '1px solid var(--border)',
                    borderRadius: 8, padding: '12px 16px',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{req.name}</div>
                    {req.description && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{req.description}</div>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                      background: fc.bg, color: fc.color, textTransform: 'uppercase',
                    }}>
                      {req.frequency}
                    </span>
                    {req.due_days_after_period != null && (
                      <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 600,
                        background: 'rgba(132,148,167,0.1)', color: '#8494A7',
                      }}>
                        +{req.due_days_after_period}d
                      </span>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </ChartPanel>

      {/* Payment Waterfall */}
      {(waterfallNormal.length > 0 || waterfallDefault.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <ChartPanel title="Normal Waterfall" subtitle="Payment priority — normal operations">
            {waterfallNormal.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  display: 'flex', gap: 12, padding: '8px 0',
                  borderBottom: i < waterfallNormal.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                <span style={{
                  width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(45,212,191,0.12)', color: '#2DD4BF', fontSize: 11, fontWeight: 700, flexShrink: 0,
                }}>
                  {step.priority}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5 }}>{step.description}</span>
              </motion.div>
            ))}
          </ChartPanel>

          <ChartPanel title="Default Waterfall" subtitle="Payment priority — upon event of default">
            {waterfallDefault.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  display: 'flex', gap: 12, padding: '8px 0',
                  borderBottom: i < waterfallDefault.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                <span style={{
                  width: 24, height: 24, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(240,96,96,0.12)', color: '#F06060', fontSize: 11, fontWeight: 700, flexShrink: 0,
                }}>
                  {step.priority}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-primary)', lineHeight: 1.5 }}>{step.description}</span>
              </motion.div>
            ))}
          </ChartPanel>
        </div>
      )}
    </div>
  )
}
