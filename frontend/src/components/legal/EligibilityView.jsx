import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalEligibility } from '../../services/api'
import ChartPanel from '../ChartPanel'

export default function EligibilityView({ company, product }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalEligibility(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  if (loading) return <ChartPanel title="Eligibility & Advance Rates" loading />
  if (!data?.available) return (
    <ChartPanel title="Eligibility & Advance Rates" subtitle="No legal documents extracted yet." />
  )

  const criteria = data.eligibility_criteria || []
  const rates = data.advance_rates || []

  return (
    <div>
      {/* Eligibility Criteria */}
      <ChartPanel title="Eligibility Criteria" subtitle={`${criteria.length} criteria extracted`}>
        {criteria.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
            No eligibility criteria found in the document.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Criterion', 'Value', 'Parameter', 'Section', 'Confidence'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {criteria.map((ec, i) => (
                <motion.tr
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{ec.name}</div>
                    <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 2 }}>{ec.description}</div>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--accent-teal)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {ec.value ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    {ec.parameter || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 10 }}>
                    {ec.section_ref || '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <ConfBadge confidence={ec.confidence} />
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartPanel>

      {/* Advance Rates */}
      <ChartPanel title="Advance Rate Schedule" subtitle={`${rates.length} rate${rates.length !== 1 ? 's' : ''} extracted`}>
        {rates.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
            No advance rates found.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(rates.length, 4)}, 1fr)`, gap: 16 }}>
            {rates.map((ar, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 10,
                  padding: 16, textAlign: 'center',
                }}
              >
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                  {ar.category}
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--gold)', fontFamily: 'var(--font-mono)' }}>
                  {(ar.rate * 100).toFixed(0)}%
                </div>
                {ar.condition && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>{ar.condition}</div>
                )}
                <ConfBadge confidence={ar.confidence} style={{ marginTop: 8 }} />
              </motion.div>
            ))}
          </div>
        )}
      </ChartPanel>
    </div>
  )
}

function ConfBadge({ confidence, style }) {
  if (confidence == null) return null
  const color = confidence >= 0.85 ? '#2DD4BF' : confidence >= 0.7 ? '#C9A84C' : '#F06060'
  const label = confidence >= 0.85 ? 'HIGH' : confidence >= 0.7 ? 'MED' : 'LOW'
  return (
    <span style={{
      display: 'inline-block', padding: '1px 6px', borderRadius: 3,
      fontSize: 9, fontWeight: 600, background: `${color}18`, color,
      ...style,
    }}>
      {label}
    </span>
  )
}
