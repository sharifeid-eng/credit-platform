import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

export const getCompanies = async () => {
  const response = await api.get('/companies');
  return response.data;
};

export const getProducts = async (company) => {
  const response = await api.get(`/companies/${company}/products`);
  return response.data;
};

export const getSnapshots = async (company, product) => {
  const response = await api.get(`/companies/${company}/products/${product}/snapshots`);
  return response.data;
};

export const getProductConfig = async (company, product) => {
  const response = await api.get(`/companies/${company}/products/${product}/config`);
  return response.data;
};

export const getDateRange = async (company, product, snapshot) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/date-range`,
    { params: { snapshot } }
  );
  return response.data;
};

export const getPortfolioSummary = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/summary`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export default api;

export const getAICommentary = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/ai-commentary`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getDeploymentChart = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/deployment`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getCollectionVelocity = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/collection-velocity`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getDenialTrend = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/denial-trend`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getCohortAnalysis = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/cohort`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getActualVsExpected = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/actual-vs-expected`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getAgeing = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/ageing`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getRevenue = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/revenue`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};

export const getConcentration = async (company, product, snapshot, asOfDate, currency) => {
  const response = await api.get(
    `/companies/${company}/products/${product}/charts/concentration`,
    { params: { snapshot, as_of_date: asOfDate, currency } }
  );
  return response.data;
};
