import { useState, useRef, useEffect } from 'react'
import { postChat } from '../services/api'

/**
 * DataChat — dark theme natural language chat panel
 *
 * Props:
 *   company   string
 *   product   string
 *   snapshot  string
 *   currency  string
 */
export default function DataChat({ company, product, snapshot, currency }) {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const reply = await postChat(company, product, snapshot, currency, q, messages)
      setMessages(prev => [...prev, { role: 'ai', text: reply }])
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error — please try again.', isError: true }])
    } finally {
      setLoading(false)
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
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
          background: 'var(--blue)',
          boxShadow: '0 0 6px rgba(91,141,239,0.5)',
        }} />
        <span style={{
          fontSize: 10, fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.08em',
          color: 'var(--blue)',
        }}>
          Data Chat
        </span>
        <span style={{ fontSize: 9, color: 'var(--text-faint)', marginLeft: 2 }}>
          Ask anything about this portfolio
        </span>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '14px 16px',
        display: 'flex', flexDirection: 'column', gap: 10,
        minHeight: 180, maxHeight: 340,
      }}>
        {messages.length === 0 && (
          <Suggestions onSelect={q => { setInput(q); }} />
        )}
        {messages.map((m, i) => (
          <Bubble key={i} msg={m} />
        ))}
        {loading && <TypingIndicator />}
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
          placeholder="e.g. What's the denial rate trend for Daman?"
          rows={1}
          style={{
            flex: 1, resize: 'none', overflow: 'hidden',
            background: '#080B12', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 12px',
            fontSize: 12, color: 'var(--text-primary)',
            fontFamily: 'var(--font-ui)',
            outline: 'none', lineHeight: 1.5,
            transition: 'border-color 0.15s',
          }}
          onFocus={e => e.target.style.borderColor = 'var(--blue)'}
          onBlur={e => e.target.style.borderColor = 'var(--border)'}
        />
        <button onClick={send} disabled={loading || !input.trim()} style={{
          background: input.trim() && !loading ? 'var(--blue)' : 'var(--bg-deep)',
          border: '1px solid var(--border)',
          borderRadius: 8, padding: '8px 14px',
          fontSize: 11, fontWeight: 600, color: input.trim() ? 'white' : 'var(--text-faint)',
          cursor: input.trim() && !loading ? 'pointer' : 'default',
          transition: 'all 0.15s', flexShrink: 0,
        }}>
          Send
        </button>
      </div>
    </div>
  )
}

/* ── Sub-components ── */

function Bubble({ msg }) {
  const isUser = msg.role === 'user'
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

function Suggestions({ onSelect }) {
  const prompts = [
    'What is the current denial rate by insurer?',
    'Which cohort has the worst collection performance?',
    'How has deployment trended over the last 6 months?',
  ]
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