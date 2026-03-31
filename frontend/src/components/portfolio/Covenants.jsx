import { useState } from 'react'
import CovenantCard from './CovenantCard'
import { notifyBreaches } from '../../services/api'

export default function Covenants({ data, availableDates, selectedDate, onDateChange, company, product, snapshot, currency }) {
  const covenants = data.covenants || []
  const compliantCount = data.compliant_count ?? covenants.filter(c => c.compliant).length
  const breachCount = data.breach_count ?? (covenants.length - compliantCount)
  const testDate = data.test_date || ''
  const ccy = data.currency || currency || 'AED'

  const [notifState, setNotifState] = useState('idle')  // idle | sending | sent | error
  const [notifMsg,   setNotifMsg]   = useState('')

  const handleNotify = async () => {
    setNotifState('sending')
    setNotifMsg('')
    try {
      const res = await notifyBreaches(company, product, snapshot, ccy)
      setNotifState('sent')
      setNotifMsg(res.breach_count > 0
        ? `Alert sent — ${res.breach_count} breach(es) reported`
        : 'All-clear sent — no breaches')
      setTimeout(() => setNotifState('idle'), 4000)
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Send failed'
      setNotifState('error')
      setNotifMsg(detail)
      setTimeout(() => setNotifState('idle'), 5000)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header with date selector */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 20px',
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            Covenants
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <span style={{ fontSize: 11, color: 'var(--accent-teal)' }}>
              ● {compliantCount} Compliant
            </span>
            {breachCount > 0 && (
              <span style={{ fontSize: 11, color: 'var(--accent-red)' }}>
                ● {breachCount} Breach
              </span>
            )}
          </div>
        </div>

        {/* Right side: notify button + date selector */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {/* Slack notification button */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={handleNotify}
              disabled={notifState === 'sending'}
              title="Send breach alert to Slack"
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px', borderRadius: 7, cursor: notifState === 'sending' ? 'default' : 'pointer',
                background: 'transparent',
                border: `1px solid ${notifState === 'error' ? 'var(--accent-red)' : notifState === 'sent' ? 'var(--accent-teal)' : 'var(--border)'}`,
                color: notifState === 'error' ? 'var(--accent-red)' : notifState === 'sent' ? 'var(--accent-teal)' : 'var(--text-muted)',
                fontSize: 11, transition: 'all 150ms',
              }}
            >
              {notifState === 'sending' ? (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
              )}
              {notifState === 'sent' ? 'Sent' : notifState === 'error' ? 'Error' : 'Notify'}
            </button>
            {notifMsg && (
              <div style={{
                position: 'absolute', top: 36, right: 0, zIndex: 10,
                background: 'var(--bg-deep)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '6px 10px',
                fontSize: 10, color: notifState === 'error' ? 'var(--accent-red)' : 'var(--accent-teal)',
                whiteSpace: 'nowrap', boxShadow: 'var(--shadow-card)',
              }}>
                {notifMsg}
              </div>
            )}
          </div>

        {/* Date selector or static date */}
        {availableDates && availableDates.length > 1 ? (
          <select
            value={selectedDate || testDate}
            onChange={e => onDateChange?.(e.target.value)}
            style={{
              padding: '5px 12px',
              background: 'var(--bg-base)',
              border: '1px solid var(--border)',
              borderRadius: 7,
              fontSize: 11,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {availableDates.map(d => (
              <option key={d} value={d} style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)' }}>
                {d}
              </option>
            ))}
          </select>
        ) : testDate ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 12px',
            background: 'var(--bg-base)',
            border: '1px solid var(--border)',
            borderRadius: 7,
            fontSize: 11,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono)',
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            {testDate}
          </div>
        ) : null}
        </div>  {/* end flex wrapper */}
      </div>

      {/* Covenant cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {covenants.map((covenant, i) => (
          <CovenantCard key={i} covenant={covenant} currency={ccy} />
        ))}
      </div>
    </div>
  )
}
