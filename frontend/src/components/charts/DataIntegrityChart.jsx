import { useState, useEffect, useRef, useCallback } from 'react'
import {
  getIntegrityCached, runIntegrityCheck,
  generateIntegrityReport, getIntegrityReportCached,
  saveIntegrityNotes, getIntegrityNotes,
} from '../../services/api'

// ── Severity styling ─────────────────────────────────────────────────────────
const SEV = {
  critical: { bg: 'rgba(240,96,96,0.15)', color: 'var(--red)',  label: 'CRITICAL' },
  warning:  { bg: 'rgba(201,168,76,0.15)', color: 'var(--gold)', label: 'WARNING'  },
  info:     { bg: 'rgba(45,212,191,0.15)', color: 'var(--teal)', label: 'INFO'     },
}

function Badge({ type, text }) {
  const s = SEV[type] ?? SEV.info
  return (
    <span style={{
      display: 'inline-block', fontSize: 9, fontWeight: 700, letterSpacing: '0.06em',
      padding: '2px 7px', borderRadius: 4,
      background: s.bg, color: s.color,
      textTransform: 'uppercase', fontFamily: 'var(--font-mono)',
    }}>
      {text ?? s.label}
    </span>
  )
}

function PassFailBadge({ passed }) {
  return (
    <Badge
      type={passed ? 'info' : 'critical'}
      text={passed ? 'PASS' : 'FAIL'}
    />
  )
}

// ── Loading bar (matches Company.jsx) ────────────────────────────────────────
function GoldLoadingBar() {
  return (
    <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', background: 'var(--border)' }}>
      <div style={{
        height: '100%', width: '40%', borderRadius: 2, background: 'var(--gold)',
        animation: 'integrityLoadSlide 1s ease-in-out infinite',
      }} />
      <style>{`@keyframes integrityLoadSlide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }`}</style>
    </div>
  )
}

// ── Dark Select (same pattern as Company.jsx) ────────────────────────────────
function DarkSelect({ value, onChange, children }) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{
        fontSize: 11, padding: '6px 10px',
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 7, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', outline: 'none',
      }}
    >
      {children}
    </select>
  )
}

// ── Card wrapper ─────────────────────────────────────────────────────────────
function Card({ children, style }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '18px 20px',
      ...style,
    }}>
      {children}
    </div>
  )
}

// ── Expandable issue list ────────────────────────────────────────────────────
function IssueList({ items, type, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  if (!items || items.length === 0) return null
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-muted)', fontSize: 11, fontWeight: 600,
        }}
      >
        <span style={{ fontSize: 9, transition: 'transform 0.15s', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>
          &#9654;
        </span>
        <Badge type={type} /> <span style={{ marginLeft: 4 }}>{items.length} {SEV[type]?.label?.toLowerCase() ?? type}{items.length !== 1 ? 's' : ''}</span>
      </button>
      {expanded && (
        <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 6, paddingLeft: 16 }}>
          {items.map((item, i) => (
            <IssueItem key={i} item={item} type={type} />
          ))}
        </div>
      )}
    </div>
  )
}

