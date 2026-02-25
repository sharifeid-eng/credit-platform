import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  getProducts, getSnapshots, getConfig,
  getSummary, getDateRange,
} from '../services/api'

import KpiCard       from '../components/KpiCard'
import AICommentary  from '../components/AICommentary'
import DataChat      from '../components/DataChat'
import TabInsight    from '../components/TabInsight'
import ChartPanel    from '../components/ChartPanel'

// Charts
import DeploymentChart        from '../components/charts/DeploymentChart'
import ActualVsExpectedChart  from '../components/charts/ActualVsExpectedChart'
import CollectionVelocityChart from '../components/charts/CollectionVelocityChart'
import DenialTrendChart       from '../components/charts/DenialTrendChart'
import AgeingChart            from '../components/charts/AgeingChart'
import RevenueChart           from '../components/charts/RevenueChart'
import ConcentrationChart     from '../components/charts/ConcentrationChart'
import CohortTable            from '../components/charts/CohortTable'

const TABS = [
  'Overview', 'Actual vs Expected', 'Deployment', 'Collection',
  'Denial Trend', 'Ageing', 'Revenue', 'Portfolio', 'Cohort Analysis',
]

export default function Company() {
  const { companyName: company } = useParams()

  const [products, setProducts]     = useState([])
  const [product, setProduct]       = useState(null)
  const [snapshots, setSnapshots]   = useState([])
  const [snapshot, setSnapshot]     = useState(null)
  const [config, setConfig]         = useState({})
  const [currency, setCurrency]     = useState('USD')
  const [summary, setSummary]       = useState(null)
  const [activeTab, setActiveTab]   = useState('Overview')
  const [aiCache, setAiCache]       = useState(null)   // cached commentary

  // Load products
  useEffect(() => {
    getProducts(company).then(ps => {
      setProducts(ps)
      if (ps.length) setProduct(ps[0])
    })
  }, [company])

  // Load snapshots + config when product changes
  useEffect(() => {
    if (!product) return
    Promise.all([
      getSnapshots(company, product),
      getConfig(company, product),
    ]).then(([snaps, cfg]) => {
      // snaps may be strings or objects like {filename, date}
      const snapStrings = snaps.map(s => typeof s === 'string' ? s : s.filename ?? s.date ?? String(s))
      setSnapshots(snapStrings)
      setSnapshot(snapStrings[snapStrings.length - 1] ?? null)
      setConfig(cfg)
      setCurrency(cfg.currency ?? 'USD')
    })
    setAiCache(null)
  }, [product])

  // Load summary KPIs
  useEffect(() => {
    if (!product || !snapshot) return
    getSummary(company, product, snapshot, currency).then(setSummary)
  }, [product, snapshot, currency])

  const localCcy = config.currency ?? 'AED'

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
      {/* Page header */}
      <div style={{ padding: '24px 28px 0' }}>
        {/* Breadcrumb */}
        <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-faint)', marginBottom: 12 }}>
          Companies ›{' '}
          <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{company.toUpperCase()}</span>
        </div>

        {/* Title row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)', margin: 0 }}>
              {company.toUpperCase()}
            </h1>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
              {config.description ?? '—'}
            </div>
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
            {/* Product selector */}
            {products.length > 1 && (
              <ControlGroup label="Product">
                <DarkSelect value={product} onChange={setProduct}>
                  {products.map(p => <option key={p} value={p}>{p}</option>)}
                </DarkSelect>
              </ControlGroup>
            )}

            {/* Snapshot selector */}
            <ControlGroup label="Tape">
              <DarkSelect value={snapshot ?? ''} onChange={setSnapshot}>
                {snapshots.map(s => <option key={s} value={s}>{s}</option>)}
              </DarkSelect>
            </ControlGroup>

            {/* Currency toggle */}
            <ControlGroup label="Currency">
              <CurrencyToggle
                localCcy={localCcy}
                value={currency}
                onChange={setCurrency}
              />
            </ControlGroup>
          </div>
        </div>

        {/* Tab bar */}
        <div style={{
          display: 'flex', gap: 0,
          borderBottom: '1px solid var(--border)',
          overflowX: 'auto',
        }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              fontSize: 11, fontWeight: 500,
              padding: '9px 15px',
              background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: `2px solid ${activeTab === tab ? 'var(--gold)' : 'transparent'}`,
              color: activeTab === tab ? 'var(--gold)' : 'var(--text-muted)',
              whiteSpace: 'nowrap',
              marginBottom: -1,
              transition: 'color 0.15s',
            }}>
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div style={{ padding: '20px 28px 40px' }}>
        {activeTab === 'Overview' && (
          <OverviewTab
            summary={summary} company={company} product={product}
            snapshot={snapshot} currency={currency}
            aiCache={aiCache} onAiCache={setAiCache}
          />
        )}
        {activeTab === 'Actual vs Expected' && (
          <ChartTab tab="actual-vs-expected" company={company} product={product} snapshot={snapshot} currency={currency}>
            <ActualVsExpectedChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Deployment' && (
          <ChartTab tab="deployment" company={company} product={product} snapshot={snapshot} currency={currency}>
            <DeploymentChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Collection' && (
          <ChartTab tab="collection-velocity" company={company} product={product} snapshot={snapshot} currency={currency}>
            <CollectionVelocityChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Denial Trend' && (
          <ChartTab tab="denial-trend" company={company} product={product} snapshot={snapshot} currency={currency}>
            <DenialTrendChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Ageing' && (
          <ChartTab tab="ageing" company={company} product={product} snapshot={snapshot} currency={currency}>
            <AgeingChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Revenue' && (
          <ChartTab tab="revenue" company={company} product={product} snapshot={snapshot} currency={currency}>
            <RevenueChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Portfolio' && (
          <ChartTab tab="concentration" company={company} product={product} snapshot={snapshot} currency={currency}>
            <ConcentrationChart company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
        {activeTab === 'Cohort Analysis' && (
          <ChartTab tab="cohort" company={company} product={product} snapshot={snapshot} currency={currency}>
            <CohortTable company={company} product={product} snapshot={snapshot} currency={currency} />
          </ChartTab>
        )}
      </div>
    </div>
  )
}

