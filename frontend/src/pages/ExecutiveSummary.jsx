import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import { getExecutiveSummary } from '../services/api'

const SEVERITY_STYLES = {
  critical: { border: '#F06060', bg: 'rgba(240,96,96,0.06)', badge: '#F06060', label: 'Critical' },
  warning:  { border: '#C9A84C', bg: 'rgba(201,168,76,0.06)', badge: '#C9A84C', label: 'Warning' },
  positive: { border: '#2DD4BF', bg: 'rgba(45,212,191,0.06)', badge: '#2DD4BF', label: 'Positive' },
}

export default function ExecutiveSummary() {
  const { company, product, snapshot, currency, asOfDate } = useCompany()
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [meta, setMeta] = useState(null)

  const basePath = `/company/${company}/${product}`

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const snap = snapshot?.filename || snapshot
      const data = await getExecutiveSummary(company, product, snap, currency, asOfDate)
      setFindings(data.findings || [])
      setMeta({ generated_at: data.generated_at, coverage: data.context_coverage })
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to generate summary')
    } finally {
      setLoading(false)
    }
  }

  const tabUrl = (slug) => {
    if (!slug) return null
    // Map to tape or portfolio route
    const portfolioTabs = ['borrowing-base', 'concentration-limits', 'covenants', 'invoices', 'payments', 'bank-statements']
    const section = portfolioTabs.includes(slug) ? 'portfolio' : 'tape'
    return `${basePath}/${section}/${slug}`
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Executive Summary
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            AI-powered analysis of all portfolio metrics — top findings ranked by business impact
          </p>
        </div>

        <button
          onClick={generate}
          disabled={loading}
          style={{
            padding: '10px 24px',
            borderRadius: 6,
            border: loading ? '1px solid var(--border)' : '1px solid var(--gold)',
            background: loading ? 'var(--bg-surface)' : 'transparent',
            color: loading ? 'var(--text-muted)' : 'var(--gold)',
            fontSize: 12,
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all var(--transition-fast)',
          }}
        >
          {loading && (
            <span style={{
              width: 14, height: 14, border: '2px solid var(--border)',
              borderTop: '2px solid var(--gold)', borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
          )}
          {loading ? 'Analyzing...' : findings ? 'Regenerate' : 'Generate Summary'}
        </button>
      </div>

      {/* Meta info */}
      {meta && (
        <div style={{
          display: 'flex', gap: 16, marginBottom: 20,
          fontSize: 10, color: 'var(--text-muted)',
        }}>
          <span>Analyzed {meta.coverage} metrics</span>
          <span>Generated {new Date(meta.generated_at).toLocaleString()}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 6,
          background: 'rgba(240,96,96,0.08)', border: '1px solid rgba(240,96,96,0.2)',
          color: '#F06060', fontSize: 12, marginBottom: 20,
        }}>
          {error}
        </div>
      )}

      {/* Empty state */}
      {!findings && !loading && !error && (
        <div style={{
          padding: '60px 24px', textAlign: 'center',
          border: '1px dashed var(--border)', borderRadius: 8,
          color: 'var(--text-muted)',
        }}>
          <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v6m0 0H3m6 0h12m0 0V5m0 4v10a2 2 0 01-2 2H5a2 2 0 01-2-2V9" />
            </svg>
          </div>
          <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>No summary generated yet</p>
          <p style={{ fontSize: 11 }}>Click "Generate Summary" to analyze all portfolio metrics and surface the top findings.</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1,2,3,4,5].map(i => (
            <div key={i} style={{
              height: 100, borderRadius: 8,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              animation: 'pulse 1.5s ease-in-out infinite',
              opacity: 1 - i * 0.1,
            }} />
          ))}
        </div>
      )}

      {/* Findings */}
      <AnimatePresence>
        {findings && findings.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            {findings.map((f, i) => {
              const sev = SEVERITY_STYLES[f.severity] || SEVERITY_STYLES.warning
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  style={{
                    padding: '16px 20px',
                    borderRadius: 8,
                    background: sev.bg,
                    border: `1px solid ${sev.border}22`,
                    borderLeft: `3px solid ${sev.border}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{
                          fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3,
                          background: `${sev.badge}18`, color: sev.badge,
                          textTransform: 'uppercase', letterSpacing: '0.05em',
                        }}>
                          {sev.label}
                        </span>
                        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>#{f.rank}</span>
                      </div>

                      <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>
                        {f.title}
                      </h3>

                      <p style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)', margin: 0 }}>
                        {f.explanation}
                      </p>

                      {f.data_points && f.data_points.length > 0 && (
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                          {f.data_points.map((dp, j) => (
                            <span key={j} style={{
                              fontSize: 10, fontFamily: 'IBM Plex Mono, monospace',
                              padding: '2px 8px', borderRadius: 4,
                              background: 'rgba(255,255,255,0.04)', color: 'var(--text-primary)',
                              border: '1px solid var(--border)',
                            }}>
                              {dp}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {f.tab && (
                      <Link
                        to={tabUrl(f.tab)}
                        style={{
                          fontSize: 10, fontWeight: 500, color: 'var(--gold)',
                          textDecoration: 'none', whiteSpace: 'nowrap',
                          padding: '4px 10px', borderRadius: 4,
                          border: '1px solid rgba(201,168,76,0.2)',
                          transition: 'all var(--transition-fast)',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(201,168,76,0.08)' }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
                      >
                        View Tab
                      </Link>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  )
}