function IssueItem({ item, type }) {
  const [showIds, setShowIds] = useState(false)
  const name = typeof item === 'string' ? item : (item.check ?? item.name ?? '')
  const detail = typeof item === 'string' ? '' : (item.detail ?? item.message ?? '')
  const ids = typeof item === 'object' ? (item.ids ?? item.deal_ids ?? []) : []

  return (
    <div style={{
      fontSize: 12, lineHeight: 1.7, color: 'var(--text-muted)',
      borderLeft: `2px solid ${SEV[type]?.color ?? 'var(--border)'}`,
      paddingLeft: 10,
    }}>
      <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
        {name}
      </span>
      {detail && <span style={{ marginLeft: 6 }}>{detail}</span>}
      {ids.length > 0 && (
        <div style={{ marginTop: 2 }}>
          <button
            onClick={() => setShowIds(v => !v)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              color: 'var(--gold)', fontSize: 10, fontWeight: 600,
            }}
          >
            {showIds ? 'Hide' : 'Show'} {ids.length} affected deal{ids.length !== 1 ? 's' : ''}
          </button>
          {showIds && (
            <div style={{
              marginTop: 4, padding: '6px 8px', background: 'var(--bg-deep)',
              borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)',
              fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.6,
              maxHeight: 120, overflowY: 'auto',
            }}>
              {ids.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Note textarea with debounced save ────────────────────────────────────────
function NoteField({ value, onChange, onSave }) {
  const [saved, setSaved] = useState(false)
  const timerRef = useRef(null)

  const handleChange = useCallback((e) => {
    const v = e.target.value
    onChange(v)
    setSaved(false)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      onSave(v)
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    }, 500)
  }, [onChange, onSave])

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  const hasContent = value && value.trim().length > 0

  return (
    <div style={{ position: 'relative', marginTop: 6 }}>
      <textarea
        value={value ?? ''}
        onChange={handleChange}
        placeholder="Add your notes here..."
        rows={2}
        style={{
          width: '100%', resize: 'vertical',
          fontSize: 11, lineHeight: 1.6, padding: '8px 10px',
          background: 'var(--bg-deep)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
          fontFamily: 'var(--font-ui)', outline: 'none',
          borderLeft: `3px solid ${hasContent ? 'var(--gold)' : 'var(--border)'}`,
          transition: 'border-color 0.15s',
        }}
      />
      {saved && (
        <span style={{
          position: 'absolute', right: 8, bottom: 8,
          fontSize: 9, fontWeight: 600, color: 'var(--teal)',
          letterSpacing: '0.04em',
        }}>
          Saved
        </span>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────
export default function DataIntegrityChart({ company, product, snapshots, currency }) {
  // Defaults: second-to-last and last snapshot
  const defaultOld = snapshots?.length >= 2 ? snapshots[snapshots.length - 2] : snapshots?.[0] ?? ''
  const defaultNew = snapshots?.length >= 1 ? snapshots[snapshots.length - 1] : ''

  const [snapOld, setSnapOld]             = useState(defaultOld)
  const [snapNew, setSnapNew]             = useState(defaultNew)
  const [results, setResults]             = useState(null)
  const [report, setReport]               = useState(null)
  const [notes, setNotes]                 = useState({})
  const [loading, setLoading]             = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [error, setError]                 = useState(null)

  // Update defaults when snapshots change
  useEffect(() => {
    if (!snapshots || snapshots.length === 0) return
    const newOld = snapshots.length >= 2 ? snapshots[snapshots.length - 2] : snapshots[0]
    const newNew = snapshots[snapshots.length - 1]
    setSnapOld(newOld)
    setSnapNew(newNew)
  }, [snapshots])

  // Check for cached results when snapshots are selected
  useEffect(() => {
    if (!snapOld || !snapNew || !company || !product) return
    setLoading(true)
    setError(null)
    getIntegrityCached(company, product, snapOld, snapNew)
      .then(res => {
        if (res && (res.validation_old || res.validation_new || res.consistency)) {
          setResults(res)
          // Also check for cached report + notes
          return Promise.all([
            getIntegrityReportCached(company, product, snapOld, snapNew).catch(() => null),
            getIntegrityNotes(company, product, snapOld, snapNew).catch(() => null),
          ])
        }
        setResults(null)
        setReport(null)
        setNotes({})
        return null
      })
      .then(extras => {
        if (extras) {
          const [cachedReport, cachedNotes] = extras
          if (cachedReport && cachedReport.analysis_text) setReport(cachedReport)
          else setReport(null)
          if (cachedNotes && cachedNotes.notes) setNotes(cachedNotes.notes)
          else setNotes({})
        }
      })
      .catch(() => {
        setResults(null)
        setReport(null)
        setNotes({})
      })
      .finally(() => setLoading(false))
  }, [company, product, snapOld, snapNew])

  // Run integrity checks
  const handleRun = useCallback(() => {
    if (!snapOld || !snapNew) return
    setLoading(true)
    setError(null)
    setResults(null)
    setReport(null)
    setNotes({})
    runIntegrityCheck(company, product, snapOld, snapNew)
      .then(res => {
        setResults(res)
        setError(null)
      })
      .catch(err => {
        setError(err?.response?.data?.detail ?? 'Failed to run integrity checks.')
      })
      .finally(() => setLoading(false))
  }, [company, product, snapOld, snapNew])

  // Generate AI report
  const handleGenerateReport = useCallback(() => {
    if (!snapOld || !snapNew) return
    setReportLoading(true)
    generateIntegrityReport(company, product, snapOld, snapNew)
      .then(res => {
        setReport(res)
        // Load notes if any
        return getIntegrityNotes(company, product, snapOld, snapNew).catch(() => null)
      })
      .then(notesRes => {
        if (notesRes?.notes) setNotes(notesRes.notes)
      })
      .catch(() => setReport({ error: 'Failed to generate AI report.' }))
      .finally(() => setReportLoading(false))
  }, [company, product, snapOld, snapNew])

  // Save a single note
  const handleSaveNote = useCallback((idx, text) => {
    const updated = { ...notes, [idx]: text }
    setNotes(updated)
    saveIntegrityNotes(company, product, snapOld, snapNew, updated).catch(() => {})
  }, [company, product, snapOld, snapNew, notes])

  const oldVal = results?.validation_old
  const newVal = results?.validation_new
  const consistency = results?.consistency

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* ── Section A: Tape Selector Bar ── */}
      <Card style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>
            Old Tape
          </div>
          <DarkSelect value={snapOld} onChange={setSnapOld}>
            {(snapshots ?? []).map(s => <option key={s} value={s}>{s}</option>)}
          </DarkSelect>
        </div>
        <div style={{ fontSize: 16, color: 'var(--text-faint)', fontWeight: 700, paddingTop: 14 }}>
          &rarr;
        </div>
        <div>
          <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>
            New Tape
          </div>
          <DarkSelect value={snapNew} onChange={setSnapNew}>
            {(snapshots ?? []).map(s => <option key={s} value={s}>{s}</option>)}
          </DarkSelect>
        </div>
        <div style={{ flex: 1 }} />
        {!results ? (
          <button
            onClick={handleRun}
            disabled={loading || !snapOld || !snapNew}
            style={{
              fontSize: 11, fontWeight: 700, padding: '8px 20px',
              background: loading ? 'var(--border)' : 'var(--gold)',
              color: loading ? 'var(--text-muted)' : '#000',
              border: 'none', borderRadius: 7, cursor: loading ? 'default' : 'pointer',
              letterSpacing: '0.02em', transition: 'all 0.15s',
            }}
          >
            {loading ? 'Running...' : 'Run Integrity Checks'}
          </button>
        ) : (
          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--gold)', fontSize: 10, fontWeight: 600,
              textDecoration: 'underline', padding: '4px 0',
            }}
          >
            {loading ? 'Running...' : 'Re-run'}
          </button>
        )}
      </Card>

      {/* Loading indicator */}
      {loading && <GoldLoadingBar />}

      {/* Error */}
      {error && (
        <Card style={{ borderColor: 'rgba(240,96,96,0.3)' }}>
          <div style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600 }}>{error}</div>
        </Card>
      )}

      {/* ── Section B: Validation Results ── */}
      {results && oldVal && newVal && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
          <ValidationCard title={snapOld} validation={oldVal} />
          <ValidationCard title={snapNew} validation={newVal} />
        </div>
      )}

      {/* ── Section C: Consistency Check Results ── */}
      {results && consistency && (
        <ConsistencyCard consistency={consistency} />
      )}

      {/* ── Section D: AI Report ── */}
      {results && !report && !reportLoading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0' }}>
          <button
            onClick={handleGenerateReport}
            style={{
              fontSize: 11, fontWeight: 700, padding: '9px 24px',
              background: 'transparent',
              color: 'var(--gold)', border: '1.5px solid var(--gold)',
              borderRadius: 7, cursor: 'pointer',
              letterSpacing: '0.02em', transition: 'all 0.15s',
            }}
          >
            Generate AI Report
          </button>
        </div>
      )}

      {reportLoading && (
        <Card>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>
            Generating AI report...
          </div>
          <GoldLoadingBar />
        </Card>
      )}

      {report && !report.error && (
        <ReportSection
          report={report}
          notes={notes}
          onNoteChange={(idx, text) => {
            setNotes(prev => ({ ...prev, [idx]: text }))
          }}
          onNoteSave={handleSaveNote}
        />
      )}

      {report?.error && (
        <Card style={{ borderColor: 'rgba(240,96,96,0.3)' }}>
          <div style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600 }}>{report.error}</div>
        </Card>
      )}
    </div>
  )
}

