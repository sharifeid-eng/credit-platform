import axios from 'axios';

const API_BASE = 'http://localhost:8000';
const api = axios.create({ baseURL: API_BASE, headers: { 'Content-Type': 'application/json' } });

export default api;

export const getCompanies        = () => api.get('/companies').then(r => r.data);
export const getProducts         = (co) => api.get(`/companies/${co}/products`).then(r => r.data);
export const getSnapshots        = (co, p) => api.get(`/companies/${co}/products/${p}/snapshots`).then(r => r.data);
export const getProductConfig    = (co, p) => api.get(`/companies/${co}/products/${p}/config`).then(r => r.data);
export const getDateRange        = (co, p, snap) =>
  api.get(`/companies/${co}/products/${p}/date-range`, { params: { snapshot: snap } }).then(r => r.data);

const chartParams = (snap, asOf, cur) => ({ snapshot: snap, as_of_date: asOf, currency: cur });

export const getPortfolioSummary = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/summary`, { params: chartParams(snap, asOf, cur) }).then(r => r.data);

export const getAICommentary     = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/ai-commentary`, { params: chartParams(snap, asOf, cur) }).then(r => r.data);

export const getTabInsight       = (co, p, snap, asOf, cur, tab) =>
  api.get(`/companies/${co}/products/${p}/ai-tab-insight`, { params: { ...chartParams(snap, asOf, cur), tab } }).then(r => r.data);

export const getDeploymentChart      = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/deployment`,          { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getCollectionVelocity   = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/collection-velocity`, { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getDenialTrend          = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/denial-trend`,        { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getCohortAnalysis       = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/cohort`,              { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getActualVsExpected     = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/actual-vs-expected`,  { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getAgeing               = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/ageing`,              { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getRevenue              = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/revenue`,             { params: chartParams(snap, asOf, cur) }).then(r => r.data);
export const getConcentration        = (co, p, snap, asOf, cur) =>
  api.get(`/companies/${co}/products/${p}/charts/concentration`,       { params: chartParams(snap, asOf, cur) }).then(r => r.data);