import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'
import useBreakpoint from '../hooks/useBreakpoint'
import { generatePDFReport, getParChart, getDtfcChart, getSummary, getCollectionVelocityChart, getDeploymentChart, getOperationalWal, getStaleExposure } from '../services/api'
import StaleExposurePanel from '../components/StaleExposurePanel'

import KpiCard       from '../components/KpiCard'
import AICommentary  from '../components/AICommentary'
import DataChat      from '../components/DataChat'
import TabInsight       from '../components/TabInsight'
import BackdatedBanner  from '../components/BackdatedBanner'
import SnapshotSelect   from '../components/SnapshotSelect'

// Klaim Charts
import DeploymentChart         from '../components/charts/DeploymentChart'
import ActualVsExpectedChart   from '../components/charts/ActualVsExpectedChart'
import CollectionVelocityChart from '../components/charts/CollectionVelocityChart'
import DenialTrendChart        from '../components/charts/DenialTrendChart'
import AgeingChart             from '../components/charts/AgeingChart'
import RevenueChart            from '../components/charts/RevenueChart'
import ConcentrationChart      from '../components/charts/ConcentrationChart'
import CohortTable             from '../components/charts/CohortTable'
import ReturnsAnalysisChart    from '../components/charts/ReturnsAnalysisChart'
import RiskMigrationChart      from '../components/charts/RiskMigrationChart'
import DenialFunnelChart       from '../components/charts/DenialFunnelChart'
import DataIntegrityChart      from '../components/charts/DataIntegrityChart'

// New analytical charts
import CdrCcrChart              from '../components/charts/CdrCcrChart'
import CohortLossWaterfallChart from '../components/charts/CohortLossWaterfallChart'
import RecoveryAnalysisChart    from '../components/charts/RecoveryAnalysisChart'
import CollectionsTimingChart   from '../components/charts/CollectionsTimingChart'
import UnderwritingDriftChart   from '../components/charts/UnderwritingDriftChart'
import SegmentAnalysisChart     from '../components/charts/SegmentAnalysisChart'
import SeasonalityChart         from '../components/charts/SeasonalityChart'

// SILQ Charts
import SilqDelinquencyChart    from '../components/charts/silq/DelinquencyChart'
import SilqCollectionsChart    from '../components/charts/silq/SilqCollectionsChart'
import SilqConcentrationChart  from '../components/charts/silq/SilqConcentrationChart'
import SilqCohortTable         from '../components/charts/silq/SilqCohortTable'
import YieldMarginsChart       from '../components/charts/silq/YieldMarginsChart'
import TenureAnalysisChart     from '../components/charts/silq/TenureAnalysisChart'
import SilqCovenantsChart      from '../components/charts/silq/SilqCovenantsChart'
import SilqSeasonalityChart    from '../components/charts/silq/SilqSeasonalityChart'
import SilqLossWaterfallChart  from '../components/charts/silq/SilqLossWaterfallChart'
import SilqUnderwritingDriftChart from '../components/charts/silq/SilqUnderwritingDriftChart'
import SilqCdrCcrChart           from '../components/charts/silq/SilqCdrCcrChart'
import EjariDashboard          from './EjariDashboard'
import TamaraDashboard         from './TamaraDashboard'
import AajilDashboard          from './AajilDashboard'

import { TAPE_TABS } from '../components/Sidebar'

const SLUG_TO_LABEL = Object.fromEntries(TAPE_TABS.map(t => [t.slug, t.label]))

