import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL !== undefined ? import.meta.env.VITE_API_URL : 'http://localhost:8000';
const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // Send CF_Authorization cookie with every request
});

// Log API errors for debugging (errors still propagate to callers)
api.interceptors.response.use(
  response => response,
  error => {
    const status = error.response?.status
    const url = error.config?.url
    const detail = error.response?.data?.detail
    if (status >= 500) {
      console.error(`[API] ${status} on ${url}:`, detail || error.message)
    } else if (status >= 400 && status !== 401) {
      console.warn(`[API] ${status} on ${url}:`, detail || error.message)
    }
    return Promise.reject(error)
  }
)

export default api;

// ── Framework ────────────────────────────────────────────────────────────────
export const getFramework       = () => api.get('/framework').then(r => r.data.content);
export const getMethodology     = (analysisType) => api.get(`/methodology/${analysisType}`).then(r => r.data);
export const getAggregateStats  = ()  => api.get('/aggregate-stats').then(r => r.data);

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

export const getAICommentary     = (co, prod, snap, cur, asOf, { refresh = false, mode = null } = {}) =>
  api.get(`/companies/${co}/products/${prod}/ai-commentary`, { params: { ...p(snap, cur, asOf), ...(refresh ? { refresh: true } : {}), ...(mode ? { mode } : {}) } }).then(r => r.data);

export const getTabInsight       = (co, prod, snap, cur, tab, asOf, { refresh = false, mode = null } = {}) =>
  api.get(`/companies/${co}/products/${prod}/ai-tab-insight`, { params: { ...p(snap, cur, asOf), tab, ...(refresh ? { refresh: true } : {}), ...(mode ? { mode } : {}) } }).then(r => r.data);

export const getExecutiveSummaryAgent = (co, prod, snap, cur, asOf, { refresh = false } = {}) =>
  api.get(`/companies/${co}/products/${prod}/ai-executive-summary`, { params: { ...p(snap, cur, asOf), ...(refresh ? { refresh: true } : {}), mode: 'agent' } }).then(r => r.data);

export const postChat            = (co, prod, snap, cur, question, history = []) =>
  api.post(`/companies/${co}/products/${prod}/chat`, { question, history, snapshot: snap, currency: cur }).then(r => r.data.answer);

// ── Agent endpoints ─────────────────────────────────────────────────────
export const AGENT_ANALYST_URL   = (co, prod) => `/agents/${co}/${prod}/analyst/stream`;
export const AGENT_MEMO_URL      = (co, prod) => `/agents/${co}/${prod}/memo/generate`;
export const AGENT_COMPLIANCE_URL = (co, prod) => `/agents/${co}/${prod}/compliance/check`;

export const postAgentChat       = (co, prod, question, sessionId, snap, cur) =>
  api.post(`/agents/${co}/${prod}/analyst/sync`, { question, session_id: sessionId, snapshot: snap, currency: cur }).then(r => r.data);

export const postAgentCompliance = (co, prod, snap, cur) =>
  api.post(`/agents/${co}/${prod}/compliance/check/sync`, { snapshot: snap, currency: cur }).then(r => r.data);

export const getExecutiveSummary = (co, prod, snap, cur, asOf, { refresh = false } = {}) =>
  api.get(`/companies/${co}/products/${prod}/ai-executive-summary`, { params: { ...p(snap, cur, asOf), ...(refresh ? { refresh: true } : {}) } }).then(r => r.data);

export const getAICacheStatus    = (co, prod, snap, asOf) =>
  api.get(`/companies/${co}/products/${prod}/ai-cache-status`, { params: { snapshot: snap, ...(asOf ? { as_of_date: asOf } : {}) } }).then(r => r.data);

// ── PAR & DTFC ──────────────────────────────────────────────────────────────
export const getParChart              = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/par`,               { params: p(snap, cur, asOf) }).then(r => r.data);
export const getDtfcChart             = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/dtfc`,              { params: p(snap, cur, asOf) }).then(r => r.data);

// ── Ejari summary ───────────────────────────────────────────────────────────
export const getEjariSummary          = (co, prod, snap) =>
  api.get(`/companies/${co}/products/${prod}/ejari-summary`, { params: { snapshot: snap } }).then(r => r.data);

// ── Tamara summary ──────────────────────────────────────────────────────────
export const getTamaraSummary         = (co, prod, snap) =>
  api.get(`/companies/${co}/products/${prod}/tamara-summary`, { params: { snapshot: snap } }).then(r => r.data);

