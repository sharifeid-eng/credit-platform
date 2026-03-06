import axios from 'axios';

const API_BASE = 'http://localhost:8000';
const api = axios.create({ baseURL: API_BASE, headers: { 'Content-Type': 'application/json' } });

export default api;

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

// ── Legacy aliases (old names kept for any existing code) ────────────────────
export const getCollectionVelocity = getCollectionVelocityChart;
export const getDenialTrend        = getDenialTrendChart;
export const getActualVsExpected   = getActualVsExpectedChart;
export const getAgeing             = getAgeingChart;
export const getRevenue            = getRevenueChart;
export const getConcentration      = getConcentrationChart;
export const getCohortAnalysis     = getCohortChart;