// ── Validation Card (one per tape) ───────────────────────────────────────────
function ValidationCard({ title, validation }) {
  const critical = validation?.critical ?? []
  const warnings = validation?.warnings ?? []
  const info     = validation?.info ?? []
  const passed   = validation?.passed ?? (critical.length === 0)
  const rowCount = validation?.total_rows ?? '—'

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
          {title}
        </div>
        <PassFailBadge passed={passed} />
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
        <StatChip label="critical" value={critical.length} color="var(--red)" />
        <StatChip label="warnings" value={warnings.length} color="var(--gold)" />
        <StatChip label="info" value={info.length} color="var(--teal)" />
        <StatChip label="rows" value={rowCount} color="var(--text-muted)" />
      </div>

      <IssueList items={critical} type="critical" defaultExpanded={critical.length > 0 && critical.length <= 5} />
      <IssueList items={warnings} type="warning" defaultExpanded={false} />
      <IssueList items={info} type="info" defaultExpanded={false} />

      {critical.length === 0 && warnings.length === 0 && info.length === 0 && (
        <div style={{ fontSize: 11, color: 'var(--teal)', marginTop: 8 }}>
          All checks passed.
        </div>
      )}
    </Card>
  )
}

function StatChip({ label, value, color }) {
  return (
    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color }}>
      <span style={{ fontWeight: 700 }}>{value}</span>{' '}
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
    </span>
  )
}

