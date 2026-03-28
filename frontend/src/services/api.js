import axios from 'axios';

const API_BASE = 'http://localhost:8000';
const api = axios.create({ baseURL: API_BASE, headers: { 'Content-Type': 'application/json' } });

export default api;

// ── Framework ────────────────────────────────────────────────────────────────
export const getFramework     = () => api.get('/framework').then(r => r.data.content);

// ── Core ──────────────────────────────────────────────────────────────────────
export const getCompanies     = () => api.get('/companies').then(r => r.data);
export const getProducts      = (co) => api.get(`/companies/${co}/products`).then(r => r.data);
export const getSnapshots     = (co, p) => api.get(`/companies/${co}/products/${p}/snapshots`).then(r => r.data);
export const getConfig        = (co, p) => api.get(`/companies/${co}/products/${p}/config`).then(r => r.data);
export const getProductConfig = getConfig; // legacy alias
export const getDateRange     = (co, p, snap) =>
  api.get(`/companies/${co}/products/${p}/date-range`, { params: { snapshot: snap } }).then(r => r.data);

// ── Params helper — asOf is optional ─────────────────────────────────────────
const p = (snap, cur, asOf) => ({
  snapshot: snap,
  currency: cur,
  ...(asOf ? { as_of_date: asOf } : {}),
});

// ── Summary & AI ──────────────────────────────────────────────────────────────
export const getSummary          = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/summary`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getPortfolioSummary = getSummary; // legacy alias

export const getAICommentary     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/ai-commentary`, { params: p(snap, cur, asOf) }).then(r => r.data.commentary);

export const getTabInsight       = (co, prod, snap, cur, tab, asOf) =>
  api.get(`/companies/${co}/products/${prod}/ai-tab-insight`, { params: { ...p(snap, cur, asOf), tab } }).then(r => r.data.insight);

export const postChat            = (co, prod, snap, cur, question, history = []) =>
  api.post(`/companies/${co}/products/${prod}/chat`, { question, history, snapshot: snap, currency: cur }).then(r => r.data.answer);

export const getExecutiveSummary = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/ai-executive-summary`, { params: p(snap, cur, asOf) }).then(r => r.data);

// ── PAR & DTFC ──────────────────────────────────────────────────────────────
export const getParChart              = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/par`,               { params: p(snap, cur, asOf) }).then(r => r.data);
export const getDtfcChart             = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/dtfc`,              { params: p(snap, cur, asOf) }).then(r => r.data);

// ── Ejari summary ───────────────────────────────────────────────────────────
export const getEjariSummary          = (co, prod, snap) =>
  api.get(`/companies/${co}/products/${prod}/ejari-summary`, { params: { snapshot: snap } }).then(r => r.data);

// ── New analytical endpoints ────────────────────────────────────────────────
export const getCohortLossWaterfall   = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/cohort-loss-waterfall`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getRecoveryAnalysis      = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/recovery-analysis`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getVintageLossCurves     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/vintage-loss-curves`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getUnderwritingDrift     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/underwriting-drift`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getSegmentAnalysis       = (co, prod, snap, cur, asOf, segBy = 'product') =>
  api.get(`/companies/${co}/products/${prod}/charts/segment-analysis`, { params: { ...p(snap, cur, asOf), segment_by: segBy } }).then(r => r.data);
export const getCollectionsTiming     = (co, prod, snap, cur, asOf, view = 'origination_month') =>
  api.get(`/companies/${co}/products/${prod}/charts/collections-timing`, { params: { ...p(snap, cur, asOf), view } }).then(r => r.data);
export const getSeasonality           = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/seasonality`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getLossCategorization    = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/loss-categorization`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getMethodologyLog        = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/methodology-log`, { params: { snapshot: snap, ...(asOf ? { as_of_date: asOf } : {}) } }).then(r => r.data);
export const getHhiTimeseries         = (co, prod, cur) =>
  api.get(`/companies/${co}/products/${prod}/charts/hhi-timeseries`, { params: { currency: cur } }).then(r => r.data);

// ── Charts — new names (used by new chart components) ────────────────────────
export const getDeploymentChart         = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/deployment`,          { params: p(snap, cur, asOf) }).then(r => r.data);
export const getActualVsExpectedChart   = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/actual-vs-expected`,  { params: p(snap, cur, asOf) }).then(r => r.data);
export const getCollectionVelocityChart = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/collection-velocity`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getDenialTrendChart        = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/denial-trend`,        { params: p(snap, cur, asOf) }).then(r => r.data);
export const getAgeingChart             = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/ageing`,              { params: p(snap, cur, asOf) }).then(r => r.data);
export const getRevenueChart            = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/revenue`,             { params: p(snap, cur, asOf) }).then(r => r.data);
export const getConcentrationChart      = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/concentration`,       { params: p(snap, cur, asOf) }).then(r => r.data);
export const getCohortChart             = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/cohort`,              { params: p(snap, cur, asOf) }).then(r => r.data);
export const getReturnsAnalysisChart = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/returns-analysis`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getDeploymentByProductChart = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/deployment-by-product`, { params: p(snap, cur, asOf) }).then(r => r.data);

