import { useState, useRef, useEffect } from 'react'
import { postChat, postChatFeedback } from '../services/api'
import { useCompany } from '../contexts/CompanyContext'
import { useAgentStream } from '../hooks/useAgentStream'

/**
 * DataChat — dark theme natural language chat panel
 *
 * Supports two modes:
 *   1. Agent mode (default) — SSE streaming with tool call indicators
 *   2. Legacy mode — single-turn API call (fallback)
 *
 * Props:
 *   company   string
 *   product   string
 *   snapshot  string
 *   currency  string
 */
export default function DataChat({ company, product, snapshot, currency }) {
  const { analysisType } = useCompany()
  const [input, setInput] = useState('')
  const [useAgent, setUseAgent] = useState(true) // Toggle between agent and legacy mode
  const bottomRef = useRef(null)

  // Agent mode state
  const agent = useAgentStream()

  // Legacy mode state
  const [legacyMessages, setLegacyMessages] = useState([])
  const [legacyLoading, setLegacyLoading] = useState(false)

  const messages = useAgent ? agent.messages : legacyMessages
  const loading = useAgent ? agent.isStreaming : legacyLoading

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, agent.currentToolCall])

  async function send() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')

    if (useAgent) {
      agent.send(`/agents/${company}/${product}/analyst/stream`, {
        question: q,
        snapshot,
        currency,
      })
    } else {
      // Legacy mode
      setLegacyMessages(prev => [...prev, { role: 'user', text: q }])
      setLegacyLoading(true)
      try {
        // postChat now returns the full payload {answer, question,
        // asset_class_sources} so we can render Layer 2.5 citations
        // alongside the answer text (D2).
        const reply = await postChat(company, product, snapshot, currency, q, legacyMessages)
        const answer = reply?.answer || ''
        const sources = Array.isArray(reply?.asset_class_sources) ? reply.asset_class_sources : []
        if (!answer.trim()) {
          setLegacyMessages(prev => [...prev, { role: 'ai', text: 'No response received — please try again.', isError: true }])
        } else {
          setLegacyMessages(prev => [...prev, { role: 'ai', text: answer, assetClassSources: sources }])
        }
      } catch {
        setLegacyMessages(prev => [...prev, { role: 'ai', text: 'Error — please try again.', isError: true }])
      } finally {
        setLegacyLoading(false)
      }
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  function handleReset() {
    if (useAgent) {
      agent.reset()
    } else {
      setLegacyMessages([])
    }
  }

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '13px 16px 11px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 7,
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: useAgent ? 'var(--gold)' : 'var(--blue)',
          boxShadow: useAgent ? '0 0 6px rgba(201,168,76,0.5)' : '0 0 6px rgba(91,141,239,0.5)',
        }} />
        <span style={{
          fontSize: 10, fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.08em',
          color: useAgent ? 'var(--gold)' : 'var(--blue)',
        }}>
          {useAgent ? 'Agent Chat' : 'Data Chat'}
        </span>
        <span style={{ fontSize: 9, color: 'var(--text-faint)', marginLeft: 2 }}>
          {useAgent ? 'AI analyst with live data access' : 'Ask anything about this portfolio'}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
          {messages.length > 0 && (
            <button onClick={handleReset} style={{
              background: 'none', border: '1px solid var(--border)', borderRadius: 6,
              padding: '2px 8px', fontSize: 9, color: 'var(--text-faint)', cursor: 'pointer',
            }}>
              New
            </button>
          )}
          <button
            onClick={() => { setUseAgent(!useAgent); handleReset() }}
            title={useAgent ? 'Switch to legacy mode' : 'Switch to agent mode'}
            style={{
              background: 'none', border: '1px solid var(--border)', borderRadius: 6,
              padding: '2px 8px', fontSize: 9, color: 'var(--text-faint)', cursor: 'pointer',
            }}
          >
            {useAgent ? 'Legacy' : 'Agent'}
          </button>
        </div>
      </div>

      {/* Tool call indicator */}
      {agent.currentToolCall && useAgent && (
        <div style={{
          padding: '6px 16px',
          background: 'rgba(201,168,76,0.08)',
          borderBottom: '1px solid rgba(201,168,76,0.15)',
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 10, color: 'var(--gold)',
        }}>
          <div style={{
            width: 4, height: 4, borderRadius: '50%',
            background: 'var(--gold)',
            animation: 'pulse 1s infinite',
          }} />
          {agent.currentToolCall.description}
          <style>{`@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.3 } }`}</style>
        </div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: 10,
        minHeight: 180, maxHeight: 340,
      }}>
        {messages.length === 0 && (
          <Suggestions analysisType={analysisType} onSelect={q => { setInput(q); }} />
        )}
        {messages.map((m, i) => (
          <Bubble key={i} msg={m} company={company} product={product} />
        ))}
        {legacyLoading && !useAgent && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: '10px 12px',
        display: 'flex', gap: 8, alignItems: 'flex-end',
      }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask a question about the portfolio..."
          rows={1}
          style={{
            flex: 1, resize: 'none', overflow: 'hidden',
            background: 'var(--bg-deep)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 12px',
            fontSize: 12, color: 'var(--text-primary)',
            fontFamily: 'var(--font-ui)',
            outline: 'none', lineHeight: 1.5,
            transition: 'border-color 0.15s',
          }}
          onFocus={e => e.target.style.borderColor = useAgent ? 'var(--gold)' : 'var(--blue)'}
          onBlur={e => e.target.style.borderColor = 'var(--border)'}
        />
        {loading && useAgent ? (
          <button onClick={agent.cancel} style={{
            background: 'var(--red)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 14px',
            fontSize: 11, fontWeight: 600, color: 'white',
            cursor: 'pointer', transition: 'all 0.15s', flexShrink: 0,
          }}>
            Stop
          </button>
        ) : (
          <button onClick={send} disabled={loading || !input.trim()} style={{
            background: input.trim() && !loading ? (useAgent ? 'var(--gold)' : 'var(--blue)') : 'var(--bg-deep)',
            border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 14px',
            fontSize: 11, fontWeight: 600, color: input.trim() ? 'white' : 'var(--text-faint)',
            cursor: input.trim() && !loading ? 'pointer' : 'default',
            transition: 'all 0.15s', flexShrink: 0,
          }}>
            Send
          </button>
        )}
      </div>

      {/* Token stats (agent mode) */}
      {useAgent && agent.tokenStats && (
        <div style={{
          padding: '4px 16px 6px', fontSize: 9, color: 'var(--text-faint)',
          borderTop: '1px solid var(--border)',
          display: 'flex', gap: 12,
        }}>
          <span>Tokens: {(agent.tokenStats.input + agent.tokenStats.output).toLocaleString()}</span>
          <span>Turns: {agent.tokenStats.turns}</span>
          {agent.sessionId && <span>Session: {agent.sessionId.slice(0, 6)}</span>}
        </div>
      )}
    </div>
  )
}

