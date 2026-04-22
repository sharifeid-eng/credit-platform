import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import { streamExecutiveSummary } from '../services/api'
import useBreakpoint from '../hooks/useBreakpoint'

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

function StreamProgressPanel({ stage, history, elapsed, fromCache }) {
  // Renders a live terminal-ish timeline of agent tool calls so the analyst
  // can see what the model is doing. The final entry is marked "active"
  // until the next tool_call lands. See ExecutiveSummary.generate for the
  // source of truth on stage strings.
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const ss = String(elapsed % 60).padStart(2, '0')
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{
        padding: '20px 24px', borderRadius: 8,
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        paddingBottom: 12, marginBottom: 12,
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: fromCache ? '#2DD4BF' : '#C9A84C',
          boxShadow: `0 0 0 3px ${fromCache ? 'rgba(45,212,191,0.15)' : 'rgba(201,168,76,0.15)'}`,
          animation: fromCache ? 'none' : 'pulse 1.5s ease-in-out infinite',
        }} />
        <span style={{
          fontSize: 11, fontWeight: 700, color: fromCache ? '#2DD4BF' : '#C9A84C',
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>
          {fromCache ? 'Cached' : 'Analyst Agent Running'}
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {mm}:{ss}
        </span>
      </div>

      {/* Current stage — large and animated */}
      {stage && (
        <div style={{
          fontSize: 14, color: 'var(--text-primary)', fontWeight: 500,
          marginBottom: history.length > 0 ? 16 : 4,
        }}>
          <span style={{ color: 'var(--gold)', marginRight: 8 }}>▸</span>
          {stage}
          <span style={{ marginLeft: 4, animation: 'blink 1s step-end infinite', color: 'var(--gold)' }}>_</span>
        </div>
      )}

      {/* Prior stages */}
      {history.length > 1 && (
        <div style={{
          fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.9,
          maxHeight: 220, overflowY: 'auto',
        }}>
          {history.slice(0, -1).map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span style={{ color: 'var(--text-faint)', fontSize: 10, minWidth: 14 }}>✓</span>
              <span>{h.label}</span>
            </div>
          ))}
        </div>
      )}

      {!fromCache && elapsed > 45 && (
        <div style={{
          marginTop: 14, paddingTop: 12,
          borderTop: '1px solid var(--border)',
          fontSize: 10, color: 'var(--text-faint)', fontStyle: 'italic',
        }}>
          Executive summaries typically complete in 60–120 seconds. The stream is
          kept alive with heartbeats so long runs won't be cut off.
        </div>
      )}
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
  const { company, product, snapshot, currency, asOfDate, isBackdated } = useCompany()
  const { isMobile } = useBreakpoint()
  const [narrative, setNarrative] = useState(null)
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [meta, setMeta] = useState(null)
  const [assetClassSources, setAssetClassSources] = useState([])
  const [sourcesExpanded, setSourcesExpanded] = useState(false)

  // Live streaming progress — mirrors the agent's tool-call timeline so the
  // analyst watching the page can see what the model is doing rather than a
  // mystery spinner for 60-90s.
  const [stage, setStage] = useState(null)        // "Pulling portfolio summary…"
  const [stageHistory, setStageHistory] = useState([]) // completed stages for the live panel
  const [elapsed, setElapsed] = useState(0)
  const [fromCache, setFromCache] = useState(false)
  const abortRef = useRef(null)
  const elapsedTimerRef = useRef(null)

  const basePath = `/company/${company}/${product}`

  // Friendly labels for agent tool names — keeps the stream panel readable.
  // Unknown tools fall back to their description (which the runtime already
  // prettifies). Keys cover both short and fully-qualified forms.
  const TOOL_LABELS = {
    get_portfolio_summary:      'Pulling portfolio summary',
    get_collection_velocity:    'Analysing collection velocity',
    get_deployment:             'Reviewing capital deployment',
    get_denial_trend:           'Checking denial trend',
    get_ageing_breakdown:       'Inspecting ageing buckets',
    get_returns_analysis:       'Computing returns & margins',
    get_concentration:          'Measuring concentration risk',
    get_cohort_analysis:        'Walking vintage cohorts',
    get_covenants:              'Checking covenant compliance',
    get_loss_waterfall:         'Building loss waterfall',
    get_par_analysis:           'Assessing portfolio at risk',
    get_underwriting_drift:     'Detecting underwriting drift',
    get_segment_analysis:       'Cutting portfolio segments',
    get_cdr_ccr:                'Running CDR / CCR',
    get_metric_trend:           'Pulling metric time-series',
    search_dataroom:            'Searching the data room',
    search_dataroom_documents:  'Searching the data room',
    search_dataroom_knowledge_base: 'Searching knowledge base',
    get_thesis:                 'Cross-referencing investment thesis',
    get_company_mind:           'Pulling platform memory',
    get_master_mind:            'Pulling fund-level lessons',
  }
  const labelForTool = (tool, fallback) => {
    if (!tool) return fallback || 'Thinking'
    // Agent runtime strips its own prefixes, but be defensive.
    const key = tool.replace(/^analytics_|^dataroom_|^mind_|^memo_|^portfolio_|^compliance_|^computation_/, '')
    return TOOL_LABELS[key] || fallback || `Running ${key.replace(/_/g, ' ')}`
  }

  // Cleanup on unmount: cancel stream + kill elapsed timer
  useEffect(() => () => {
    if (abortRef.current) abortRef.current.abort()
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
  }, [])

  const generate = (refresh = false) => {
    if (isBackdated) return
    if (abortRef.current) abortRef.current.abort()

    setLoading(true)
    setError(null)
    setStage('Starting…')
    setStageHistory([])
    setElapsed(0)
    setFromCache(false)
    if (refresh) {
      // On explicit refresh, clear prior content so the user sees the rebuild.
      setNarrative(null)
      setFindings(null)
      setMeta(null)
    }

    // Tick the elapsed counter once per second so the UI feels alive under
    // CF's idle proxy; the heartbeat also feeds this.
    const startedAt = Date.now()
    elapsedTimerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)

    // Local flags (not state) — React closures in the callback set below
    // would otherwise snapshot stale `findings` when onDone fires.
    let resultEmitted = false
    let errorSet = false

    const finish = () => {
      setLoading(false)
      setStage(null)
      if (elapsedTimerRef.current) {
        clearInterval(elapsedTimerRef.current)
        elapsedTimerRef.current = null
      }
      abortRef.current = null
    }

    const snap = snapshot?.filename || snapshot
    abortRef.current = streamExecutiveSummary(
      company, product, snap, currency, asOfDate,
      {
        onCached: () => { setFromCache(true); setStage('Serving cached summary') },
        onToolCall: ({ tool, description }) => {
          const label = labelForTool(tool, description)
          setStage(label)
          setStageHistory(prev => [...prev, { label, at: Date.now() }])
        },
        onText: () => {
          // First text delta = agent is writing the final JSON response.
          setStage('Writing narrative & findings')
        },
        onBudgetWarning: ({ pct }) => {
          setStage(`Token budget ${pct}% — wrapping up`)
        },
        onResult: (data) => {
          resultEmitted = true
          setNarrative(data.narrative || null)
          setFindings(data.findings || [])
          setMeta({
            generated_at: data.generated_at,
            as_of_date: data.as_of_date,
            mode: data.mode,
          })
          setAssetClassSources(Array.isArray(data.asset_class_sources) ? data.asset_class_sources : [])
        },
        onError: (err) => {
          setError(err?.message || 'Failed to generate summary')
          errorSet = true
          finish()
        },
        onDone: (d) => {
          // Only set fallback error if nothing else has surfaced one already.
          // onError fires before onDone when the runtime yields an error event,
          // and we don't want onDone's generic fallback to clobber the real
          // message from the agent runtime.
          if (d && d.ok === false && !resultEmitted && !errorSet) {
            setError(d.error || 'Stream ended without a result')
          }
          finish()
        },
        onAbort: () => { finish() },
      },
      { refresh },
    )
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
    <div style={{ padding: isMobile ? '16px 14px' : '24px 32px', maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: isMobile ? 'flex-start' : 'center', justifyContent: 'space-between', marginBottom: 24, flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 12 : 0 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Executive Summary
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            AI-powered portfolio analysis — credit memo narrative with key findings ranked by business impact
          </p>
        </div>

        {isBackdated ? (
          <span style={{ fontSize: 11, color: 'var(--text-faint)', fontStyle: 'italic', maxWidth: 260, textAlign: 'right', lineHeight: 1.5 }}>
            AI analysis is only available at the tape snapshot date. Balance metrics reflect the snapshot date, not the as-of date.
          </span>
        ) : (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {hasResults && (
              <button
                onClick={() => generate(true)}
                disabled={loading}
                style={{
                  padding: '8px 14px', borderRadius: 6,
                  border: '1px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
                title="Regenerate from scratch (new AI call)"
              >
                Regenerate
              </button>
            )}
            <button
              onClick={() => generate(false)}
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
              {loading ? 'Analyzing...' : hasResults ? 'Refresh' : 'Generate Summary'}
            </button>
          </div>
        )}
      </div>

      {/* Meta info */}
      {meta && !loading && (
        <div style={{
          display: 'flex', gap: 16, marginBottom: 20,
          fontSize: 10, color: 'var(--text-muted)', alignItems: 'center',
          flexWrap: 'wrap',
        }}>
          {meta.generated_at && (
            <span>Generated {new Date(meta.generated_at).toLocaleString()}</span>
          )}
          {meta.mode === 'agent' && (
            <span style={{
              fontSize: 9, fontWeight: 600, color: 'var(--text-faint)',
              background: 'rgba(45,212,191,0.08)', padding: '2px 8px',
              borderRadius: 3, letterSpacing: '0.06em',
              border: '1px solid rgba(45,212,191,0.15)',
            }}>
              AGENT
            </span>
          )}
          {fromCache && (
            <span style={{
              fontSize: 9, fontWeight: 600, color: 'var(--text-faint)',
              background: 'rgba(201,168,76,0.1)', padding: '2px 8px',
              borderRadius: 3, letterSpacing: '0.06em',
            }}>
              CACHED — loaded instantly
            </span>
          )}
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

      {/* Loading — live agent stream panel */}
      {loading && (
        <StreamProgressPanel
          stage={stage}
          history={stageHistory}
          elapsed={elapsed}
          fromCache={fromCache}
        />
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

          {/* D2: Layer 2.5 external sources that fed the summary */}
          {assetClassSources.length > 0 && (
            <AssetClassSourcesFooter
              sources={assetClassSources}
              expanded={sourcesExpanded}
              onToggle={() => setSourcesExpanded(v => !v)}
            />
          )}
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
        @keyframes blink { 50% { opacity: 0; } }
      `}</style>
    </div>
  )
}

// ── Layer 2.5 sources footer (D2) ─────────────────────────────────────────────
// Collapsible list of external URLs the Asset Class Mind contributed to the
// executive summary. NOT an attribution per paragraph (we don't have that
// provenance); a "what was in context" list. Lands below the Bottom Line and
// above the Key Findings section to stay visually tethered to the narrative.

function AssetClassSourcesFooter({ sources, expanded, onToggle }) {
  // Cap render at 25 rows — build_mind_context already dedupes+caps at 50.
  const visible = sources.slice(0, 25)
  const overflow = sources.length - visible.length

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      style={{
        marginTop: 18, padding: 14,
        background: 'rgba(45,212,191,0.04)',
        border: '1px solid rgba(45,212,191,0.18)',
        borderRadius: 8,
      }}
    >
      <button
        onClick={onToggle}
        style={{
          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
          fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
          textTransform: 'uppercase', color: 'var(--teal)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}
        title="External sources from the Asset Class Mind that were in AI context during generation"
      >
        <span>{expanded ? '▾' : '▸'}</span>
        Informed by {sources.length} asset-class source{sources.length === 1 ? '' : 's'}
      </button>

      {expanded && (
        <ol style={{
          margin: '10px 0 0 18px', padding: 0,
          fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6,
        }}>
          {visible.map((s, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
              <a
                href={s.url}
                target="_blank"
                rel="noreferrer noopener"
                style={{ color: 'var(--teal)', textDecoration: 'none' }}
                onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline' }}
                onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none' }}
              >
                {s.title || s.url}
              </a>
              <span style={{ color: 'var(--text-faint)', marginLeft: 8, fontSize: 10 }}>
                · {s.entry_category || 'entry'} · {s.source || 'unknown'}
                {s.page_age ? ` · ${s.page_age}` : ''}
              </span>
            </li>
          ))}
          {overflow > 0 && (
            <li style={{ color: 'var(--text-faint)', fontSize: 10, listStyle: 'none', marginTop: 6 }}>
              … and {overflow} more source{overflow === 1 ? '' : 's'} (Operator → Asset Classes to browse all)
            </li>
          )}
        </ol>
      )}
    </motion.div>
  )
}
