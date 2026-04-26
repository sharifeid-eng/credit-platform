export default function ComplianceBadge({ compliant, size = 'normal', unverifiedReason }) {
  const isSmall = size === 'small'
  // Three states: true (Compliant teal), false (Breach red), null/undefined (Unverified gold).
  // Unverified surfaces a §17 data-gap (e.g., proxy column in use — boolean compliant
  // would be misleading). UI must NOT render False-y as Breach for null.
  const isUnverified = compliant == null
  const palette = isUnverified
    ? { bg: 'rgba(201, 168, 76, 0.12)', fg: 'var(--accent-gold, #C9A84C)', border: 'rgba(201, 168, 76, 0.30)' }
    : compliant
    ? { bg: 'rgba(45, 212, 191, 0.12)', fg: 'var(--accent-teal)', border: 'rgba(45, 212, 191, 0.25)' }
    : { bg: 'rgba(240, 96, 96, 0.12)', fg: 'var(--accent-red)', border: 'rgba(240, 96, 96, 0.25)' }
  const label = isUnverified ? 'Unverified' : (compliant ? 'Compliant' : 'Breach')
  return (
    <span
      title={isUnverified && unverifiedReason ? unverifiedReason : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: isSmall ? '2px 8px' : '3px 10px',
        borderRadius: 20,
        fontSize: isSmall ? 9 : 10,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        background: palette.bg,
        color: palette.fg,
        border: `1px solid ${palette.border}`,
        cursor: isUnverified && unverifiedReason ? 'help' : 'default',
      }}>
      <span style={{ fontSize: isSmall ? 7 : 8 }}>●</span>
      {label}
    </span>
  )
}
