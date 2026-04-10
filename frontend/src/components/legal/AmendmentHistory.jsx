import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getLegalDocuments, getLegalAmendmentDiff } from '../../services/api'
import ChartPanel from '../ChartPanel'

export default function AmendmentHistory({ company, product }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [oldFile, setOldFile] = useState('')
  const [newFile, setNewFile] = useState('')
  const [diff, setDiff] = useState(null)
  const [diffLoading, setDiffLoading] = useState(false)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getLegalDocuments(company, product)
      .then(d => {
        const docs = (d.documents || []).filter(doc => doc.extracted)
        setDocuments(docs)
        if (docs.length >= 2) {
          setOldFile(docs[0].filename)
          setNewFile(docs[docs.length - 1].filename)
        }
      })
      .catch(() => setDocuments([]))
      .finally(() => setLoading(false))
  }, [company, product])

  const handleCompare = async () => {
    if (!oldFile || !newFile || oldFile === newFile) return
    setDiffLoading(true)
    try {
      const result = await getLegalAmendmentDiff(company, product, oldFile, newFile)
      setDiff(result)
    } catch (e) {
      setDiff({ error: e.response?.data?.detail || e.message })
    } finally {
      setDiffLoading(false)
    }
  }

  if (loading) return <ChartPanel title="Amendment History" loading />

  const extractedDocs = documents.filter(d => d.extracted)

  if (extractedDocs.length < 2) return (
    <ChartPanel title="Amendment History" subtitle="Upload and extract at least two document versions to compare amendments." />
  )

  return (
    <div>
      {/* Document Selection */}
      <ChartPanel title="Compare Documents" subtitle="Select two document versions to see material changes">
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase' }}>Older Document</label>
            <select
              value={oldFile}
              onChange={e => setOldFile(e.target.value)}
              style={{
                background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text-primary)', padding: '6px 12px', fontSize: 11, minWidth: 200,
              }}
            >
              {extractedDocs.map(d => <option key={d.filename} value={d.filename}>{d.filename}</option>)}
            </select>
          </div>
          <div style={{ fontSize: 16, color: 'var(--text-muted)', padding: '0 4px' }}>vs</div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginBottom: 4, textTransform: 'uppercase' }}>Newer Document</label>
            <select
              value={newFile}
              onChange={e => setNewFile(e.target.value)}
              style={{
                background: 'var(--bg-deep)', border: '1px solid var(--border)', borderRadius: 6,
                color: 'var(--text-primary)', padding: '6px 12px', fontSize: 11, minWidth: 200,
              }}
            >
              {extractedDocs.map(d => <option key={d.filename} value={d.filename}>{d.filename}</option>)}
            </select>
          </div>
          <button
            onClick={handleCompare}
            disabled={!oldFile || !newFile || oldFile === newFile || diffLoading}
            style={{
              background: 'var(--gold)', color: '#000', border: 'none', borderRadius: 6,
              padding: '7px 16px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              opacity: (!oldFile || !newFile || oldFile === newFile) ? 0.4 : 1,
            }}
          >
            {diffLoading ? 'Comparing...' : 'Compare'}
          </button>
        </div>
      </ChartPanel>

      {/* Diff Results */}
      {diff && !diff.error && (
        <ChartPanel
          title="Material Changes"
          subtitle={`${diff.material_change_count || 0} material change${(diff.material_change_count || 0) !== 1 ? 's' : ''} detected`}
        >
          {(diff.changes || []).length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--accent-teal)', fontSize: 12 }}>
              No differences found between the two documents.
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Section', 'Field', 'Old Value', 'New Value', 'Material'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {diff.changes.map((change, i) => (
                  <motion.tr
                    key={i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      background: change.material ? 'rgba(201,168,76,0.04)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{change.section}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-primary)', fontWeight: 500 }}>{change.field}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--accent-red)', fontFamily: 'var(--font-mono)' }}>
                      {change.old_value || '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--accent-teal)', fontFamily: 'var(--font-mono)' }}>
                      {change.new_value || '—'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {change.material && (
                        <span style={{
                          padding: '2px 6px', borderRadius: 3, fontSize: 9, fontWeight: 600,
                          background: 'rgba(201,168,76,0.12)', color: '#C9A84C',
                        }}>
                          MATERIAL
                        </span>
                      )}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          )}
        </ChartPanel>
      )}

      {diff?.error && (
        <ChartPanel title="Error">
          <div style={{ color: 'var(--accent-red)', fontSize: 12 }}>{diff.error}</div>
        </ChartPanel>
      )}
    </div>
  )
}