export const getCollectionCurvesChart  = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/collection-curves`, { params: p(snap, cur, asOf) }).then(r => r.data);

// ── New analytics endpoints ───────────────────────────────────────────────────
export const getDSOChart              = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/dso`,              { params: p(snap, cur, asOf) }).then(r => r.data);
export const getDenialFunnelChart     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/denial-funnel`,    { params: p(snap, cur, asOf) }).then(r => r.data);
export const getStressTestChart       = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/stress-test`,      { params: p(snap, cur, asOf) }).then(r => r.data);
export const getExpectedLossChart     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/expected-loss`,    { params: p(snap, cur, asOf) }).then(r => r.data);
export const getLossTriangleChart     = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/loss-triangle`,    { params: p(snap, cur, asOf) }).then(r => r.data);
export const getGroupPerformanceChart = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/group-performance`,{ params: p(snap, cur, asOf) }).then(r => r.data);
export const getRiskMigrationChart    = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/risk-migration`,   { params: p(snap, cur, asOf) }).then(r => r.data);
export const validateSnapshot         = (co, prod, snap) =>
  api.get(`/companies/${co}/products/${prod}/validate`, { params: { snapshot: snap } }).then(r => r.data);

// ── Data Integrity ───────────────────────────────────────────────────────────
export const getIntegrityCached = (co, prod, snapOld, snapNew) =>
  api.get(`/companies/${co}/products/${prod}/integrity/cached`, { params: { snapshot_old: snapOld, snapshot_new: snapNew } }).then(r => r.data);
export const runIntegrityCheck = (co, prod, snapOld, snapNew) =>
  api.get(`/companies/${co}/products/${prod}/integrity`, { params: { snapshot_old: snapOld, snapshot_new: snapNew } }).then(r => r.data);
export const generateIntegrityReport = (co, prod, snapOld, snapNew) =>
  api.post(`/companies/${co}/products/${prod}/integrity/report`, { snapshot_old: snapOld, snapshot_new: snapNew }).then(r => r.data);
export const getIntegrityReportCached = (co, prod, snapOld, snapNew) =>
  api.get(`/companies/${co}/products/${prod}/integrity/report`, { params: { snapshot_old: snapOld, snapshot_new: snapNew } }).then(r => r.data);
export const saveIntegrityNotes = (co, prod, snapOld, snapNew, notes) =>
  api.post(`/companies/${co}/products/${prod}/integrity/notes`, { snapshot_old: snapOld, snapshot_new: snapNew, notes }).then(r => r.data);
export const getIntegrityNotes = (co, prod, snapOld, snapNew) =>
  api.get(`/companies/${co}/products/${prod}/integrity/notes`, { params: { snapshot_old: snapOld, snapshot_new: snapNew } }).then(r => r.data);

// ── PDF Report Generation ───────────────────────────────────────────────────
export const generatePDFReport = (co, prod, snap, cur) =>
  api.post(
    `/companies/${co}/products/${prod}/generate-report`,
    { snapshot: snap, currency: cur },
    { timeout: 180_000, responseType: 'blob' },
  ).then(r => {
    const blob = new Blob([r.data], { type: 'application/pdf' });
    const url  = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  });

// ── Portfolio Analytics ─────────────────────────────────────────────────────
export const getPortfolioBorrowingBase      = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/borrowing-base`,      { params: p(snap, cur, asOf) }).then(r => r.data);
export const getPortfolioConcentrationLimits = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/concentration-limits`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getPortfolioCovenants          = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/covenants`,           { params: p(snap, cur, asOf) }).then(r => r.data);
export const getPortfolioFlow               = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/flow`,                { params: p(snap, cur, asOf) }).then(r => r.data);
export const getFacilityParams              = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/facility-params`).then(r => r.data);
export const saveFacilityParams             = (co, prod, params) =>
  api.post(`/companies/${co}/products/${prod}/portfolio/facility-params`, params).then(r => r.data);

// ── Portfolio Dashboard Data ────────────────────────────────────────────────
export const getPortfolioInvoices          = (co, prod, page = 1, perPage = 50, filters = {}) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/invoices`, { params: { page, per_page: perPage, ...filters } }).then(r => r.data);
export const getPortfolioPayments          = (co, prod, page = 1, perPage = 50, filters = {}) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/payments`, { params: { page, per_page: perPage, ...filters } }).then(r => r.data);
export const getPortfolioBankStatements    = (co, prod, page = 1, perPage = 50) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/bank-statements`, { params: { page, per_page: perPage } }).then(r => r.data);
export const getPortfolioCovenantDates     = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/portfolio/covenant-dates`).then(r => r.data);

// ── Legacy aliases (old names kept for any existing code) ────────────────────
export const getCollectionVelocity = getCollectionVelocityChart;
export const getDenialTrend        = getDenialTrendChart;
export const getActualVsExpected   = getActualVsExpectedChart;
export const getAgeing             = getAgeingChart;
export const getRevenue            = getRevenueChart;
export const getConcentration      = getConcentrationChart;
export const getCohortAnalysis     = getCohortChart;