import { useState, useEffect } from 'react'
import ChartPanel from '../../ChartPanel'
import api from '../../../services/api'
import { fmtMoney, fmtPct } from '../../../styles/chartTheme'

function KpiCard({ label, value, sub, color }) {
  const colors = { gold: '#C9A84C', teal: '#2DD4BF', red: '#F06060', blue: '#5B8DEF' }
  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', position: 'relative' }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: colors[color] || colors.gold, borderRadius: '10px 0 0 10px' }} />
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function SilqLossWaterfallChart({ company, product, snapshot, currency, asOfDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    setLoading(true)
    api.get(`/companies/${company}/products/${product}/charts/silq/loss-waterfall`, {
      params: { snapshot, currency, as_of_date: asOfDate },
    })
      .then(r => { setData(r.data); setError(null) })
      .catch(() => setError('Failed to load loss waterfall data.'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate])

  if (!data?.available) {
    return <ChartPanel title="Loss Waterfall" subtitle="Requires disbursement date data" loading={loading} error={error || 'Not available for this tape'} minHeight={200} />
  }

  const vintages = data.vintages || []
  const totals = data.totals || {}
  const ccy = data.currency || currency
  const fmt = v => fmtMoney(v, ccy)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Portfolio KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <KpiCard label="Total Originated" value={fmt(totals.originated)} color="blue" />
        <KpiCard label="Gross Default Rate" value={fmtPct(totals.default_rate)} sub="DPD > 90 days" color="red" />
        <KpiCard label="Recovery Rate" value={fmtPct(totals.recovery_rate)} sub="Recovered from defaulted" color="teal" />
        <KpiCard label="Net Loss Rate" value={fmtPct(totals.net_loss_rate)} sub="After recoveries" color="gold" />
      </div>

      {/* Vintage Waterfall Table */}
      <ChartPanel title="Cohort Loss Waterfall" subtitle="Per-vintage: Disbursed -> Default -> Recovery -> Net Loss" loading={loading} error={error} minHeight={200}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Vintage', 'Deals', 'Originated', 'Gross Default', 'Recovery', 'Net Loss', 'Default %', 'Recovery %', 'Net Loss %'].map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: h === 'Vintage' ? 'left' : 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vintages.map((v, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                  <td style={{ padding: '6px 10px', color: 'var(--text-primary)' }}>{v.vintage}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--text-muted)' }}>{v.deals}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--text-primary)' }}>{fmt(v.originated)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.gross_default > 0 ? '#F06060' : 'var(--text-muted)' }}>{fmt(v.gross_default)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.recovery > 0 ? '#2DD4BF' : 'var(--text-muted)' }}>{fmt(v.recovery)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.net_loss > 0 ? '#F06060' : 'var(--text-muted)' }}>{fmt(v.net_loss)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.default_rate > 5 ? '#F06060' : v.default_rate > 2 ? '#C9A84C' : 'var(--text-muted)' }}>{fmtPct(v.default_rate)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: '#2DD4BF' }}>{fmtPct(v.recovery_rate)}</td>
                  <td style={{ padding: '6px 10px', textAlign: 'right', color: v.net_loss_rate > 3 ? '#F06060' : 'var(--text-muted)' }}>{fmtPct(v.net_loss_rate)}</td>
                </tr>
              ))}
              {/* Totals row */}
              <tr style={{ borderTop: '2px solid var(--gold)', fontWeight: 700 }}>
                <td style={{ padding: '8px 10px', color: 'var(--gold)' }}>TOTAL</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-primary)' }}>{vintages.reduce((s, v) => s + v.deals, 0)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: 'var(--text-primary)' }}>{fmt(totals.originated)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: '#F06060' }}>{fmt(totals.gross_default)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: '#2DD4BF' }}>{fmt(totals.recovery)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: '#F06060' }}>{fmt(totals.net_loss)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: totals.default_rate > 5 ? '#F06060' : '#C9A84C' }}>{fmtPct(totals.default_rate)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: '#2DD4BF' }}>{fmtPct(totals.recovery_rate)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', color: '#F06060' }}>{fmtPct(totals.net_loss_rate)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </ChartPanel>
    </div>
  )
}
