import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useCompany } from '../contexts/CompanyContext'
import {
  getPortfolioBorrowingBase, getPortfolioConcentrationLimits, getPortfolioCovenants,
  getPortfolioCovenantDates,
} from '../services/api'
import BorrowingBase from '../components/portfolio/BorrowingBase'
import ConcentrationLimits from '../components/portfolio/ConcentrationLimits'
import Covenants from '../components/portfolio/Covenants'
import InvoicesTable from '../components/portfolio/InvoicesTable'
import PaymentsTable from '../components/portfolio/PaymentsTable'
import BankStatementsView from '../components/portfolio/BankStatementsView'

// Tabs that manage their own data fetching (no parent loading state needed)
const SELF_LOADING_TABS = ['invoices', 'payments', 'bank-statements']

export default function PortfolioAnalytics() {
  const { tab } = useParams()
  const { company, product, snapshot, currency, asOfDate } = useCompany()

  const [bbData, setBbData] = useState(null)
  const [clData, setClData] = useState(null)
  const [covData, setCovData] = useState(null)
  const [covDates, setCovDates] = useState([])
  const [covSelectedDate, setCovSelectedDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch covenant dates when on covenants tab
  useEffect(() => {
    if (tab === 'covenants' && company && product) {
      getPortfolioCovenantDates(company, product)
        .then(d => setCovDates(d.dates || []))
        .catch(() => setCovDates([]))
    }
  }, [tab, company, product])

  // Re-fetch covenants when selected date changes
  useEffect(() => {
    if (tab === 'covenants' && covSelectedDate && company && product && snapshot) {
      setLoading(true)
      getPortfolioCovenants(company, product, snapshot, currency, covSelectedDate)
        .then(setCovData)
        .catch(err => setError(err.response?.data?.detail || err.message))
        .finally(() => setLoading(false))
    }
  }, [covSelectedDate])

  // Main data fetch for parent-managed tabs
  useEffect(() => {
    if (!company || !product || !snapshot) return
    if (SELF_LOADING_TABS.includes(tab)) return  // These tabs fetch their own data

    setLoading(true)
    setError(null)

    const aod = asOfDate || undefined
    const fetcher =
      tab === 'borrowing-base'       ? getPortfolioBorrowingBase(company, product, snapshot, currency, aod).then(setBbData) :
      tab === 'concentration-limits' ? getPortfolioConcentrationLimits(company, product, snapshot, currency, aod).then(setClData) :
      tab === 'covenants'            ? getPortfolioCovenants(company, product, snapshot, currency, aod).then(setCovData) :
      Promise.resolve()

    fetcher
      .catch(err => setError(err.response?.data?.detail || err.message || 'Failed to load data'))
      .finally(() => setLoading(false))
  }, [company, product, snapshot, currency, asOfDate, tab])

  const loadingBar = (
    <div style={{ padding: '40px 28px', textAlign: 'center' }}>
      <div style={{
        width: 200, height: 3, margin: '0 auto 12px', borderRadius: 2,
        background: 'var(--border)', overflow: 'hidden',
      }}>
        <div style={{
          width: '40%', height: '100%', background: 'var(--accent-gold)',
          borderRadius: 2, animation: 'slideRight 1.2s ease-in-out infinite',
        }} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading portfolio data...</div>
      <style>{`@keyframes slideRight { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }`}</style>
    </div>
  )

  const errorBanner = error && (
    <div style={{
      margin: '16px 28px 0', padding: '10px 16px',
      background: 'rgba(240, 96, 96, 0.08)', border: '1px solid rgba(240, 96, 96, 0.2)',
      borderRadius: 'var(--radius-md)', fontSize: 11, color: 'var(--accent-red)',
    }}>
      {error}
    </div>
  )

  return (
    <div>
      {errorBanner}
      <div style={{ padding: '20px 28px 40px' }}>
        {/* Parent-managed tabs with loading state */}
        {!SELF_LOADING_TABS.includes(tab) && loading ? loadingBar : (
          <>
            {tab === 'borrowing-base' && bbData && <BorrowingBase data={bbData} />}
            {tab === 'concentration-limits' && clData && <ConcentrationLimits data={clData} />}
            {tab === 'covenants' && covData && (
              <Covenants
                data={covData}
                availableDates={covDates}
                selectedDate={covSelectedDate}
                onDateChange={setCovSelectedDate}
              />
            )}
          </>
        )}

        {/* Self-loading tabs */}
        {tab === 'invoices' && <InvoicesTable />}
        {tab === 'payments' && <PaymentsTable />}
        {tab === 'bank-statements' && <BankStatementsView />}
      </div>
    </div>
  )
}