/* ── Sub-components ── */

function Bubble({ msg, company, product }) {
  const isUser = msg.role === 'user'
  const [feedback, setFeedback] = useState(null) // 'up' | 'down' | null
  const [sourcesExpanded, setSourcesExpanded] = useState(false)

  const handleFeedback = async (rating) => {
    setFeedback(rating)
    try {
      await postChatFeedback(company, product, {
        rating,
        original_response: msg.text,
      })
    } catch (e) {
      console.error('Feedback failed:', e)
    }
  }

  // Layer 2.5 external sources — only present on AI replies where the
  // Asset Class Mind had citation-bearing entries in context. Not an
  // attribution of which URL informed which sentence (we don't have
  // per-sentence provenance), just "here's the research that was
  // available in context when the model answered."
  const assetClassSources = !isUser && Array.isArray(msg.assetClassSources)
    ? msg.assetClassSources
    : []

  return (
    <div style={{
      alignSelf: isUser ? 'flex-end' : 'flex-start',
      maxWidth: '85%',
    }}>
      <div style={{
        fontSize: 11, lineHeight: 1.65,
        padding: '8px 12px', borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
        background: isUser ? 'rgba(91,141,239,0.15)' : 'var(--bg-deep)',
        border: `1px solid ${isUser ? 'rgba(91,141,239,0.3)' : 'var(--border)'}`,
        color: msg.isError ? 'var(--red)' : 'var(--text-primary)',
        whiteSpace: 'pre-wrap',
      }}>
        {msg.text}
      </div>

      {/* Layer 2.5 external sources (D2): collapsible footer */}
      {assetClassSources.length > 0 && (
        <div style={{ marginTop: 4, marginLeft: 4 }}>
          <button
            onClick={() => setSourcesExpanded(v => !v)}
            style={{
              background: 'none', border: 'none', padding: '2px 0', cursor: 'pointer',
              fontSize: 9, color: 'var(--text-faint)', letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
            title="External sources from the Asset Class Mind that were available in context"
          >
            {sourcesExpanded ? '▾' : '▸'} Informed by {assetClassSources.length} asset-class source{assetClassSources.length === 1 ? '' : 's'}
          </button>
          {sourcesExpanded && (
            <ol style={{
              margin: '4px 0 0 14px', padding: 0, fontSize: 10,
              color: 'var(--text-muted)', lineHeight: 1.5,
            }}>
              {assetClassSources.slice(0, 25).map((s, i) => (
                <li key={i} style={{ marginBottom: 3 }}>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    style={{ color: 'var(--teal)', textDecoration: 'none' }}
                    onMouseEnter={e => { e.target.style.textDecoration = 'underline' }}
                    onMouseLeave={e => { e.target.style.textDecoration = 'none' }}
                  >
                    {s.title || s.url}
                  </a>
                  <span style={{ color: 'var(--text-faint)', marginLeft: 6, fontSize: 9 }}>
                    · {s.entry_category || 'entry'} · {s.source || 'unknown'}
                    {s.page_age ? ` · ${s.page_age}` : ''}
                  </span>
                </li>
              ))}
              {assetClassSources.length > 25 && (
                <li style={{ color: 'var(--text-faint)', fontSize: 9, listStyle: 'none' }}>
                  … and {assetClassSources.length - 25} more (Operator → Asset Classes to browse)
                </li>
              )}
            </ol>
          )}
        </div>
      )}

      {/* Feedback buttons for AI responses */}
      {!isUser && !msg.isError && (
        <div style={{ display: 'flex', gap: 4, marginTop: 3, marginLeft: 4 }}>
          {feedback ? (
            <span style={{ fontSize: 9, color: 'var(--text-faint)' }}>
              {feedback === 'up' ? 'Thanks!' : 'Noted'}
            </span>
          ) : (
            <>
              <button
                onClick={() => handleFeedback('up')}
                title="Helpful"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
                  fontSize: 11, color: 'var(--text-faint)', opacity: 0.6,
                  transition: 'opacity 0.15s, color 0.15s',
                }}
                onMouseEnter={e => { e.target.style.opacity = 1; e.target.style.color = 'var(--teal)' }}
                onMouseLeave={e => { e.target.style.opacity = 0.6; e.target.style.color = 'var(--text-faint)' }}
              >
                &#x25B2;
              </button>
              <button
                onClick={() => handleFeedback('down')}
                title="Not helpful"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
                  fontSize: 11, color: 'var(--text-faint)', opacity: 0.6,
                  transition: 'opacity 0.15s, color 0.15s',
                }}
                onMouseEnter={e => { e.target.style.opacity = 1; e.target.style.color = '#F06060' }}
                onMouseLeave={e => { e.target.style.opacity = 0.6; e.target.style.color = 'var(--text-faint)' }}
              >
                &#x25BC;
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ alignSelf: 'flex-start' }}>
      <div style={{
        display: 'flex', gap: 4, alignItems: 'center',
        padding: '8px 14px',
        background: 'var(--bg-deep)', border: '1px solid var(--border)',
        borderRadius: '12px 12px 12px 2px',
      }}>
        {[0, 0.2, 0.4].map((delay, i) => (
          <div key={i} style={{
            width: 5, height: 5, borderRadius: '50%',
            background: 'var(--blue)',
            animation: `bounce 0.8s ${delay}s infinite`,
          }} />
        ))}
        <style>{`
          @keyframes bounce {
            0%,80%,100% { transform: translateY(0); opacity:0.4 }
            40%          { transform: translateY(-4px); opacity:1 }
          }
        `}</style>
      </div>
    </div>
  )
}