/* ── Overview Tab ── */
function OverviewTab({ summary, company, product, snapshot, currency, aiCache, onAiCache }) {
  const ccy = summary?.display_currency ?? 'AED'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`

  const kpis = summary ? [
    { label: 'Purchase Value',  value: fmt(summary.total_purchase_value), sub: `${summary.total_deals} deals`,    color: 'gold' },
    { label: 'Collection Rate', value: pct(summary.collection_rate),      sub: 'vs Purchase Value',               color: 'teal' },
    { label: 'Denial Rate',     value: pct(summary.denial_rate),          sub: 'vs Purchase Value',               color: 'red'  },
    { label: 'Pending Exposure',value: fmt(summary.total_pending),        sub: pct(summary.pending_rate),         color: 'blue' },
    { label: 'Active Deals',    value: String(summary.active_deals),      sub: 'currently executing',             color: 'blue' },
    { label: 'Completed Deals', value: String(summary.completed_deals),   sub: 'fully collected',                 color: 'teal' },
    { label: 'Total Collected', value: fmt(summary.total_collected),      sub: 'cumulative collections',          color: 'teal' },
    { label: 'Total Denied',    value: fmt(summary.total_denied),         sub: 'denied by insurance',             color: 'red'  },
  ] : Array(8).fill(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* KPI grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        {kpis.map((k, i) => k
          ? <KpiCard key={i} {...k} />
          : <SkeletonKpi key={i} />
        )}
      </div>

      {/* Bottom row: AI commentary + Data Chat */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <AICommentary
          company={company} product={product}
          snapshot={snapshot} currency={currency}
          cached={aiCache} onCache={onAiCache}
        />
        <DataChat
          company={company} product={product}
          snapshot={snapshot} currency={currency}
        />
      </div>
    </div>
  )
}

/* ── Chart Tab wrapper ── */
function ChartTab({ tab, company, product, snapshot, currency, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TabInsight company={company} product={product} snapshot={snapshot} currency={currency} tab={tab} />
      {children}
    </div>
  )
}

/* ── Skeleton KPI ── */
function SkeletonKpi() {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: '16px', position: 'relative', overflow: 'hidden',
      minHeight: 90,
    }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: 'var(--border)', borderRadius: '10px 0 0 10px' }} />
      {[40, 70, 50].map((w, i) => (
        <div key={i} style={{
          height: i === 1 ? 18 : 8, borderRadius: 4, marginBottom: i === 1 ? 8 : 6,
          background: 'linear-gradient(90deg, var(--border) 25%, #1E2D40 50%, var(--border) 75%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 1.4s infinite',
          width: `${w}%`,
        }} />
      ))}
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
    </div>
  )
}

/* ── Small UI primitives ── */
function ControlGroup({ label, children }) {
  return (
    <div>
      <div style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 4 }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function DarkSelect({ value, onChange, children }) {
  return (
    <select
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      style={{
        fontSize: 11, padding: '6px 10px',
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 7, color: 'var(--text-primary)',
        fontFamily: 'var(--font-mono)', outline: 'none',
      }}
    >
      {children}
    </select>
  )
}

function CurrencyToggle({ localCcy, value, onChange }) {
  const opts = [localCcy, 'USD'].filter((v, i, a) => a.indexOf(v) === i)
  return (
    <div style={{ display: 'flex', borderRadius: 7, overflow: 'hidden', border: '1px solid var(--border)' }}>
      {opts.map(opt => (
        <button key={opt} onClick={() => onChange(opt)} style={{
          fontSize: 11, padding: '6px 12px',
          background: value === opt ? 'var(--gold)' : 'var(--bg-surface)',
          color: value === opt ? '#000' : 'var(--text-muted)',
          border: 'none', cursor: 'pointer',
          fontFamily: 'var(--font-mono)', fontWeight: value === opt ? 700 : 400,
          transition: 'all 0.15s',
        }}>
          {opt}
        </button>
      ))}
    </div>
  )
}