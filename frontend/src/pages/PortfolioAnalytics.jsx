import { useParams } from 'react-router-dom'
import BorrowingBase from '../components/portfolio/BorrowingBase'
import ConcentrationLimits from '../components/portfolio/ConcentrationLimits'
import Covenants from '../components/portfolio/Covenants'

export default function PortfolioAnalytics() {
  const { tab } = useParams()

  return (
    <div>
      {/* Sample data banner */}
      <div style={{
        margin: '16px 28px 0',
        padding: '10px 16px',
        background: 'rgba(91, 141, 239, 0.08)',
        border: '1px solid rgba(91, 141, 239, 0.2)',
        borderRadius: 'var(--radius-md)',
        fontSize: 11,
        color: 'var(--accent-blue)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        Showing sample data — connect a data source for live portfolio analytics.
      </div>

      {/* Tab content */}
      <div style={{ padding: '20px 28px 40px' }}>
        {tab === 'borrowing-base' && <BorrowingBase />}
        {tab === 'concentration-limits' && <ConcentrationLimits />}
        {tab === 'covenants' && <Covenants />}
      </div>
    </div>
  )
}
