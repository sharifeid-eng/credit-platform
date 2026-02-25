import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getProducts, getSnapshots, getPortfolioSummary,
  getDateRange, getProductConfig,
  getDeploymentChart, getCollectionVelocity,
  getDenialTrend, getCohortAnalysis,
  getActualVsExpected, getAgeing, getRevenue, getConcentration
} from '../services/api';
import KpiCard from '../components/KpiCard';
import DeploymentChart from '../components/charts/DeploymentChart';
import CollectionVelocityChart from '../components/charts/CollectionVelocityChart';
import DenialTrendChart from '../components/charts/DenialTrendChart';
import CohortTable from '../components/charts/CohortTable';
import ActualVsExpectedChart from '../components/charts/ActualVsExpectedChart';
import AgeingChart from '../components/charts/AgeingChart';
import RevenueChart from '../components/charts/RevenueChart';
import ConcentrationChart from '../components/charts/ConcentrationChart';
import AICommentary from '../components/AICommentary';
import DataChat from '../components/DataChat';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'actual-vs-expected', label: 'Actual vs Expected' },
  { id: 'deployment', label: 'Deployment' },
  { id: 'collection', label: 'Collection' },
  { id: 'ageing', label: 'Ageing' },
  { id: 'revenue', label: 'Revenue' },
  { id: 'concentration', label: 'Portfolio' },
  { id: 'cohort', label: 'Cohort Analysis' },
];

