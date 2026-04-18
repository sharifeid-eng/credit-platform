import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { getMemoTemplates, generateMemo, AGENT_MEMO_URL } from '../../services/api'

// Icon chosen from template key (backend doesn't supply an icon field).
const ICON_BY_KEY = {
  credit_memo: 'doc',
  monitoring_update: 'pulse',
  due_diligence: 'search',
  quarterly_review: 'grid',
  amendment_memo: 'doc',
}

// Backend returns lowercase source identifiers (SourceLayer enum values).
// Map to human-readable labels used in the SOURCE_BADGES lookup.
const SOURCE_LABELS = {
  analytics: 'Analytics',
  dataroom: 'Data Room',
  mixed: 'Mixed',
  auto: 'Auto',
  ai_narrative: 'AI Narrative',
  manual: 'Manual',
}

const ICONS = {
  doc: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  pulse: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  search: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  ),
  grid: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="9" y1="21" x2="9" y2="9" />
    </svg>
  ),
}

const SOURCE_BADGES = {
  Analytics:    { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF' },
  'Data Room':  { bg: 'rgba(91,141,239,0.12)', color: '#5B8DEF' },
  Mixed:        { bg: 'rgba(201,168,76,0.12)',  color: '#C9A84C' },
  Auto:         { bg: 'rgba(132,148,167,0.12)', color: '#8494A7' },
  'AI Narrative': { bg: 'rgba(201,168,76,0.12)', color: '#C9A84C' },
  Manual:       { bg: 'rgba(132,148,167,0.12)', color: '#8494A7' },
}

export default function MemoBuilder() {
  const { company, product } = useCompany()
  const { isMobile } = useBreakpoint()
  const navigate = useNavigate()

  const [step, setStep] = useState(0)
  const [templates, setTemplates] = useState([])
  const [templatesError, setTemplatesError] = useState(null)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [sectionToggles, setSectionToggles] = useState({})
  const [generating, setGenerating] = useState(false)
  const [genProgress, setGenProgress] = useState('')
  const [genToolCall, setGenToolCall] = useState(null) // current tool being called
  const [useAgent, setUseAgent] = useState(true)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  // Load templates from backend. The backend is the single source of truth
  // for section keys, titles, and source layers — any fallback would drift
  // the moment the template definition changes in core/memo/templates.py.
  // If the fetch fails, surface an error rather than serving a stale list.
  useEffect(() => {
    getMemoTemplates()
      .then(data => {
        if (!data || !Array.isArray(data) || data.length === 0) {
          setTemplatesError('No memo templates returned by backend.')
          return
        }
        const hydrated = data.map(tmpl => ({
          ...tmpl,
          title: tmpl.title || tmpl.name,
          icon: tmpl.icon || ICON_BY_KEY[tmpl.key] || 'doc',
          sections: tmpl.sections || [],
        }))
        setTemplates(hydrated)
        setTemplatesError(null)
      })
      .catch(err => {
        setTemplatesError(err?.message || 'Failed to load memo templates.')
      })
  }, [])

  // Initialize section toggles when template selected
  useEffect(() => {
    if (!selectedTemplate) return
    const toggles = {}
    selectedTemplate.sections.forEach(s => {
      toggles[s.key] = true // all on by default
    })
    setSectionToggles(toggles)
  }, [selectedTemplate])

  function selectTemplate(tmpl) {
    setSelectedTemplate(tmpl)
    setStep(1)
  }

  function toggleSection(key, required) {
    if (required) return
    setSectionToggles(prev => ({ ...prev, [key]: !prev[key] }))
  }

  function goToReview() {
    setStep(2)
  }

  const enabledSections = selectedTemplate
    ? selectedTemplate.sections.filter(s => sectionToggles[s.key])
    : []

  async function handleGenerate() {
    if (!company || !product || !selectedTemplate) return
    setGenerating(true)
    setError(null)
    setGenProgress('Initializing generation...')
    setGenToolCall(null)

    const sectionKeys = enabledSections.map(s => s.key)

    if (useAgent) {
      // Agent mode: SSE streaming with live tool indicators
      const API_BASE = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : 'http://localhost:8000'
      const abortController = new AbortController()
      abortRef.current = abortController

      try {
        const response = await fetch(`${API_BASE}/agents/${company}/${product}/memo/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template_key: selectedTemplate.key,
            sections: sectionKeys,
          }),
          signal: abortController.signal,
          credentials: 'include',
        })

        if (!response.ok) {
          const errText = await response.text()
          throw new Error(errText)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let totalSections = 0
        let sectionsDone = 0
        let savedMemoId = null

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const events = buffer.split('\n\n')
          buffer = events.pop()

          for (const event of events) {
            if (!event.trim()) continue
            const lines = event.split('\n')
            let eventType = '', eventData = ''
            for (const line of lines) {
              if (line.startsWith('event: ')) eventType = line.slice(7)
              if (line.startsWith('data: ')) eventData = line.slice(6)
            }
            if (!eventType || !eventData) continue
            try {
              const data = JSON.parse(eventData)
              if (eventType === 'pipeline_start') {
                totalSections = (data.parallel_sections || 0) + (data.judgment_sections || 0)
                setGenProgress(`Generating ${totalSections} sections (parallel + judgment)...`)
              } else if (eventType === 'section_start') {
                const tierLabel = data.tier === 'judgment' ? 'Synthesising' :
                                   data.tier === 'auto' ? 'Building appendix for' : 'Writing'
                setGenToolCall(`${tierLabel} ${data.key}...`)
              } else if (eventType === 'section_done') {
                sectionsDone += 1
                setGenToolCall(null)
                setGenProgress(`${sectionsDone}/${totalSections || '?'} sections complete`)
              } else if (eventType === 'research_start') {
                setGenToolCall(`Gathering research pack for ${data.key}...`)
              } else if (eventType === 'research_done') {
                setGenToolCall(null)
              } else if (eventType === 'polish_start') {
                setGenProgress('Polishing full memo (Opus coherence pass)...')
                setGenToolCall(null)
              } else if (eventType === 'polish_done') {
                setGenProgress(data.polished ? 'Polish complete.' : 'Polish skipped — saving draft.')
              } else if (eventType === 'saved') {
                savedMemoId = data.memo_id
                setGenProgress('Memo saved. Redirecting...')
              } else if (eventType === 'done') {
                if (!savedMemoId && data.memo_id) savedMemoId = data.memo_id
                setGenToolCall(null)
              } else if (eventType === 'error') {
                setError(data.message)
              }
            } catch (_) { /* skip malformed */ }
          }
        }

        // Backend persisted the memo during the stream — navigate to it.
        if (savedMemoId) {
          setTimeout(() => {
            navigate(`/company/${company}/${product}/research/memos/${savedMemoId}`)
          }, 400)
        } else {
          // Backend didn't emit a saved event — fall back to archive
          console.warn('[MemoBuilder] No memo_id emitted; navigating to archive')
          navigate(`/company/${company}/${product}/research/memos`)
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Agent generation failed. Please try again.')
        }
      } finally {
        setGenerating(false)
        setGenToolCall(null)
        abortRef.current = null
      }
    } else {
      // Legacy mode: single API call with simulated progress
      let progressIdx = 0
      const progressTimer = setInterval(() => {
        if (progressIdx < enabledSections.length) {
          setGenProgress(`Generating: ${enabledSections[progressIdx].title}...`)
          progressIdx++
        }
      }, 3000)

      try {
        const result = await generateMemo(company, product, selectedTemplate.key, sectionKeys)
        clearInterval(progressTimer)
        setGenProgress('Complete!')
        const memoId = result.memo_id || result.id
        if (memoId) {
          setTimeout(() => {
            navigate(`/company/${company}/${product}/research/memos/${memoId}`)
          }, 600)
        }
      } catch (err) {
        clearInterval(progressTimer)
        setError(err?.response?.data?.detail || 'Generation failed. Please try again.')
        setGenerating(false)
      }
    }
  }

  const pad = isMobile ? 14 : 28

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ padding: pad, maxWidth: 1000, margin: '0 auto' }}
    >
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <button
          onClick={() => navigate(`/company/${company}/${product}/research/memos`)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', fontSize: 12, padding: 0,
            display: 'flex', alignItems: 'center', gap: 4, marginBottom: 12,
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back to Memos
        </button>
        <h1 style={{
          fontSize: isMobile ? 20 : 24,
          fontWeight: 800,
          color: 'var(--text-primary)',
          margin: 0,
          fontFamily: 'var(--font-display)',
          letterSpacing: '-0.02em',
        }}>
          New Investment Memo
        </h1>
      </div>

      {/* Step indicator */}
      <StepIndicator current={step} steps={['Select Template', 'Customize Sections', 'Review & Generate']} />

      {/* Step content */}
      <AnimatePresence mode="wait">
        {step === 0 && (
          <motion.div
            key="step0"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
          >
            {templatesError ? (
              <div style={{
                marginTop: 24,
                padding: '16px 20px',
                borderRadius: 8,
                background: 'rgba(240,96,96,0.08)',
                border: '1px solid rgba(240,96,96,0.2)',
                color: '#F06060',
                fontSize: 13,
                fontWeight: 500,
              }}>
                Unable to load memo templates: {templatesError}
              </div>
            ) : templates.length === 0 ? (
              <div style={{
                marginTop: 24,
                padding: '16px 20px',
                borderRadius: 8,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                color: 'var(--text-muted)',
                fontSize: 13,
              }}>
                Loading memo templates…
              </div>
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)',
                gap: 16,
                marginTop: 24,
              }}>
                {templates.map((tmpl, i) => (
                  <TemplateCard
                    key={tmpl.key}
                    template={tmpl}
                    index={i}
                    selected={selectedTemplate?.key === tmpl.key}
                    onSelect={() => selectTemplate(tmpl)}
                  />
                ))}
              </div>
            )}
          </motion.div>
        )}

        {step === 1 && selectedTemplate && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            style={{ marginTop: 24 }}
          >
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              overflow: 'hidden',
            }}>
              {/* Template header */}
              <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{ color: 'var(--accent-gold)' }}>
                  {ICONS[selectedTemplate.icon]}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {selectedTemplate.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {selectedTemplate.description}
                  </div>
                </div>
              </div>

              {/* Section list */}
              {selectedTemplate.sections.map((sec, i) => {
                const on = sectionToggles[sec.key]
                const sourceLabel = SOURCE_LABELS[sec.source] || sec.source || 'Mixed'
                const srcBadge = SOURCE_BADGES[sourceLabel] || SOURCE_BADGES.Mixed
                return (
                  <motion.div
                    key={sec.key}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    onClick={() => toggleSection(sec.key, sec.required)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '12px 20px',
                      borderBottom: i < selectedTemplate.sections.length - 1 ? '1px solid var(--border)' : 'none',
                      cursor: sec.required ? 'default' : 'pointer',
                      opacity: on ? 1 : 0.45,
                      transition: 'opacity var(--transition-fast)',
                    }}
                  >
                    {/* Checkbox */}
                    <div style={{
                      width: 18, height: 18, borderRadius: 4,
                      border: `1.5px solid ${on ? 'var(--accent-gold)' : 'var(--border)'}`,
                      background: on ? 'rgba(201,168,76,0.15)' : 'transparent',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all var(--transition-fast)',
                      flexShrink: 0,
                    }}>
                      {on && (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent-gold)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </div>

                    {/* Section info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                        display: 'flex', alignItems: 'center', gap: 8,
                      }}>
                        {sec.title}
                        {sec.required && (
                          <span style={{
                            fontSize: 8, fontWeight: 700, textTransform: 'uppercase',
                            letterSpacing: '0.06em', padding: '2px 6px', borderRadius: 3,
                            background: 'rgba(240,96,96,0.12)', color: '#F06060',
                          }}>
                            Required
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Source badge */}
                    <span style={{
                      fontSize: 9, fontWeight: 600,
                      padding: '3px 8px', borderRadius: 4,
                      background: srcBadge.bg, color: srcBadge.color,
                      whiteSpace: 'nowrap', flexShrink: 0,
                    }}>
                      {sourceLabel}
                    </span>
                  </motion.div>
                )
              })}
            </div>

            {/* Navigation */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
              <button
                onClick={() => setStep(0)}
                style={{
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '8px 20px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                Back
              </button>
              <button
                onClick={goToReview}
                style={{
                  background: 'var(--accent-gold)',
                  border: 'none',
                  borderRadius: 6,
                  padding: '8px 24px',
                  fontSize: 12,
                  fontWeight: 700,
                  color: '#0D1520',
                  cursor: 'pointer',
                }}
              >
                Continue
              </button>
            </div>
          </motion.div>
        )}

        {step === 2 && selectedTemplate && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.25 }}
            style={{ marginTop: 24 }}
          >
            {/* Review card */}
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 24,
              marginBottom: 20,
            }}>
              <div style={{
                fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 16,
              }}>
                Generation Summary
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 16 }}>
                <SummaryRow label="Template" value={selectedTemplate.title} />
                <SummaryRow label="Company" value={company} />
                <SummaryRow label="Product" value={product?.replace(/_/g, ' ')} />
                <SummaryRow label="Sections" value={`${enabledSections.length} of ${selectedTemplate.sections.length}`} />
              </div>

              {/* Section list preview */}
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                <div style={{
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: 10,
                }}>
                  Included Sections
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {enabledSections.map(s => (
                    <span key={s.key} style={{
                      fontSize: 10, fontWeight: 600,
                      padding: '4px 10px', borderRadius: 4,
                      background: 'var(--bg-deep)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border)',
                    }}>
                      {s.title}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={{
                padding: '12px 16px', borderRadius: 6, marginBottom: 16,
                background: 'rgba(240,96,96,0.08)',
                border: '1px solid rgba(240,96,96,0.2)',
                color: '#F06060', fontSize: 12,
              }}>
                {error}
              </div>
            )}

            {/* Progress indicator */}
            {generating && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: 20,
                  marginBottom: 20,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 20, height: 20,
                    border: '2px solid var(--border)',
                    borderTopColor: 'var(--accent-gold)',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                  }} />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {useAgent ? 'Generating Memo (live progress)' : 'Generating Memo'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {genProgress}
                    </div>
                    {genToolCall && (
                      <div style={{ fontSize: 10, color: 'var(--accent-gold)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent-gold)', animation: 'pulse 1s infinite' }} />
                        {genToolCall}
                      </div>
                    )}
                  </div>
                </div>
                {/* Inline keyframes */}
                <style>{`@keyframes spin { to { transform: rotate(360deg); } } @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.3 } }`}</style>
              </motion.div>
            )}

            {/* Navigation */}
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <button
                onClick={() => setStep(1)}
                disabled={generating}
                style={{
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '8px 20px',
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-muted)',
                  cursor: generating ? 'not-allowed' : 'pointer',
                  opacity: generating ? 0.5 : 1,
                }}
              >
                Back
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating}
                style={{
                  background: generating ? 'var(--border)' : 'var(--accent-gold)',
                  border: 'none',
                  borderRadius: 6,
                  padding: '10px 32px',
                  fontSize: 13,
                  fontWeight: 700,
                  color: generating ? 'var(--text-muted)' : '#0D1520',
                  cursor: generating ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}
              >
                {generating ? (
                  <>
                    <div style={{
                      width: 14, height: 14,
                      border: '2px solid var(--text-muted)',
                      borderTopColor: 'transparent',
                      borderRadius: '50%',
                      animation: 'spin 0.8s linear infinite',
                    }} />
                    Generating...
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                    </svg>
                    Generate Memo
                  </>
                )}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── Step indicator ───────────────────────────────────────────────────────────
function StepIndicator({ current, steps }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '12px 16px',
      marginBottom: 8,
    }}>
      {steps.map((label, i) => {
        const isActive = i === current
        const isDone = i < current
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < steps.length - 1 ? 1 : 0 }}>
            {/* Step circle + label */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap' }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                background: isActive ? 'var(--accent-gold)' : isDone ? 'rgba(45,212,191,0.15)' : 'var(--bg-deep)',
                color: isActive ? '#0D1520' : isDone ? '#2DD4BF' : 'var(--text-muted)',
                border: `1.5px solid ${isActive ? 'var(--accent-gold)' : isDone ? 'rgba(45,212,191,0.3)' : 'var(--border)'}`,
                transition: 'all var(--transition-normal)',
              }}>
                {isDone ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span style={{
                fontSize: 11, fontWeight: isActive ? 700 : 500,
                color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
              }}>
                {label}
              </span>
            </div>
            {/* Connector line */}
            {i < steps.length - 1 && (
              <div style={{
                flex: 1, height: 1, margin: '0 12px',
                background: isDone ? 'rgba(45,212,191,0.3)' : 'var(--border)',
                transition: 'background var(--transition-normal)',
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Template card ────────────────────────────────────────────────────────────
function TemplateCard({ template, index, selected, onSelect }) {
  const [hovered, setHovered] = useState(false)
  const sectionCount = template.sections?.length || 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 + index * 0.05, ease: 'easeOut' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onSelect}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${selected ? 'var(--accent-gold)' : hovered ? 'var(--border-hover)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: 20,
        cursor: 'pointer',
        transition: 'border-color var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast)',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: selected ? '0 0 0 1px var(--accent-gold), 0 4px 20px rgba(201,168,76,0.1)' : hovered ? '0 4px 20px rgba(0,0,0,0.15)' : 'none',
        position: 'relative',
      }}
    >
      {/* Section count badge */}
      <span style={{
        position: 'absolute', top: 12, right: 12,
        fontSize: 9, fontWeight: 700,
        padding: '3px 8px', borderRadius: 4,
        background: 'var(--bg-deep)',
        color: 'var(--text-muted)',
        border: '1px solid var(--border)',
        fontFamily: 'var(--font-mono)',
      }}>
        {sectionCount} sections
      </span>

      {/* Icon */}
      <div style={{ color: selected ? 'var(--accent-gold)' : 'var(--text-muted)', marginBottom: 14, opacity: selected ? 1 : 0.7 }}>
        {ICONS[template.icon]}
      </div>

      {/* Title */}
      <div style={{
        fontSize: 15, fontWeight: 700,
        color: selected ? 'var(--accent-gold)' : 'var(--text-primary)',
        marginBottom: 6,
      }}>
        {template.title}
      </div>

      {/* Description */}
      <div style={{
        fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6,
      }}>
        {template.description}
      </div>
    </motion.div>
  )
}

// ── Summary row ─────────────────────────────────────────────────────────────
function SummaryRow({ label, value }) {
  return (
    <div>
      <div style={{
        fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
        textTransform: 'capitalize',
      }}>
        {value}
      </div>
    </div>
  )
}
