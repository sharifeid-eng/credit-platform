import { useState, useEffect } from 'react'
import { useCompany } from '../../contexts/CompanyContext'
import { getPortfolioPayments } from '../../services/api'

const PAGE_SIZE = 25

const TYPE_COLORS = {
  ADVANCE: { bg: 'rgba(201,168,76,0.1)', color: 'var(--accent-gold)' },
  PARTIAL: { bg: 'rgba(91,141,239,0.1)', color: 'var(--accent-blue)' },
  FINAL:   { bg: 'rgba(45,212,191,0.1)', color: 'var(--accent-teal)' },
}

export default function PaymentsTable() {
  const { company, product } = useCompany()
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    const filters = typeFilter ? { payment_type: typeFilter } : {}
    getPortfolioPayments(company, product, page, PAGE_SIZE, filters)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product, page, typeFilter])

  const fmt = (v) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : v.toFixed(2)
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  const types = ['', 'ADVANCE', 'PARTIAL', 'FINAL']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 20px', background: 'var(--bg-surface)',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Payments</div>
          {data && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{data.total} transactions</span>}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {types.map(t => (
            <button key={t} onClick={() => { setTypeFilter(t); setPage(1) }} style={{
              padding: '5px 12px', fontSize: 11, borderRadius: 6, cursor: 'pointer',
              border: typeFilter === t ? '1px solid var(--accent-gold)' : '1px solid var(--border)',
              background: typeFilter === t ? 'rgba(201, 168, 76, 0.1)' : 'transparent',
              color: typeFilter === t ? 'var(--accent-gold)' : 'var(--text-muted)',
            }}>{t || 'All'}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)', overflow: 'auto',
      }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>
        ) : !data || data.payments.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>No payments found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Transaction ID', 'Invoice', 'Type', 'Amount', 'Currency', 'Date'].map(h => (
                  <th key={h} style={{
                    padding: '10px 12px', textAlign: 'left', fontSize: 9, fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.payments.map(pay => {
                const tc = TYPE_COLORS[pay.payment_type] || TYPE_COLORS.PARTIAL
                return (
                  <tr key={pay.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {pay.transaction_id || pay.id.slice(0, 8)}
                    </td>
                    <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-blue)' }}>
                      {pay.invoice_number}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                        background: tc.bg, color: tc.color,
                      }}>{pay.payment_type}</span>
                    </td>
                    <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right' }}>
                      {fmt(pay.payment_amount)}
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-muted)' }}>{pay.currency}</td>
                    <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                      {pay.payment_date || '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, alignItems: 'center' }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: '4px 10px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
              border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)',
              opacity: page === 1 ? 0.4 : 1 }}>Prev</button>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Page {page} of {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            style={{ padding: '4px 10px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
              border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)',
              opacity: page === totalPages ? 0.4 : 1 }}>Next</button>
        </div>
      )}
    </div>
  )
}
