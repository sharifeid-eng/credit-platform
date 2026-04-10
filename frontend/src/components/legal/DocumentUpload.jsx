import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { getLegalDocuments, uploadLegalDocument, reExtractLegalDocument, deleteLegalDocument } from '../../services/api'
import ChartPanel from '../ChartPanel'

export default function DocumentUpload({ company, product }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState(null)
  const [docType, setDocType] = useState('credit_agreement')

  const fetchDocs = useCallback(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalDocuments(company, product)
      .then(d => setDocuments(d.documents || []))
      .catch(() => setDocuments([]))
      .finally(() => setLoading(false))
  }, [company, product])

  useEffect(() => { fetchDocs() }, [fetchDocs])

  const handleUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted')
      return
    }
    setUploading(true)
    setError(null)
    try {
      await uploadLegalDocument(company, product, file, docType)
      // Poll for extraction completion
      setTimeout(fetchDocs, 2000)
      setTimeout(fetchDocs, 8000)
      setTimeout(fetchDocs, 20000)
      setTimeout(fetchDocs, 45000)
      fetchDocs()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer?.files?.[0]
    if (file) handleUpload(file)
  }

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
  }

  const handleReExtract = async (filename) => {
    try {
      await reExtractLegalDocument(company, product, filename, docType)
      setTimeout(fetchDocs, 3000)
      setTimeout(fetchDocs, 15000)
      setTimeout(fetchDocs, 40000)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const handleDelete = async (filename) => {
    try {
      await deleteLegalDocument(company, product, filename)
      fetchDocs()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  const DOC_TYPES = [
    { value: 'credit_agreement', label: 'Credit Agreement' },
    { value: 'amendment', label: 'Amendment' },
    { value: 'security_agreement', label: 'Security Agreement' },
    { value: 'fee_letter', label: 'Fee Letter' },
    { value: 'intercreditor', label: 'Intercreditor Agreement' },
    { value: 'servicing_agreement', label: 'Servicing Agreement' },
  ]

  return (
    <div>
      {/* Upload Area */}
      <ChartPanel title="Upload Document" subtitle="Drag & drop a PDF facility agreement or click to browse">
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <label style={{ fontSize: 11, color: 'var(--text-muted)' }}>Document Type:</label>
          <select
            value={docType}
            onChange={e => setDocType(e.target.value)}
            style={{
              background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 6,
              color: 'var(--text-primary)', padding: '4px 8px', fontSize: 11,
            }}
          >
            {DOC_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('legal-file-input')?.click()}
          style={{
            border: `2px dashed ${dragOver ? 'var(--gold)' : 'var(--border)'}`,
            borderRadius: 12,
            padding: '40px 20px',
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'border-color 0.2s, background 0.2s',
            background: dragOver ? 'rgba(201,168,76,0.05)' : 'transparent',
          }}
        >
          <input
            id="legal-file-input"
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          {uploading ? (
            <div style={{ color: 'var(--gold)', fontSize: 13 }}>
              Uploading and extracting... This takes 30-60 seconds.
            </div>
          ) : (
            <>
              <div style={{ fontSize: 32, marginBottom: 8 }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
                Drop PDF here or click to browse
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Supports facility agreements, amendments, security agreements
              </div>
            </>
          )}
        </div>

        {error && (
          <div style={{ color: 'var(--accent-red)', fontSize: 11, marginTop: 8 }}>{error}</div>
        )}
      </ChartPanel>

      {/* Document List */}
      <ChartPanel title="Documents" subtitle={`${documents.length} document${documents.length !== 1 ? 's' : ''}`} loading={loading}>
        {documents.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-muted)', fontSize: 12 }}>
            No documents uploaded yet. Upload a facility agreement PDF to get started.
          </div>
        )}
        {documents.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Filename', 'Size', 'Status', 'Confidence', 'Extracted', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc, i) => (
                <motion.tr
                  key={doc.filename}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <td style={{ padding: '10px 12px', color: 'var(--text-primary)', fontWeight: 500 }}>
                    {doc.filename}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                    {(doc.file_size / 1024).toFixed(0)} KB
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <StatusBadge status={doc.extraction_status} />
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                    {doc.overall_confidence != null ? `${(doc.overall_confidence * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>
                    {doc.extracted_at ? new Date(doc.extracted_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', display: 'flex', gap: 8 }}>
                    <ActionBtn label="Re-extract" onClick={() => handleReExtract(doc.filename)} />
                    <ActionBtn label="Delete" onClick={() => handleDelete(doc.filename)} danger />
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartPanel>
    </div>
  )
}

function StatusBadge({ status }) {
  const colors = {
    completed: { bg: 'rgba(45,212,191,0.12)', color: '#2DD4BF' },
    processing: { bg: 'rgba(201,168,76,0.12)', color: '#C9A84C' },
    pending: { bg: 'rgba(132,148,167,0.12)', color: '#8494A7' },
    failed: { bg: 'rgba(240,96,96,0.12)', color: '#F06060' },
  }
  const c = colors[status] || colors.pending
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 4,
      fontSize: 10, fontWeight: 600, background: c.bg, color: c.color,
      textTransform: 'uppercase', letterSpacing: '0.03em',
    }}>
      {status}
    </span>
  )
}

function ActionBtn({ label, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'transparent', border: `1px solid ${danger ? 'var(--accent-red)' : 'var(--border)'}`,
        borderRadius: 4, padding: '3px 8px', fontSize: 10, cursor: 'pointer',
        color: danger ? 'var(--accent-red)' : 'var(--text-muted)',
        transition: 'all 0.15s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = danger ? 'rgba(240,96,96,0.1)' : 'rgba(255,255,255,0.05)' }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
    >
      {label}
    </button>
  )
}
