import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import {
  getMemo,
  regenerateSection,
  updateMemoSection,
  updateMemoStatus,
  exportMemoPdf,
} from '../../services/api'

const ASSESSMENT_COLORS = {
  healthy:    '#2DD4BF',
  acceptable: '#C9A84C',
  monitor:    '#C9A84C',
  warning:    '#F06060',
  critical:   '#F06060',
  Healthy:    '#2DD4BF',
  Acceptable: '#C9A84C',
  Monitor:    '#C9A84C',
  Warning:    '#F06060',
  Critical:   '#F06060',
}

const STATUS_STYLES = {
  draft:  { bg: 'rgba(91,141,239,0.12)',  color: '#5B8DEF', label: 'Draft' },
  review: { bg: 'rgba(201,168,76,0.12)',  color: '#C9A84C', label: 'Review' },
  final:  { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'Final' },
}

const STATUS_FLOW = ['draft', 'review', 'final']

export default function MemoEditor() {
  const { company, product } = useCompany()
  const { memoId } = useParams()
  const navigate = useNavigate()
  const { isMobile } = useBreakpoint()

  const [memo, setMemo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeSection, setActiveSection] = useState(null)
  const [editingSection, setEditingSection] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [statusDropdownOpen, setStatusDropdownOpen] = useState(false)

  // Load memo
  useEffect(() => {
    if (!company || !product || !memoId) return
    setLoading(true)
    setError(null)
    getMemo(company, product, memoId)
      .then(data => {
        setMemo(data)
        // Set first section as active
        if (data.sections && data.sections.length > 0) {
          setActiveSection(data.sections[0].key)
        }
      })
      .catch(err => {
        setError(err?.response?.data?.detail || 'Failed to load memo')
      })
      .finally(() => setLoading(false))
  }, [company, product, memoId])

  const isFinal = memo?.status === 'final'
  const sections = memo?.sections || []
  const currentSection = sections.find(s => s.key === activeSection)
  const statusStyle = STATUS_STYLES[memo?.status] || STATUS_STYLES.draft

  // Edit handlers
  function startEdit(section) {
    if (isFinal) return
    setEditingSection(section.key)
    setEditContent(section.content || '')
  }

  function cancelEdit() {
    setEditingSection(null)
    setEditContent('')
  }

  async function saveEdit() {
    if (!editingSection || !company || !product || !memoId) return
    setSaving(true)
    try {
      const result = await updateMemoSection(company, product, memoId, editingSection, editContent)
      // Update local state
      setMemo(prev => {
        if (!prev) return prev
        const updated = { ...prev }
        updated.sections = updated.sections.map(s =>
          s.key === editingSection ? { ...s, content: editContent } : s
        )
        if (result.version) updated.version = result.version
        return updated
      })
      setEditingSection(null)
      setEditContent('')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  async function handleRegenerate(sectionKey) {
    if (!company || !product || !memoId || isFinal) return
    setRegenerating(sectionKey)
    try {
      const result = await regenerateSection(company, product, memoId, sectionKey)
      setMemo(prev => {
        if (!prev) return prev
        const updated = { ...prev }
        updated.sections = updated.sections.map(s =>
          s.key === sectionKey ? { ...s, content: result.content || result.section?.content || s.content } : s
        )
        if (result.version) updated.version = result.version
        return updated
      })
    } catch (err) {
      setError(err?.response?.data?.detail || 'Regeneration failed')
    } finally {
      setRegenerating(null)
    }
  }

  async function handleStatusChange(newStatus) {
    if (!company || !product || !memoId) return
    setStatusDropdownOpen(false)
    try {
      await updateMemoStatus(company, product, memoId, newStatus)
      setMemo(prev => prev ? { ...prev, status: newStatus } : prev)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Status change failed')
    }
  }

  async function handleExport() {
    if (!company || !product || !memoId) return
    setExporting(true)
    try {
      await exportMemoPdf(company, product, memoId)
    } catch (err) {
      setError(err?.response?.data?.detail || 'PDF export failed')
    } finally {
      setExporting(false)
    }
  }

  const pad = isMobile ? 14 : 28

  if (loading) {
    return (
      <div style={{ padding: pad, maxWidth: 1200, margin: '0 auto' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: 40, justifyContent: 'center',
        }}>
          <div style={{
            width: 20, height: 20,
            border: '2px solid var(--border)',
            borderTopColor: 'var(--accent-gold)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading memo...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (error && !memo) {
    return (
      <div style={{ padding: pad, maxWidth: 1200, margin: '0 auto' }}>
        <div style={{
          padding: 40, textAlign: 'center',
          background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8,
        }}>
          <div style={{ fontSize: 14, color: '#F06060', marginBottom: 8 }}>{error}</div>
          <button
            onClick={() => navigate(`/company/${company}/${product}/research/memos`)}
            style={{
              background: 'none', border: '1px solid var(--border)',
              borderRadius: 6, padding: '8px 20px', fontSize: 12,
              fontWeight: 600, color: 'var(--text-muted)', cursor: 'pointer',
            }}
          >
            Back to Memos
          </button>
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ padding: pad, maxWidth: 1200, margin: '0 auto' }}
    >
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: isMobile ? 'flex-start' : 'center',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 12 : 16,
        marginBottom: 24,
        paddingBottom: 20,
        borderBottom: '1px solid var(--border)',
      }}>
        {/* Left: back + title */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <button
            onClick={() => navigate(`/company/${company}/${product}/research/memos`)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', fontSize: 11, padding: 0,
              display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6,
            }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Memos
          </button>
          <h1 style={{
            fontSize: isMobile ? 18 : 22,
            fontWeight: 800,
            color: 'var(--text-primary)',
            margin: 0,
            fontFamily: 'var(--font-display)',
            letterSpacing: '-0.02em',
          }}>
            {memo?.title || 'Untitled Memo'}
          </h1>
        </div>

        {/* Right: badges + actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          {/* Status badge with dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => !isFinal && setStatusDropdownOpen(!statusDropdownOpen)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 12px', borderRadius: 5,
                background: statusStyle.bg,
                color: statusStyle.color,
                border: `1px solid ${statusStyle.color}30`,
                fontSize: 10, fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                cursor: isFinal ? 'default' : 'pointer',
              }}
            >
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: statusStyle.color,
              }} />
              {statusStyle.label}
              {!isFinal && (
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              )}
            </button>

            {/* Dropdown */}
            <AnimatePresence>
              {statusDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  style={{
                    position: 'absolute', top: '100%', right: 0, marginTop: 4,
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: 4,
                    minWidth: 120,
                    zIndex: 50,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                  }}
                >
                  {STATUS_FLOW.map(s => {
                    const st = STATUS_STYLES[s]
                    const isCurrent = s === memo?.status
                    return (
                      <button
                        key={s}
                        onClick={() => handleStatusChange(s)}
                        disabled={isCurrent}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          width: '100%', padding: '7px 10px', borderRadius: 4,
                          background: isCurrent ? 'var(--bg-deep)' : 'transparent',
                          border: 'none', cursor: isCurrent ? 'default' : 'pointer',
                          color: st.color, fontSize: 11, fontWeight: 600,
                          opacity: isCurrent ? 0.5 : 1,
                        }}
                      >
                        <span style={{
                          width: 6, height: 6, borderRadius: '50%',
                          background: st.color,
                        }} />
                        {st.label}
                      </button>
                    )
                  })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Version badge */}
          {memo?.version && (
            <span style={{
              fontSize: 9, fontWeight: 700,
              padding: '4px 8px', borderRadius: 4,
              background: 'var(--bg-deep)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border)',
              fontFamily: 'var(--font-mono)',
            }}>
              v{memo.version}
            </span>
          )}

          {/* Export PDF button */}
          <button
            onClick={handleExport}
            disabled={exporting}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 6,
              background: 'transparent',
              border: '1px solid var(--accent-gold)',
              color: 'var(--accent-gold)',
              fontSize: 11, fontWeight: 700,
              cursor: exporting ? 'not-allowed' : 'pointer',
              opacity: exporting ? 0.5 : 1,
            }}
          >
            {exporting ? (
              <>
                <div style={{
                  width: 12, height: 12,
                  border: '1.5px solid var(--accent-gold)',
                  borderTopColor: 'transparent',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }} />
                Exporting...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download PDF
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 6, marginBottom: 16,
          background: 'rgba(240,96,96,0.08)',
          border: '1px solid rgba(240,96,96,0.2)',
          color: '#F06060', fontSize: 11,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#F06060', padding: 4,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {/* Main layout: section nav + content */}
      <div style={{
        display: 'flex',
        gap: 0,
        minHeight: 500,
        border: '1px solid var(--border)',
        borderRadius: 8,
        overflow: 'hidden',
        background: 'var(--bg-surface)',
      }}>
        {/* Left panel: section nav */}
        {!isMobile && (
          <div style={{
            width: 200, flexShrink: 0,
            borderRight: '1px solid var(--border)',
            background: 'var(--bg-nav)',
            overflowY: 'auto',
            padding: '12px 0',
          }}>
            <div style={{
              fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.1em', color: 'var(--text-muted)',
              padding: '4px 16px 10px',
            }}>
              Sections
            </div>
            {sections.map((sec, i) => {
              const isActive = sec.key === activeSection
              return (
                <button
                  key={sec.key}
                  onClick={() => setActiveSection(sec.key)}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '8px 16px',
                    background: isActive ? 'rgba(201,168,76,0.06)' : 'transparent',
                    border: 'none',
                    borderLeft: isActive ? '2px solid var(--accent-gold)' : '2px solid transparent',
                    color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
                    fontSize: 11, fontWeight: isActive ? 700 : 500,
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  {sec.title}
                </button>
              )
            })}
          </div>
        )}

        {/* Mobile: horizontal section tabs */}
        {isMobile && (
          <div style={{
            display: 'flex', gap: 0,
            borderBottom: '1px solid var(--border)',
            overflowX: 'auto',
            flexShrink: 0,
          }}>
            {sections.map(sec => {
              const isActive = sec.key === activeSection
              return (
                <button
                  key={sec.key}
                  onClick={() => setActiveSection(sec.key)}
                  style={{
                    padding: '10px 14px',
                    background: 'none', border: 'none',
                    borderBottom: isActive ? '2px solid var(--accent-gold)' : '2px solid transparent',
                    color: isActive ? 'var(--accent-gold)' : 'var(--text-muted)',
                    fontSize: 10, fontWeight: isActive ? 700 : 500,
                    cursor: 'pointer', whiteSpace: 'nowrap',
                  }}
                >
                  {sec.title}
                </button>
              )
            })}
          </div>
        )}

        {/* Main content panel */}
        <div style={{ flex: 1, padding: isMobile ? 16 : 28, overflowY: 'auto' }}>
          <AnimatePresence mode="wait">
            {currentSection && (
              <motion.div
                key={currentSection.key}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2 }}
              >
                {/* Section header */}
                <div style={{
                  display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
                  marginBottom: 20,
                }}>
                  <h2 style={{
                    fontSize: 18, fontWeight: 800,
                    color: 'var(--accent-gold)',
                    margin: 0,
                    fontFamily: 'var(--font-display)',
                    letterSpacing: '-0.01em',
                  }}>
                    {currentSection.title}
                  </h2>

                  {/* Section actions */}
                  {!isFinal && editingSection !== currentSection.key && (
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={() => handleRegenerate(currentSection.key)}
                        disabled={regenerating === currentSection.key}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          padding: '4px 10px', borderRadius: 4,
                          background: 'transparent',
                          border: '1px solid var(--border)',
                          color: 'var(--text-muted)',
                          fontSize: 10, fontWeight: 600,
                          cursor: regenerating === currentSection.key ? 'not-allowed' : 'pointer',
                          opacity: regenerating === currentSection.key ? 0.5 : 1,
                        }}
                      >
                        {regenerating === currentSection.key ? (
                          <>
                            <div style={{
                              width: 10, height: 10,
                              border: '1.5px solid var(--text-muted)',
                              borderTopColor: 'transparent',
                              borderRadius: '50%',
                              animation: 'spin 0.8s linear infinite',
                            }} />
                            Regenerating
                          </>
                        ) : (
                          <>
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="23 4 23 10 17 10" />
                              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                            </svg>
                            Regenerate
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => startEdit(currentSection)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          padding: '4px 10px', borderRadius: 4,
                          background: 'transparent',
                          border: '1px solid var(--border)',
                          color: 'var(--text-muted)',
                          fontSize: 10, fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                        Edit
                      </button>
                    </div>
                  )}
                </div>

                {/* Section content */}
                {editingSection === currentSection.key ? (
                  /* Edit mode */
                  <div>
                    <textarea
                      value={editContent}
                      onChange={e => setEditContent(e.target.value)}
                      style={{
                        width: '100%', minHeight: 300,
                        background: 'var(--bg-deep)',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        color: 'var(--text-primary)',
                        fontSize: 13, lineHeight: 1.7,
                        padding: 16,
                        fontFamily: 'var(--font-body)',
                        resize: 'vertical',
                        outline: 'none',
                      }}
                      onFocus={e => e.target.style.borderColor = 'var(--accent-gold)'}
                      onBlur={e => e.target.style.borderColor = 'var(--border)'}
                    />
                    <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                      <button
                        onClick={cancelEdit}
                        style={{
                          padding: '6px 16px', borderRadius: 5,
                          background: 'transparent',
                          border: '1px solid var(--border)',
                          color: 'var(--text-muted)',
                          fontSize: 11, fontWeight: 600, cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={saveEdit}
                        disabled={saving}
                        style={{
                          padding: '6px 20px', borderRadius: 5,
                          background: 'var(--accent-gold)',
                          border: 'none',
                          color: '#0D1520',
                          fontSize: 11, fontWeight: 700,
                          cursor: saving ? 'not-allowed' : 'pointer',
                          opacity: saving ? 0.6 : 1,
                        }}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Read mode */
                  <div>
                    {/* Content paragraphs */}
                    <div style={{
                      fontSize: 13, lineHeight: 1.8,
                      color: 'var(--text-primary)',
                      textAlign: 'justify',
                    }}>
                      {(currentSection.content || 'No content generated yet.').split('\n\n').filter(Boolean).map((para, i) => (
                        <p key={i} style={{ margin: '0 0 14px' }}>{para}</p>
                      ))}
                    </div>

                    {/* Metrics row */}
                    {currentSection.metrics && currentSection.metrics.length > 0 && (
                      <div style={{
                        display: 'flex', gap: 8, flexWrap: 'wrap',
                        marginTop: 16, paddingTop: 14,
                        borderTop: '1px solid var(--border)',
                      }}>
                        {currentSection.metrics.map((m, j) => {
                          const color = ASSESSMENT_COLORS[m.assessment] || 'var(--text-muted)'
                          return (
                            <span key={j} style={{
                              fontSize: 10, fontFamily: 'var(--font-mono)',
                              padding: '4px 10px', borderRadius: 4,
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

                    {/* Citations */}
                    {currentSection.citations && currentSection.citations.length > 0 && (
                      <div style={{
                        marginTop: 16, paddingTop: 14,
                        borderTop: '1px solid var(--border)',
                      }}>
                        <div style={{
                          fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                          letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 8,
                        }}>
                          Sources
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {currentSection.citations.map((cite, k) => (
                            <span key={k} style={{
                              display: 'inline-flex', alignItems: 'center', gap: 4,
                              fontSize: 10, fontWeight: 600,
                              padding: '3px 8px', borderRadius: 4,
                              background: 'rgba(201,168,76,0.1)',
                              color: 'var(--accent-gold)',
                              border: '1px solid rgba(201,168,76,0.2)',
                            }}>
                              <span style={{
                                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                width: 14, height: 14, borderRadius: '50%',
                                background: 'rgba(201,168,76,0.2)',
                                fontSize: 8, fontWeight: 700,
                              }}>
                                {k + 1}
                              </span>
                              {typeof cite === 'string' ? cite : cite.title || cite.source || `Source ${k + 1}`}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Empty state when no sections */}
          {sections.length === 0 && (
            <div style={{
              textAlign: 'center', padding: 40,
              color: 'var(--text-muted)', fontSize: 13,
            }}>
              This memo has no sections yet.
            </div>
          )}
        </div>
      </div>

      {/* Inline keyframes */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </motion.div>
  )
}
