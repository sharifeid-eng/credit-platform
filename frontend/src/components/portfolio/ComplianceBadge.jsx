export default function ComplianceBadge({ compliant, size = 'normal' }) {
  const isSmall = size === 'small'
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: isSmall ? '2px 8px' : '3px 10px',
      borderRadius: 20,
      fontSize: isSmall ? 9 : 10,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      background: compliant ? 'rgba(45, 212, 191, 0.12)' : 'rgba(240, 96, 96, 0.12)',
      color: compliant ? 'var(--accent-teal)' : 'var(--accent-red)',
      border: `1px solid ${compliant ? 'rgba(45, 212, 191, 0.25)' : 'rgba(240, 96, 96, 0.25)'}`,
    }}>
      <span style={{ fontSize: isSmall ? 7 : 8 }}>{compliant ? '●' : '●'}</span>
      {compliant ? 'Compliant' : 'Breach'}
    </span>
  )
}
