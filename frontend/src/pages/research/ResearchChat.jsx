import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { postResearchChat, getNotebookLMStatus, syncNotebookLM } from '../../services/api'

const SUGGESTED_QUESTIONS = {
  tamara_summary: [
    'What are the covenant trigger levels?',
    'Summarize the securitisation facility terms',
    'What does the Deloitte FDD conclude?',
    'Compare vintage performance across reports',
    'What are the key risk factors identified?',
    'Summarize the facility structure',
  ],
  klaim: [
    'What are the facility advance rates and eligibility criteria?',
    'Which provider groups have the highest denial rates?',
    'Summarize the key risk factors from the legal documents',
    'What is the current collection performance by vintage?',
    'What are the concentration limits and are any breached?',
    'How does the loss waterfall break down by vintage?',
  ],
  silq: [
    'Which product type (BNPL, RBF, RCL) performs best?',
    'What is the overdue rate trend across shops?',
    'Summarize the key covenants and compliance status',
    'How does loan tenure affect collection rates?',
    'What are the concentration risks in the portfolio?',
    'Compare delinquency trends across recent tapes',
  ],
  ejari_summary: [
    'What is the current DPD distribution and trend?',
    'Which cohort vintage has the highest loss rate?',
    'How do roll rates compare across DPD buckets?',
    'What is the recovery rate from legal proceedings?',
    'Summarize the key credit quality indicators',
    'What are the write-off trends and fraud patterns?',
  ],
  aajil: [
    'What is the business model and how does the raw materials credit work?',
    'What are the underwriting criteria and financial ratio thresholds?',
    'How does the trust score system drive collections strategy?',
    'What are the key risk mitigation factors?',
    'What is the DPD profile and collections phase breakdown?',
    'Who are the key investors and what is the growth trajectory?',
  ],
  default: [
    'What are the key risk factors in this portfolio?',
    'Summarize the facility structure and terms',
    'What is the current collection performance?',
    'What are the covenant levels and compliance status?',
    'Compare performance trends across recent reports',
    'What are the main concentration risks?',
  ],
}

const ENGINE_LABELS = {
  claude: 'Claude RAG',
  notebooklm: 'NotebookLM',
  merged: 'Dual Engine',
  retrieval_only: 'Retrieval Only',
}

const ENGINE_COLORS = {
  claude: { bg: 'rgba(91,141,239,0.12)', border: 'rgba(91,141,239,0.25)', text: '#5B8DEF' },
  notebooklm: { bg: 'rgba(45,212,191,0.12)', border: 'rgba(45,212,191,0.25)', text: '#2DD4BF' },
  merged: { bg: 'rgba(201,168,76,0.12)', border: 'rgba(201,168,76,0.25)', text: '#C9A84C' },
  retrieval_only: { bg: 'rgba(132,148,167,0.12)', border: 'rgba(132,148,167,0.25)', text: '#8494A7' },
}

function EngineBadge({ engine }) {
  const colors = ENGINE_COLORS[engine] || ENGINE_COLORS.retrieval_only
  const label = ENGINE_LABELS[engine] || engine
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 700,
      fontFamily: 'var(--font-mono)',
      padding: '2px 8px',
      borderRadius: 10,
      background: colors.bg,
      color: colors.text,
      border: `1px solid ${colors.border}`,
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
    }}>
      {label}
    </span>
  )
}

function NLMStatusIndicator({ status, onSync, syncing }) {
  if (!status) return null

  const isAvailable = status.available
  const isInstalled = status.library_installed
  const isAuth = status.authenticated

  let color, label, detail
  if (isAvailable) {
    color = '#2DD4BF'
    label = 'NLM Active'
    detail = `${status.integration_method} | ${status.notebooks_cached} notebook(s)`
  } else if (isInstalled && !isAuth) {
    color = '#F0C040'
    label = 'NLM Not Authenticated'
    detail = 'Run notebooklm login'
  } else {
    color = '#8494A7'
    label = 'NLM Unavailable'
    detail = 'Package not installed'
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      fontSize: 10,
      color: 'var(--text-muted)',
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: color,
        boxShadow: `0 0 6px ${color}50`,
      }} />
      <span style={{ fontWeight: 600, color }}>{label}</span>
      <span style={{ color: 'var(--text-faint)' }}>{detail}</span>
      {isAvailable && (
        <button
          onClick={onSync}
          disabled={syncing}
          style={{
            fontSize: 9,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: syncing ? 'var(--border)' : 'transparent',
            color: syncing ? 'var(--text-faint)' : 'var(--accent-teal)',
            cursor: syncing ? 'not-allowed' : 'pointer',
            transition: 'all var(--transition-fast)',
          }}
        >
          {syncing ? 'Syncing...' : 'Sync Sources'}
        </button>
      )}
    </div>
  )
}

