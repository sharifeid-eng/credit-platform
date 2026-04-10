import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalRiskFlags } from '../../services/api'
import ChartPanel from '../ChartPanel'

const SEV_STYLES = {
  high:   { bg: 'rgba(240,96,96,0.10)', border: 'var(--accent-red)', color: '#F06060', icon: '!' },
  medium: { bg: 'rgba(201,168,76,0.10)', border: 'var(--gold)', color: '#C9A84C', icon: '~' },
  low:    { bg: 'rgba(91,141,239,0.10)', border: '#5B8DEF', color: '#5B8DEF', icon: 'i' },
}

const CAT_LABELS = {
  missing_provision: 'Missing Provision',
  below_market:      'Below Market',
  unusual_term:      'Unusual Term',
  deviation:         'Deviation',
}

export default function RiskAssessment({ company, product }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalRiskFlags(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  if (loading) return <ChartPanel title="Risk Assessment" loading />
  if (!data?.available) return (
    <ChartPanel title="Risk Assessment" subtitle="No legal documents extracted yet." />
  )

  const flags = data.risk_flags || []
  const highCount = flags.filter(f => f.severity === 'high').length
  const medCount = flags.filter(f => f.severity === 'medium').length
  const lowCount = flags.filter(f => f.severity === 'low').length

  return (
    <div>
      {/* Summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[['High', highCount, '#F06060'], ['Medium', medCount, '#C9A84C'], ['Low', lowCount, '#5B8DEF']].map(([label, count, color]) => (
          <div key={label} style={{
            background: `${color}12`, borderRadius: 8, padding: '8px 20px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontSize: 20, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{count}</span>
            <span style={{ fontSize: 11, color, fontWeight: 500 }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Risk Flags */}
      <ChartPanel title="AI Risk Flags" subtitle={`${flags.length} flag${flags.length !== 1 ? 's' : ''} identified`}>
        {flags.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '30px 0',
            color: 'var(--accent-teal)', fontSize: 13,
          }}>
            No significant risk flags identified. Facility agreement appears well-structured.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {flags.map((flag, i) => {
              const s = SEV_STYLES[flag.severity] || SEV_STYLES.low
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  style={{
                    background: s.bg, border: `1px solid ${s.border}30`,
                    borderRadius: 10, padding: 16,
                    borderLeft: `3px solid ${s.color}`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 700,
                      background: `${s.color}20`, color: s.color, textTransform: 'uppercase',
                    }}>
                      {CAT_LABELS[flag.category] || flag.category}
                    </span>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 700,
                      background: `${s.color}20`, color: s.color, textTransform: 'uppercase',
                    }}>
                      {flag.severity}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: flag.recommendation ? 8 : 0 }}>
                    {flag.description}
                  </div>
                  {flag.recommendation && (
                    <div style={{
                      fontSize: 11, color: 'var(--accent-teal)', padding: '6px 10px',
                      background: 'rgba(45,212,191,0.06)', borderRadius: 6, marginTop: 4,
                    }}>
                      Recommendation: {flag.recommendation}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        )}
      </ChartPanel>
    </div>
  )
}
