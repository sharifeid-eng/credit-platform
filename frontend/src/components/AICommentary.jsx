import { useState } from 'react'
import { getAICommentary } from '../services/api'

/**
 * AICommentary — dark theme panel
 *
 * Props:
 *   company   string
 *   product   string
 *   snapshot  string
 *   currency  string
 *   cached    string | null   — pre-fetched text from parent (Company.jsx)
 *   onCache   fn(text)        — callback to store in parent state
 */
export default function AICommentary({ company, product, snapshot, currency, cached, onCache }) {
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function generate() {
    if (cached) return
    setLoading(true)
    setError(null)
    try {
      const text = await getAICommentary(company, product, snapshot, currency)
      onCache?.(text)
    } catch (e) {
      setError('Failed to generate commentary.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      background: '#0E1220',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '13px 16px 11px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <PulseDot color="var(--gold)" glow="rgba(201,168,76,0.4)" active={loading} />
          <span style={{
            fontSize: 10, fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.08em',
            color: 'var(--gold)',
          }}>
            AI Commentary
          </span>
        </div>
        {!cached && (
          <button onClick={generate} disabled={loading} style={{
            fontSize: 10, fontWeight: 700,
            padding: '4px 12px', borderRadius: 5,
            background: loading ? 'var(--gold-dim)' : 'var(--gold)',
            color: '#000', border: 'none', cursor: loading ? 'default' : 'pointer',
            fontFamily: 'var(--font-ui)',
            transition: 'background 0.15s',
          }}>
            {loading ? 'Generating…' : 'Generate'}
          </button>
        )}
      </div>

      {/* Body */}
      <div style={{ padding: '14px 16px' }}>
        {error && (
          <div style={{ fontSize: 11, color: 'var(--red)', marginBottom: 10 }}>{error}</div>
        )}

        {!cached && !loading && !error && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Click Generate to produce an AI-powered portfolio summary.
          </div>
        )}

        {loading && <Skeleton />}

        {cached && <CommentaryBody text={cached} />}
      </div>
    </div>
  )
}

/* ── Sub-components ──────────────────────────────── */

function CommentaryBody({ text }) {
  // Expect sections separated by newlines; lines starting with "•" or "-" are bullets
  const lines = text.split('\n').filter(l => l.trim())

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {lines.map((line, i) => {
        const isBullet = /^[•\-›]/.test(line.trim())
        const isHeader = line.trim().endsWith(':') && line.length < 40

        if (isHeader) return (
          <div key={i} style={{
            fontSize: 9, fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.1em',
            color: 'var(--gold-dim)',
            paddingBottom: 4,
            borderBottom: '1px solid rgba(201,168,76,0.15)',
            marginTop: i > 0 ? 4 : 0,
          }}>
            {line.replace(/:$/, '')}
          </div>
        )

        if (isBullet) return (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--gold)', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>›</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.65 }}>
              {line.replace(/^[•\-›]\s*/, '')}
            </span>
          </div>
        )

        return (
          <p key={i} style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.65, margin: 0 }}>
            {line}
          </p>
        )
      })}
    </div>
  )
}

function Skeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[80, 100, 65, 90, 55].map((w, i) => (
        <div key={i} style={{
          height: 10, borderRadius: 4,
          background: 'linear-gradient(90deg, var(--border) 25%, #263040 50%, var(--border) 75%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 1.4s infinite',
          width: `${w}%`,
        }} />
      ))}
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  )
}

function PulseDot({ color, glow, active }) {
  return (
    <div style={{
      width: 6, height: 6, borderRadius: '50%',
      background: color,
      boxShadow: active ? `0 0 8px ${glow}` : 'none',
      animation: active ? 'pulse 1s infinite' : 'none',
    }}>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
    </div>
  )
}