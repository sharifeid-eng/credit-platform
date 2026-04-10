import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalFacilityTerms } from '../../services/api'
import KpiCard from '../KpiCard'
import ChartPanel from '../ChartPanel'

export default function FacilityTerms({ company, product }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalFacilityTerms(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  if (loading) return <ChartPanel title="Facility Terms" loading />
  if (!data?.available) return (
    <ChartPanel title="Facility Terms" subtitle="No legal documents extracted yet. Upload a facility agreement on the Documents tab." />
  )

  const ft = data.facility_terms || {}
  const doc = data.document || {}

  const fmtAmount = (v) => {
    if (!v) return '—'
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
    return v.toLocaleString()
  }

  return (
    <div>
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <KpiCard label="Facility Limit" value={ft.facility_limit ? `${ft.currency || ''} ${fmtAmount(ft.facility_limit)}` : '—'} index={0} confidence={ft.confidence >= 0.9 ? 'A' : ft.confidence >= 0.7 ? 'B' : 'C'} />
        <KpiCard label="Facility Type" value={ft.facility_type || '—'} index={1} />
        <KpiCard label="Maturity" value={ft.maturity_date || '—'} index={2} />
        <KpiCard label="Governing Law" value={ft.governing_law || '—'} index={3} />
      </div>

      {/* Details Table */}
      <ChartPanel title="Facility Details" subtitle={`Extracted from ${doc.filename || 'document'}`}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <tbody>
            {[
              ['Facility Type', ft.facility_type],
              ['Facility Limit', ft.facility_limit ? `${ft.currency || ''} ${fmtAmount(ft.facility_limit)}` : null],
              ['Currency', ft.currency],
              ['Effective Date', ft.effective_date],
              ['Maturity Date', ft.maturity_date],
              ['Commitment Period End', ft.commitment_period_end],
              ['Governing Law', ft.governing_law],
              ['Interest Rate', ft.interest_rate_description],
              ['Parties', ft.parties?.join(', ')],
              ['Section Reference', ft.section_ref],
            ].filter(([, v]) => v).map(([label, value], i) => (
              <motion.tr
                key={label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.03 }}
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 500, width: '30%' }}>{label}</td>
                <td style={{ padding: '10px 12px', color: 'var(--text-primary)' }}>{value}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        <ConfidenceLine confidence={ft.confidence} extractedAt={doc.extracted_at} />
      </ChartPanel>
    </div>
  )
}

function ConfidenceLine({ confidence, extractedAt }) {
  if (!confidence && !extractedAt) return null
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 10, color: 'var(--text-muted)' }}>
      {confidence != null && (
        <span>Extraction confidence: <span style={{ color: confidence >= 0.85 ? 'var(--accent-teal)' : confidence >= 0.7 ? 'var(--gold)' : 'var(--accent-red)' }}>{(confidence * 100).toFixed(0)}%</span></span>
      )}
      {extractedAt && <span>Extracted: {new Date(extractedAt).toLocaleString()}</span>}
    </div>
  )
}
