/**
 * ChartPanel — consistent wrapper for every chart tab
 *
 * Props:
 *   title      string    — chart title
 *   subtitle   string    — one-line context below title
 *   action     node      — optional right-side element (button, toggle, etc.)
 *   loading    bool
 *   error      string
 *   minHeight  number    — default 320
 *   children   node      — the Recharts component
 */
export default function ChartPanel({ title, subtitle, action, loading, error, minHeight = 320, children }) {
  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px 12px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
            {title}
          </div>
          {subtitle && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
              {subtitle}
            </div>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>

      {/* Body */}
      <div style={{ padding: '20px', minHeight }}>
        {loading ? (
          <LoadingState minHeight={minHeight} />
        ) : error ? (
          <ErrorState message={error} minHeight={minHeight} />
        ) : (
          children
        )}
      </div>
    </div>
  )
}

function LoadingState({ minHeight }) {
  return (
    <div style={{
      minHeight: minHeight - 40,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 10,
    }}>
      <div style={{
        width: 24, height: 24, borderRadius: '50%',
        border: '2px solid var(--border)',
        borderTopColor: 'var(--gold)',
        animation: 'spin 0.8s linear infinite',
      }} />
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Loading…</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function ErrorState({ message, minHeight }) {
  return (
    <div style={{
      minHeight: minHeight - 40,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        fontSize: 11, color: 'var(--red)',
        background: 'var(--red-muted)', padding: '8px 14px',
        borderRadius: 'var(--radius-sm)', border: '1px solid rgba(240,96,96,0.2)',
      }}>
        {message || 'Failed to load chart data.'}
      </div>
    </div>
  )
}