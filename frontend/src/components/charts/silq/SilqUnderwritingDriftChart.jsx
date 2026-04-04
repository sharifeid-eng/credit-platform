import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line, ComposedChart } from 'recharts'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { gridProps, xAxisProps, yAxisProps, tooltipStyle, fmtMoney, fmtPct, COLORS } from '../../../styles/chartTheme'

const FLAG_LABELS = {
  avg_loan_size: 'Loan Size',
  avg_tenure: 'Tenure',
  delinquency_rate: 'Delinquency',
  collection_rate: 'Collection Rate',
}

function DriftBadge({ flag }) {
  const isUp = flag.direction === 'up'
  const color = flag.metric === 'delinquency_rate'
    ? (isUp ? '#F06060' : '#2DD4BF')
    : flag.metric === 'collection_rate'
      ? (isUp ? '#2DD4BF' : '#F06060')
      : '#C9A84C'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
      background: `${color}15`, color, border: `1px solid ${color}30`,
    }}>
      {isUp ? '\u2191' : '\u2193'} {FLAG_LABELS[flag.metric] || flag.metric} ({flag.z_score > 0 ? '+' : ''}{flag.z_score}\u03c3)
    </span>
  )
}

export default function SilqUnderwritingDriftChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/underwriting-drift`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load underwriting drift data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (!data?.available) {
    return <ChartPanel title="Underwriting Drift" subtitle="Requires disbursement date data" loading={loading} error={error || 'Not available for this tape'} minHeight={200} />
  }

  const vintages = data.vintages || []
  const norms = data.historical_norms || {}
  const ccy = data.currency || currency
  const flaggedCount = vintages.filter(v => v.flags && v.flags.length > 0).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Summary */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
        background: flaggedCount > 0 ? 'rgba(201,168,76,0.06)' : 'rgba(45,212,191,0.06)',
        border: `1px solid ${flaggedCount > 0 ? 'rgba(201,168,76,0.2)' : 'rgba(45,212,191,0.2)'}`,
        borderRadius: 8,
      }}>
        <span style={{ fontSize: 20 }}>{flaggedCount > 0 ? '\u26a0' : '\u2713'}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            {flaggedCount > 0 ? `${flaggedCount} vintage${flaggedCount > 1 ? 's' : ''} with drift signals` : 'No drift detected'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Comparing per-vintage origination metrics against rolling 6-month historical norms
          </div>
        </div>
      </div>

      {/* Loan Size + Tenure chart */}
      <ChartPanel title="Origination Quality by Vintage" subtitle="Average loan size and tenure per disbursement month" loading={loading} error={error} minHeight={300}>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={vintages} {...gridProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="vintage" {...xAxisProps} angle={-45} textAnchor="end" height={60} />
            <YAxis yAxisId="left" {...yAxisProps} tickFormatter={v => fmtMoney(v, ccy)} />
            <YAxis yAxisId="right" orientation="right" {...yAxisProps} unit="w" />
            <Tooltip {...tooltipStyle} />
            <Bar yAxisId="left" dataKey="avg_loan_size" fill="#5B8DEF" radius={[4,4,0,0]} name="Avg Loan Size" />
            <Line yAxisId="right" type="monotone" dataKey="avg_tenure" stroke="#C9A84C" strokeWidth={2} dot={{ r: 3 }} name="Avg Tenure (wks)" />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* Delinquency + Collection rate chart */}
      <ChartPanel title="Performance Quality by Vintage" subtitle="Delinquency and collection rates per disbursement month" loading={loading} error={error} minHeight={300}>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={vintages} {...gridProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="vintage" {...xAxisProps} angle={-45} textAnchor="end" height={60} />
            <YAxis {...yAxisProps} unit="%" />
            <Tooltip {...tooltipStyle} />
            <Bar dataKey="delinquency_rate" fill="#F06060" radius={[4,4,0,0]} name="Delinquency %" />
            <Line type="monotone" dataKey="collection_rate" stroke="#2DD4BF" strokeWidth={2} dot={{ r: 3 }} name="Collection %" />
          </ComposedChart>
        </ResponsiveContainer>
      </ChartPanel>

      {/* Drift flags table */}
      <ChartPanel title="Drift Flags" subtitle="Vintages where metrics deviate > 1 standard deviation from norm" loading={loading} error={error} minHeight={100}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Vintage', 'Deals', 'Avg Size', 'Tenure', 'Delinquency', 'Collection', 'Flags'].map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: h === 'Vintage' || h === 'Flags' ? 'left' : 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vintages.map((v, i) => (
                <tr key={i} style={{
                  borderBottom: '1px solid var(--border)',
                  background: v.flags?.length ? 'rgba(201,168,76,0.03)' : 'transparent',
                }}>
                  <td style={{ padding: '6px 10px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{v.vintage}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--text-muted)' }}>{v.deals}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{fmtMoney(v.avg_loan_size, ccy)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{v.avg_tenure?.toFixed(1)}w</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.delinquency_rate > 10 ? '#F06060' : 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{fmtPct(v.delinquency_rate)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: '#2DD4BF', fontFamily: 'var(--font-mono)' }}>{fmtPct(v.collection_rate)}</td>
                  <td style={{ padding: '6px 10px' }}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {(v.flags || []).map((f, j) => <DriftBadge key={j} flag={f} />)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartPanel>

      {/* Historical norms reference */}
      {Object.keys(norms).length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <strong>Historical norms:</strong>{' '}
          {Object.entries(norms).map(([k, v]) => `${FLAG_LABELS[k] || k}: ${typeof v === 'number' ? v.toFixed(1) : v}`).join(' | ')}
        </div>
      )}
    </div>
  )
}
