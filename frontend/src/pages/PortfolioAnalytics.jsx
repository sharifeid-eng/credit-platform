import { useState, useEffect, useCallback } from 'react'
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
import FacilityParamsPanel from '../components/portfolio/FacilityParamsPanel'

// Tabs that manage their own data fetching (no parent loading state needed)
const SELF_LOADING_TABS = ['invoices', 'payments', 'bank-statements']

export default function PortfolioAnalytics() {
  const { tab } = useParams()
  const { company, product, snapshot, currency, asOfDate, analysisType } = useCompany()

  const [bbData, setBbData] = useState(null)
  const [clData, setClData] = useState(null)
  const [covData, setCovData] = useState(null)
  const [covDates, setCovDates] = useState([])
  const [covSelectedDate, setCovSelectedDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showParams, setShowParams] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

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

  // Callback when facility params are saved — re-fetch all portfolio data
  const handleParamsSaved = useCallback(() => {
    setRefreshKey(k => k + 1)
  }, [])

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
  }, [company, product, snapshot, currency, asOfDate, tab, refreshKey])

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

  // Show gear icon on BB, CL, Covenants tabs (the ones affected by facility params)
  const showGear = ['borrowing-base', 'concentration-limits', 'covenants'].includes(tab)

  return (
    <div>
      {errorBanner}

      {/* Gear icon for facility params — positioned top-right of content area */}
      {showGear && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 28px 0' }}>
          <button
            onClick={() => setShowParams(true)}
            title="Facility Parameters"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', fontSize: 11, fontWeight: 500,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm, 4px)', color: 'var(--text-muted)',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.target.style.borderColor = 'var(--accent-gold)'; e.target.style.color = 'var(--accent-gold)' }}
            onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-muted)' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            Facility Params
          </button>
        </div>
      )}

      <div style={{ padding: '12px 28px 40px' }}>
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

      {/* Facility Params slide-out panel */}
      {showParams && (
        <FacilityParamsPanel
          company={company}
          product={product}
          analysisType={analysisType}
          onClose={() => setShowParams(false)}
          onSave={handleParamsSaved}
        />
      )}
    </div>
  )
}
