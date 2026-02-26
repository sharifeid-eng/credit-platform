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

// ── Legacy aliases (old names kept for any existing code) ────────────────────
export const getCollectionVelocity = getCollectionVelocityChart;
export const getDenialTrend        = getDenialTrendChart;
export const getActualVsExpected   = getActualVsExpectedChart;
export const getAgeing             = getAgeingChart;
export const getRevenue            = getRevenueChart;
export const getConcentration      = getConcentrationChart;
export const getCohortAnalysis     = getCohortChart;