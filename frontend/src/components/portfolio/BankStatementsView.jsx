import { useState, useEffect } from 'react'
import { useCompany } from '../../contexts/CompanyContext'
import { getPortfolioBankStatements } from '../../services/api'
import KpiCard from '../KpiCard'

export default function BankStatementsView() {
  const { company, product } = useCompany()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!company || !product) return
    setLoading(true)
    getPortfolioBankStatements(company, product)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [company, product])

  const fmtBal = (v) => {
    if (!v) return '$0'
    return v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1_000).toFixed(0)}K`
  }

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>
  }

  const summary = data?.summary || {}
  const statements = data?.statements || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <KpiCard label="Cash Account" value={fmtBal(summary.cash_balance)} sub="Operating cash" color="gold" />
        <KpiCard label="Collection Account" value={fmtBal(summary.collection_balance)} sub="Dedicated collections" color="teal" />
        <KpiCard label="Last Upload" value={summary.last_upload || 'None'} sub="Most recent statement" color="blue" />
      </div>

      {/* Statements Table */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Statement History</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{data?.total || 0} statements</div>
        </div>

        {statements.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
            No bank statements uploaded yet
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Account Type', 'Balance', 'Currency', 'Uploaded'].map(h => (
                  <th key={h} style={{
                    padding: '10px 16px', textAlign: 'left', fontSize: 9, fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {statements.map(bs => (
                <tr key={bs.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)' }}>
                    {bs.statement_date}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                      background: bs.account_type === 'cash-account' ? 'rgba(201,168,76,0.1)' : 'rgba(45,212,191,0.1)',
                      color: bs.account_type === 'cash-account' ? 'var(--accent-gold)' : 'var(--accent-teal)',
                    }}>{bs.account_type || 'general'}</span>
                  </td>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right', fontWeight: 600 }}>
                    {bs.currency} {bs.balance >= 1_000_000 ? `${(bs.balance / 1_000_000).toFixed(2)}M` : bs.balance.toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text-muted)' }}>{bs.currency}</td>
                  <td style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text-muted)' }}>
                    {bs.created_at ? bs.created_at.split('T')[0] : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