export default function Company() {
  const { companyName } = useParams();
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);
  const [dateRange, setDateRange] = useState(null);
  const [asOfDate, setAsOfDate] = useState(null);
  const [productConfig, setProductConfig] = useState(null);
  const [displayCurrency, setDisplayCurrency] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [chartData, setChartData] = useState({});
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [tabLoading, setTabLoading] = useState(false);

  useEffect(() => {
    getProducts(companyName).then(data => {
      setProducts(data);
      if (data.length > 0) setSelectedProduct(data[0]);
      setLoading(false);
    });
  }, [companyName]);

  useEffect(() => {
    if (!selectedProduct) return;
    getProductConfig(companyName, selectedProduct).then(config => {
      setProductConfig(config);
      setDisplayCurrency(config.currency);
    });
    getSnapshots(companyName, selectedProduct).then(data => {
      setSnapshots(data);
      if (data.length > 0) setSelectedSnapshot(data[data.length - 1].date);
    });
  }, [selectedProduct]);

  useEffect(() => {
    if (!selectedProduct || !selectedSnapshot) return;
    getDateRange(companyName, selectedProduct, selectedSnapshot).then(data => {
      setDateRange(data);
      setAsOfDate(data.max_date);
    });
  }, [selectedSnapshot]);

  useEffect(() => {
    if (!selectedProduct || !selectedSnapshot || !asOfDate || !displayCurrency) return;
    setSummaryLoading(true);
    getPortfolioSummary(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency)
      .then(data => { setSummary(data); setSummaryLoading(false); })
      .catch(() => setSummaryLoading(false));
  }, [selectedProduct, selectedSnapshot, asOfDate, displayCurrency]);

  // Load chart data when tab changes
  useEffect(() => {
    if (!selectedProduct || !selectedSnapshot || !asOfDate || !displayCurrency) return;
    if (activeTab === 'overview') return;

    setTabLoading(true);

    const loaders = {
      'actual-vs-expected': () => getActualVsExpected(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'deployment': () => getDeploymentChart(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'collection': () => getCollectionVelocity(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'ageing': () => getAgeing(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'revenue': () => getRevenue(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'concentration': () => getConcentration(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
      'cohort': () => getCohortAnalysis(companyName, selectedProduct, selectedSnapshot, asOfDate, displayCurrency),
    };

    if (loaders[activeTab]) {
      loaders[activeTab]()
        .then(data => {
          setChartData(prev => ({ ...prev, [activeTab]: data }));
          setTabLoading(false);
        })
        .catch(() => setTabLoading(false));
    }
  }, [activeTab, selectedProduct, selectedSnapshot, asOfDate, displayCurrency]);

  const currencySymbol = displayCurrency === 'USD' ? '$' : (displayCurrency + ' ');

  if (loading) return (
    <div className="min-h-screen pt-24 flex items-center justify-center"
         style={{ backgroundColor: '#0A0F1E' }}>
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen pt-24 px-6 pb-12" style={{ backgroundColor: '#0A0F1E' }}>
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link to="/" className="text-xs hover:text-white transition-colors"
                    style={{ color: '#64748B' }}>Companies</Link>
              <span style={{ color: '#64748B' }}>›</span>
              <span className="text-xs" style={{ color: '#93C5FD' }}>
                {companyName.toUpperCase()}
              </span>
            </div>
            <h1 className="text-3xl font-bold text-white">{companyName.toUpperCase()}</h1>
            {productConfig?.description && (
              <p className="text-sm mt-1" style={{ color: '#64748B' }}>
                {productConfig.description}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-3 items-end">
            <div className="flex items-end gap-3">
              {products.length > 1 && (
                <div className="flex flex-col gap-1">
                  <label className="text-xs" style={{ color: '#64748B' }}>Product</label>
                  <select value={selectedProduct || ''}
                    onChange={e => setSelectedProduct(e.target.value)}
                    className="text-sm px-3 py-2 rounded-lg outline-none"
                    style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A', color: '#93C5FD' }}>
                    {products.map(p => (
                      <option key={p} value={p}>{p.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: '#64748B' }}>Data Tape</label>
                <select value={selectedSnapshot || ''}
                  onChange={e => setSelectedSnapshot(e.target.value)}
                  className="text-sm px-3 py-2 rounded-lg outline-none"
                  style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A', color: '#93C5FD' }}>
                  {snapshots.map(s => (
                    <option key={s.date} value={s.date}>{s.date}</option>
                  ))}
                </select>
              </div>
              {productConfig && (
                <div className="flex flex-col gap-1">
                  <label className="text-xs" style={{ color: '#64748B' }}>Currency</label>
                  <div className="flex rounded-lg overflow-hidden"
                       style={{ border: '1px solid #1B2B5A' }}>
                    <button onClick={() => setDisplayCurrency(productConfig.currency)}
                      className="text-sm px-3 py-2 transition-colors"
                      style={{
                        backgroundColor: displayCurrency === productConfig.currency ? '#3B82F6' : '#111D3E',
                        color: displayCurrency === productConfig.currency ? 'white' : '#93C5FD'
                      }}>
                      {productConfig.currency}
                    </button>
                    <button onClick={() => setDisplayCurrency('USD')}
                      className="text-sm px-3 py-2 transition-colors"
                      style={{
                        backgroundColor: displayCurrency === 'USD' ? '#3B82F6' : '#111D3E',
                        color: displayCurrency === 'USD' ? 'white' : '#93C5FD',
                        borderLeft: '1px solid #1B2B5A'
                      }}>
                      USD
                    </button>
                  </div>
                </div>
              )}
            </div>
            {dateRange && (
              <div className="flex flex-col gap-1">
                <label className="text-xs" style={{ color: '#64748B' }}>
                  As-of Date
                  <span className="ml-2" style={{ color: '#334155' }}>
                    ({dateRange.min_date} → {dateRange.max_date})
                  </span>
                </label>
                <input type="date" value={asOfDate || ''}
                  min={dateRange.min_date} max={dateRange.max_date}
                  onChange={e => setAsOfDate(e.target.value)}
                  className="text-sm px-3 py-2 rounded-lg outline-none"
                  style={{
                    backgroundColor: '#111D3E', border: '1px solid #1B2B5A',
                    color: '#93C5FD', colorScheme: 'dark'
                  }} />
              </div>
            )}
          </div>
        </div>

        {/* Context bar */}
        {summary && (
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <div className="text-xs px-3 py-1.5 rounded-full"
                 style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A', color: '#93C5FD' }}>
              {summary.total_deals.toLocaleString()} deals as of {asOfDate}
            </div>
            <div className="text-xs px-3 py-1.5 rounded-full"
                 style={{ backgroundColor: '#0D1428', border: '1px solid #1B2B5A', color: '#64748B' }}>
              Tape: {selectedSnapshot}
            </div>
            {displayCurrency !== summary.reported_currency && (
              <div className="text-xs px-3 py-1.5 rounded-full"
                   style={{ backgroundColor: '#0D1F1E', border: '1px solid #134040', color: '#2DD4BF' }}>
                1 {summary.reported_currency} = {summary.usd_rate} USD
              </div>
            )}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-6 overflow-x-auto"
             style={{ borderBottom: '1px solid #1B2B5A' }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="text-xs px-4 py-2.5 whitespace-nowrap transition-all"
              style={{
                color: activeTab === tab.id ? '#3B82F6' : '#64748B',
                borderBottom: activeTab === tab.id ? '2px solid #3B82F6' : '2px solid transparent',
                marginBottom: '-1px'
              }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Loading bar */}
        {(summaryLoading || tabLoading) && (
          <div className="flex items-center gap-3 mb-6 p-4 rounded-xl"
               style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
            <span className="text-sm" style={{ color: '#93C5FD' }}>Loading...</span>
          </div>
        )}

        {/* Tab content */}
        {!summaryLoading && summary && (

          <div className="space-y-6">

            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <KpiCard title="Total Deals"
                    value={summary.total_deals.toLocaleString()}
                    subtitle="As of selected date" color="blue" />
                  <KpiCard title="Purchase Value"
                    value={`${currencySymbol}${(summary.total_purchase_value / 1e6).toFixed(1)}M`}
                    subtitle={displayCurrency} color="blue" />
                  <KpiCard title="Collection Rate"
                    value={`${summary.collection_rate.toFixed(1)}%`}
                    subtitle="Collected / Purchase Value" color="teal" />
                  <KpiCard title="Denial Rate"
                    value={`${summary.denial_rate.toFixed(1)}%`}
                    subtitle="Denied / Purchase Value" color="red" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <KpiCard title="Total Collected"
                    value={`${currencySymbol}${(summary.total_collected / 1e6).toFixed(1)}M`}
                    color="teal" />
                  <KpiCard title="Pending Response"
                    value={`${currencySymbol}${(summary.total_pending / 1e6).toFixed(1)}M`}
                    subtitle={`${summary.pending_rate.toFixed(1)}% of portfolio`} color="gold" />
                  <KpiCard title="Completed Deals"
                    value={summary.completed_deals.toLocaleString()}
                    subtitle={`${((summary.completed_deals / summary.total_deals) * 100).toFixed(1)}% of total`}
                    color="blue" />
                  <KpiCard title="Active Deals"
                    value={summary.active_deals.toLocaleString()}
                    subtitle={`${((summary.active_deals / summary.total_deals) * 100).toFixed(1)}% of total`}
                    color="gold" />
                </div>
                <AICommentary
                  company={companyName}
                  product={selectedProduct}
                  snapshot={selectedSnapshot}
                  asOfDate={asOfDate}
                  currency={displayCurrency}
                />
                <DataChat
                  company={companyName}
                  product={selectedProduct}
                  snapshot={selectedSnapshot}
                  asOfDate={asOfDate}
                  currency={displayCurrency}
                />
              </>
            )}

            {/* ACTUAL VS EXPECTED TAB */}
            {activeTab === 'actual-vs-expected' && !tabLoading && chartData['actual-vs-expected'] && (
              <ActualVsExpectedChart
                data={chartData['actual-vs-expected'].data}
                currency={displayCurrency}
                totals={chartData['actual-vs-expected']}
              />
            )}

            {/* DEPLOYMENT TAB */}
            {activeTab === 'deployment' && !tabLoading && chartData['deployment'] && (
              <DeploymentChart
                data={chartData['deployment'].data}
                currency={displayCurrency}
              />
            )}

            {/* COLLECTION TAB */}
            {activeTab === 'collection' && !tabLoading && chartData['collection'] && (
              <CollectionVelocityChart
                data={chartData['collection']}
                currency={displayCurrency}
              />
            )}

            {/* AGEING TAB */}
            {activeTab === 'ageing' && !tabLoading && chartData['ageing'] && (
              <AgeingChart
                data={chartData['ageing']}
                currency={displayCurrency}
              />
            )}

            {/* REVENUE TAB */}
            {activeTab === 'revenue' && !tabLoading && chartData['revenue'] && (
              <RevenueChart
                data={chartData['revenue']}
                currency={displayCurrency}
              />
            )}

            {/* CONCENTRATION TAB */}
            {activeTab === 'concentration' && !tabLoading && chartData['concentration'] && (
              <ConcentrationChart
                data={chartData['concentration']}
                currency={displayCurrency}
              />
            )}

            {/* COHORT TAB */}
            {activeTab === 'cohort' && !tabLoading && chartData['cohort'] && (
              <CohortTable
                cohorts={chartData['cohort'].cohorts}
                currency={displayCurrency}
              />
            )}

          </div>
        )}
      </div>
    </div>
  );
}