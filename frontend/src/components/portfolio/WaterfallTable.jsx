export default function WaterfallTable({ data, currency = 'AED' }) {
  const fmt = (v) => {
    const abs = Math.abs(v)
    const str = abs >= 1_000_000
      ? `${(abs / 1_000_000).toFixed(1)}M`
      : abs >= 1_000
      ? `${(abs / 1_000).toFixed(0)}K`
      : abs.toFixed(0)
    return `${currency} ${v < 0 ? '-' : ''}${str}`
  }

  let running = 0
  const rows = data.map(row => {
    if (row.type === 'total') {
      running = row.value
      return { ...row, running }
    }
    if (row.type === 'subtotal' || row.type === 'result') {
      running = row.value
      return { ...row, running }
    }
    running += row.value
    return { ...row, running }
  })

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 140px 140px',
        padding: '10px 20px',
        borderBottom: '1px solid var(--border)',
        fontSize: 9,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        color: 'var(--text-muted)',
      }}>
        <div>Item</div>
        <div style={{ textAlign: 'right' }}>Amount</div>
        <div style={{ textAlign: 'right' }}>Running Total</div>
      </div>

      {/* Rows */}
      {rows.map((row, i) => {
        const isResult = row.type === 'result'
        const isSubtotal = row.type === 'subtotal'
        const isDeduction = row.type === 'deduction'

        return (
          <div
            key={i}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 140px 140px',
              padding: '10px 20px',
              borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none',
              background: isResult ? 'rgba(201, 168, 76, 0.06)' : isSubtotal ? 'rgba(91, 141, 239, 0.04)' : 'transparent',
            }}
          >
            <div style={{
              fontSize: 12,
              fontWeight: isResult || isSubtotal ? 700 : 400,
              color: isResult ? 'var(--gold)' : 'var(--text-primary)',
              paddingLeft: isDeduction ? 16 : 0,
            }}>
              {isDeduction && <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>−</span>}
              {row.label}
            </div>
            <div style={{
              textAlign: 'right',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: isResult ? 700 : 400,
              color: isDeduction ? 'var(--accent-red)' : isResult ? 'var(--gold)' : 'var(--text-primary)',
            }}>
              {fmt(row.value)}
            </div>
            <div style={{
              textAlign: 'right',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: isResult || isSubtotal ? 600 : 400,
              color: isResult ? 'var(--gold)' : 'var(--text-muted)',
            }}>
              {fmt(row.running)}
            </div>
          </div>
        )
      })}
    </div>
  )
}
