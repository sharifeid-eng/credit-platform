import { createContext, useContext, useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getProducts, getSnapshots, getConfig,
  getSummary, getDateRange, generatePDFReport,
} from '../services/api'

const CompanyContext = createContext(null)

export function useCompany() {
  const ctx = useContext(CompanyContext)
  if (!ctx) throw new Error('useCompany must be used within CompanyProvider')
  return ctx
}

export function CompanyProvider({ children }) {
  const { companyName: company, product: urlProduct } = useParams()
  const navigate = useNavigate()

  const [products, setProducts]     = useState([])
  const [product, setProduct]       = useState(null)
  const [snapshots, setSnapshots]   = useState([])
  const [snapshot, setSnapshot]     = useState(null)
  const [config, setConfig]         = useState({})
  const [currency, setCurrency]     = useState('USD')
  const [summary, setSummary]       = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [aiCache, setAiCache]       = useState(null)
  const [asOfDate, setAsOfDate]     = useState('')
  const [dateRange, setDateRange]   = useState({ min: '', max: '' })
  const [snapshotDate, setSnapshotDate] = useState('')
  const [reportGenerating, setReportGenerating] = useState(false)
  const [reportError, setReportError] = useState(null)

  // Load products
  useEffect(() => {
    getProducts(company).then(ps => {
      setProducts(ps)
      // If URL has a product param, use it; otherwise pick first
      const match = urlProduct ? ps.find(p => p === urlProduct) : null
      setProduct(match ?? (ps.length ? ps[0] : null))
    })
  }, [company])

  // Sync product from URL changes
  useEffect(() => {
    if (urlProduct && products.length && products.includes(urlProduct)) {
      setProduct(urlProduct)
    }
  }, [urlProduct, products])

  // Load snapshots + config when product changes
  useEffect(() => {
    if (!product) return
    Promise.all([
      getSnapshots(company, product),
      getConfig(company, product),
    ]).then(([snaps, cfg]) => {
      const snapStrings = snaps.map(s => typeof s === 'string' ? s : s.filename ?? s.date ?? String(s))
      setSnapshots(snapStrings)
      setSnapshot(snapStrings[snapStrings.length - 1] ?? null)
      setConfig(cfg)
      setCurrency(cfg.currency ?? 'USD')
    })
    setAiCache(null)
  }, [product])

  // Load date range when snapshot changes
  useEffect(() => {
    if (!product || !snapshot) return
    getDateRange(company, product, snapshot).then(dr => {
      setDateRange({ min: dr.min_date ?? '', max: dr.max_date ?? '' })
      setAsOfDate(dr.max_date ?? '')
      setSnapshotDate(dr.snapshot_date ?? '')
    }).catch(() => {
      setDateRange({ min: '', max: '' })
      setAsOfDate('')
      setSnapshotDate('')
    })
  }, [product, snapshot])

  // Load summary KPIs
  useEffect(() => {
    if (!product || !snapshot) return
    setSummaryLoading(true)
    setSummary(null)
    getSummary(company, product, snapshot, currency, asOfDate || undefined)
      .then(setSummary)
      .finally(() => setSummaryLoading(false))
  }, [product, snapshot, currency, asOfDate])

  const localCcy = config.currency ?? 'AED'
  const isBackdated = !!(snapshotDate && asOfDate && asOfDate < snapshotDate)

  const handleGenerateReport = () => {
    setReportGenerating(true)
    setReportError(null)
    generatePDFReport(company, product, snapshot, currency)
      .then(() => {})
      .catch(err => {
        const msg = err?.response?.data?.detail || 'Report generation failed'
        setReportError(msg)
        setTimeout(() => setReportError(null), 8000)
      })
      .finally(() => setReportGenerating(false))
  }

  return (
    <CompanyContext.Provider value={{
      company, products, product, setProduct,
      snapshots, snapshot, setSnapshot,
      config, currency, setCurrency, localCcy,
      summary, summaryLoading,
      aiCache, setAiCache,
      asOfDate, setAsOfDate, dateRange, snapshotDate, isBackdated,
      reportGenerating, reportError, handleGenerateReport,
      navigate,
      analysisType: config.analysis_type || 'klaim',
      tapeTabs: config.tabs || null,
    }}>
      {children}
    </CompanyContext.Provider>
  )
}
