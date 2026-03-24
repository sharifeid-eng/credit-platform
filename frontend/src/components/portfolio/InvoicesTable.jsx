import { useState, useEffect } from 'react'
import { useCompany } from '../../contexts/CompanyContext'
import { getPortfolioInvoices } from '../../services/api'

const PAGE_SIZE = 25

export default function InvoicesTable() {
  const { company, product } = useCompany()
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState('all') // all, eligible, ineligible
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    const filters = {}
    if (tab === 'eligible') filters.eligible = 'true'
    if (tab === 'ineligible') filters.eligible = 'false'
    getPortfolioInvoices(company, product, page, PAGE_SIZE, filters)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product, page, tab])

  const fmt = (v) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : v.toFixed(0)

  const tabs = [
    { key: 'all', label: 'All Invoices' },
    { key: 'eligible', label: 'Eligible' },
    { key: 'ineligible', label: 'Ineligible' },
  ]

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 20px', background: 'var(--bg-surface)',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Invoices</div>
          {data && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{data.total} total</span>}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {tabs.map(t => (
            <button key={t.key} onClick={() => { setTab(t.key); setPage(1) }} style={{
              padding: '5px 12px', fontSize: 11, borderRadius: 6, cursor: 'pointer',
              border: tab === t.key ? '1px solid var(--accent-gold)' : '1px solid var(--border)',
              background: tab === t.key ? 'rgba(201, 168, 76, 0.1)' : 'transparent',
              color: tab === t.key ? 'var(--accent-gold)' : 'var(--text-muted)',
            }}>{t.label}</button>
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
        ) : !data || data.invoices.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>No invoices found</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Invoice ID', 'Customer', 'Payer', 'Amount', 'Collected', 'Status', 'Date', 'Due Date', 'Days Overdue', 'Eligible'].map(h => (
                  <th key={h} style={{
                    padding: '10px 12px', textAlign: 'left', fontSize: 9, fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.invoices.map(inv => (
                <tr key={inv.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontSize: 11 }}>{inv.invoice_number}</td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>{inv.customer_name || '—'}</td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-muted)' }}>{inv.payer_name || '—'}</td>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right' }}>
                    {inv.currency} {fmt(inv.amount_due)}
                  </td>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--accent-teal)', textAlign: 'right' }}>
                    {inv.currency} {fmt(inv.collected)}
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                      background: inv.status === 'paid' ? 'rgba(45,212,191,0.1)' :
                                  inv.status === 'denied' ? 'rgba(240,96,96,0.1)' : 'rgba(91,141,239,0.1)',
                      color: inv.status === 'paid' ? 'var(--accent-teal)' :
                             inv.status === 'denied' ? 'var(--accent-red)' : 'var(--accent-blue)',
                    }}>{inv.status}</span>
                  </td>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{inv.invoice_date || '—'}</td>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{inv.due_date || '—'}</td>
                  <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', textAlign: 'right',
                    color: inv.days_overdue > 90 ? 'var(--accent-red)' : inv.days_overdue > 30 ? 'var(--accent-gold)' : 'var(--text-muted)',
                  }}>{inv.days_overdue > 0 ? inv.days_overdue : '—'}</td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: '50%', display: 'inline-block',
                      background: inv.eligible ? 'var(--accent-teal)' : 'var(--accent-red)',
                    }} />
                  </td>
                </tr>
              ))}
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
