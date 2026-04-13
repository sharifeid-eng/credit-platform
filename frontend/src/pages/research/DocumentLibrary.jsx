import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { getDataroomDocuments, getDataroomStats, ingestDataroom } from '../../services/api'

const TYPE_BADGES = {
  pdf:   { bg: 'rgba(240,96,96,0.12)',  color: '#F06060', label: 'PDF' },
  excel: { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'Excel' },
  xlsx:  { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'Excel' },
  xls:   { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'Excel' },
  csv:   { bg: 'rgba(91,141,239,0.12)',  color: '#5B8DEF', label: 'CSV' },
  json:  { bg: 'rgba(201,168,76,0.12)',  color: '#C9A84C', label: 'JSON' },
  docx:  { bg: 'rgba(132,148,167,0.12)', color: '#8494A7', label: 'Word' },
  ods:   { bg: 'rgba(45,212,191,0.12)',  color: '#2DD4BF', label: 'ODS' },
}

function getTypeBadge(docType) {
  const key = (docType || '').toLowerCase()
  return TYPE_BADGES[key] || { bg: 'rgba(132,148,167,0.12)', color: '#8494A7', label: key.toUpperCase() || 'FILE' }
}

export default function DocumentLibrary() {
  const { company, product } = useCompany()
  const { isMobile } = useBreakpoint()

  const [docs, setDocs] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    setError(null)
    Promise.all([
      getDataroomDocuments(company, product).catch(() => []),
      getDataroomStats(company, product).catch(() => null),
    ]).then(([docsData, statsData]) => {
      setDocs(docsData || [])
      setStats(statsData)
    }).catch(() => {
      setError('Failed to load documents')
    }).finally(() => setLoading(false))
  }, [company, product])

  async function handleIngest() {
    if (ingesting) return
    setIngesting(true)
    setError(null)
    try {
      await ingestDataroom(company, product)
      // Refresh documents after ingestion
      const [docsData, statsData] = await Promise.all([
        getDataroomDocuments(company, product).catch(() => []),
        getDataroomStats(company, product).catch(() => null),
      ])
      setDocs(docsData || [])
      setStats(statsData)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Ingestion failed')
    } finally {
      setIngesting(false)
    }
  }

  const filtered = docs.filter(d =>
    !search || (d.filename || '').toLowerCase().includes(search.toLowerCase())
  )

  const pad = isMobile ? 14 : 28

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{ padding: pad, maxWidth: 1200, margin: '0 auto' }}
    >
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{
          fontSize: isMobile ? 20 : 24,
          fontWeight: 800,
          color: 'var(--text-primary)',
          margin: 0,
          fontFamily: 'var(--font-display)',
          letterSpacing: '-0.02em',
        }}>
          Document Library
        </h1>
        <p style={{
          fontSize: 12,
          color: 'var(--text-muted)',
          margin: '6px 0 0',
        }}>
          Browse and manage ingested data room documents
        </p>
      </div>

      {/* Stats strip */}
      {stats && (
        <div style={{
          display: 'flex',
          gap: isMobile ? 12 : 20,
          flexWrap: 'wrap',
          marginBottom: 20,
        }}>
          {[
            { label: 'Total Documents', value: stats.total_documents ?? 0 },
            { label: 'Total Pages', value: stats.total_pages ?? 0 },
            { label: 'Total Chunks', value: stats.total_chunks ?? 0 },
            ...(stats.by_type ? Object.entries(stats.by_type).map(([type, val]) => ({
              label: type.toUpperCase(), value: typeof val === 'object' ? (val.count ?? 0) : (val ?? 0),
            })) : []),
          ].map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '10px 16px',
                minWidth: 100,
              }}
            >
              <div style={{
                fontSize: 18,
                fontWeight: 700,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-mono)',
              }}>
                {typeof s.value === 'number' ? s.value.toLocaleString() : s.value}
              </div>
              <div style={{
                fontSize: 9,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--text-muted)',
                marginTop: 2,
              }}>
                {s.label}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Action bar */}
      <div style={{
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        marginBottom: 24,
        flexWrap: isMobile ? 'wrap' : 'nowrap',
      }}>
        <button
          onClick={handleIngest}
          disabled={ingesting}
          style={{
            padding: '9px 20px',
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 6,
            border: ingesting ? '1px solid var(--border)' : '1px solid var(--accent-gold)',
            background: ingesting ? 'var(--bg-surface)' : 'transparent',
            color: ingesting ? 'var(--text-muted)' : 'var(--accent-gold)',
            cursor: ingesting ? 'not-allowed' : 'pointer',
            transition: 'all var(--transition-fast)',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
          onMouseEnter={e => {
            if (!ingesting) {
              e.currentTarget.style.background = 'rgba(201,168,76,0.1)'
            }
          }}
          onMouseLeave={e => {
            if (!ingesting) {
              e.currentTarget.style.background = 'transparent'
            }
          }}
        >
          {ingesting && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
              <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
            </svg>
          )}
          {ingesting ? 'Ingesting...' : 'Ingest Data Room'}
        </button>

        <div style={{ flex: 1, minWidth: 180 }}>
          <input
            type="text"
            placeholder="Search documents..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '9px 14px',
              fontSize: 12,
              background: 'var(--bg-deep)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              color: 'var(--text-primary)',
              outline: 'none',
              transition: 'border-color var(--transition-fast)',
            }}
            onFocus={e => { e.target.style.borderColor = 'var(--border-hover)' }}
            onBlur={e => { e.target.style.borderColor = 'var(--border)' }}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '10px 16px',
          borderRadius: 6,
          background: 'rgba(240,96,96,0.08)',
          border: '1px solid rgba(240,96,96,0.2)',
          color: '#F06060',
          fontSize: 12,
          marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.05 }}
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: 20,
                minHeight: 140,
              }}
            >
              <div style={{ height: 12, width: '60%', background: 'var(--border)', borderRadius: 4, marginBottom: 12 }} />
              <div style={{ height: 10, width: '40%', background: 'var(--border)', borderRadius: 4, marginBottom: 20 }} />
              <div style={{ height: 10, width: '80%', background: 'var(--border)', borderRadius: 4, marginBottom: 8 }} />
              <div style={{ height: 10, width: '50%', background: 'var(--border)', borderRadius: 4 }} />
            </motion.div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{
            textAlign: 'center',
            padding: '60px 20px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 8,
          }}
        >
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: 16 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
            {search ? 'No matching documents' : 'No documents ingested yet'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 360, margin: '0 auto' }}>
            {search
              ? 'Try a different search term.'
              : "Click 'Ingest Data Room' to scan your data room and index documents for research."}
          </div>
        </motion.div>
      )}

      {/* Document grid */}
      {!loading && filtered.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          <AnimatePresence>
            {filtered.map((doc, i) => (
              <DocumentCard key={doc.id || doc.filename || i} doc={doc} index={i} />
            ))}
          </AnimatePresence>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </motion.div>
  )
}