// ── Aajil summary + charts ─────────────────────────────────────────────────
export const getAajilSummary          = (co, prod, snap) =>
  api.get(`/companies/${co}/products/${prod}/aajil-summary`, { params: { snapshot: snap } }).then(r => r.data);
export const getAajilChart            = (co, prod, chartName, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/aajil/${chartName}`, { params: p(snap, cur, asOf) }).then(r => r.data);

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
export const getCdrCcr                = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/cdr-ccr`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getSilqCdrCcr            = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/charts/silq/cdr-ccr`, { params: p(snap, cur, asOf) }).then(r => r.data);

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

// ── Compliance Certificate & Notifications ────────────────────────────────────
export const downloadComplianceCert = (co, prod, snap, cur, officerName = '') =>
  api.post(
    `/companies/${co}/products/${prod}/portfolio/compliance-cert`,
    { officer_name: officerName, currency: cur },
    { params: { snapshot: snap }, timeout: 30_000, responseType: 'blob' },
  ).then(r => {
    const blob = new Blob([r.data], { type: 'application/pdf' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `BBC_${co}_${prod}_${snap || 'latest'}.pdf`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  });

export const notifyBreaches = (co, prod, snap, cur) =>
  api.post(
    `/companies/${co}/products/${prod}/portfolio/notify-breaches`,
    {},
    { params: p(snap, cur) },
  ).then(r => r.data);

// ── Research Hub (Data Room & Research Chat) ────────────────────────────────
export const getDataroomDocuments = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/dataroom/documents`).then(r => r.data);
export const getDataroomStats = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/dataroom/stats`).then(r => r.data);
export const ingestDataroom = (co, prod) =>
  api.post(`/companies/${co}/products/${prod}/dataroom/ingest`).then(r => r.data);
export const getDataroomDocumentViewUrl = (co, prod, docId) =>
  `${API_BASE}/companies/${co}/products/${prod}/dataroom/documents/${docId}/view`;
export const postResearchChat = (co, prod, question, history = []) =>
  api.post(`/companies/${co}/products/${prod}/research/chat`, { question, history }).then(r => r.data);

// ── Memo Engine ──────────────────────────────────────────────────────────────
export const getMemoTemplates = () =>
  api.get('/memo-templates').then(r => r.data);
export const listMemos = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/memos`).then(r => r.data);
export const createMemo = (co, prod, template, title, sections) =>
  api.post(`/companies/${co}/products/${prod}/memos`, { template, title, sections }).then(r => r.data);
export const getMemo = (co, prod, memoId) =>
  api.get(`/companies/${co}/products/${prod}/memos/${memoId}`).then(r => r.data);
export const generateMemo = (co, prod, template, customSections) =>
  api.post(`/companies/${co}/products/${prod}/memos/generate`,
    { template, custom_sections: customSections },
    { timeout: 300_000 }
  ).then(r => r.data);
export const regenerateSection = (co, prod, memoId, sectionKey, { mode = null } = {}) =>
  api.post(`/companies/${co}/products/${prod}/memos/${memoId}/sections/${sectionKey}/regenerate`,
    {}, { timeout: 120_000, params: mode ? { mode } : {} }
  ).then(r => r.data);
export const updateMemoSection = (co, prod, memoId, sectionKey, content) =>
  api.patch(`/companies/${co}/products/${prod}/memos/${memoId}/sections/${sectionKey}`, { content }).then(r => r.data);
export const updateMemoStatus = (co, prod, memoId, status) =>
  api.patch(`/companies/${co}/products/${prod}/memos/${memoId}/status`, { status }).then(r => r.data);
export const exportMemoPdf = (co, prod, memoId) =>
  api.post(`/companies/${co}/products/${prod}/memos/${memoId}/export-pdf`, {},
    { timeout: 120_000, responseType: 'blob' }
  ).then(r => {
    const blob = new Blob([r.data], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  });

// ── Legal Analysis ───────────────────────────────────────────────────────────
export const uploadLegalDocument = (co, prod, file, documentType = 'credit_agreement') => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/companies/${co}/products/${prod}/legal/upload`, formData, {
    params: { document_type: documentType },
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data);
};
export const getLegalDocuments          = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/documents`).then(r => r.data);
export const getLegalDocument           = (co, prod, filename) =>
  api.get(`/companies/${co}/products/${prod}/legal/documents/${filename}`).then(r => r.data);
export const reExtractLegalDocument     = (co, prod, filename, docType = 'credit_agreement') =>
  api.post(`/companies/${co}/products/${prod}/legal/documents/${filename}/re-extract`, null, { params: { document_type: docType } }).then(r => r.data);
