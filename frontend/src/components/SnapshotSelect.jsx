import { useEffect, useMemo, useRef, useState } from 'react'

const SOURCE_STYLES = {
  live: {
    bg: 'rgba(45, 212, 191, 0.15)',
    border: 'rgba(45, 212, 191, 0.35)',
    color: 'var(--accent-teal)',
  },
  tape: {
    bg: 'rgba(201, 168, 76, 0.12)',
    border: 'rgba(201, 168, 76, 0.3)',
    color: 'var(--accent-gold)',
  },
  manual: {
    bg: 'rgba(91, 141, 239, 0.12)',
    border: 'rgba(91, 141, 239, 0.3)',
    color: 'var(--accent-blue)',
  },
}

function SourcePill({ source }) {
  const style = SOURCE_STYLES[source] || SOURCE_STYLES.tape
  return (
    <span style={{
      fontSize: 8, fontWeight: 700, letterSpacing: '0.06em',
      padding: '2px 6px', borderRadius: 3,
      background: style.bg, border: `1px solid ${style.border}`, color: style.color,
      textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      {source || 'tape'}
    </span>
  )
}

/**
 * Styled dropdown for picking a snapshot. Renders a TAPE / LIVE / MANUAL pill
 * next to each option keyed off `snapshotsMeta[filename].source`.
 *
 * Props:
 *   value         — currently-selected snapshot filename (string)
 *   onChange      — (filename) => void
 *   snapshots     — string[] of filenames (order preserved, oldest first)
 *   snapshotsMeta — optional array of {filename, date, source, row_count}
 *                   used to render source pills. When absent, renders plain names.
 *   minWidth      — CSS width for the trigger (default 220px)
 *
 * Keyboard: Esc closes, Arrow Up/Down navigates, Enter selects.
 * Click outside closes.
 */
export default function SnapshotSelect({ value, onChange, snapshots = [], snapshotsMeta, minWidth = 220 }) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(-1)
  const rootRef = useRef(null)

  const metaByFilename = useMemo(() => {
    const m = {}
    ;(snapshotsMeta ?? []).forEach(s => { if (s && s.filename) m[s.filename] = s })
    return m
  }, [snapshotsMeta])

  const currentMeta = value ? metaByFilename[value] : null

  // Click outside closes
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Keyboard nav while open
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (e.key === 'Escape') { setOpen(false); e.preventDefault() }
      else if (e.key === 'ArrowDown') {
        setHighlight(i => Math.min((i < 0 ? snapshots.indexOf(value) : i) + 1, snapshots.length - 1))
        e.preventDefault()
      }
      else if (e.key === 'ArrowUp') {
        setHighlight(i => Math.max((i < 0 ? snapshots.indexOf(value) : i) - 1, 0))
        e.preventDefault()
      }
      else if (e.key === 'Enter' && highlight >= 0 && highlight < snapshots.length) {
        onChange?.(snapshots[highlight])
        setOpen(false)
        e.preventDefault()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, highlight, snapshots, value, onChange])

  const openDropdown = () => {
    setHighlight(value ? Math.max(0, snapshots.indexOf(value)) : 0)
    setOpen(true)
  }

  return (
    <div ref={rootRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openDropdown())}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          fontSize: 11, padding: '6px 10px',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 7, color: 'var(--text-primary)',
          fontFamily: 'var(--font-mono)', outline: 'none', cursor: 'pointer',
          minWidth, justifyContent: 'space-between',
        }}
      >
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {value || '—'}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {currentMeta?.source && <SourcePill source={currentMeta.source} />}
          <span style={{ color: 'var(--text-muted)', fontSize: 9 }}>▾</span>
        </span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0,
          minWidth: '100%', maxHeight: 320, overflowY: 'auto',
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 7, zIndex: 30,
          boxShadow: '0 6px 20px rgba(0, 0, 0, 0.4)',
        }}>
          {snapshots.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text-muted)' }}>
              No snapshots
            </div>
          ) : snapshots.map((s, i) => {
            const meta = metaByFilename[s]
            const isCurrent = s === value
            const isHover = i === highlight
            return (
              <div
                key={s}
                role="option"
                aria-selected={isCurrent}
                onClick={() => { onChange?.(s); setOpen(false) }}
                onMouseEnter={() => setHighlight(i)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 12px',
                  fontSize: 11, fontFamily: 'var(--font-mono)',
                  color: isCurrent ? 'var(--accent-gold)' : 'var(--text-primary)',
                  background: isHover ? 'var(--bg-deep)' : 'transparent',
                  cursor: 'pointer',
                  borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                  justifyContent: 'space-between',
                  fontWeight: isCurrent ? 600 : 400,
                }}
              >
                <span>{s}</span>
                {meta?.source && <SourcePill source={meta.source} />}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
