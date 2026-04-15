import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import api from '../services/api'

const GOLD = '#C9A84C'
const TEAL = '#2DD4BF'
const RED = '#F06060'
const MUTED = '#8494A7'
const SURFACE = '#172231'
const BORDER = '#243040'
const DEEP = '#0A1119'

const ANALYSIS_TYPES = [
  { value: 'klaim', label: 'Healthcare Receivables' },
  { value: 'silq', label: 'POS Lending' },
  { value: 'aajil', label: 'SME Trade Credit' },
  { value: 'custom', label: 'Custom (other asset class)' },
]

const CURRENCIES = ['USD', 'AED', 'SAR', 'EUR', 'GBP', 'KWD']

export default function Onboarding() {
  const [step, setStep] = useState(1)
  const [orgName, setOrgName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [products, setProducts] = useState([{ name: '', currency: 'SAR', analysis_type: '', description: '' }])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const inputStyle = {
    width: '100%', padding: '10px 14px', borderRadius: 6,
    border: `1px solid ${BORDER}`, background: DEEP, color: '#E8EAF0',
    fontSize: 14, outline: 'none', boxSizing: 'border-box',
  }

  const btnStyle = (primary) => ({
    padding: '10px 24px', borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13,
    border: primary ? 'none' : `1px solid ${BORDER}`,
    background: primary ? GOLD : 'transparent',
    color: primary ? '#0A1119' : MUTED,
  })

  const updateProduct = (idx, field, value) => {
    const updated = [...products]
    updated[idx] = { ...updated[idx], [field]: value }
    setProducts(updated)
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.post('/api/onboarding/organizations', {
        name: orgName,
        admin_email: adminEmail,
        products: products.filter(p => p.name),
      })
      setResult(res.data)
      setStep(4)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create organization')
    }
    setSubmitting(false)
  }

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', padding: '0 20px' }}>
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 style={{ color: '#E8EAF0', fontSize: 24, marginBottom: 8 }}>Onboard New Company</h1>
        <p style={{ color: MUTED, fontSize: 13, marginBottom: 32 }}>
          Create an organization, configure products, and generate an API key for integration.
        </p>

        {/* Step indicators */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
          {[1, 2, 3, 4].map(s => (
            <div key={s} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: s <= step ? GOLD : BORDER,
              transition: 'background 0.3s',
            }} />
          ))}
        </div>

        {/* Step 1: Organization */}
        {step === 1 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: MUTED, marginBottom: 6, display: 'block' }}>Organization Name</label>
              <input style={inputStyle} value={orgName} onChange={e => setOrgName(e.target.value)}
                placeholder="e.g., Klaim, SILQ, Aajil" />
            </div>
            <div>
              <label style={{ fontSize: 11, color: MUTED, marginBottom: 6, display: 'block' }}>Admin Email</label>
              <input style={inputStyle} value={adminEmail} onChange={e => setAdminEmail(e.target.value)}
                placeholder="admin@company.com" type="email" />
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
              <button style={btnStyle(false)} onClick={() => navigate('/')}>Cancel</button>
              <button style={btnStyle(true)} onClick={() => setStep(2)}
                disabled={!orgName || !adminEmail}>Next</button>
            </div>
          </div>
        )}

        {/* Step 2: Products */}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {products.map((p, i) => (
              <div key={i} style={{ padding: 16, background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: GOLD, fontWeight: 700, marginBottom: 12 }}>Product {i + 1}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <input style={inputStyle} value={p.name} onChange={e => updateProduct(i, 'name', e.target.value)}
                    placeholder="Product name (e.g., KSA, UAE_healthcare)" />
                  <div style={{ display: 'flex', gap: 12 }}>
                    <select style={{ ...inputStyle, flex: 1 }} value={p.currency}
                      onChange={e => updateProduct(i, 'currency', e.target.value)}>
                      {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <select style={{ ...inputStyle, flex: 1 }} value={p.analysis_type}
                      onChange={e => updateProduct(i, 'analysis_type', e.target.value)}>
                      <option value="">Select asset class</option>
                      {ANALYSIS_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                  <input style={inputStyle} value={p.description} onChange={e => updateProduct(i, 'description', e.target.value)}
                    placeholder="Description (optional)" />
                </div>
              </div>
            ))}
            <button style={{ ...btnStyle(false), alignSelf: 'flex-start' }}
              onClick={() => setProducts([...products, { name: '', currency: 'SAR', analysis_type: '', description: '' }])}>
              + Add Product
            </button>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
              <button style={btnStyle(false)} onClick={() => setStep(1)}>Back</button>
              <button style={btnStyle(true)} onClick={() => setStep(3)}
                disabled={!products.some(p => p.name && p.analysis_type)}>Review</button>
            </div>
          </div>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: 16, background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}>
              <div style={{ fontSize: 11, color: GOLD, fontWeight: 700, marginBottom: 12 }}>Organization</div>
              <div style={{ fontSize: 14, color: '#E8EAF0' }}>{orgName}</div>
              <div style={{ fontSize: 12, color: MUTED }}>{adminEmail}</div>
            </div>
            {products.filter(p => p.name).map((p, i) => (
              <div key={i} style={{ padding: 16, background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: GOLD, fontWeight: 700, marginBottom: 8 }}>Product: {p.name}</div>
                <div style={{ fontSize: 12, color: MUTED }}>
                  {p.analysis_type} | {p.currency} | {p.description || 'No description'}
                </div>
              </div>
            ))}
            {error && (
              <div style={{ padding: 12, background: 'rgba(240,96,96,0.1)', border: `1px solid rgba(240,96,96,0.3)`, borderRadius: 8, color: RED, fontSize: 12 }}>
                {error}
              </div>
            )}
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
              <button style={btnStyle(false)} onClick={() => setStep(2)}>Back</button>
              <button style={btnStyle(true)} onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Creating...' : 'Create Organization'}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Success + API Key */}
        {step === 4 && result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: 16, background: 'rgba(45,212,191,0.08)', border: `1px solid rgba(45,212,191,0.2)`, borderRadius: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: TEAL, marginBottom: 8 }}>Organization Created</div>
              <div style={{ fontSize: 13, color: '#E8EAF0' }}>{result.org_name}</div>
            </div>

            <div style={{ padding: 16, background: 'rgba(201,168,76,0.08)', border: `1px solid rgba(201,168,76,0.3)`, borderRadius: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: GOLD, marginBottom: 8 }}>API Key (shown only once)</div>
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 13, color: '#E8EAF0',
                padding: '10px 14px', background: DEEP, borderRadius: 6, wordBreak: 'break-all',
                userSelect: 'all', cursor: 'text',
              }}>
                {result.api_key}
              </div>
              <div style={{ fontSize: 11, color: RED, marginTop: 8 }}>
                Copy and store this key securely. It cannot be retrieved again.
              </div>
            </div>

            <div style={{ padding: 16, background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: MUTED, marginBottom: 8 }}>Next Steps</div>
              {(result.next_steps || []).map((s, i) => (
                <div key={i} style={{ fontSize: 12, color: '#E8EAF0', padding: '4px 0' }}>{s}</div>
              ))}
            </div>

            <button style={{ ...btnStyle(true), alignSelf: 'flex-end' }} onClick={() => navigate('/')}>
              Go to Dashboard
            </button>
          </div>
        )}
      </motion.div>
    </div>
  )
}