export default function TapeAnalytics() {
  const { tab } = useParams()
  const { isMobile } = useBreakpoint()

  const {
    company, product, snapshots, snapshotsMeta, snapshot, setSnapshot,
    config, currency, setCurrency, localCcy,
    summary, summaryLoading,
    aiCache, setAiCache,
    asOfDate, setAsOfDate, dateRange, snapshotDate, isBackdated,
    reportGenerating, reportError, handleGenerateReport,
    analysisType, tapeTabs,
  } = useCompany()

  // Build slug→label map from config tabs or default
  const tabs = tapeTabs || TAPE_TABS
  const slugToLabel = Object.fromEntries(tabs.map(t => [t.slug, t.label]))
  const activeTab = slugToLabel[tab] || 'Overview'

  // Ejari: render read-only summary dashboard instead of normal tabs
  if (analysisType === 'ejari_summary') {
    return (
      <div style={{ padding: isMobile ? '12px 14px' : '16px 28px' }}>
        <EjariDashboard />
      </div>
    )
  }

  // Tamara: render BNPL summary dashboard
  if (analysisType === 'tamara_summary') {
    return (
      <div style={{ padding: isMobile ? '12px 14px' : '16px 28px' }}>
        <TamaraDashboard />
      </div>
    )
  }

  // Aajil: render SME trade credit dashboard
  if (analysisType === 'aajil') {
    return (
      <div style={{ padding: isMobile ? '12px 14px' : '16px 28px' }}>
        <AajilDashboard />
      </div>
    )
  }

  return (
    <div>
      {/* Controls bar */}
      <div style={{ padding: isMobile ? '12px 14px 0' : '16px 28px 0', display: 'flex', gap: isMobile ? 8 : 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        {/* Snapshot selector */}
        <ControlGroup label="Tape">
          <SnapshotSelect
            value={snapshot ?? ''}
            onChange={v => { setSnapshot(v); setAiCache(null) }}
            snapshots={snapshots}
            snapshotsMeta={snapshotsMeta}
          />
        </ControlGroup>

        {/* As-of Date picker */}
        <ControlGroup label="As-of Date">
          <input
            type="date"
            value={asOfDate}
            min={dateRange.min}
            max={dateRange.max}
            onChange={e => setAsOfDate(e.target.value)}
            style={{
              fontSize: 11, padding: '5px 10px',
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              borderRadius: 7, color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)', outline: 'none',
              colorScheme: 'dark',
            }}
          />
        </ControlGroup>

        {/* Currency toggle */}
        <ControlGroup label="Currency">
          <CurrencyToggle localCcy={localCcy} value={currency} onChange={setCurrency} />
        </ControlGroup>

        {/* Divider */}
        <div style={{ width: 1, height: 32, background: 'var(--border)', alignSelf: 'flex-end', marginBottom: 2 }} />

        {/* PDF Report button — only for Klaim (SILQ PDF not yet supported) */}
        {analysisType !== 'silq' && (
          <div style={{ alignSelf: 'flex-end' }}>
            <button
              disabled={reportGenerating || !product || !snapshot}
              onClick={handleGenerateReport}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 11, fontWeight: 600, padding: '6px 14px',
                borderRadius: 7, cursor: reportGenerating ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
                fontFamily: 'inherit',
                ...(reportError
                  ? { background: 'transparent', border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }
                  : reportGenerating
                  ? { background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' }
                  : { background: 'transparent', border: '1px solid var(--gold)', color: 'var(--gold)' }
                ),
              }}
            >
              {reportGenerating ? (
                <>
                  <SpinnerIcon />
                  Generating…
                </>
              ) : reportError ? (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  Retry
                </>
              ) : (
                <>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
                  </svg>
                  PDF Report
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Tab content */}
      <div style={{ padding: isMobile ? '14px 14px 28px' : '20px 28px 40px' }}>
        {isBackdated && <BackdatedBanner asOfDate={asOfDate} snapshotDate={snapshotDate} />}
        <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 12, filter: 'blur(3px)' }}
          animate={{ opacity: 1, y: 0,  filter: 'blur(0px)' }}
          exit={{    opacity: 0, y: -4, filter: 'blur(2px)' }}
          transition={{ duration: 0.28, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
        {analysisType === 'silq' ? (
          <SilqTabContent
            tab={tab} activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
            isBackdated={isBackdated}
          />
        ) : (
          <KlaimTabContent
            activeTab={activeTab}
            company={company} product={product}
            snapshot={snapshot} snapshots={snapshots}
            currency={currency} asOfDate={asOfDate}
            summary={summary} summaryLoading={summaryLoading}
            aiCache={aiCache} onAiCache={setAiCache}
            isBackdated={isBackdated}
          />
        )}
        </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

/* ── SILQ Tab Content ── */
function SilqTabContent({ tab, activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache, isBackdated }) {
  const chartProps = { company, product, snapshot, currency, asOfDate, isBackdated }

  if (tab === 'overview') {
    return (
      <SilqOverviewTab
        summary={summary} summaryLoading={summaryLoading}
        company={company} product={product}
        snapshot={snapshot} currency={currency} asOfDate={asOfDate}
        aiCache={aiCache} onAiCache={onAiCache}
        isBackdated={isBackdated}
      />
    )
  }
  if (tab === 'data-integrity') {
    return <DataIntegrityChart company={company} product={product} snapshots={snapshots} snapshotsMeta={snapshotsMeta} currency={currency} />
  }
  // Map tab slugs to components
  const SILQ_TABS = {
    'delinquency':     <ChartTab tab="delinquency" {...chartProps}><SilqDelinquencyChart {...chartProps} /></ChartTab>,
    'collections':     <ChartTab tab="collections" {...chartProps}><SilqCollectionsChart {...chartProps} /></ChartTab>,
    'concentration':   <ChartTab tab="concentration" {...chartProps}><SilqConcentrationChart {...chartProps} /></ChartTab>,
    'cohort-analysis': <ChartTab tab="cohort" {...chartProps}><SilqCohortTable {...chartProps} /></ChartTab>,
    'yield-margins':   <ChartTab tab="yield-margins" {...chartProps}><YieldMarginsChart {...chartProps} /></ChartTab>,
    'tenure':          <ChartTab tab="tenure" {...chartProps}><TenureAnalysisChart {...chartProps} /></ChartTab>,
    'covenants':          <ChartTab tab="covenants" {...chartProps}><SilqCovenantsChart {...chartProps} /></ChartTab>,
    'seasonality':        <ChartTab tab="seasonality" {...chartProps}><SilqSeasonalityChart {...chartProps} /></ChartTab>,
    'loss-waterfall':     <ChartTab tab="loss-waterfall" {...chartProps}><SilqLossWaterfallChart {...chartProps} /></ChartTab>,
    'underwriting-drift': <ChartTab tab="underwriting-drift" {...chartProps}><SilqUnderwritingDriftChart {...chartProps} /></ChartTab>,
    'cdr-ccr':            <ChartTab tab="cdr-ccr" {...chartProps}><SilqCdrCcrChart {...chartProps} /></ChartTab>,
  }
  return SILQ_TABS[tab] || <div style={{ color: 'var(--text-muted)' }}>Tab not found</div>
}

/* ── Klaim Tab Content ── */
function KlaimTabContent({ activeTab, company, product, snapshot, snapshots, currency, asOfDate, summary, summaryLoading, aiCache, onAiCache, isBackdated }) {
  return (
    <>
      {activeTab === 'Overview' && (
        <OverviewTab
          summary={summary} summaryLoading={summaryLoading}
          company={company} product={product}
          snapshot={snapshot} currency={currency} asOfDate={asOfDate}
          aiCache={aiCache} onAiCache={onAiCache}
          isBackdated={isBackdated}
        />
      )}
      {activeTab === 'Actual vs Expected' && (
        <ChartTab tab="actual-vs-expected" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <ActualVsExpectedChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Deployment' && (
        <ChartTab tab="deployment" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <DeploymentChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Collection' && (
        <ChartTab tab="collection-velocity" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <CollectionVelocityChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Denial Trend' && (
        <ChartTab tab="denial-trend" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <DenialFunnelChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
          <DenialTrendChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Ageing' && (
        <ChartTab tab="ageing" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <AgeingChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Revenue' && (
        <ChartTab tab="revenue" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <RevenueChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Portfolio' && (
        <ChartTab tab="concentration" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <ConcentrationChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Cohort Analysis' && (
        <ChartTab tab="cohort" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <CohortTable company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Returns' && (
        <ChartTab tab="returns" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <ReturnsAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Collections Timing' && (
        <ChartTab tab="collections-timing" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <CollectionsTimingChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Loss Waterfall' && (
        <ChartTab tab="loss-waterfall" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <CohortLossWaterfallChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Recovery Analysis' && (
        <ChartTab tab="recovery-analysis" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <RecoveryAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Underwriting Drift' && (
        <ChartTab tab="underwriting-drift" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <UnderwritingDriftChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Segment Analysis' && (
        <ChartTab tab="segment-analysis" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <SegmentAnalysisChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Seasonality' && (
        <ChartTab tab="seasonality" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <SeasonalityChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'CDR / CCR' && (
        <ChartTab tab="cdr-ccr" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <CdrCcrChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Risk & Migration' && (
        <ChartTab tab="risk-migration" company={company} product={product} snapshot={snapshot} currency={currency} isBackdated={isBackdated}>
          <RiskMigrationChart company={company} product={product} snapshot={snapshot} currency={currency} asOfDate={asOfDate} />
        </ChartTab>
      )}
      {activeTab === 'Data Integrity' && (
        <DataIntegrityChart company={company} product={product} snapshots={snapshots} snapshotsMeta={snapshotsMeta} currency={currency} />
      )}
    </>
  )
}

/* ── SILQ Overview Tab ── */
function SilqOverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache, isBackdated }) {
  const ccy = summary?.display_currency ?? 'SAR'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`

  const { snapshots } = useCompany()
  const [prevSummary, setPrevSummary] = useState(null)

  useEffect(() => {
    if (!product || !snapshot || !snapshots?.length) { setPrevSummary(null); return }
    const idx      = snapshots.indexOf(snapshot)
    const prevSnap = idx > 0 ? snapshots[idx - 1] : null
    if (!prevSnap) { setPrevSummary(null); return }
    getSummary(company, product, prevSnap, currency).then(setPrevSummary).catch(() => setPrevSummary(null))
  }, [company, product, snapshot, currency, snapshots])

  const δcoll    = prevSummary ? (summary?.collection_rate ?? 0) - prevSummary.collection_rate  : undefined
  const δoverdue = prevSummary ? -((summary?.overdue_rate  ?? 0) - prevSummary.overdue_rate)     : undefined  // inverted
  const δactive  = prevSummary && prevSummary.active_deals > 0
    ? (((summary?.active_deals ?? 0) - prevSummary.active_deals) / prevSummary.active_deals) * 100
    : undefined

  const bd = isBackdated  // shorthand
  const kpis = summary ? [
    { label: 'Total Disbursed',  value: fmt(summary.total_disbursed),  sub: `${summary.total_deals} loans`,        color: 'gold' },
    { label: 'Outstanding',      value: fmt(summary.total_outstanding),sub: 'current exposure',                     color: 'blue', stale: bd },
    { label: 'Total Overdue',    value: fmt(summary.total_overdue),    sub: 'past repayment deadline',              color: 'red',  stale: bd },
    { label: 'Collection Rate',  value: pct(summary.collection_rate),  sub: 'repaid vs collectable',                color: 'teal', stale: bd, trend: δcoll,    trendLabel: 'vs prev snapshot' },
    { label: 'Overdue Rate',     value: pct(summary.overdue_rate),     sub: 'of outstanding',                       color: summary.overdue_rate > 15 ? 'red' : 'gold', stale: bd, trend: δoverdue, trendLabel: 'vs prev snapshot' },
    { label: 'Active Loans',     value: String(summary.active_deals),  sub: 'currently open',                       color: 'blue',             trend: δactive,  trendLabel: 'vs prev snapshot' },
    { label: 'Completed Loans',  value: String(summary.completed_deals), sub: 'closed',                             color: 'teal' },
    { label: 'Avg Tenure',       value: `${summary.avg_tenure?.toFixed(0) ?? '—'}w`, sub: 'weeks',                  color: 'gold' },
    { label: 'HHI (Shop)',       value: summary.hhi_shop?.toFixed(4) ?? '—', sub: `Top shop: ${pct(summary.top_1_shop_pct)}`, color: summary.hhi_shop > 0.15 ? 'red' : 'teal' },
    { label: 'Total Repaid',     value: fmt(summary.total_repaid),     sub: 'cumulative collections',               color: 'teal', stale: bd },
  ] : Array(10).fill(null)

  // Credit Quality — PAR as dedicated section.
  // Framework §17 (session 36 universal rule): lifetime-primary across ALL
  // asset classes. Lifetime goes in the headline (denominator: total_disbursed);
  // active-outstanding is the secondary context shown in the subtitle +
  // confidence tooltip. Cross-company IC consistency — analysts compare SILQ's
  // lifetime PAR to Klaim's and Aajil's without re-normalising.
  const silqParBuildSub = (amount, activePct) => {
    const atRisk = amount != null ? `${ccy} ${(amount / 1000).toFixed(0)}K at risk` : '—'
    if (activePct != null) {
      return `${atRisk} · Active: ${activePct.toFixed(2)}%`
    }
    return atRisk
  }
  const parKpis = summary ? [
    { label: 'PAR 30+', value: pct(summary.lifetime_par30 ?? summary.par30), sub: silqParBuildSub(summary.par30_amount, summary.par30), color: (summary.lifetime_par30 ?? summary.par30) > 10 ? 'red' : (summary.lifetime_par30 ?? summary.par30) > 5 ? 'gold' : 'teal', stale: bd, confidence: summary.par_confidence || 'A', population: summary.par_lifetime_population || 'total_originated', confidenceNote: summary.par30 != null ? `Active-outstanding PAR 30+ (live book): ${summary.par30.toFixed(2)}%` : undefined },
    { label: 'PAR 60+', value: pct(summary.lifetime_par60 ?? summary.par60), sub: silqParBuildSub(summary.par60_amount, summary.par60), color: (summary.lifetime_par60 ?? summary.par60) > 5 ? 'red' : (summary.lifetime_par60 ?? summary.par60) > 2.5 ? 'gold' : 'teal', stale: bd, confidence: summary.par_confidence || 'A', population: summary.par_lifetime_population || 'total_originated', confidenceNote: summary.par60 != null ? `Active-outstanding PAR 60+ (live book): ${summary.par60.toFixed(2)}%` : undefined },
    { label: 'PAR 90+', value: pct(summary.lifetime_par90 ?? summary.par90), sub: silqParBuildSub(summary.par90_amount, summary.par90), color: (summary.lifetime_par90 ?? summary.par90) > 2.5 ? 'red' : (summary.lifetime_par90 ?? summary.par90) > 1 ? 'gold' : 'teal', stale: bd, confidence: summary.par_confidence || 'A', population: summary.par_lifetime_population || 'total_originated', confidenceNote: summary.par90 != null ? `Active-outstanding PAR 90+ (live book): ${summary.par90.toFixed(2)}%` : undefined },
  ] : []

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} index={i} />)
        }
      </div>

      {/* Credit Quality — PAR section (lifetime-primary, session 36 §17 rule) */}
      {summary && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
              Credit Quality
            </span>
            <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', opacity: 0.7 }}>
              vs Total Disbursed (lifetime)
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {parKpis.map((k, i) => <KpiCard key={`par-${i}`} {...k} index={i} />)}
          </div>
        </div>
      )}

      {summary?.portfolio_commentary && (
        <PortfolioCommentaryPanel text={summary.portfolio_commentary} />
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
        <AICommentary company={company} product={product} snapshot={snapshot} currency={currency} cached={aiCache} onCache={onAiCache} isBackdated={isBackdated} />
        <DataChat company={company} product={product} snapshot={snapshot} currency={currency} />
      </div>
    </div>
  )
}

/* ── Portfolio Commentary Panel ── */
function PortfolioCommentaryPanel({ text }) {
  const [expanded, setExpanded] = React.useState(false)
  const preview = text.length > 280 ? text.slice(0, 280) + '...' : text

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8,
      padding: '12px 16px', borderLeft: '3px solid var(--accent-gold)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-gold)' }}>Portfolio Commentary</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>from tape</span>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
        {expanded ? text : preview}
      </div>
      {text.length > 280 && (
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            marginTop: 6, background: 'none', border: 'none', color: 'var(--accent-gold)',
            fontSize: 12, cursor: 'pointer', padding: 0,
          }}
        >{expanded ? 'Show less' : 'Read more'}</button>
      )}
    </div>
  )
}

/* ── Klaim Overview Tab ── */
function OverviewTab({ summary, summaryLoading, company, product, snapshot, currency, asOfDate, aiCache, onAiCache, isBackdated }) {
  const ccy = summary?.display_currency ?? 'AED'
  const fmt  = (v) => v == null ? '—' : v >= 1_000_000 ? `${ccy} ${(v/1_000_000).toFixed(1)}M` : `${ccy} ${(v/1_000).toFixed(0)}K`
  const pct  = (v) => v == null ? '—' : `${v.toFixed(1)}%`
  const hhiFmt = (v) => v == null ? '—' : v.toFixed(4)
  const bd = isBackdated

  const { snapshots } = useCompany()

  // Fetch PAR, DTFC, Operational WAL, Stale Exposure, and sparkline data
  const [par,             setPar]             = useState(null)
  const [dtfc,            setDtfc]            = useState(null)
  const [opWal,           setOpWal]           = useState(null)
  const [staleExp,        setStaleExp]        = useState(null)
  const [prevSummary,     setPrevSummary]     = useState(null)
  const [collSparkline,   setCollSparkline]   = useState(null)
  const [deploySparkline, setDeploySparkline] = useState(null)

  useEffect(() => {
    if (!product || !snapshot) return
    getParChart(company, product, snapshot, currency, asOfDate).then(setPar).catch(() => setPar(null))
    getDtfcChart(company, product, snapshot, currency, asOfDate).then(setDtfc).catch(() => setDtfc(null))
    getOperationalWal(company, product, snapshot, currency, asOfDate).then(setOpWal).catch(() => setOpWal(null))
    getStaleExposure(company, product, snapshot, currency, asOfDate).then(setStaleExp).catch(() => setStaleExp(null))
    getCollectionVelocityChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const monthly = res.monthly ?? []
        const vals = monthly.slice(-6).map(d => d.collection_rate ?? 0)
        setCollSparkline(vals.length >= 3 ? vals : null)
      }).catch(() => setCollSparkline(null))
    getDeploymentChart(company, product, snapshot, currency, asOfDate)
      .then(res => {
        const monthly = Array.isArray(res.data ?? res) ? (res.data ?? res) : []
        const vals = monthly.slice(-6).map(d => (d.new_business ?? 0) + (d.repeat_business ?? d.repeat ?? 0))
        setDeploySparkline(vals.length >= 3 ? vals : null)
      }).catch(() => setDeploySparkline(null))
  }, [company, product, snapshot, currency, asOfDate])

  // Fetch previous snapshot summary for delta indicators
  useEffect(() => {
    if (!product || !snapshot || !snapshots?.length) { setPrevSummary(null); return }
    const idx     = snapshots.indexOf(snapshot)
    const prevSnap = idx > 0 ? snapshots[idx - 1] : null
    if (!prevSnap) { setPrevSummary(null); return }
    getSummary(company, product, prevSnap, currency).then(setPrevSummary).catch(() => setPrevSummary(null))
  }, [company, product, snapshot, currency, snapshots])

  // Snapshot-over-snapshot deltas (percentage points for rate metrics)
  const δcoll   = prevSummary ? (summary?.collection_rate ?? 0) - prevSummary.collection_rate   : undefined
  const δdenial = prevSummary ? -((summary?.denial_rate   ?? 0) - prevSummary.denial_rate)       : undefined  // inverted: lower denial = positive
  const δactive = prevSummary && prevSummary.active_deals > 0
    ? (((summary?.active_deals ?? 0) - prevSummary.active_deals) / prevSummary.active_deals) * 100
    : undefined

  const kpis = summary ? [
    { label: 'Purchase Value',  value: fmt(summary.total_purchase_value), sub: `${summary.total_deals} deals`,    color: 'gold', confidence: 'A', sparklineData: deploySparkline },
    { label: 'Collection Rate', value: pct(summary.collection_rate),      sub: 'vs Purchase Value',               color: 'teal', stale: bd, confidence: 'A', trend: δcoll,   trendLabel: 'vs prev snapshot', sparklineData: collSparkline },
    { label: 'Denial Rate',     value: pct(summary.denial_rate),          sub: 'vs Purchase Value',               color: 'red',  stale: bd, confidence: 'A', trend: δdenial, trendLabel: 'vs prev snapshot' },
    { label: 'Pending Exposure',value: fmt(summary.total_pending),        sub: pct(summary.pending_rate),         color: 'blue', stale: bd, confidence: 'A' },
    { label: 'Active Deals',    value: String(summary.active_deals),      sub: 'currently executing',             color: 'blue', confidence: 'A',             trend: δactive, trendLabel: 'vs prev snapshot' },
    { label: 'Completed Deals', value: String(summary.completed_deals),   sub: 'fully collected',                 color: 'teal', confidence: 'A' },
    { label: 'Total Collected', value: fmt(summary.total_collected),      sub: 'cumulative collections',          color: 'teal', stale: bd, confidence: 'A' },
    { label: 'Total Denied',    value: fmt(summary.total_denied),         sub: 'denied by insurance',             color: 'red',  stale: bd, confidence: 'A' },
    ...(summary.dso_available ? [{ label: 'Wtd Avg DSO', value: summary.dso != null ? `${summary.dso.toFixed(0)}d` : '—', sub: `Median: ${summary.median_dso != null ? summary.median_dso.toFixed(0) + 'd' : '—'}`, color: 'gold', stale: bd, confidence: 'B' }] : []),
    { label: 'HHI (Group)',     value: hhiFmt(summary.hhi_group), sub: `Top provider: ${pct(summary.top_1_group_pct)}`, color: summary.hhi_group > 0.15 ? 'red' : summary.hhi_group > 0.10 ? 'gold' : 'teal', confidence: 'A' },
  ] : Array(10).fill(null)

  // PAR KPIs — Framework §17 session 36 rule: lifetime-primary across all asset
  // classes. Lifetime = headline (denominator: total_originated), active = secondary.
  const parConfidence = par?.method === 'primary' ? 'B' : 'C'
  const klaimParSub = (amount, activePct) => {
    const atRisk = `${ccy} ${(amount / 1000).toFixed(0)}K at risk`
    return activePct != null
      ? `${atRisk} · Active: ${activePct.toFixed(2)}%`
      : atRisk
  }
  const parKpis = par?.available ? [
    { label: 'PAR 30+', value: pct(par.lifetime_par30 ?? par.par30), sub: klaimParSub(par.par30_amount, par.par30), color: (par.lifetime_par30 ?? par.par30) > 2 ? 'red' : (par.lifetime_par30 ?? par.par30) > 1 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence, population: par.par_lifetime_population || 'total_originated', confidenceNote: par.par30 != null ? `Active-outstanding PAR 30+: ${par.par30.toFixed(2)}%` : undefined },
    { label: 'PAR 60+', value: pct(par.lifetime_par60 ?? par.par60), sub: klaimParSub(par.par60_amount, par.par60), color: (par.lifetime_par60 ?? par.par60) > 1.5 ? 'red' : (par.lifetime_par60 ?? par.par60) > 0.75 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence, population: par.par_lifetime_population || 'total_originated', confidenceNote: par.par60 != null ? `Active-outstanding PAR 60+: ${par.par60.toFixed(2)}%` : undefined },
    { label: 'PAR 90+', value: pct(par.lifetime_par90 ?? par.par90), sub: klaimParSub(par.par90_amount, par.par90), color: (par.lifetime_par90 ?? par.par90) > 1 ? 'red' : (par.lifetime_par90 ?? par.par90) > 0.5 ? 'gold' : 'teal', derived: par.method === 'derived', confidence: parConfidence, population: par.par_lifetime_population || 'total_originated', confidenceNote: par.par90 != null ? `Active-outstanding PAR 90+: ${par.par90.toFixed(2)}%` : undefined },
  ] : []

  // DTFC KPIs — only shown when available
  const dtfcConfidence = dtfc?.method === 'curve_based' ? 'B' : 'C'
  const dtfcKpis = dtfc?.available ? [
    { label: 'DTFC (Median)', value: `${dtfc.median_dtfc.toFixed(0)}d`, sub: `${dtfc.total_deals} deals`, color: 'blue', confidence: dtfcConfidence },
    { label: 'DTFC (P90)',    value: `${dtfc.p90_dtfc.toFixed(0)}d`, sub: 'slowest 10%',                  color: dtfc.p90_dtfc > 90 ? 'red' : 'gold', confidence: dtfcConfidence },
  ] : []

  // Capital Life (Operational WAL + Realized WAL) — Klaim Tape-side only.
  // Strips the zombie tail from the covenant-facing WAL Total (which lives on
  // Portfolio Covenants and stays unchanged per MMA Art. 21). Operational WAL =
  // "how long is capital deployed in the live book?". Realized WAL =
  // "how long did completed-clean deals actually take to resolve?".
  const walKpis = opWal?.available ? [
    {
      label: 'Operational WAL',
      value: `${opWal.operational_wal_days.toFixed(0)}d`,
      sub: opWal.confidence === 'C'
        ? `Degraded — active-clean only (tape lacks close-age)`
        : `Clean book · excludes ${opWal.stale_deal_count} stale deals (${((opWal.stale_pv / opWal.total_pv) * 100).toFixed(1)}% of PV)`,
      color: 'gold',
      confidence: opWal.confidence,
      stale: bd,
    },
    ...(opWal.realized_wal_days != null ? [{
      label: 'Realized WAL',
      value: `${opWal.realized_wal_days.toFixed(0)}d`,
      sub: 'Completed-clean · PV-weighted close-age',
      color: 'teal',
      confidence: opWal.confidence,
      stale: bd,
    }] : []),
  ] : []

  const showSkeleton = summaryLoading || !summary

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {summaryLoading && <LoadingBar />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
        {showSkeleton
          ? Array(10).fill(null).map((_, i) => <SkeletonKpi key={i} />)
          : kpis.map((k, i) => <KpiCard key={i} {...k} index={i} />)
        }
      </div>

      {/* Credit Quality — PAR section */}
      {parKpis.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
              Credit Quality
            </span>
            <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', opacity: 0.7 }}>
              vs Total Originated
            </span>
            {par?.method === 'derived' && (
              <span style={{
                fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                background: 'rgba(201,168,76,0.1)', color: 'var(--gold)',
                border: '1px dashed rgba(201,168,76,0.3)',
              }}>
                Derived from historical patterns
              </span>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {parKpis.map((k, i) => (
              <div key={`par-${i}`} style={k.derived ? { borderStyle: 'dashed' } : undefined}>
                <KpiCard {...k} index={i} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Capital Life — Operational WAL + Realized WAL (clean book view) */}
      {walKpis.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>
              Capital Life
            </span>
            <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--text-muted)', opacity: 0.7 }}>
              Clean book · excludes zombie tail
            </span>
            {opWal?.confidence === 'C' && (
              <span style={{
                fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                background: 'rgba(201,168,76,0.1)', color: 'var(--accent-gold)',
                border: '1px dashed rgba(201,168,76,0.3)',
              }}>
                Degraded on this tape — active only
              </span>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {walKpis.map((k, i) => (
              <div key={`wal-${i}`} style={opWal?.confidence === 'C' ? { borderStyle: 'dashed' } : undefined}>
                <KpiCard {...k} index={i} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Leading Indicators — DTFC section */}
      {dtfcKpis.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 8 }}>
            Leading Indicators
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {dtfcKpis.map((k, i) => <KpiCard key={`dtfc-${i}`} {...k} index={i} />)}
          </div>
        </div>
      )}

      {/* Stale Exposure — zombie-tail PV with category breakdown + top-25 offenders drill-down */}
      {staleExp?.available && (
        <StaleExposurePanel data={staleExp} ccy={ccy} />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
        <AICommentary company={company} product={product} snapshot={snapshot} currency={currency} cached={aiCache} onCache={onAiCache} isBackdated={isBackdated} />
        <DataChat company={company} product={product} snapshot={snapshot} currency={currency} />
      </div>
    </div>
  )
}

/* ── Loading Bar ── */
function LoadingBar() {
  return (
    <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', background: 'var(--border)' }}>
      <div style={{ height: '100%', width: '40%', borderRadius: 2, background: 'var(--gold)', animation: 'loadSlide 1s ease-in-out infinite' }} />
      <style>{`@keyframes loadSlide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }`}</style>
    </div>
  )
}

/* ── Chart Tab wrapper ── */
function ChartTab({ tab, company, product, snapshot, currency, children, isBackdated }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TabInsight company={company} product={product} snapshot={snapshot} currency={currency} tab={tab} isBackdated={isBackdated} />
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
          background: 'linear-gradient(90deg, var(--border) 25%, #243A50 50%, var(--border) 75%)',
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

function SpinnerIcon() {
  return (
    <>
      <div style={{
        width: 12, height: 12,
        border: '2px solid var(--border)',
        borderTopColor: 'var(--gold)',
        borderRadius: '50%',
        animation: 'reportSpin 0.8s linear infinite',
      }} />
      <style>{`@keyframes reportSpin { to { transform: rotate(360deg); } }`}</style>
    </>
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
