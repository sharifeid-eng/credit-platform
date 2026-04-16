import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { postResearchChat } from '../../services/api'

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

export default function ResearchChat() {
  const { company, product, analysisType } = useCompany()
  const { isMobile } = useBreakpoint()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(question) {
    const q = (question || input).trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const reply = await postResearchChat(company, product, q, messages)
      setMessages(prev => [...prev, {
        role: 'ai',
        text: reply.answer || reply.text || reply,
        citations: reply.citations || [],
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
          margin: 0,
        }}>
          AI-powered research across all ingested documents
        </p>
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
          {/* Welcome state */}
          {messages.length === 0 && !loading && (
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
                Research Chat queries all ingested documents using Claude RAG.
                Answers include source citations.
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
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '80%',
                }}
              >
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

                {/* Citations row */}
                {msg.role === 'ai' && !msg.isError && msg.citations && msg.citations.length > 0 && (
                  <div style={{
                    marginTop: 8,
                    display: 'flex',
                    gap: 6,
                    flexWrap: 'wrap',
                    paddingLeft: 2,
                  }}>
                    {msg.citations.map((cit, j) => (
                      <span
                        key={j}
                        title={cit.filename || cit.source || `Source ${j + 1}`}
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          fontFamily: 'var(--font-mono)',
                          padding: '2px 8px',
                          borderRadius: 10,
                          background: 'rgba(201,168,76,0.12)',
                          color: 'var(--accent-gold)',
                          border: '1px solid rgba(201,168,76,0.2)',
                          cursor: 'default',
                        }}
                      >
                        [{cit.index || j + 1}] {cit.filename || cit.source || `Source ${j + 1}`}
                      </span>
                    ))}
                  </div>
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
                Querying Claude RAG...
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
