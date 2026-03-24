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
import { motion, AnimatePresence } from 'framer-motion'

export default function ChartPanel({ title, subtitle, action, loading, error, minHeight = 320, children }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 20px 12px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
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
        <AnimatePresence mode="wait">
          {loading ? (
            <SkeletonChart key="skeleton" minHeight={minHeight} />
          ) : error ? (
            <ErrorState key="error" message={error} minHeight={minHeight} />
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

function SkeletonChart({ minHeight }) {
  return (
    <motion.div
      key="skeleton"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      style={{
        minHeight: minHeight - 40,
        display: 'flex', flexDirection: 'column',
        gap: 12, padding: '20px 0',
      }}
    >
      {/* Fake chart bars */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: minHeight - 120, padding: '0 20px' }}>
        {[65, 80, 45, 90, 55, 70, 40, 85, 60, 75, 50, 88].map((h, i) => (
          <div key={i} style={{
            flex: 1,
            height: `${h}%`,
            borderRadius: '4px 4px 0 0',
            background: 'linear-gradient(90deg, var(--border) 25%, #243A50 50%, var(--border) 75%)',
            backgroundSize: '200% 100%',
            animation: `shimmer 1.4s infinite ${i * 0.05}s`,
          }} />
        ))}
      </div>
      {/* Fake axis */}
      <div style={{
        height: 8, borderRadius: 4, width: '100%',
        background: 'linear-gradient(90deg, var(--border) 25%, #243A50 50%, var(--border) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s infinite',
      }} />
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </motion.div>
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