export const deleteLegalDocument        = (co, prod, filename) =>
  api.delete(`/companies/${co}/products/${prod}/legal/documents/${filename}`).then(r => r.data);
export const getLegalFacilityTerms      = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/facility-terms`).then(r => r.data);
export const getLegalEligibility        = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/eligibility`).then(r => r.data);
export const getLegalCovenantsExtracted = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/covenants-extracted`).then(r => r.data);
export const getLegalEventsOfDefault    = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/events-of-default`).then(r => r.data);
export const getLegalReporting          = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/reporting`).then(r => r.data);
export const getLegalRiskFlags          = (co, prod) =>
  api.get(`/companies/${co}/products/${prod}/legal/risk-flags`).then(r => r.data);
export const getLegalComplianceComparison = (co, prod, snap, cur, asOf) =>
  api.get(`/companies/${co}/products/${prod}/legal/compliance-comparison`, { params: p(snap, cur, asOf) }).then(r => r.data);
export const getLegalAmendmentDiff      = (co, prod, oldFile, newFile) =>
  api.get(`/companies/${co}/products/${prod}/legal/amendment-diff`, { params: { filename_old: oldFile, filename_new: newFile } }).then(r => r.data);

// ── Operator Command Center ──────────────────────────────────────────────────
export const getOperatorStatus       = () => api.get('/operator/status').then(r => r.data);
export const getOperatorTodos        = () => api.get('/operator/todo').then(r => r.data);
export const createOperatorTodo      = (item) => api.post('/operator/todo', item).then(r => r.data);
export const updateOperatorTodo      = (id, update) => api.patch(`/operator/todo/${id}`, update).then(r => r.data);
export const deleteOperatorTodo      = (id) => api.delete(`/operator/todo/${id}`).then(r => r.data);
export const getOperatorMind         = (company = null, category = null) =>
  api.get('/operator/mind', { params: { ...(company ? { company } : {}), ...(category ? { category } : {}) } }).then(r => r.data);
export const updateOperatorMindEntry = (id, update) => api.patch(`/operator/mind/${id}`, update).then(r => r.data);
export const sendOperatorDigest      = (webhookUrl = null) =>
  api.post('/operator/digest', null, { params: webhookUrl ? { webhook_url: webhookUrl } : {} }).then(r => r.data);

// ── Intelligence System ────────────────────────────────────────────────────
export const getOperatorBriefing     = () => api.get('/operator/briefing').then(r => r.data);
export const getOperatorLearning     = () => api.get('/operator/learning').then(r => r.data);
export const getOperatorLearningRules = () => api.get('/operator/learning/rules').then(r => r.data);
export const getThesis               = (co, prod) => api.get(`/companies/${co}/products/${prod}/thesis`).then(r => r.data);
export const saveThesis              = (co, prod, thesis) => api.post(`/companies/${co}/products/${prod}/thesis`, thesis).then(r => r.data);
export const getThesisDrift          = (co, prod) => api.get(`/companies/${co}/products/${prod}/thesis/drift`).then(r => r.data);
export const getThesisLog            = (co, prod) => api.get(`/companies/${co}/products/${prod}/thesis/log`).then(r => r.data);
export const postChatFeedback        = (co, prod, feedback) =>
  api.post(`/companies/${co}/products/${prod}/chat-feedback`, feedback).then(r => r.data);

// ── Auth ────────────────────────────────────────────────────────────────────
export const getAuthMe             = () => api.get('/auth/me').then(r => r.data);
export const getAuthLogoutUrl      = () => api.get('/auth/logout-url').then(r => r.data);
export const getAuthUsers          = () => api.get('/auth/users').then(r => r.data);
export const createAuthUser        = (user) => api.post('/auth/users', user).then(r => r.data);
export const updateAuthUser        = (id, update) => api.patch(`/auth/users/${id}`, update).then(r => r.data);
export const deleteAuthUser        = (id) => api.delete(`/auth/users/${id}`).then(r => r.data);

// ── Legacy aliases (old names kept for any existing code) ────────────────────
export const getCollectionVelocity = getCollectionVelocityChart;
export const getDenialTrend        = getDenialTrendChart;
export const getActualVsExpected   = getActualVsExpectedChart;
export const getAgeing             = getAgeingChart;
export const getRevenue            = getRevenueChart;
export const getConcentration      = getConcentrationChart;
export const getCohortAnalysis     = getCohortChart;