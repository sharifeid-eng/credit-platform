import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../../contexts/CompanyContext'
import useBreakpoint from '../../hooks/useBreakpoint'
import { getDataroomDocuments, getDataroomStats, ingestDataroom, getDataroomDocumentViewUrl } from '../../services/api'

// ── Category config (document_type → display) ────────────────────────────────
// Keys MUST match backend `DocumentType` enum values from
// core/dataroom/classifier.py. Any backend type missing here falls through
// to `other`, which used to cause multiple "Other (N)" chips (each keyed by
// a different unmapped enum value).

const CATEGORY_CONFIG = {
  // Legal / facility
  facility_agreement:    { label: 'Facility Agreement',    color: '#C9A84C', bg: 'rgba(201,168,76,0.12)' },
  legal_document:        { label: 'Legal Document',        color: '#F0C040', bg: 'rgba(240,192,64,0.12)' },

  // Investor / reporting — quarterly_investor_pack is gold because it's a
  // first-class recurring data input that feeds the dashboard directly
  // (not just RAG-searchable narrative).
  quarterly_investor_pack: { label: 'Quarterly Investor Pack', color: '#C9A84C', bg: 'rgba(201,168,76,0.18)' },
  investor_report:       { label: 'Investor Report',       color: '#5B8DEF', bg: 'rgba(91,141,239,0.12)' },
  company_presentation:  { label: 'Company Presentation',  color: '#5B8DEF', bg: 'rgba(91,141,239,0.12)' },
  board_pack:            { label: 'Board Pack',            color: '#5B8DEF', bg: 'rgba(91,141,239,0.12)' },

  // Due diligence / audit
  fdd_report:            { label: 'FDD Report',            color: '#F06060', bg: 'rgba(240,96,96,0.12)' },
  audit_report:          { label: 'Audit Report',          color: '#F06060', bg: 'rgba(240,96,96,0.12)' },
  credit_report:         { label: 'Credit Report',         color: '#F06060', bg: 'rgba(240,96,96,0.12)' },

  // Financial
  financial_model:       { label: 'Financial Model',       color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  financial_statement:   { label: 'Financial Statement',   color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  financial_statements:  { label: 'Financial Statements',  color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  tax_filing:            { label: 'Tax Filing',            color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  bank_statement:        { label: 'Bank Statement',        color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
  business_plan:         { label: 'Business Plan',         color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },
  debt_overview:         { label: 'Debt Overview',         color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },

  // Portfolio / vintage
  portfolio_tape:        { label: 'Portfolio Tape',        color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  vintage_cohort:        { label: 'Vintage Cohort',        color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  sales_data:            { label: 'Sales Data',            color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  demographics:          { label: 'Demographics',          color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },

  // Analytics snapshots (platform-generated)
  analytics_tape:        { label: 'Analytics Snapshot',    color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },
  analytics_portfolio:   { label: 'Analytics Snapshot',    color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },
  analytics_ai:          { label: 'AI Summary',            color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },
  analytics_report:      { label: 'Analytics Report',      color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' },
  tape_summary:          { label: 'Analytics Snapshot',    color: '#2DD4BF', bg: 'rgba(45,212,191,0.12)' }, // legacy alias

  // Memos
  memo_draft:            { label: 'Memo (Draft)',          color: '#C9A84C', bg: 'rgba(201,168,76,0.12)' },
  memo_final:            { label: 'Memo',                  color: '#C9A84C', bg: 'rgba(201,168,76,0.12)' },

  // Governance / compliance
  cap_table:             { label: 'Cap Table',             color: '#F0C040', bg: 'rgba(240,192,64,0.12)' },
  kyc_compliance:        { label: 'KYC / Compliance',      color: '#F0C040', bg: 'rgba(240,192,64,0.12)' },
  credit_policy:         { label: 'Credit Policy',         color: '#F0C040', bg: 'rgba(240,192,64,0.12)' },

  // Fallbacks
  other:                 { label: 'Other',                 color: '#8494A7', bg: 'rgba(132,148,167,0.12)' },
  unknown:               { label: 'Unknown',               color: '#8494A7', bg: 'rgba(132,148,167,0.12)' },
}

function getCategoryConfig(docType) {
  return CATEGORY_CONFIG[docType] || CATEGORY_CONFIG.other
}

// ── Folder breadcrumb extraction ─────────────────────────────────────────────

function extractBreadcrumb(filepath, filename) {
  if (!filepath) return null
  // Find the path after "dataroom/" and before the filename
  const dataroomIdx = filepath.toLowerCase().indexOf('dataroom')
  if (dataroomIdx === -1) return null
  const afterDataroom = filepath.slice(dataroomIdx + 'dataroom'.length + 1)
  const filenameIdx = afterDataroom.lastIndexOf(filename)
  if (filenameIdx <= 0) return null
  const folderPath = afterDataroom.slice(0, filenameIdx).replace(/[/\\]+$/, '')
  if (!folderPath) return null
  // Simplify: take last 2 folder segments for display
  const parts = folderPath.split(/[/\\]/).filter(Boolean)
  if (parts.length <= 2) return parts.join(' > ')
  return parts.slice(-2).join(' > ')
}

// ── Sort options ─────────────────────────────────────────────────────────────

const SORT_OPTIONS = [
  { key: 'name',     label: 'Name' },
  { key: 'category', label: 'Category' },
  { key: 'pages',    label: 'Pages' },
  { key: 'date',     label: 'Date Ingested' },
]

function sortDocs(docs, sortKey) {
  const sorted = [...docs]
  switch (sortKey) {
    case 'name':
      sorted.sort((a, b) => (a.filename || '').localeCompare(b.filename || ''))
      break
    case 'category':
      sorted.sort((a, b) => (a.document_type || 'zzz').localeCompare(b.document_type || 'zzz'))
      break
    case 'pages':
      sorted.sort((a, b) => (b.page_count || 0) - (a.page_count || 0))
      break
    case 'date':
      sorted.sort((a, b) => (b.ingested_at || '').localeCompare(a.ingested_at || ''))
      break
    default:
      break
  }
  return sorted
}

// ── Main component ───────────────────────────────────────────────────────────

export default function DocumentLibrary() {
  const { company, product } = useCompany()
  const { isMobile } = useBreakpoint()

  const [docs, setDocs] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [search, setSearch] = useState('')
  const [error, setError] = useState(null)
  const [activeCategory, setActiveCategory] = useState(null)
  const [sortBy, setSortBy] = useState('name')

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
      const ingestResult = await ingestDataroom(company, product)
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

  const filtered = useMemo(() => {
    let result = docs
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(d => (d.filename || '').toLowerCase().includes(q))
    }
    if (activeCategory) {
      result = result.filter(d => (d.document_type || 'other') === activeCategory)
    }
    return sortDocs(result, sortBy)
  }, [docs, search, activeCategory, sortBy])

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

      {/* Stats strip — top-level metrics */}
      {stats && (
        <div style={{
          display: 'flex',
          gap: isMobile ? 12 : 20,
          flexWrap: 'wrap',
          marginBottom: 12,
        }}>
          {[
            { label: 'Total Documents', value: stats.total_documents ?? 0, key: null },
            { label: 'Total Pages', value: stats.total_pages ?? 0, key: null },
            { label: 'Total Chunks', value: stats.total_chunks ?? 0, key: null },
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

      {/* Category filter chips */}
      {stats?.by_type && (
        <div style={{
          display: 'flex',
          gap: 8,
          flexWrap: 'wrap',
          marginBottom: 20,
        }}>
          <button
            onClick={() => setActiveCategory(null)}
            style={{
              padding: '5px 12px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 20,
              border: `1px solid ${!activeCategory ? 'var(--text-primary)' : 'var(--border)'}`,
              background: !activeCategory ? 'rgba(232,234,240,0.1)' : 'transparent',
              color: !activeCategory ? 'var(--text-primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
          >
            All
          </button>
          {Object.entries(stats.by_type).map(([type, val]) => {
            const cfg = getCategoryConfig(type)
            const count = typeof val === 'object' ? (val.count ?? 0) : (val ?? 0)
            const isActive = activeCategory === type
            return (
              <button
                key={type}
                onClick={() => setActiveCategory(isActive ? null : type)}
                style={{
                  padding: '5px 12px',
                  fontSize: 11,
                  fontWeight: 600,
                  borderRadius: 20,
                  border: `1px solid ${isActive ? cfg.color : 'var(--border)'}`,
                  background: isActive ? cfg.bg : 'transparent',
                  color: isActive ? cfg.color : 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                {cfg.label} ({count})
              </button>
            )
          })}
        </div>
      )}

      {/* Action bar: ingest + search + sort */}
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
          onMouseEnter={e => { if (!ingesting) e.currentTarget.style.background = 'rgba(201,168,76,0.1)' }}
          onMouseLeave={e => { if (!ingesting) e.currentTarget.style.background = 'transparent' }}
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

        {/* Sort dropdown */}
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          style={{
            padding: '9px 12px',
            fontSize: 12,
            background: 'var(--bg-deep)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            color: 'var(--text-muted)',
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {SORT_OPTIONS.map(o => (
            <option key={o.key} value={o.key}>Sort: {o.label}</option>
          ))}
        </select>
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
            {search || activeCategory ? 'No matching documents' : 'No documents ingested yet'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 360, margin: '0 auto' }}>
            {search || activeCategory
              ? 'Try a different search term or category.'
              : "Click 'Ingest Data Room' to scan your data room and index documents for research."}
          </div>
        </motion.div>
      )}

      {/* Results count */}
      {!loading && filtered.length > 0 && (activeCategory || search) && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
          Showing {filtered.length} of {docs.length} documents
          {activeCategory && <> in <strong style={{ color: getCategoryConfig(activeCategory).color }}>{getCategoryConfig(activeCategory).label}</strong></>}
        </div>
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
              <DocumentCard
                key={doc.doc_id || doc.filename || i}
                doc={doc}
                index={i}
                company={company}
                product={product}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </motion.div>
  )
}

// ── Document card ────────────────────────────────────────────────────────────

function DocumentCard({ doc, index, company, product }) {
  const [hovered, setHovered] = useState(false)
  const category = getCategoryConfig(doc.document_type || 'other')
  const breadcrumb = extractBreadcrumb(doc.filepath, doc.filename)
  const viewUrl = doc.doc_id ? getDataroomDocumentViewUrl(company, product, doc.doc_id) : null

  // Determine if this file is viewable in browser (PDF, images)
  const ext = (doc.filename || '').split('.').pop().toLowerCase()
  const isViewable = ['pdf'].includes(ext)

  function handleClick() {
    if (isViewable && viewUrl) {
      window.open(viewUrl, '_blank')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.02, 0.5), ease: 'easeOut' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${hovered ? (isViewable ? category.color + '40' : 'var(--border-hover)') : 'var(--border)'}`,
        borderRadius: 8,
        padding: 20,
        cursor: isViewable ? 'pointer' : 'default',
        transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast)',
        transform: hovered ? 'translateY(-2px)' : 'none',
        boxShadow: hovered ? '0 4px 20px rgba(0,0,0,0.15)' : 'none',
      }}
    >
      {/* Top row: category badge + chunk count */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.04em',
          padding: '3px 8px',
          borderRadius: 4,
          background: category.bg,
          color: category.color,
        }}>
          {category.label}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {doc.chunk_count != null && (
            <span style={{
              fontSize: 9,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)',
            }}>
              {doc.chunk_count} chunks
            </span>
          )}
          {isViewable && (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke={hovered ? category.color : 'var(--text-faint)'}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              style={{ transition: 'stroke var(--transition-fast)' }}>
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
          )}
        </div>
      </div>

      {/* Filename */}
      <div style={{
        fontSize: 13,
        fontWeight: 600,
        color: hovered && isViewable ? category.color : 'var(--text-primary)',
        marginBottom: breadcrumb ? 4 : 8,
        lineHeight: 1.4,
        wordBreak: 'break-word',
        transition: 'color var(--transition-fast)',
      }}>
        {doc.filename || doc.name || 'Untitled'}
      </div>

      {/* Folder breadcrumb */}
      {breadcrumb && (
        <div style={{
          fontSize: 10,
          color: 'var(--text-faint)',
          marginBottom: 8,
          fontStyle: 'italic',
        }}>
          {breadcrumb}
        </div>
      )}

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
        {doc.text_length > 0 && (
          <span>{(doc.text_length / 1000).toFixed(1)}K chars</span>
        )}
      </div>
    </motion.div>
  )
}