function DocumentCard({ doc, index }) {
  const [hovered, setHovered] = useState(false)
  const badge = getTypeBadge(doc.type || doc.file_type)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, delay: index * 0.03, ease: 'easeOut' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? 'var(--border-hover)' : 'var(--border)'}`,
        borderRadius: 8,
        padding: 20,
        cursor: 'default',
        transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast)',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? '0 4px 20px rgba(0,0,0,0.15)' : 'none',
      }}
    >
      {/* Top row: type badge + chunk count */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{
          fontSize: 9,
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          padding: '3px 8px',
          borderRadius: 4,
          background: badge.bg,
          color: badge.color,
        }}>
          {badge.label}
        </span>
        {doc.chunk_count != null && (
          <span style={{
            fontSize: 9,
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}>
            {doc.chunk_count} chunks
          </span>
        )}
      </div>

      {/* Filename */}
      <div style={{
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--text-primary)',
        marginBottom: 8,
        lineHeight: 1.4,
        wordBreak: 'break-word',
      }}>
        {doc.filename || doc.name || 'Untitled'}
      </div>

      {/* Meta row */}
      <div style={{
        display: 'flex',
        gap: 16,
        fontSize: 10,
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        {doc.page_count != null && (
          <span>{doc.page_count} pages</span>
        )}
        {doc.ingested_at && (
          <span>{new Date(doc.ingested_at).toLocaleDateString()}</span>
        )}
        {doc.size && (
          <span>{formatSize(doc.size)}</span>
        )}
      </div>
    </motion.div>
  )
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
