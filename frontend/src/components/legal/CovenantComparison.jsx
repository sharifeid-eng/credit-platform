import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalComplianceComparison } from '../../services/api'
import ChartPanel from '../ChartPanel'
import KpiCard from '../KpiCard'

export default function CovenantComparison({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalComplianceComparison(company, product, snapshot, currency, asOfDate)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (loading) return <ChartPanel title="Covenants & Limits — Document vs Live" loading />
  if (!data?.available) return (
    <ChartPanel title="Covenants & Limits" subtitle="Upload a facility agreement to compare document terms against live portfolio metrics." />
  )

  const covs = data.covenant_comparison || []
  const concs = data.concentration_comparison || []
  const summary = data.summary || {}

  return (
    <div>
      {/* Summary KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <KpiCard label="Terms Compared" value={summary.total_terms_compared || 0} index={0} />
        <KpiCard label="Compliant" value={summary.compliant || 0} index={1} subtitle="Within thresholds" />
        <KpiCard label="Breaches" value={summary.breaches || 0} index={2} subtitle={summary.breaches > 0 ? 'Action required' : 'None'} />
        <KpiCard label="Discrepancies" value={summary.discrepancies || 0} index={3} subtitle="Doc vs platform default" />
      </div>

      {/* Covenant Comparison */}
      <ChartPanel title="Covenant Comparison" subtitle="Document thresholds vs live portfolio values">
        {covs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
            No covenants to compare.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }}>
            {covs.map((cov, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  background: 'var(--bg-deep)', border: `1px solid ${cov.compliant === false ? 'var(--accent-red)' : cov.discrepancy ? 'var(--gold)' : 'var(--border)'}`,
                  borderRadius: 10, padding: 16,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{cov.name}</div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {cov.compliant === false && <Badge color="#F06060" label="BREACH" />}
                    {cov.compliant === true && <Badge color="#2DD4BF" label="COMPLIANT" />}
                    {cov.discrepancy && <Badge color="#C9A84C" label="DISCREPANCY" />}
                    {!cov.matched && <Badge color="#8494A7" label="NO MATCH" />}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                  <MetricBox label="Document Threshold" value={fmtThreshold(cov.doc_threshold, cov.doc_direction)} color="var(--gold)" />
                  <MetricBox label="Live Value" value={fmtPct(cov.live_value)} color={cov.compliant === false ? 'var(--accent-red)' : 'var(--accent-teal)'} />
                  <MetricBox label="Breach Distance" value={cov.breach_distance_pct != null ? `${cov.breach_distance_pct.toFixed(1)}%` : '—'} color={cov.breach_distance_pct != null && cov.breach_distance_pct < 20 ? 'var(--gold)' : 'var(--text-muted)'} />
                </div>

                {cov.discrepancy && cov.hardcoded_threshold != null && (
                  <div style={{ marginTop: 8, fontSize: 10, color: 'var(--gold)', padding: '4px 8px', background: 'rgba(201,168,76,0.08)', borderRadius: 4 }}>
                    Platform default: {fmtPct(cov.hardcoded_threshold)} — Document says: {fmtPct(cov.doc_threshold)}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </ChartPanel>

      {/* Concentration Limit Comparison */}
      {concs.length > 0 && (
        <ChartPanel title="Concentration Limit Comparison" subtitle="Document limits vs live exposure">
          <div style={{ display: 'grid', gap: 12 }}>
            {concs.map((cl, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  background: 'var(--bg-deep)', border: `1px solid ${cl.compliant === false ? 'var(--accent-red)' : 'var(--border)'}`,
                  borderRadius: 10, padding: 16,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{cl.name}</div>
                  {cl.compliant === false ? <Badge color="#F06060" label="BREACH" /> : cl.compliant === true ? <Badge color="#2DD4BF" label="COMPLIANT" /> : null}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                  <MetricBox label="Document Limit" value={fmtPct(cl.doc_limit)} color="var(--gold)" />
                  <MetricBox label="Live Exposure" value={fmtPct(cl.live_current)} color={cl.compliant === false ? 'var(--accent-red)' : 'var(--accent-teal)'} />
                  <MetricBox label="Headroom" value={cl.headroom != null ? `${cl.headroom.toFixed(1)}%` : '—'} color="var(--text-muted)" />
                </div>
              </motion.div>
            ))}
          </div>
        </ChartPanel>
      )}
    </div>
  )
}

function Badge({ color, label }) {
  return (
    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 9, fontWeight: 700, background: `${color}18`, color, textTransform: 'uppercase' }}>
      {label}
    </span>
  )
}

function MetricBox({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</div>
    </div>
  )
}

function fmtPct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtThreshold(v, dir) {
  if (v == null) return '—'
  return `${dir || ''} ${(v * 100).toFixed(1)}%`
}
