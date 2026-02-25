import { useState } from 'react'
import { getTabInsight } from '../services/api'

/**
 * TabInsight — compact one-click AI insight bar shown at top of each non-overview tab
 *
 * Props:
 *   company   string
 *   product   string
 *   snapshot  string
 *   currency  string
 *   tab       string   — e.g. "deployment", "denial-trend"
 */
export default function TabInsight({ company, product, snapshot, currency, tab }) {
  const [text, setText]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen]       = useState(false)
  const [error, setError]     = useState(null)

  async function fetch() {
    if (text) { setOpen(o => !o); return }
    setLoading(true)
    setOpen(true)
    setError(null)
    try {
      const result = await getTabInsight(company, product, snapshot, currency, tab)
      setText(result)
    } catch {
      setError('Failed to load insight.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      background: open ? 'rgba(201,168,76,0.06)' : 'transparent',
      border: '1px solid',
      borderColor: open ? 'rgba(201,168,76,0.25)' : 'var(--border)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
      marginBottom: 16,
      transition: 'all 0.2s',
    }}>
      {/* Trigger row */}
      <button onClick={fetch} style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 8,
        padding: '9px 14px', background: 'none', border: 'none',
        cursor: 'pointer', textAlign: 'left',
      }}>
        <SparkIcon />
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--gold)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          AI Insight
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-faint)', flex: 1 }}>
          {loading ? 'Analysing…' : text ? 'Click to toggle' : `Get AI insight for this view`}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
          ▾
        </span>
      </button>

      {/* Expanded body */}
      {open && (
        <div style={{
          padding: '2px 14px 12px 36px',
          borderTop: '1px solid rgba(201,168,76,0.12)',
        }}>
          {loading && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', paddingTop: 8 }}>
              Generating…
            </div>
          )}
          {error && (
            <div style={{ fontSize: 11, color: 'var(--red)', paddingTop: 8 }}>{error}</div>
          )}
          {text && !loading && (
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.7, margin: '8px 0 0' }}>
              {text}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function SparkIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"
        fill="#C9A84C" opacity="0.9" />
    </svg>
  )
}