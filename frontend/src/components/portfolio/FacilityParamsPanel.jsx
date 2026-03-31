import { useState, useEffect } from 'react'
import { getFacilityParams, saveFacilityParams } from '../../services/api'

const KLAIM_DEFAULTS = {
  advance_rate: 0.90,
  advance_rates_by_region: { UAE: 0.90, 'Non-UAE': 0.85 },
  single_payer_limit: 0.10,
  wal_threshold_days: 60,
}

const SILQ_DEFAULTS = {
  advance_rate: 0.80,
  advance_rates_by_product: {},
}

// ── Reusable field components ────────────────────────────────────────────────

function CurrencyField({ label, value, onChange, placeholder, currencySymbol = '' }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={styles.label}>{label}</label>
      <div style={{ position: 'relative' }}>
        {currencySymbol && (
          <span style={styles.currencyPrefix}>{currencySymbol}</span>
        )}
        <input
          type="number"
          step="any"
          value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
          placeholder={placeholder}
          style={{ ...styles.input, ...(currencySymbol ? { paddingLeft: 40 } : {}) }}
        />
      </div>
    </div>
  )
}

function PctField({ label, value, onChange, placeholder }) {
  // Store as decimal internally (0.10), display as percent (10)
  const displayVal = value != null ? (value * 100) : ''
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={styles.label}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          type="number"
          step="any"
          value={displayVal}
          onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value) / 100)}
          placeholder={placeholder}
          style={{ ...styles.input, paddingRight: 32 }}
        />
        <span style={styles.pctSuffix}>%</span>
      </div>
    </div>
  )
}

function DaysField({ label, value, onChange, placeholder }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={styles.label}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          type="number"
          step="1"
          value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
          placeholder={placeholder}
          style={{ ...styles.input, paddingRight: 48 }}
        />
        <span style={styles.daysSuffix}>days</span>
      </div>
    </div>
  )
}

function KeyValueRates({ label, value, onChange }) {
  const entries = Object.entries(value || {})
  const [newKey, setNewKey] = useState('')

  const update = (key, rate) => {
    const next = { ...value }
    if (rate === null) {
      delete next[key]
    } else {
      next[key] = rate
    }
    onChange(next)
  }

  const addRow = () => {
    if (newKey.trim()) {
      onChange({ ...value, [newKey.trim()]: 0.80 })
      setNewKey('')
    }
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <label style={styles.label}>{label}</label>
      {entries.map(([key, rate]) => (
        <div key={key} style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'center' }}>
          <span style={{ ...styles.kvKey, flex: 1 }}>{key}</span>
          <div style={{ position: 'relative', width: 90 }}>
            <input
              type="number"
              step="any"
              value={rate != null ? (rate * 100) : ''}
              onChange={e => update(key, e.target.value === '' ? null : Number(e.target.value) / 100)}
              style={{ ...styles.input, paddingRight: 24, fontSize: 12, padding: '5px 24px 5px 8px' }}
            />
            <span style={{ ...styles.pctSuffix, top: 6, fontSize: 11 }}>%</span>
          </div>
          <button
            onClick={() => update(key, null)}
            style={styles.removeBtn}
            title="Remove"
          >×</button>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <input
          type="text"
          value={newKey}
          onChange={e => setNewKey(e.target.value)}
          placeholder="Add region/product..."
          style={{ ...styles.input, flex: 1, fontSize: 11, padding: '4px 8px' }}
          onKeyDown={e => e.key === 'Enter' && addRow()}
        />
        <button onClick={addRow} style={styles.addBtn}>+</button>
      </div>
    </div>
  )
}

function TextListField({ label, value, onChange, placeholder }) {
  const display = Array.isArray(value) ? value.join(', ') : (value || '')
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={styles.label}>{label}</label>
      <input
        type="text"
        value={display}
        onChange={e => {
          const raw = e.target.value
          onChange(raw ? raw.split(',').map(s => s.trim()).filter(Boolean) : [])
        }}
        placeholder={placeholder}
        style={styles.input}
      />
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
        Comma-separated list
      </div>
    </div>
  )
}

// ── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  )
}

// ── Main Panel ───────────────────────────────────────────────────────────────