function SynthesisNotes({ notes }) {
  const [expanded, setExpanded] = useState(false)
  if (!notes) return null

  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          fontSize: 9,
          fontWeight: 600,
          color: 'var(--accent-gold)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        <span style={{
          transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: 'transform 150ms',
          display: 'inline-block',
        }}>
          {'>>'}
        </span>
        Synthesis Notes
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              marginTop: 6,
              padding: '8px 12px',
              background: 'rgba(201,168,76,0.06)',
              border: '1px solid rgba(201,168,76,0.15)',
              borderRadius: 6,
              fontSize: 11,
              lineHeight: 1.5,
              color: 'var(--text-muted)',
            }}
          >
            {notes}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function ResearchChat() {
  const { company, product, analysisType } = useCompany()
  const { isMobile } = useBreakpoint()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [nlmStatus, setNlmStatus] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [nlmDismissed, setNlmDismissed] = useState(false)
  const [nlmWarning, setNlmWarning] = useState(null)
  const [pendingQuestion, setPendingQuestion] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Fetch NLM status on mount
  useEffect(() => {
    getNotebookLMStatus()
      .then(status => {
        setNlmStatus(status)
        if (status && !status.available) {
          setNlmWarning(
            status.library_installed && !status.authenticated
              ? { code: 'nlm_auth_expired', message: 'NotebookLM authentication has expired. Research will use Claude RAG only.', fix: "Run 'notebooklm login' in the project virtual environment to re-authenticate." }
              : !status.library_installed
                ? { code: 'nlm_not_installed', message: 'NotebookLM library is not installed. Research will use Claude RAG only.', fix: "Install with 'pip install notebooklm-py' then run 'notebooklm login'." }
                : null
          )
        }
      })
      .catch(() => setNlmStatus(null))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSync() {
    if (!company || !product || syncing) return
    setSyncing(true)
    try {
      const result = await syncNotebookLM(company, product)
      // Refresh status after sync
      const freshStatus = await getNotebookLMStatus()
      setNlmStatus(freshStatus)
      // Show sync result as system message
      const uploaded = result.uploaded || 0
      const skipped = result.skipped || 0
      const errors = result.errors?.length || 0
      setMessages(prev => [...prev, {
        role: 'system',
        text: `NotebookLM sync complete: ${uploaded} uploaded, ${skipped} already synced${errors ? `, ${errors} errors` : ''}.`,
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'system',
        text: 'NotebookLM sync failed. Check authentication.',
        isError: true,
      }])
    } finally {
      setSyncing(false)
    }
  }

  async function send(question) {
    const q = (question || input).trim()
    if (!q || loading) return

    // Block first query if NLM is unavailable and user hasn't acknowledged
    if (nlmWarning && !nlmDismissed) {
      setPendingQuestion(q)
      setInput('')
      return
    }
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const reply = await postResearchChat(company, product, q, messages)
      setMessages(prev => [...prev, {
        role: 'ai',
        text: reply.answer || reply.text || reply,
        citations: reply.citations || [],
        engine: reply.engine || 'claude',
        synthesis_notes: reply.synthesis_notes || null,
        nlm_available: reply.nlm_available || false,
        claude_answer: reply.claude_answer || null,
        nlm_answer: reply.nlm_answer || null,
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'ai',
        text: 'Error -- please try again.',
        isError: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  function handleNlmDismiss() {
    setNlmDismissed(true)
    if (pendingQuestion) {
      const q = pendingQuestion
      setPendingQuestion(null)
      // Use setTimeout to let state update before re-sending
      setTimeout(() => send(q), 0)
    }
  }

  async function handleNlmRetry() {
    try {
      const status = await getNotebookLMStatus()
      setNlmStatus(status)
      if (status && status.available) {
        setNlmWarning(null)
        if (pendingQuestion) {
          const q = pendingQuestion
          setPendingQuestion(null)
          setTimeout(() => send(q), 0)
        }
      }
    } catch { /* status check failed, warning stays */ }
  }

  const pad = isMobile ? 14 : 28

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{
        padding: pad,
        maxWidth: 900,
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - var(--navbar-height) - 56px)',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: 20, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <h1 style={{
            fontSize: isMobile ? 20 : 24,
            fontWeight: 800,
            color: 'var(--text-primary)',
            margin: 0,
            fontFamily: 'var(--font-display)',
            letterSpacing: '-0.02em',
          }}>
            Research Chat
          </h1>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--accent-blue)',
            boxShadow: '0 0 8px rgba(91,141,239,0.5)',
            animation: 'pulse 2s ease-in-out infinite',
          }} />
        </div>
        <p style={{
          fontSize: 12,
          color: 'var(--text-muted)',
          margin: '0 0 8px',
        }}>
          Dual-engine research across all ingested documents
        </p>
        <NLMStatusIndicator status={nlmStatus} onSync={handleSync} syncing={syncing} />
      </div>

      {/* Chat area */}
      <div style={{
        flex: 1,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 8,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Messages */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          scrollbarWidth: 'thin',
          scrollbarColor: 'var(--border) transparent',
        }}>
          {/* NLM Warning Banner — blocks first query until user acknowledges */}
          {pendingQuestion && nlmWarning && !nlmDismissed && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                margin: '8px 0',
                padding: '16px 20px',
                background: 'rgba(240,192,64,0.08)',
                border: '1px solid rgba(240,192,64,0.25)',
                borderRadius: 8,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 13, color: '#F0C040', marginBottom: 6 }}>
                NotebookLM Unavailable
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                {nlmWarning.message}
              </div>
              <div style={{
                fontSize: 11, color: 'var(--text-faint)',
                fontFamily: 'var(--font-mono)',
                padding: '6px 10px',
                background: 'var(--bg-deep)',
                borderRadius: 4,
                margin: '8px 0 12px',
              }}>
                {nlmWarning.fix}
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={handleNlmDismiss}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: 'var(--accent-gold)', color: '#000', border: 'none', cursor: 'pointer',
                  }}
                >
                  Proceed without NLM
                </button>
                <button
                  onClick={handleNlmRetry}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                    background: 'transparent', color: 'var(--text-muted)',
                    border: '1px solid var(--border)', cursor: 'pointer',
                  }}
                >
                  Retry Connection
                </button>
              </div>
            </motion.div>
          )}

          {/* Welcome state */}
          {messages.length === 0 && !loading && !pendingQuestion && (
            <div style={{ padding: '40px 0', textAlign: 'center' }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 16 }}>
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <div style={{
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--text-primary)',
                marginBottom: 6,
              }}>
                Ask about your data room
              </div>
              <div style={{
                fontSize: 11,
                color: 'var(--text-muted)',
                marginBottom: 12,
                maxWidth: 400,
                margin: '0 auto 12px',
                lineHeight: 1.5,
              }}>
                Research Chat queries all ingested documents using Claude RAG
                {nlmStatus?.available && ' and NotebookLM for dual-engine synthesis'}.
                Answers include source citations.
              </div>

              {/* Engine status badges */}
              <div style={{
                display: 'flex',
                gap: 8,
                justifyContent: 'center',
                marginBottom: 20,
              }}>
                <EngineBadge engine="claude" />
                {nlmStatus?.available && <EngineBadge engine="notebooklm" />}
              </div>

              {/* Suggested questions */}
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 8,
                justifyContent: 'center',
                maxWidth: 560,
                margin: '0 auto',
              }}>
                {(SUGGESTED_QUESTIONS[analysisType] || SUGGESTED_QUESTIONS.default).map((q, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                    onClick={() => send(q)}
                    style={{
                      padding: '7px 14px',
                      fontSize: 11,
                      color: 'var(--text-muted)',
                      background: 'var(--bg-deep)',
                      border: '1px solid var(--border)',
                      borderRadius: 20,
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                      whiteSpace: 'nowrap',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'var(--accent-gold)'
                      e.currentTarget.style.color = 'var(--accent-gold)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border)'
                      e.currentTarget.style.color = 'var(--text-muted)'
                    }}
                  >
                    {q}
                  </motion.button>
                ))}
              </div>
            </div>
          )}

          {/* Message bubbles */}
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end'
                    : msg.role === 'system' ? 'center' : 'flex-start',
                  maxWidth: msg.role === 'system' ? '90%' : '80%',
                }}
              >
                {/* System messages */}
                {msg.role === 'system' ? (
                  <div style={{
                    padding: '6px 14px',
                    borderRadius: 12,
                    background: msg.isError ? 'rgba(240,96,96,0.08)' : 'rgba(45,212,191,0.08)',
                    border: `1px solid ${msg.isError ? 'rgba(240,96,96,0.15)' : 'rgba(45,212,191,0.15)'}`,
                    fontSize: 10,
                    color: msg.isError ? '#F06060' : '#2DD4BF',
                    textAlign: 'center',
                    fontWeight: 600,
                  }}>
                    {msg.text}
                  </div>
                ) : (
                  <>
                    <div style={{
                      padding: '10px 14px',
                      borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                      background: msg.role === 'user'
                        ? 'rgba(201,168,76,0.12)'
                        : msg.isError ? 'rgba(240,96,96,0.08)' : 'var(--bg-deep)',
                      border: `1px solid ${
                        msg.role === 'user'
                          ? 'rgba(201,168,76,0.2)'
                          : msg.isError ? 'rgba(240,96,96,0.15)' : 'var(--border)'
                      }`,
                      fontSize: 12,
                      lineHeight: 1.65,
                      color: msg.isError ? '#F06060' : 'var(--text-primary)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>
                      {msg.text}
                    </div>

                    {/* Engine badge + citations row */}
                    {msg.role === 'ai' && !msg.isError && (
                      <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {/* Engine badge */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          {msg.engine && <EngineBadge engine={msg.engine} />}
                          {msg.engine === 'merged' && (
                            <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>
                              Claude + NotebookLM synthesized
                            </span>
                          )}
                          {msg.nlm_available === false && msg.engine === 'claude' && (
                            <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>
                              NLM unavailable
                            </span>
                          )}
                        </div>

                        {/* Citations */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div style={{
                            display: 'flex',
                            gap: 6,
                            flexWrap: 'wrap',
                            paddingLeft: 2,
                          }}>
                            {msg.citations.map((cit, j) => {
                              const origin = cit.origin || 'claude'
                              const originColor = origin === 'notebooklm'
                                ? 'rgba(45,212,191,0.12)' : 'rgba(201,168,76,0.12)'
                              const originBorder = origin === 'notebooklm'
                                ? 'rgba(45,212,191,0.2)' : 'rgba(201,168,76,0.2)'
                              const originText = origin === 'notebooklm'
                                ? 'var(--accent-teal)' : 'var(--accent-gold)'
                              return (
                                <span
                                  key={j}
                                  title={`${cit.filename || cit.source || `Source ${j + 1}`} (${origin})`}
                                  style={{
                                    fontSize: 9,
                                    fontWeight: 700,
                                    fontFamily: 'var(--font-mono)',
                                    padding: '2px 8px',
                                    borderRadius: 10,
                                    background: originColor,
                                    color: originText,
                                    border: `1px solid ${originBorder}`,
                                    cursor: 'default',
                                  }}
                                >
                                  [{cit.index || j + 1}] {cit.filename || cit.source || `Source ${j + 1}`}
                                </span>
                              )
                            })}
                          </div>
                        )}

                        {/* Synthesis notes for merged answers */}
                        {msg.engine === 'merged' && msg.synthesis_notes && (
                          <SynthesisNotes notes={msg.synthesis_notes} />
                        )}
                      </div>
                    )}
                  </>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Loading indicator */}
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                alignSelf: 'flex-start',
                padding: '10px 14px',
                borderRadius: '12px 12px 12px 4px',
                background: 'var(--bg-deep)',
                border: '1px solid var(--border)',
                display: 'flex',
                gap: 8,
                alignItems: 'center',
              }}
            >
              {[0, 1, 2].map(i => (
                <motion.div
                  key={i}
                  animate={{ y: [0, -6, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                  style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'var(--accent-gold)',
                    opacity: 0.6,
                  }}
                />
              ))}
              <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 4 }}>
                {nlmStatus?.available ? 'Querying Claude + NotebookLM...' : 'Querying Claude RAG...'}
              </span>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          gap: 10,
          alignItems: 'flex-end',
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask about your documents..."
            rows={1}
            style={{
              flex: 1,
              padding: '10px 14px',
              fontSize: 12,
              background: 'var(--bg-deep)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--text-primary)',
              resize: 'none',
              outline: 'none',
              fontFamily: 'inherit',
              lineHeight: 1.5,
              transition: 'border-color var(--transition-fast)',
              maxHeight: 120,
              overflow: 'auto',
            }}
            onFocus={e => { e.target.style.borderColor = 'var(--border-hover)' }}
            onBlur={e => { e.target.style.borderColor = 'var(--border)' }}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || loading}
            style={{
              padding: '10px 18px',
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 8,
              border: 'none',
              background: input.trim() && !loading ? 'var(--accent-gold)' : 'var(--border)',
              color: input.trim() && !loading ? '#000' : 'var(--text-muted)',
              cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
              transition: 'all var(--transition-fast)',
              flexShrink: 0,
            }}
          >
            Send
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(0.85); }
        }
      `}</style>
    </motion.div>
  )
}
