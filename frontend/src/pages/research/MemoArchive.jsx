import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { listMemos } from '../../services/api'

const STATUS_STYLES = {
  draft:  { bg: 'rgba(91,141,239,0.12)',  color: '#5B8DEF', label: 'Draft' },
  review: { bg: 'rgba(201,168,76,0.12)',  color: '#C9A84C', label: 'Review' },
  final:  { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'Final' },
}

const TEMPLATE_BADGES = {
  credit_memo:       { label: 'Credit Memo',   color: '#C9A84C' },
  monitoring_update: { label: 'Monitoring',     color: '#5B8DEF' },
  due_diligence:     { label: 'Due Diligence',  color: '#2DD4BF' },
  quarterly_review:  { label: 'Quarterly',      color: '#8494A7' },
}

const FILTER_OPTIONS = [
  { key: 'all',    label: 'All' },
  { key: 'draft',  label: 'Draft' },
  { key: 'review', label: 'Review' },
  { key: 'final',  label: 'Final' },
]

export default function MemoArchive() {
  const { company, product } = useCompany()
  const { isMobile } = useBreakpoint()
  const navigate = useNavigate()

  const [memos, setMemos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    setError(null)
    listMemos(company, product)
      .then(data => {
        setMemos(Array.isArray(data) ? data : data?.memos || [])
      })
      .catch(() => {
        // API not yet wired - show empty state gracefully
        setMemos([])
      })
      .finally(() => setLoading(false))
  }, [company, product])

  const filtered = filter === 'all'
    ? memos
    : memos.filter(m => m.status === filter)

  const pad = isMobile ? 14 : 28

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ padding: pad, maxWidth: 1200, margin: '0 auto' }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: isMobile ? 'flex-start' : 'center',
        justifyContent: 'space-between',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 12 : 0,
        marginBottom: 24,
      }}>
        <div>
          <h1 style={{
            fontSize: isMobile ? 20 : 24,
            fontWeight: 800,
            color: 'var(--text-primary)',
            margin: 0,
            fontFamily: 'var(--font-display)',
            letterSpacing: '-0.02em',
          }}>
            Investment Memos
          </h1>
          <p style={{
            fontSize: 12,
            color: 'var(--text-muted)',
            margin: '6px 0 0',
          }}>
            Generate and manage IC-ready investment documents
          </p>
        </div>

        <button
          onClick={() => navigate(`/company/${company}/${product}/research/memos/new`)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 20px', borderRadius: 6,
            background: 'var(--accent-gold)',
            border: 'none',
            color: '#0D1520',
            fontSize: 12, fontWeight: 700,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Memo
        </button>
      </div>

      {/* Filter bar */}
      <div style={{
        display: 'flex', gap: 4, marginBottom: 20,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: 3,
        width: 'fit-content',
      }}>
        {FILTER_OPTIONS.map(opt => {
          const active = opt.key === filter
          return (
            <button
              key={opt.key}
              onClick={() => setFilter(opt.key)}
              style={{
                padding: '5px 14px', borderRadius: 4,
                background: active ? 'var(--bg-deep)' : 'transparent',
                border: active ? '1px solid var(--border)' : '1px solid transparent',
                color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                fontSize: 11, fontWeight: active ? 700 : 500,
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
              }}
            >
              {opt.label}
              {opt.key !== 'all' && (
                <span style={{
                  marginLeft: 5,
                  fontSize: 9,
                  fontFamily: 'var(--font-mono)',
                  opacity: 0.7,
                }}>
                  {memos.filter(m => m.status === opt.key).length}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: 40, justifyContent: 'center',
        }}>
          <div style={{
            width: 18, height: 18,
            border: '2px solid var(--border)',
            borderTopColor: 'var(--accent-gold)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading memos...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          style={{
            textAlign: 'center',
            padding: '48px 20px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 8,
          }}
        >
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 16 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="12" x2="12" y2="18" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <div style={{
            fontSize: 14, fontWeight: 600,
            color: 'var(--text-primary)', marginBottom: 8,
          }}>
            {filter !== 'all' ? `No ${filter} memos found` : 'No memos yet'}
          </div>
          <div style={{
            fontSize: 12, color: 'var(--text-muted)',
            maxWidth: 380, margin: '0 auto', lineHeight: 1.6,
          }}>
            {filter !== 'all'
              ? 'Try a different filter or create a new memo.'
              : 'Create your first investment memo. AI-powered document generation from your data room and portfolio analytics.'}
          </div>
          {filter === 'all' && (
            <button
              onClick={() => navigate(`/company/${company}/${product}/research/memos/new`)}
              style={{
                marginTop: 16,
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '8px 20px', borderRadius: 6,
                background: 'var(--accent-gold)',
                border: 'none',
                color: '#0D1520',
                fontSize: 12, fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Create First Memo
            </button>
          )}
        </motion.div>
      )}

      {/* Memo list */}
      {!loading && filtered.length > 0 && (
        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          overflow: 'hidden',
        }}>
          {/* Table header */}
          {!isMobile && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 90px 110px 60px 70px',
              gap: 12,
              padding: '10px 20px',
              background: 'var(--bg-deep)',
              borderBottom: '1px solid var(--border)',
            }}>
              {['Title', 'Template', 'Status', 'Date', 'Version', ''].map(h => (
                <div key={h} style={{
                  fontSize: 9, fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: 'var(--text-muted)',
                }}>
                  {h}
                </div>
              ))}
            </div>
          )}

          {/* Rows */}
          {filtered.map((memo, i) => (
            <MemoRow key={memo.id || i} memo={memo} index={i} isMobile={isMobile} company={company} product={product} navigate={navigate} isLast={i === filtered.length - 1} />
          ))}
        </div>
      )}
    </motion.div>
  )
}

