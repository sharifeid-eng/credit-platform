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

const ASSESSMENT_COLORS = {
  healthy:    '#2DD4BF',
  acceptable: '#C9A84C',
  monitor:    '#C9A84C',
  warning:    '#F06060',
  critical:   '#F06060',
  // Capitalize variants (summary table uses capitalized)
  Healthy:    '#2DD4BF',
  Acceptable: '#C9A84C',
  Monitor:    '#C9A84C',
  Warning:    '#F06060',
  Critical:   '#F06060',
}

function SectionHeading({ children }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, margin: '32px 0 20px',
    }}>
      <div style={{ height: 1, flex: 1, background: 'var(--border)' }} />
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
        color: 'var(--gold)', textTransform: 'uppercase',
      }}>
        {children}
      </span>
      <div style={{ height: 1, flex: 1, background: 'var(--border)' }} />
    </div>
  )
}

function NarrativeSection({ section, index }) {
  const paragraphs = (section.content || '').split('\n\n').filter(Boolean)
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      style={{
        padding: '20px 24px',
        borderRadius: 8,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        marginBottom: 12,
      }}
    >
      <h3 style={{
        fontSize: 15, fontWeight: 700, color: 'var(--text-primary)',
        margin: '0 0 12px', letterSpacing: '-0.01em',
      }}>
        {section.title}
      </h3>

      <div style={{ fontSize: 12.5, lineHeight: 1.7, color: 'var(--text-muted)' }}>
        {paragraphs.map((p, i) => (
          <p key={i} style={{ margin: i < paragraphs.length - 1 ? '0 0 10px' : 0 }}>{p}</p>
        ))}
      </div>

      {section.metrics && section.metrics.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
          {section.metrics.map((m, j) => {
            const color = ASSESSMENT_COLORS[m.assessment] || 'var(--text-muted)'
            return (
              <span key={j} style={{
                fontSize: 10, fontFamily: 'var(--font-mono)',
                padding: '3px 10px', borderRadius: 4,
                background: `${color}10`, color,
                border: `1px solid ${color}30`,
                fontWeight: 600,
              }}>
                {m.label} = {m.value}
              </span>
            )
          })}
        </div>
      )}

      {section.conclusion && (
        <div style={{
          marginTop: 14, paddingTop: 12,
          borderTop: '1px solid var(--border)',
          fontSize: 12, fontWeight: 600, color: 'var(--gold)',
          lineHeight: 1.5,
        }}>
          <span style={{ opacity: 0.6, marginRight: 6 }}>▸</span>
          {section.conclusion}
        </div>
      )}
    </motion.div>
  )
}

function SummaryTable({ rows }) {
  if (!rows || rows.length === 0) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        borderRadius: 8, overflow: 'hidden',
        border: '1px solid var(--border)',
        marginBottom: 12,
      }}
    >
      <table style={{
        width: '100%', borderCollapse: 'collapse',
        fontSize: 12, fontFamily: 'var(--font-mono)',
      }}>
        <thead>
          <tr style={{ background: 'var(--bg-deep)' }}>
            <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Metric</th>
            <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Value</th>
            <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Assessment</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const color = ASSESSMENT_COLORS[r.assessment] || 'var(--text-muted)'
            return (
              <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '8px 16px', color: 'var(--text-primary)', fontWeight: 500 }}>{r.metric}</td>
                <td style={{ padding: '8px 16px', color: 'var(--text-primary)' }}>{r.value}</td>
                <td style={{ padding: '8px 16px' }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    fontSize: 10, fontWeight: 600, color,
                  }}>
                    <span style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: color,
                    }} />
                    {r.assessment}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </motion.div>
  )
}

function BottomLine({ text }) {
  if (!text) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        padding: '20px 24px',
        borderRadius: 8,
        background: 'rgba(201,168,76,0.04)',
        border: '1px solid rgba(201,168,76,0.15)',
        borderLeft: '3px solid var(--gold)',
        marginBottom: 12,
      }}
    >
      <div style={{
        fontSize: 11, fontWeight: 700, color: 'var(--gold)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        marginBottom: 10,
      }}>
        Bottom Line
      </div>
      <p style={{
        fontSize: 13, lineHeight: 1.7, color: 'var(--text-primary)',
        margin: 0, fontWeight: 500,
      }}>
        {text}
      </p>
    </motion.div>
  )
}

export default function ExecutiveSummary() {
  const { company, product, snapshot, currency, asOfDate } = useCompany()
  const [narrative, setNarrative] = useState(null)
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
      setNarrative(data.narrative || null)
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

  const hasResults = narrative || (findings && findings.length > 0)

  return (
    <div style={{ padding: '24px 32px', maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Executive Summary
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            AI-powered portfolio analysis — credit memo narrative with key findings ranked by business impact
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
          {loading ? 'Analyzing...' : hasResults ? 'Regenerate' : 'Generate Summary'}
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
      {!hasResults && !loading && !error && (
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
          <p style={{ fontSize: 11 }}>Click "Generate Summary" to produce a credit memo narrative and surface the top findings.</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Narrative skeleton - taller blocks */}
          {[1,2,3,4].map(i => (
            <div key={`n${i}`} style={{
              height: 160, borderRadius: 8,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              animation: 'pulse 1.5s ease-in-out infinite',
              opacity: 0.9 - i * 0.05,
            }} />
          ))}
          {/* Summary table skeleton */}
          <div style={{
            height: 120, borderRadius: 8,
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            animation: 'pulse 1.5s ease-in-out infinite',
            opacity: 0.6,
          }} />
          {/* Findings skeleton - shorter blocks */}
          {[1,2,3].map(i => (
            <div key={`f${i}`} style={{
              height: 80, borderRadius: 8,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              animation: 'pulse 1.5s ease-in-out infinite',
              opacity: 0.5 - i * 0.05,
            }} />
          ))}
        </div>
      )}

      {/* Narrative Analysis */}
      {narrative && !loading && (
        <>
          <SectionHeading>Portfolio Analysis</SectionHeading>

          {narrative.sections && narrative.sections.map((section, i) => (
            <NarrativeSection key={i} section={section} index={i} />
          ))}

          <SummaryTable rows={narrative.summary_table} />
          <BottomLine text={narrative.bottom_line} />
        </>
      )}

      {/* Findings */}
      <AnimatePresence>
        {findings && findings.length > 0 && !loading && (
          <>
            <SectionHeading>Key Findings</SectionHeading>

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
                                fontSize: 10, fontFamily: 'var(--font-mono)',
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
          </>
        )}
      </AnimatePresence>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 0.3; } }
      `}</style>
    </div>
  )
}