export default function FacilityParamsPanel({ company, product, analysisType, onClose, onSave }) {
  const [params, setParams] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  const isKlaim = analysisType !== 'silq'
  const isSilq = analysisType === 'silq'
  const defaults = isKlaim ? KLAIM_DEFAULTS : SILQ_DEFAULTS

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getFacilityParams(company, product)
      .then(data => setParams(data || {}))
      .catch(() => setParams({}))
      .finally(() => setLoading(false))
  }, [company, product])

  const set = (key, val) => setParams(prev => ({ ...prev, [key]: val }))

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      // Strip nulls before saving
      const clean = {}
      for (const [k, v] of Object.entries(params)) {
        if (v != null && v !== '') clean[k] = v
      }
      await saveFacilityParams(company, product, clean)
      onSave?.()
      onClose()
    } catch (err) {
      setSaveError(err.response?.data?.detail || err.message || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div style={styles.backdrop} onClick={onClose} />

      {/* Panel */}
      <div style={styles.panel}>
        {/* Header */}
        <div style={styles.header}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent-gold)" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M16.36 16.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M16.36 7.64l1.42-1.42" />
            </svg>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
              Facility Parameters
            </span>
          </div>
          <button onClick={onClose} style={styles.closeBtn}>×</button>
        </div>

        {/* Body */}
        <div style={styles.body}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 12 }}>
              Loading parameters...
            </div>
          ) : (
            <>
              {/* Section 1 — Facility */}
              <Section title="Facility">
                <CurrencyField
                  label="Facility Limit"
                  value={params.facility_limit}
                  onChange={v => set('facility_limit', v)}
                  placeholder="e.g. 20,000,000"
                />
                <CurrencyField
                  label="Facility Drawn"
                  value={params.facility_drawn}
                  onChange={v => set('facility_drawn', v)}
                  placeholder="Current outstanding"
                />
                <CurrencyField
                  label="Cash Balance"
                  value={params.cash_balance}
                  onChange={v => set('cash_balance', v)}
                  placeholder="Cash on hand"
                />
                {isSilq && (
                  <CurrencyField
                    label="Equity Injection"
                    value={params.equity_injection}
                    onChange={v => set('equity_injection', v)}
                    placeholder={String(0)}
                  />
                )}
              </Section>

              {/* Section 2 — Advance Rates */}
              <Section title="Advance Rates">
                <PctField
                  label="Default Advance Rate"
                  value={params.advance_rate ?? defaults.advance_rate}
                  onChange={v => set('advance_rate', v)}
                  placeholder={String(defaults.advance_rate * 100)}
                />
                {isKlaim && (
                  <KeyValueRates
                    label="By Region"
                    value={params.advance_rates_by_region ?? defaults.advance_rates_by_region}
                    onChange={v => set('advance_rates_by_region', v)}
                  />
                )}
                {isSilq && (
                  <KeyValueRates
                    label="By Product"
                    value={params.advance_rates_by_product ?? defaults.advance_rates_by_product}
                    onChange={v => set('advance_rates_by_product', v)}
                  />
                )}
              </Section>

              {/* Section 3 — Klaim Thresholds */}
              {isKlaim && (
                <Section title="Thresholds">
                  <PctField
                    label="Single Payer Limit"
                    value={params.single_payer_limit ?? defaults.single_payer_limit}
                    onChange={v => set('single_payer_limit', v)}
                    placeholder={String(defaults.single_payer_limit * 100)}
                  />
                  <DaysField
                    label="WAL Threshold"
                    value={params.wal_threshold_days ?? defaults.wal_threshold_days}
                    onChange={v => set('wal_threshold_days', v)}
                    placeholder={String(defaults.wal_threshold_days)}
                  />
                </Section>
              )}

              {/* Section 4 — Cash Metrics (Klaim covenants) */}
              {isKlaim && (
                <Section title="Cash Metrics (for Covenants)">
                  <CurrencyField
                    label="Net Cash Burn"
                    value={params.net_cash_burn}
                    onChange={v => set('net_cash_burn', v)}
                    placeholder="Monthly net cash burn"
                  />
                  <CurrencyField
                    label="3M Avg Cash Burn"
                    value={params.net_cash_burn_3m_avg}
                    onChange={v => set('net_cash_burn_3m_avg', v)}
                    placeholder="3-month average"
                  />
                </Section>
              )}

              {/* Section 5 — SILQ Specific */}
              {isSilq && (
                <Section title="SILQ Settings">
                  <TextListField
                    label="Approved Recipients"
                    value={params.approved_recipients}
                    onChange={v => set('approved_recipients', v)}
                    placeholder="SHOP001, SHOP002, ..."
                  />
                </Section>
              )}

              {/* Section 6 — Notifications */}
              <Section title="Notifications">
                <div style={{ marginBottom: 12 }}>
                  <label style={styles.label}>Slack Webhook URL</label>
                  <input
                    type="url"
                    value={params.slack_webhook_url || ''}
                    onChange={e => set('slack_webhook_url', e.target.value || null)}
                    placeholder="https://hooks.slack.com/services/..."
                    style={styles.input}
                  />
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                    Used to send breach alerts from the Covenants tab
                  </div>
                </div>
              </Section>
            </>
          )}
        </div>

        {/* Footer */}
        <div style={styles.footer}>
          {saveError && (
            <div style={{ fontSize: 11, color: 'var(--accent-red)', marginBottom: 8 }}>{saveError}</div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={styles.cancelBtn}>Cancel</button>
            <button onClick={handleSave} disabled={saving || loading} style={styles.saveBtn}>
              {saving ? 'Saving...' : 'Save Parameters'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  backdrop: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)', zIndex: 999,
  },
  panel: {
    position: 'fixed', top: 0, right: 0, bottom: 0, width: 400,
    background: 'var(--bg-surface)', borderLeft: '1px solid var(--border)',
    zIndex: 1000, display: 'flex', flexDirection: 'column',
    boxShadow: '-4px 0 24px rgba(0,0,0,0.3)',
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '16px 20px', borderBottom: '1px solid var(--border)',
  },
  closeBtn: {
    background: 'none', border: 'none', color: 'var(--text-muted)',
    fontSize: 20, cursor: 'pointer', padding: '2px 6px', lineHeight: 1,
  },
  body: {
    flex: 1, overflowY: 'auto', padding: '16px 20px',
  },
  footer: {
    padding: '12px 20px', borderTop: '1px solid var(--border)',
  },
  sectionTitle: {
    fontSize: 11, fontWeight: 600, color: 'var(--accent-gold)',
    textTransform: 'uppercase', letterSpacing: '0.05em',
    marginBottom: 10, paddingBottom: 6,
    borderBottom: '1px solid var(--border)',
  },
  label: {
    display: 'block', fontSize: 11, color: 'var(--text-muted)',
    marginBottom: 4, fontWeight: 500,
  },
  input: {
    width: '100%', padding: '7px 10px', fontSize: 13,
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm, 4px)', color: 'var(--text-primary)',
    outline: 'none', fontFamily: "'IBM Plex Mono', monospace",
    boxSizing: 'border-box',
  },
  currencyPrefix: {
    position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
    fontSize: 12, color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace",
  },
  pctSuffix: {
    position: 'absolute', right: 10, top: 8,
    fontSize: 12, color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace",
    pointerEvents: 'none',
  },
  daysSuffix: {
    position: 'absolute', right: 10, top: 8,
    fontSize: 11, color: 'var(--text-muted)',
    pointerEvents: 'none',
  },
  kvKey: {
    fontSize: 12, color: 'var(--text-primary)',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  removeBtn: {
    background: 'none', border: 'none', color: 'var(--accent-red)',
    fontSize: 16, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
  },
  addBtn: {
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    color: 'var(--accent-gold)', fontSize: 14, cursor: 'pointer',
    padding: '2px 10px', borderRadius: 'var(--radius-sm, 4px)',
  },
  cancelBtn: {
    flex: 1, padding: '8px 0', fontSize: 12, fontWeight: 500,
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm, 4px)', color: 'var(--text-muted)',
    cursor: 'pointer',
  },
  saveBtn: {
    flex: 2, padding: '8px 0', fontSize: 12, fontWeight: 600,
    background: 'var(--accent-gold)', border: 'none',
    borderRadius: 'var(--radius-sm, 4px)', color: '#0A1119',
    cursor: 'pointer',
  },
}