function MemoRow({ memo, index, isMobile, company, product, navigate, isLast }) {
  const [hovered, setHovered] = useState(false)
  const status = STATUS_STYLES[memo.status] || STATUS_STYLES.draft
  const tmplBadge = TEMPLATE_BADGES[memo.template] || { label: memo.template || 'Memo', color: '#8494A7' }

  const dateStr = memo.created_at || memo.date
  const formatted = dateStr ? new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  }) : '--'

  function openMemo() {
    const id = memo.id || memo.memo_id
    if (id) {
      navigate(`/company/${company}/${product}/research/memos/${id}`)
    }
  }

  if (isMobile) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: index * 0.03 }}
        onClick={openMemo}
        style={{
          padding: 16,
          borderBottom: isLast ? 'none' : '1px solid var(--border)',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 3,
            background: status.bg, color: status.color,
          }}>
            {status.label}
          </span>
          <span style={{
            fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 3,
            background: `${tmplBadge.color}15`, color: tmplBadge.color,
          }}>
            {tmplBadge.label}
          </span>
        </div>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          {memo.title || 'Untitled Memo'}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {formatted}{memo.version ? ` / v${memo.version}` : ''}
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.03 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={openMemo}
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 120px 90px 110px 60px 70px',
        gap: 12,
        padding: '12px 20px',
        alignItems: 'center',
        borderBottom: isLast ? 'none' : '1px solid var(--border)',
        background: hovered ? 'rgba(201,168,76,0.03)' : 'transparent',
        cursor: 'pointer',
        transition: 'background var(--transition-fast)',
      }}
    >
      {/* Title */}
      <div style={{
        fontSize: 13, fontWeight: 600,
        color: hovered ? 'var(--accent-gold)' : 'var(--text-primary)',
        transition: 'color var(--transition-fast)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {memo.title || 'Untitled Memo'}
      </div>

      {/* Template badge */}
      <div>
        <span style={{
          fontSize: 9, fontWeight: 600,
          padding: '3px 8px', borderRadius: 4,
          background: `${tmplBadge.color}15`,
          color: tmplBadge.color,
        }}>
          {tmplBadge.label}
        </span>
      </div>

      {/* Status badge */}
      <div>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 9, fontWeight: 700,
          padding: '3px 8px', borderRadius: 4,
          background: status.bg,
          color: status.color,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%',
            background: status.color,
          }} />
          {status.label}
        </span>
      </div>

      {/* Date */}
      <div style={{
        fontSize: 11, color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        {formatted}
      </div>

      {/* Version */}
      <div style={{
        fontSize: 10, color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        {memo.version ? `v${memo.version}` : '--'}
      </div>

      {/* Open link */}
      <div style={{ textAlign: 'right' }}>
        <span style={{
          fontSize: 10, fontWeight: 600,
          color: hovered ? 'var(--accent-gold)' : 'var(--text-muted)',
          transition: 'color var(--transition-fast)',
        }}>
          Open
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 3, verticalAlign: 'middle' }}>
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </span>
      </div>
    </motion.div>
  )
}