const PROMPTS = {
  silq: [
    'Which product type (BNPL, RBF, RCL) has the best collection performance? Drill into the worst-performing type.',
    'What is driving delinquency? Check the overdue rate trend and identify the top contributing shops.',
    'Compare our covenant compliance to thresholds — are any close to breach?',
    'What is the PAR 30+ and how does it break down by vintage?',
  ],
  ejari_summary: [
    'What is the current DPD distribution and how is it trending?',
    'Which cohort vintage has the highest net loss rate? What drove it?',
    'How do roll rates compare across DPD buckets?',
    'What is the recovery rate and size of the legal recovery pipeline?',
  ],
  aajil: [
    'What is the DPD 60+ rate and how does it compare to the covenant threshold?',
    'How has GMV and customer growth trended? Check the deployment history.',
    'Which customer segments have the worst collection rates? Run a segment analysis.',
    'Search the data room for information about the underwriting process.',
  ],
  default: [
    'What is driving the PAR30 level? Drill into the worst-performing vintages.',
    'Compare our collection velocity to the covenant thresholds — any breaches?',
    'Run a stress test on provider concentration — what happens if the top 3 providers default?',
    'Search the data room for any references to the facility concentration limits.',
  ],
}

function Suggestions({ analysisType, onSelect }) {
  const prompts = PROMPTS[analysisType] ?? PROMPTS.default
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ fontSize: 9, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>
        Suggested questions
      </div>
      {prompts.map((p, i) => (
        <button key={i} onClick={() => onSelect(p)} style={{
          textAlign: 'left', background: 'var(--bg-deep)',
          border: '1px solid var(--border)', borderRadius: 8,
          padding: '7px 10px', fontSize: 11, color: 'var(--text-muted)',
          cursor: 'pointer', fontFamily: 'var(--font-ui)',
          transition: 'border-color 0.15s, color 0.15s',
        }}
          onMouseEnter={e => { e.target.style.borderColor = 'var(--blue)'; e.target.style.color = 'var(--text-primary)' }}
          onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-muted)' }}
        >
          {p}
        </button>
      ))}
    </div>
  )
}