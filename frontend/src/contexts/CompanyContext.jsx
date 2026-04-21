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
  const [snapshotsMeta, setSnapshotsMeta] = useState([])   // full objects with source + row_count
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
      // Preserve full objects ({filename, date, source, row_count}) in snapshotsMeta;
      // keep string array in snapshots for back-compat with existing consumers.
      const snapObjects = snaps.map(s =>
        typeof s === 'string'
          ? { filename: s, date: null, source: 'tape', row_count: null }
          : s
      )
      const snapStrings = snapObjects.map(s => s.filename ?? s.date ?? String(s))
      setSnapshotsMeta(snapObjects)
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
      const effectiveMax = dr.max_date ?? ''
      setDateRange({ min: dr.min_date ?? '', max: effectiveMax })
      // Default as-of date to snapshot date (tape extraction date), fall back to max deal date
      setAsOfDate(dr.snapshot_date ?? effectiveMax)
      setSnapshotDate(dr.snapshot_date ?? '')
    }).catch(() => {
      setDateRange({ min: '', max: '' })
      setAsOfDate('')
      setSnapshotDate('')
    })
  }, [product, snapshot])

  // Clear AI cache when snapshot changes (covers browser back-nav, not just dropdown)
  useEffect(() => {
    setAiCache(null)
  }, [snapshot])

  // Load summary KPIs
  useEffect(() => {
    if (!product || !snapshot) return
    const controller = new AbortController()
    setSummaryLoading(true)
    setSummary(null)
    getSummary(company, product, snapshot, currency, asOfDate || undefined)
      .then(data => { if (!controller.signal.aborted) setSummary(data) })
      .catch(() => {})
      .finally(() => { if (!controller.signal.aborted) setSummaryLoading(false) })
    return () => controller.abort()
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
      snapshots, snapshotsMeta, snapshot, setSnapshot,
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