// ── Consistency Card ─────────────────────────────────────────────────────────
function ConsistencyCard({ consistency }) {
  const allIssues = []
  for (const item of (consistency?.issues ?? [])) allIssues.push({ ...normalizeItem(item), severity: 'critical' })
  for (const item of (consistency?.warnings ?? [])) allIssues.push({ ...normalizeItem(item), severity: 'warning' })
  for (const item of (consistency?.info ?? [])) allIssues.push({ ...normalizeItem(item), severity: 'info' })

  const passed = consistency?.passed ?? (consistency?.issues ?? []).length === 0

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
          Cross-Tape Consistency
        </div>
        <PassFailBadge passed={passed} />
      </div>

      {allIssues.length === 0 ? (
        <div style={{ fontSize: 11, color: 'var(--teal)' }}>
          All consistency checks passed.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {allIssues.map((issue, i) => (
            <ConsistencyItem key={i} issue={issue} />
          ))}
        </div>
      )}
    </Card>
  )
}

function normalizeItem(item) {
  if (typeof item === 'string') return { name: item, detail: '', ids: [] }
  return {
    name: item.check ?? item.name ?? '',
    detail: item.detail ?? item.message ?? '',
    ids: item.ids ?? item.deal_ids ?? [],
  }
}

function ConsistencyItem({ issue }) {
  const [showIds, setShowIds] = useState(false)
  const sev = SEV[issue.severity] ?? SEV.info

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 2,
      borderLeft: `2px solid ${sev.color}`, paddingLeft: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Badge type={issue.severity} />
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
          {issue.name}
        </span>
      </div>
      {issue.detail && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
          {issue.detail}
        </div>
      )}
      {issue.ids.length > 0 && (
        <div>
          <button
            onClick={() => setShowIds(v => !v)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              color: 'var(--gold)', fontSize: 10, fontWeight: 600,
            }}
          >
            {showIds ? 'Hide' : 'Show'} {issue.ids.length} affected deal{issue.ids.length !== 1 ? 's' : ''}
          </button>
          {showIds && (
            <div style={{
              marginTop: 4, padding: '6px 8px', background: 'var(--bg-deep)',
              borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)',
              fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.6,
              maxHeight: 120, overflowY: 'auto',
            }}>
              {issue.ids.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Report Section ───────────────────────────────────────────────────────────
function ReportSection({ report, notes, onNoteChange, onNoteSave }) {
  const analysis = report?.analysis_text ?? ''
  const questions = report?.questions ?? []
  const pdfPath = report?.pdf_path ?? null

  // Split analysis text into sections by markdown-style headers
  const sections = parseAnalysisSections(analysis)

  return (
    <Card>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
        AI Integrity Report
      </div>

      {/* Analysis text */}
      {sections.map((section, i) => (
        <div key={i} style={{ marginBottom: 14 }}>
          {section.heading && (
            <div style={{
              fontSize: 12, fontWeight: 700, color: 'var(--gold)',
              marginBottom: 6, letterSpacing: '0.01em',
            }}>
              {section.heading}
            </div>
          )}
          <div style={{
            fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7,
            whiteSpace: 'pre-wrap',
          }}>
            {section.body}
          </div>
        </div>
      ))}

      {/* Questions for the Company */}
      {questions.length > 0 && (
        <>
          <div style={{
            borderTop: '1px solid var(--border)', marginTop: 16, paddingTop: 16,
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
              Questions for the Company
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {questions.map((q, idx) => (
                <div key={idx} style={{
                  background: 'var(--bg-deep)', borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px',
                  borderLeft: `3px solid ${(notes[idx] ?? '').trim() ? 'var(--gold)' : 'var(--border)'}`,
                  transition: 'border-color 0.15s',
                }}>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, fontWeight: 500 }}>
                    {typeof q === 'string' ? q : (q.question ?? q.text ?? String(q))}
                  </div>
                  <NoteField
                    value={notes[idx] ?? ''}
                    onChange={(text) => onNoteChange(idx, text)}
                    onSave={(text) => onNoteSave(idx, text)}
                  />
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* PDF saved indicator */}
      {pdfPath && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ color: 'var(--teal)', fontWeight: 600 }}>PDF saved</span>{' '}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{pdfPath}</span>
          </div>
        </div>
      )}
    </Card>
  )
}

// ── Parse analysis text into sections ────────────────────────────────────────
function parseAnalysisSections(text) {
  if (!text) return [{ heading: null, body: '' }]

  const lines = text.split('\n')
  const sections = []
  let currentHeading = null
  let currentBody = []

  for (const line of lines) {
    // Match markdown headers: ## Heading or **Heading**
    const headerMatch = line.match(/^#{1,3}\s+(.+)$/) || line.match(/^\*\*(.+)\*\*$/)
    if (headerMatch) {
      if (currentHeading !== null || currentBody.length > 0) {
        sections.push({ heading: currentHeading, body: currentBody.join('\n').trim() })
      }
      currentHeading = headerMatch[1].replace(/\*\*/g, '').trim()
      currentBody = []
    } else {
      currentBody.push(line)
    }
  }

  // Push last section
  if (currentHeading !== null || currentBody.length > 0) {
    sections.push({ heading: currentHeading, body: currentBody.join('\n').trim() })
  }

  return sections.length > 0 ? sections : [{ heading: null, body: text }]
}
